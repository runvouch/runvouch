#!/usr/bin/env python3
"""reddit-scout.py — reads the public RSS feeds of a few subreddits and the open issues of two GitHub repos (no login) and lists
threads worth a genuine comment: scheduled/unattended agents, cron, cost, silent failures, n8n errors.

  python3 reddit-scout.py            -> prints candidates, sends them to the owner's Telegram (from the RunVouch DB)
  python3 reddit-scout.py --dry      -> print only
  python3 reddit-scout.py --thread URL -> print the post text and top comments of one thread (URL + .rss)

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


def thread_github(url: str) -> str:
    owner_repo_num = re.search(r"github\.com/([^/]+/[^/]+)/issues/(\d+)", url)
    if not owner_repo_num:
        return ""
    base = f"https://api.github.com/repos/{owner_repo_num.group(1)}/issues/{owner_repo_num.group(2)}"
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    with urllib.request.urlopen(urllib.request.Request(base, headers=h), timeout=20) as r:
        issue = json.load(r)
    with urllib.request.urlopen(urllib.request.Request(base + "/comments?per_page=30", headers=h), timeout=20) as r:
        comments = json.load(r)
    parts = ["POST " + issue.get("user", {}).get("login", "?") + ": " + strip(issue.get("title", "")) + "\n" + strip(issue.get("body") or "")[:2500]]
    parts += [f"COMMENT {c.get('user', {}).get('login', '?')}: " + strip(c.get("body") or "")[:1200] for c in comments]
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


def thread(url: str) -> str:
    if "github.com/" in url:
        return thread_github(url)
    root = ET.fromstring(fetch(url.rstrip("/") + "/.rss?limit=40"))
    parts = []
    for i, e in enumerate(root.findall("a:entry", NS)):
        who = e.findtext("a:author/a:name", default="?", namespaces=NS)
        txt = strip(e.findtext("a:content", default="", namespaces=NS))
        parts.append(("POST" if i == 0 else f"COMMENT {who}") + ": " + txt[:1500])
    return "\n\n".join(parts)


CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")  # same CLI the blog engine uses
RULES = """You draft ONE Reddit comment for the account u/nightly_runs, a developer who runs about 50 unattended jobs
(Claude Code routines, headless claude -p, cron'd Python) for a data product, and who built RunVouch, a watchdog for
unattended AI agents. Rules, all hard:
- Answer the poster's actual question or add one concrete, useful thing. Never sell. Do NOT mention RunVouch, any product,
  any link. Do not say "I built". Speak from experience with unattended jobs only where it fits.
- Plain ASCII, English, 60-140 words, no headings, no emoji, no em dashes, no "---" or other separator lines.
- Write like a person typing a reply, not like a model: contractions (it's, don't), sentences of uneven length, one concrete
  experience beats three general points, at most one short list and only if it really helps. Avoid stock phrases such as
  "genuinely", "honestly", "two things", "it's worth noting", "let me push back", "great question", and never open with praise.
- Be specific (flags, commands, file names, numbers you can defend). If you cannot add anything real, output exactly: SKIP
- Never invent facts about the poster or about tools; if unsure, say what worked for you instead.
Output only the comment text."""


def recent_drafts(n: int = 12) -> list[dict]:
    if not os.path.exists(HISTORY):
        return []
    rows = [json.loads(l) for l in open(HISTORY) if l.strip()]
    return rows[-n:]


def draft(thread_text: str) -> str:
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
        r = subprocess.run([CLAUDE, "-p", RULES + avoid + "\n\nTHREAD:\n" + thread_text[:6000], "--output-format", "json", "--max-turns", "1"],
                           capture_output=True, text=True, timeout=240)
        out = json.loads(r.stdout or "{}").get("result", "").strip()
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
                text = draft(thread(p["url"]))
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
            blocks.append(f"=== {kop} ===\n{waar}: {p['title'][:100]}\n\nLINK:\n{p['url']}\n\nANTWOORD (kopieer en plak als comment):\n{text}")
        else:
            overig.append(p)
    if blocks:
        msg = "Reddit en GitHub vandaag - " + str(drafted) + " antwoord(en) klaar\n\n" + "\n\n".join(blocks)
        if overig:
            msg += "\n\nGezien, geen antwoord geschreven (zeg 'reddit' + link als je er toch een wilt):\n" + "\n".join(
                f"- {p['url']}" for p in overig)
    else:
        msg = "Reddit en GitHub vandaag: geen antwoord geschreven."
        if overig:
            msg += "\nGezien: " + ", ".join(p["url"] for p in overig)
    print(msg)
    if "--dry" not in sys.argv:
        if not blocks:
            print("telegram: niets te melden, geen bericht gestuurd", file=sys.stderr)
        for chunk in ([msg[i:i + 3800] for i in range(0, len(msg), 3800)] if blocks else []):
            telegram(chunk)
        seen |= {p["url"] for p in top}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(sorted(seen)[-2000:], open(STATE, "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
