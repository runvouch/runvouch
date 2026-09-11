#!/usr/bin/env python3
"""reddit-scout.py — reads the public RSS feeds of a few subreddits and the open issues of two GitHub repos (no login) and lists
threads worth a genuine comment: scheduled/unattended agents, cron, cost, silent failures, n8n errors.

  python3 reddit-scout.py            -> prints candidates, sends them to the owner's Telegram (from the RunVouch DB)
  python3 reddit-scout.py --dry      -> print only
  python3 reddit-scout.py --thread URL -> print the post text and top comments of one thread (URL + .rss;
                                        a share link from the phone, /s/CODE or redd.it/ID, is resolved first)

Scoring is a keyword match on title + summary; nothing is posted anywhere. Seen threads are remembered
in data/reddit-seen.json so each one is suggested once.
"""
import html, json, os, re, sqlite3, subprocess, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "data", "reddit-seen.json")
HISTORY = os.path.join(ROOT, "data", "reddit-drafts.jsonl")   # every drafted comment, so new ones never repeat old ones
UA = "nightly-runs-reader/0.1 (personal; reads public feeds; contact launch@runvouch.com)"
SUBS = ["ClaudeAI", "ClaudeCode", "n8n", "selfhosted", "Anthropic", "claude"]
# GitHub issues are where the pain is written down first (#37686: $1,800 in two nights; openclaw #16808: polling loop).
# Same rules as Reddit: answer the question, never sell. Post from the runvouch account, never a personal one.
GH_REPOS = ["anthropics/claude-code", "openclaw/openclaw"]
GH_TERMS = 'scheduled OR routine OR cron OR headless OR loop'   # GitHub allows at most five OR/AND/NOT operators per search
GH_DAYS = 3
KEYWORDS = {  # weight per keyword (lower-case substring match)
    "routine": 3, "scheduled": 3, "schedule": 2, "cron": 3, "headless": 3, "claude -p": 3, "unattended": 4, "overnight": 3,
    "autonomous": 2, "agent": 1, "agents": 1, "loop": 2, "looping": 3, "stuck": 2, "retry": 2, "bill": 3, "cost": 2,
    "spend": 2, "budget": 2, "token": 1, "tokens": 1, "usage limit": 1, "silently": 3, "silent": 2, "failed": 2,
    "didn't run": 4, "did not run": 4, "monitor": 3, "monitoring": 3, "alert": 3, "watchdog": 4, "heartbeat": 3,
    "error workflow": 4, "openclaw": 3, "n8n": 1, "cron job": 4, "systemd": 2, "background": 1, "webhook": 1, "evidence": 2,
}
NS = {"a": "http://www.w3.org/2005/Atom"}


