#!/usr/bin/env python3
"""Weekly competitor hiring watch. Standard library only.

For every company slug in companies.txt, counts its open roles through the DataSignals MCP
tool job_openings (live from the company's own career site), writes out/hiring-YYYY-WW.md
with the counts and the change versus last week's file, and alerts when a company's count
jumped more than 25 percent.

    APIFY_TOKEN=... python3 hiring.py
    python3 hiring.py --input saved.json   # offline: a JSON object {slug: mcp_result}
"""
import argparse, datetime, glob, json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ds_mcp import call

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "out")
JUMP = 0.25
MAX_JOBS = 200


def companies():
    out = []
    for line in open(os.path.join(HERE, "companies.txt")):
        line = line.split("#")[0].strip()
        if line:
            out.append(line)
    return out


def count_for(slug, spend_cap):
    r = call("job_openings", {"companies": [slug], "max_jobs": MAX_JOBS, "max_results": MAX_JOBS}, spend_cap_usd=spend_cap)
    if not r.get("ok", True) and r.get("error"):
        raise RuntimeError(f"{slug}: {r['error']}")
    return r


def summarize(slug, r):
    items = r.get("items", [])
    depts = {}
    for j in items:
        d = j.get("department") or "unspecified"
        depts[d] = depts.get(d, 0) + 1
    top = sorted(depts.items(), key=lambda kv: -kv[1])[:3]
    return {"count": len(items), "capped": len(items) >= MAX_JOBS, "top_departments": top,
            "billed_usd": r.get("billed_usd", 0)}


def previous_counts(current_name):
    files = sorted(f for f in glob.glob(os.path.join(OUTDIR, "hiring-*.json")) if not f.endswith(current_name + ".json"))
    if not files:
        return {}, None
    return json.load(open(files[-1])), os.path.basename(files[-1])


def telegram(text):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, printing instead\n" + text); return
    body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=20).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="saved results {slug: mcp_result} instead of live calls")
    ap.add_argument("--spend-cap", type=float, default=None)
    a = ap.parse_args()
    today = datetime.date.today()
    year, week, _ = today.isocalendar()
    name = f"hiring-{year}-{week:02d}"
    saved = json.load(open(a.input)) if a.input else {}
    rows = {}
    for slug in companies():
        r = saved.get(slug) if a.input else count_for(slug, a.spend_cap)
        if r is None:
            continue
        rows[slug] = summarize(slug, r)
    if not rows:
        sys.exit("no results, nothing written")
    prev, prev_name = previous_counts(name)
    alerts = []
    lines = [f"# Competitor hiring, week {year}-W{week:02d} ({today.isoformat()})", "",
             "Open roles read live from each company's own career site (DataSignals job_openings). "
             + (f"Compared with {prev_name}." if prev_name else "First week, no comparison yet."), "",
             "| Company | Open roles | Last week | Change | Top departments |", "|---|---|---|---|---|"]
    for slug, s in rows.items():
        p = prev.get(slug, {}).get("count")
        if p is None:
            change = "new"
        elif p == 0:
            change = f"+{s['count']}" if s["count"] else "0"
        else:
            pct = (s["count"] - p) / p
            change = f"{pct:+.0%}"
            if pct > JUMP:
                alerts.append(f"{slug}: {p} -> {s['count']} open roles ({pct:+.0%})")
        cap = " (capped)" if s["capped"] else ""
        deps = ", ".join(f"{d} {n}" for d, n in s["top_departments"]) or "-"
        lines.append(f"| {slug} | {s['count']}{cap} | {'-' if p is None else p} | {change} | {deps} |")
    lines += ["", "## Alerts (count up more than 25%)", ""]
    lines += [f"- {x}" for x in alerts] or ["None."]
    lines += ["", f"Billed this run: ${sum(s['billed_usd'] for s in rows.values()):.2f} "
              "(first 50 MCP calls a month are free; one call per company per week).", ""]
    os.makedirs(OUTDIR, exist_ok=True)
    md = os.path.join(OUTDIR, name + ".md")
    open(md, "w").write("\n".join(lines))
    json.dump(rows, open(os.path.join(OUTDIR, name + ".json"), "w"))
    latest = os.path.join(OUTDIR, "hiring-latest.md")
    open(latest, "w").write("\n".join(lines))
    print(f"wrote {md}: {len(rows)} companies, {len(alerts)} alert(s)")
    if alerts:
        telegram("Hiring jump this week\n" + "\n".join(alerts))


if __name__ == "__main__":
    main()
