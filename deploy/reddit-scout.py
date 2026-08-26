#!/usr/bin/env python3
"""reddit-scout.py — reads the public RSS feeds of a few subreddits (no API, no login) and lists
threads worth a genuine comment: scheduled/unattended agents, cron, cost, silent failures, n8n errors.

  python3 reddit-scout.py            -> prints candidates, sends them to the owner's Telegram (from the RunVouch DB)
  python3 reddit-scout.py --dry      -> print only
  python3 reddit-scout.py --thread URL -> print the post text and top comments of one thread (URL + .rss)

Scoring is a keyword match on title + summary; nothing is posted anywhere. Seen threads are remembered
in data/reddit-seen.json so each one is suggested once.
"""
import html, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "data", "reddit-seen.json")
UA = "nightly-runs-reader/0.1 (personal; reads public feeds; contact launch@runvouch.com)"
SUBS = ["ClaudeAI", "ClaudeCode", "n8n", "selfhosted", "Anthropic", "claude"]
KEYWORDS = {  # weight per keyword (lower-case substring match)
    "routine": 3, "scheduled": 3, "schedule": 2, "cron": 3, "headless": 3, "claude -p": 3, "unattended": 4, "overnight": 3,
    "autonomous": 2, "agent": 1, "agents": 1, "loop": 2, "looping": 3, "stuck": 2, "retry": 2, "bill": 3, "cost": 2,
    "spend": 2, "budget": 2, "token": 1, "tokens": 1, "usage limit": 1, "silently": 3, "silent": 2, "failed": 2,
    "didn't run": 4, "did not run": 4, "monitor": 3, "monitoring": 3, "alert": 3, "watchdog": 4, "heartbeat": 3,
    "error workflow": 4, "openclaw": 3, "n8n": 1, "cron job": 4, "systemd": 2, "background": 1, "webhook": 1, "evidence": 2,
}
NS = {"a": "http://www.w3.org/2005/Atom"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


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


def score(p: dict) -> int:
    t = (p["title"] + " " + p["body"]).lower()
    s = sum(w for k, w in KEYWORDS.items() if k in t)
    if "?" in p["title"]:
        s += 2                       # a question is an invitation
    if re.search(r"\b(i built|launch|check out my|my new tool)\b", t):
        s -= 3                       # someone else's showcase: not our place to sell
    return s


def thread(url: str) -> str:
    root = ET.fromstring(fetch(url.rstrip("/") + "/.rss?limit=40"))
    parts = []
    for i, e in enumerate(root.findall("a:entry", NS)):
        who = e.findtext("a:author/a:name", default="?", namespaces=NS)
        txt = strip(e.findtext("a:content", default="", namespaces=NS))
        parts.append(("POST" if i == 0 else f"COMMENT {who}") + ": " + txt[:1500])
    return "\n\n".join(parts)


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
    fresh = [p for p in cands if p["url"] not in seen]
    fresh.sort(key=score, reverse=True)
    top = [p for p in fresh if score(p) >= 5][:5]
    lines = [f"[{score(p)}] r/{p['sub']}: {p['title'][:110]}\n{p['url']}" for p in top]
    msg = "Reddit vandaag - threads waar een echte reactie past (zeg 'reddit' + nummer):\n\n" + "\n\n".join(f"{i+1}. {l}" for i, l in enumerate(lines)) if top else "Reddit vandaag: geen passende nieuwe threads."
    print(msg)
    if "--dry" not in sys.argv:
        telegram(msg)
        seen |= {p["url"] for p in top}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(sorted(seen)[-2000:], open(STATE, "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