def fetch(url: str) -> bytes:
    """Reddit rate-limits anonymous feed reads hard: space requests out and retry once on 429."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            time.sleep(10)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                time.sleep(60)
                continue
            raise


def strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def feed(sub: str) -> list[dict]:
    root = ET.fromstring(fetch(f"https://www.reddit.com/r/{sub}/new/.rss?limit=40"))
    out = []
    for e in root.findall("a:entry", NS):
        link = e.find("a:link", NS).attrib.get("href", "")
        title = strip(e.findtext("a:title", default="", namespaces=NS))
        body = strip(e.findtext("a:content", default="", namespaces=NS))
        out.append({"sub": sub, "title": title, "url": link.split("?")[0], "body": body[:600], "published": e.findtext("a:updated", default="", namespaces=NS)})
    return out


def feed_github(repo: str) -> list[dict]:
    """Open issues updated in the last GH_DAYS days that mention scheduling, cost or loops. Unauthenticated: 10 searches/min."""
    since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - GH_DAYS * 86400))
    q = urllib.parse.quote(f"repo:{repo} is:issue is:open {GH_TERMS} updated:>={since}")
    req = urllib.request.Request(f"https://api.github.com/search/issues?q={q}&sort=updated&per_page=30",
                                 headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.load(r).get("items", [])
    time.sleep(7)
    return [{"sub": "github " + repo, "title": strip(i.get("title", "")), "url": i["html_url"],
             "body": strip(i.get("body") or "")[:600], "published": i.get("updated_at", ""), "comments": i.get("comments", 0)}
            for i in items if "pull_request" not in i]


GH_THREAD_RE = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+)/(issues|pull|discussions)/(\d+)", re.I)
DISC_BODY_RE = re.compile(r'(?is)<td[^>]*\bcomment-body\b[^>]*>(.*?)</td>')
DISC_TITLE_RE = re.compile(r'(?is)<(?:h1|bdi)[^>]*class="[^"]*(?:gh-header-title|js-issue-title)[^"]*"[^>]*>(.*?)</')


def gh_json(url: str):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
        return json.load(r)


def html_text(raw: str) -> str:
    """Page HTML -> readable text, with the line breaks kept: strip() would glue a whole comment into one line."""
    raw = re.sub(r"(?is)<(script|style|svg|template|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/li|/h[1-6]|/div|/tr)\b[^>]*>", "\n", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", "", raw))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", txt)).strip()


def thread_discussion(url: str) -> str:
    """A discussion has no REST endpoint and the GraphQL one needs a token, so the public page is read and the comment
    bodies are cut out of it. Author names are not paired reliably in that markup, so only the order is kept."""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25) as r:
        page = r.read().decode("utf-8", "replace")
    bodies = [t for t in (html_text(b) for b in DISC_BODY_RE.findall(page)) if t]
    if not bodies:
        raise ValueError("kon de discussion niet lezen (besloten repo, of GitHub veranderde de pagina): " + url)
    t = DISC_TITLE_RE.search(page)
    titel = strip(t.group(1)) if t else ""
    parts = ["POST: " + (titel + "\n" if titel else "") + bodies[0][:2500]]
    parts += ["COMMENT: " + b[:1200] for b in bodies[1:25]]
    return "\n\n".join(parts)


def thread_github(url: str) -> str:
    """An issue, a pull request or a discussion -> the whole conversation as plain text.

    /issues/<n> serves issues and pull requests both, so a PR needs no second call for its conversation; its inline
    review comments do come from /pulls/<n>/comments and are marked REVIEW because they hang on a file, not on the
    thread. A link that is neither raises, so the caller can say so instead of drafting on an empty thread."""
    m = GH_THREAD_RE.search(url)
    if not m:
        raise ValueError("geen GitHub-thread in deze link (verwacht /issues/, /pull/ of /discussions/ met een nummer): " + url)
    repo, soort, nummer = f"{m.group(1)}/{m.group(2)}", m.group(3).lower(), m.group(4)
    if soort == "discussions":
        return thread_discussion(f"https://github.com/{repo}/discussions/{nummer}")
    issue = gh_json(f"https://api.github.com/repos/{repo}/issues/{nummer}")
    parts = ["POST " + (issue.get("user") or {}).get("login", "?") + ": " + strip(issue.get("title", "")) +
             "\n" + strip(issue.get("body") or "")[:2500]]
    parts += ["COMMENT " + (c.get("user") or {}).get("login", "?") + ": " + strip(c.get("body") or "")[:1200]
              for c in gh_json(f"https://api.github.com/repos/{repo}/issues/{nummer}/comments?per_page=30")]
    if soort == "pull":
        try:
            parts += [f"REVIEW {(c.get('user') or {}).get('login', '?')} on {c.get('path') or '?'}: " + strip(c.get("body") or "")[:800]
                      for c in gh_json(f"https://api.github.com/repos/{repo}/pulls/{nummer}/comments?per_page=20")]
        except Exception as e:
            print("review comments:", e, file=sys.stderr)
    return "\n\n".join(parts)


def score(p: dict) -> int:
    t = (p["title"] + " " + p["body"]).lower()
    # GitHub issue bodies are long and mention everything (logs, env, "headless" in passing): there the strong signal
    # must be in the title, or the scout drafts for an issue that is not about scheduling or monitoring at all
    sterk = p["title"].lower() if p["sub"].startswith("github") else t
    if not any(k in sterk for k, w in KEYWORDS.items() if w >= 3):
        return 0                     # no strong signal (cron, routine, monitoring, bill...): skip, whatever the noise says
    s = sum(w for k, w in KEYWORDS.items() if k in t)
    if "?" in p["title"]:
        s += 2                       # a question is an invitation
    if re.search(r"\b(i built|launch|check out my|my new tool)\b", t):
        s -= 3                       # someone else's showcase: not our place to sell
    return s


# The share button in the Reddit app hands out a short link (reddit.com/r/x/s/CODE, sometimes on sh.reddit.com, or
# redd.it/ID) and on a phone the long /comments/ address is nowhere to be copied. A short link has no RSS feed, so it
# has to be resolved to the real permalink first; without that the feed read returns HTML and the XML parse blows up.
SHARE_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)?(?:reddit\.com/(?:r/[^/]+/)?s/[A-Za-z0-9]+|redd\.it/[A-Za-z0-9]+)$", re.I)
PERMALINK_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?reddit\.com/r/[^/\s\"'<>]+/comments/[A-Za-z0-9]+(?:/[^\s\"'<>]*)?", re.I)


def normalise(url: str) -> str:
    """Any Reddit address the owner can produce on a phone -> an address that has an .rss feed.

    Drops the ?utm_source=share tail (it would otherwise land in front of the /.rss and break the feed address),
    puts every subdomain (old., sh., np.) on www, and resolves a share link by following its redirect."""
    url = url.split("#")[0].split("?")[0].rstrip("/")
    url = re.sub(r"^(https?://)(?:[a-z0-9-]+\.)?reddit\.com", r"\1www.reddit.com", url, flags=re.I)
    if not SHARE_RE.match(url):
        return url
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:      # urllib follows the 30x itself
        final = r.geturl()
        body = b"" if "/comments/" in final else r.read(300000)
    time.sleep(5)                                            # same courtesy pause as fetch()
    if "/comments/" in final:
        return normalise(final)
    m = PERMALINK_RE.search(html.unescape(body.decode("utf-8", "replace")))   # some share links redirect via HTML
    if not m:
        raise ValueError("deel-link wees niet naar een thread (verwijderd of besloten?): " + url)
    return normalise(m.group(0))


def thread(url: str) -> str:
    if "github.com/" in url:
        return thread_github(url)
    feed_url = normalise(url) + "/.rss?limit=40"
    raw = fetch(feed_url)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("geen RSS-feed op dit adres, Reddit gaf geen feed terug: " + feed_url)
    parts = []
    for i, e in enumerate(root.findall("a:entry", NS)):
        who = e.findtext("a:author/a:name", default="?", namespaces=NS)
        txt = strip(e.findtext("a:content", default="", namespaces=NS))
        parts.append(("POST" if i == 0 else f"COMMENT {who}") + ": " + txt[:1500])
    return "\n\n".join(parts)


CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")  # same CLI the blog engine uses
UITGAVEN: list[float] = []   # kosten per Claude-aanroep; rv run leest de som uit RUNVOUCH_COST
STYLE = """- Plain ASCII, English, 60-140 words, no headings, no emoji, no em dashes, no "---" or other separator lines.
- Write like a person typing a reply, not like a model: contractions (it's, don't), sentences of uneven length, one concrete
  experience beats three general points, at most one short list and only if it really helps. Avoid stock phrases such as
  "genuinely", "honestly", "two things", "it's worth noting", "let me push back", "great question", and never open with praise.
