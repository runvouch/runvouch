#!/usr/bin/env python3
"""koperswandeling.py — weekly buyer walk-through of both sites, done by the local Claude Code CLI.

Every Monday: walk runvouch.com and datasignalslab.com as a buyer would (home, pricing, docs, product
pages, reports, forms, downloads, mails' landing pages), click what a buyer clicks, and report ONLY what
is broken, wrong, stale, or weaker than the rest. Nothing is changed; the report goes to the owner's
Telegram and to data/koperswandeling/YYYY-MM-DD.md. Wrapped in rv run by the systemd timer.
"""
import json, os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")
OUT = os.path.join(ROOT, "data", "koperswandeling")
UA = "runvouch-koperswandeling/0.1"

BRIEF = """You are a careful buyer, not a reviewer of style. Walk these two sites the way a paying customer would and report
ONLY defects: broken links, forms that do not respond, downloads that fail, numbers that contradict each other, dates that
are stale (older than 2 days where the page promises daily), pages that render badly (empty sections, overlapping text,
text you cannot read), and promises on a page that the product page or docs do not back up. Skip taste and wording.

Sites and the paths a buyer takes:
1. https://runvouch.com : home, /pricing (both Upgrade buttons must open a Polar checkout that shows a price and a card
   form, do not pay), /docs/ and every docs page linked from it, /verifiable-agent-runs, /blog/ and the newest article,
   /app (must render a key field), /status (all rows must resolve), api.runvouch.com/health (JSON, status ok),
   api.runvouch.com/proof/ (JSON with days), the free key form on /pricing (submit with the address
   koperswandeling@runvouch.com once; it must say the key is shown or mailed).
2. https://datasignalslab.com : home, every product card, /reports.html (three covers with dates within the last
   45 days for Form D and Congress), /events-api.html and its free key form (submit once with
   koperswandeling@runvouch.com; it must say check your inbox), /datasignals-mcp.html, /compare.html, /proof.html
   (the day file for yesterday must exist and load), /agent-templates.html, /company/, /hiring/, /filings/,
   /congress/ and one page in each, /blog.html and the newest post, /llms.txt, /sitemap.xml (sample 20 URLs).
Use curl with a browser User-Agent for status codes and a headless browser (python3 with playwright; set
LD_LIBRARY_PATH=/home/krtradingpro/chromelibs/root/usr/lib/x86_64-linux-gnu first; a working example is
/home/krtradingpro/runvouch/shot.py) for rendering checks at 1440 and 390 px wide, scrolling each page fully.

Output: plain text, Dutch, no em dashes, no separator lines. First line: "OK" if nothing is broken, otherwise "DEFECTEN: N".
Then one line per defect: site, page, what is wrong, how you measured it. Max 40 lines. Do not propose rewrites."""


def telegram(text: str) -> None:
    try:
        env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
        row = sqlite3.connect(env["RUNVOUCH_DB"]).execute(
            "SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        if row:
            for chunk in [text[i:i + 3800] for i in range(0, len(text), 3800)] or ["(leeg)"]:
                data = urllib.parse.urlencode({"chat_id": row[1], "text": chunk, "disable_web_page_preview": "true"}).encode()
                urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{row[0]}/sendMessage", data, {"User-Agent": UA}), timeout=10)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    r = subprocess.run([CLAUDE, "-p", BRIEF, "--output-format", "json", "--max-turns", "80",
                        "--allowedTools", "Bash,Read,WebFetch"], capture_output=True, text=True, timeout=2400, cwd=ROOT)
    try:
        out = json.loads(r.stdout or "{}").get("result", "").strip()
    except Exception:
        out = ""
    if not out:
        out = "Koperswandeling kon niet worden afgerond: " + (r.stderr or "geen uitvoer")[-500:]
    path = os.path.join(OUT, time.strftime("%Y-%m-%d") + ".md")
    open(path, "w").write(out + "\n")
    print(out)
    if out.startswith("OK"):
        telegram("Koperswandeling " + time.strftime("%Y-%m-%d") + ": OK, beide sites zonder defecten.")
    else:
        telegram("Koperswandeling " + time.strftime("%Y-%m-%d") + "\n\n" + out)
    return 0 if out.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main())
