#!/usr/bin/env python3
"""marktwacht.py — market watch for both businesses, every two weeks (1st and 15th), done by the local Claude Code CLI with web search.

Twice a month: what did the competition change (prices, features, positioning), who is new in the two niches,
where are we visible and where not, and which gaps are open that we could close first. Report ONLY what is measured
(a URL, a price, a date), never guesses. Goes to the owner's Telegram and to data/marktwacht/YYYY-MM.md.
"""
import json, os, sqlite3, subprocess, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")
OUT = os.path.join(ROOT, "data", "marktwacht")
UA = "runvouch-marktwacht/0.1"

BRIEF = """You are the market analyst for two small companies run by one founder. Use WebSearch and WebFetch; cite a URL for
every fact. No guesses, no invented numbers; if you cannot verify something, leave it out.

Company 1: RunVouch (runvouch.com), the watchdog for unattended AI agents: 8 detectors (MISSED, FAILED, NO_EVIDENCE,
RETRY_STORM, BUDGET_RUN, BUDGET_DAY, DRIFT, STALLED), alerts (Telegram, Slack, email, webhook, PagerDuty), a tamper-evident
proof per run anchored in Bitcoin, Claude Code plugin, MCP server, GitHub Action, pip/npm CLI. Free 3 agents, Solo $9, Team $29.
Known competitors: Healthchecks.io, Cronitor, Langfuse, LangSmith, NotiLens, AgentWatch (getagentwatch.com), AgentWatch (agent-watch.de).
Company 2: DataSignals Lab (datasignalslab.com), official US public data (SEC filings, Form D, 13F, 8-K, FDA, NIH, federal
contracts, congress trades, hiring) turned into scored signals; sold as Apify actors ($0.20/result), an Events API ($29+),
reports ($19) and a free MCP server; daily output hashed and anchored in Bitcoin. Known competitors: Quiver Quantitative,
Unusual Whales, Capitol Trades, WhaleWisdom, Fintel, Dataroma.

Deliver, in Dutch, plain text, no em dashes, no separator lines, max 70 lines:
1. Per competitor (both lists): anything that changed in the last 20 days (price, new feature, new positioning, funding,
   shutdown), with URL. Write "geen wijziging gevonden" if nothing.
2. New entrants: products launched in the last 30 days in either niche (Product Hunt, Hacker News, GitHub trending, the
   MCP registry, Apify Store), with URL and what they do.
3. Our visibility: for each of these searches, are we in the first page of results (say yes/no per search engine you can
   check): "watchdog for AI agents", "monitor Claude Code routines", "prove what an AI agent did", "AI agent audit trail",
   "SEC filings API for AI agents", "congress trading data MCP". Also: are we listed on Glama, Smithery, PulseMCP,
   awesome-mcp-servers (check the live pages).
4. Gaps: the 5 most valuable things a competitor does that we do not, and the 5 things we do that none of them do
   (verify on their sites). For each gap: one sentence on what it would take.
5. One recommendation for the next two weeks, with the measurement that would prove it worked.
6. BOUWLIJST (fixed question, every time): which detector, integration or alert channel does any competitor have that
   RunVouch does not, and which data source or delivery channel does any competitor have that DataSignals Lab does not?
   One line each: what it is, who has it (URL), estimated build time for one developer, and whether a competitor could
   copy it back within a month (if yes: low priority, it is maintenance, not an edge). Start this section with the exact
   line "BOUWLIJST" so it can be filed automatically. Write "BOUWLIJST\ngeen" if nothing was found."""


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
    r = subprocess.run([CLAUDE, "-p", BRIEF, "--output-format", "json", "--max-turns", "120",
                        "--allowedTools", "WebSearch,WebFetch,Read"], capture_output=True, text=True, timeout=3000, cwd=ROOT)
    try:
        out = json.loads(r.stdout or "{}").get("result", "").strip()
    except Exception:
        out = ""
    if not out:
        out = "Marktwacht kon niet worden afgerond: " + (r.stderr or "geen uitvoer")[-500:]
    stamp = time.strftime("%Y-%m-%d")
    path = os.path.join(OUT, stamp + ".md")
    open(path, "w").write(out + "\n")
    # the build list accumulates in one file, newest on top, so the gap between us and the market is one document
    if "BOUWLIJST" in out:
        lijst = out[out.index("BOUWLIJST") + len("BOUWLIJST"):].strip()
        bl = os.path.join(OUT, "bouwlijst.md")
        oud = open(bl).read() if os.path.exists(bl) else "# Bouwlijst uit de marktwacht (nieuwste boven)\n\n"
        kop, _, rest = oud.partition("\n\n")
        open(bl, "w").write(f"{kop}\n\n## {stamp}\n{lijst}\n\n{rest}")
    print(out)
    telegram("Marktwacht " + stamp + "\n\n" + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