- Be specific (flags, commands, file names, numbers you can defend). If you cannot add anything real, output exactly: SKIP
- Never invent facts about the poster or about tools; if unsure, say what worked for you instead.
Output only the comment text."""

# Reddit: a person, never a company. Reddit readers downvote and mods remove anything that smells like a vendor,
# so the account earns its place by being useful; the profile bio carries the RunVouch link, the comments do not.
RULES_REDDIT = """You draft ONE Reddit comment for the account u/nightly_runs, a developer who runs about 50 unattended jobs
(Claude Code routines, headless claude -p, cron'd Python) for a data product. Rules, all hard:
- Answer the poster's actual question or add one concrete, useful thing. Never sell. Do NOT mention RunVouch, any product,
  any link. Do not say "I built". Speak from experience with unattended jobs only where it fits.
""" + STYLE

# GitHub: the runvouch account, so the company voice. The account name already says who is talking, so naming the
# tool and its address is an introduction, not an advert. Twelve of our comments went up between 25 August and
# 10 September and produced zero referrals, because a helpful answer with no address leaves nowhere to go. One
# closing line, only on an answer that already stands on its own.
RULES_GITHUB = """You draft ONE GitHub issue comment posted from the account "runvouch", the company behind RunVouch, a watchdog
for unattended AI agents (missed runs, silent failures, runaway cost, verifiable run proofs). Rules, all hard:
- Write as the company: "we", "at RunVouch", never "I". Answer the issue's actual question or add one concrete, useful thing
  from running many unattended jobs on the platform in the issue.
- Do not explain how to rebuild what RunVouch does; give the insight and the pitfall, not the implementation. If the issue is
  about exactly what RunVouch does, you may say so in ONE plain sentence ("we run into this daily at RunVouch, ...").
  If the issue is not about that, do not mention RunVouch at all.
- Close with ONE short line on its own, and only when everything above it already answers the issue without it:
  "We build RunVouch for this part: https://runvouch.com" (vary the wording, keep it flat). One link, never more.
  No pricing, no features list, no "check it out", no question inviting a reply about us. If the comment would be
  weaker with that line removed, the comment is not good enough yet: rewrite the answer instead of keeping the line.
""" + STYLE

FOLLOWUP = """
THIS IS A FOLLOW-UP: our account already commented in this thread (see the thread and the earlier comment below). Someone
replied to us. Write the reply to that newest response addressed to our account: answer what they asked or said, keep the
same voice, shorter is fine (30-100 words). Do not repeat the earlier comment."""


def recent_drafts(n: int = 12) -> list[dict]:
    if not os.path.exists(HISTORY):
        return []
    rows = [json.loads(l) for l in open(HISTORY) if l.strip()]
    return rows[-n:]


def draft(thread_text: str, bron: str = "reddit", followup=None, ours: str = "") -> str:
    """Ask the local Claude Code CLI (same as the blog engine) for a comment draft; returns '' when it declines.
    The last twelve drafts go along so the new one does not reuse their openings, examples, numbers or structure:
    readers of these threads overlap, and the same anecdote twice reads as a campaign."""
    prev = recent_drafts()
    avoid = ""
    if prev:
        avoid = ("\n\nCOMMENTS ALREADY POSTED RECENTLY (do not reuse their opening line, their examples, their numbers or their "
                 "structure; pick a different angle, a different concrete detail and a different first sentence type, "
                 "for example a short observation, a direct answer, a question back, or a one-line story):\n" +
                 "\n---\n".join(d["text"][:400] for d in prev))
    try:
        rules = RULES_GITHUB if bron == "github" else RULES_REDDIT
        # followup=None: a fresh comment; followup="" or text: a reply to a response we got (text = what the owner pasted)
        extra = "" if followup is None else FOLLOWUP + "\n\nREPLY WE RECEIVED (as pasted by the owner, may be empty):\n" + followup
        # our own earlier comments in this exact thread: without them a follow-up repeats what we already said there
        eigen = ("\n\nWHAT OUR OWN ACCOUNT ALREADY POSTED IN THIS THREAD (build on it, never repeat it, never contradict it):\n"
                 + ours[:3000]) if ours else ""
        r = subprocess.run([CLAUDE, "-p", rules + avoid + extra + eigen + "\n\nTHREAD:\n" + thread_text[:6000], "--output-format", "json", "--max-turns", "1"],
                           capture_output=True, text=True, timeout=240)
        antwoord = json.loads(r.stdout or "{}")
        UITGAVEN.append(antwoord.get("total_cost_usd", 0) or 0)
        out = antwoord.get("result", "").strip()
        return "" if (not out or out.upper().startswith("SKIP")) else out
    except Exception as e:
        print("draft:", e, file=sys.stderr)
        return ""


def telegram(text: str) -> bool:
    try:
        env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
        c = sqlite3.connect(env["RUNVOUCH_DB"])
        row = c.execute("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        if not row:
            return False
        data = urllib.parse.urlencode({"chat_id": row[1], "text": text, "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{row[0]}/sendMessage", data, {"User-Agent": UA}), timeout=10)
        return True
    except Exception as e:
        print("telegram:", e, file=sys.stderr)
        return False


def main() -> int:
    if "--thread" in sys.argv:
        print(thread(sys.argv[sys.argv.index("--thread") + 1]))
        return 0
    seen = set(json.load(open(STATE))) if os.path.exists(STATE) else set()
    cands = []
    for sub in SUBS:
        try:
            cands += feed(sub)
        except Exception as e:
            print(f"{sub}: {e}", file=sys.stderr)
    for repo in GH_REPOS:
        try:
            cands += feed_github(repo)
        except Exception as e:
            print(f"github {repo}: {e}", file=sys.stderr)
    fresh = [p for p in cands if p["url"] not in seen]
    # rotate: a subreddit or repo that got a draft in the last 3 days scores lower, so the same audience
    # does not see the same account every day
    laatst = {}
    for d in recent_drafts(30):
        laatst[d.get("sub", "")] = max(laatst.get(d.get("sub", ""), 0), d.get("ts", 0))
    def rank(p):
        s_ = score(p)
        if time.time() - laatst.get(p["sub"], 0) < 3 * 86400:
            s_ -= 3
        return s_
    fresh.sort(key=rank, reverse=True)
    top = [p for p in fresh if score(p) >= 6][:4]
    blocks, drafted, bronnen, overig = [], 0, set(), []
    for p in top:
        text = ""
        bron = "github" if p["sub"].startswith("github") else "reddit"
        if drafted < 2 and bron not in bronnen and "--no-draft" not in sys.argv:
            try:
                text = draft(thread(p["url"]), bron)
            except Exception as e:
                print("thread:", e, file=sys.stderr)
        if text:
            drafted += 1
            bronnen.add(bron)
            if "--dry" not in sys.argv:
                with open(HISTORY, "a") as f:
                    f.write(json.dumps({"ts": time.time(), "sub": p["sub"], "url": p["url"], "text": text}) + "\n")
            if bron == "github":
                kop = "GITHUB - reageer als account runvouch (niet je eigen)"
                waar = p["sub"].replace("github ", "", 1) + " (issue)"
            else:
                kop = "REDDIT - reageer als u/nightly_runs"
                waar = "r/" + p["sub"]
            # two messages per draft: first the answer alone (long-press, Copy, one tap), then the link right under it
            blocks.append((text, f"^ {kop}\n{waar}: {p['title'][:100]}\nKopieer het bericht hierboven, tik de link, plak als comment:\n{p['url']}"))
        else:
            overig.append(p)
    msgs = []
    if blocks:
        msgs.append("Reddit en GitHub vandaag - " + str(drafted) + " antwoord(en) klaar; per antwoord twee berichten: eerst de tekst, dan de link.")
        for text, kop in blocks:
            msgs += [text, kop]
        if overig:
            msgs.append("Gezien, geen antwoord geschreven (zeg 'reddit' + link als je er toch een wilt):\n" + "\n".join(
                f"- {p['url']}" for p in overig))
    else:
        msgs.append("Reddit en GitHub vandaag: geen antwoord geschreven." + ("\nGezien: " + ", ".join(p["url"] for p in overig) if overig else ""))
    msg = "\n\n".join(msgs)
    print(msg)
    if "--dry" not in sys.argv:
        if not blocks:
            print("telegram: niets te melden, geen bericht gestuurd", file=sys.stderr)
        for m in (msgs if blocks else []):
            for chunk in [m[i:i + 3800] for i in range(0, len(m), 3800)]:
                telegram(chunk)
        seen |= {p["url"] for p in top}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(sorted(seen)[-2000:], open(STATE, "w"))
    print(f"RUNVOUCH_COST={round(sum(UITGAVEN), 6)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
