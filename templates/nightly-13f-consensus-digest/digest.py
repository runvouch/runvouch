#!/usr/bin/env python3
"""Nightly 13F consensus digest. Standard library only.

Pulls hedge_fund_13f for the filers in funds.txt through the DataSignals MCP server,
ranks the cross-fund consensus picks, writes out/13f-digest.md with the top 10 and
what changed since the previous digest (kept as out/13f-digest.prev.json).

    APIFY_TOKEN=... python3 digest.py            # live
    python3 digest.py --input result.json         # offline: reuse a saved MCP result
    python3 digest.py --spend-cap 5               # refuse calls once the MCP ledger hits $5
"""
import argparse, datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ds_mcp import call

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "13f-digest.md")
PREV = os.path.join(HERE, "out", "13f-digest.prev.json")
TOP = 10


def read_funds():
    ciks = []
    for line in open(os.path.join(HERE, "funds.txt")):
        line = line.split("#")[0].strip()
        if line:
            ciks.append(line.split()[0])
    return ciks


def picks_from(result):
    """The actor pushes one 'consensus' item with a ranked picks list, plus one item per filer."""
    for item in result.get("items", []):
        if item.get("type") == "consensus":
            return item.get("picks", [])
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="saved MCP result (JSON) instead of a live call")
    ap.add_argument("--spend-cap", type=float, default=None)
    a = ap.parse_args()
    if a.input:
        result = json.load(open(a.input))
    else:
        result = call("hedge_fund_13f", {"filer_ciks": read_funds(), "max_results": 50}, spend_cap_usd=a.spend_cap)
    if not result.get("ok", True) and result.get("error"):
        sys.exit("hedge_fund_13f: " + str(result["error"]))
    picks = picks_from(result)
    if not picks:
        sys.exit("no consensus picks in the result; nothing written")
    picks = sorted(picks, key=lambda p: (-p.get("buyers", 0), -p.get("funds_holding", 0), -p.get("total_value", 0)))[:TOP]
    now = {p["issuer"]: p for p in picks}

    prev = {}
    if os.path.exists(PREV):
        prev = {p["issuer"]: p for p in json.load(open(PREV))}
    entered = [n for n in now if n not in prev]
    dropped = [n for n in prev if n not in now]
    changed = [n for n in now if n in prev and (now[n].get("buyers") != prev[n].get("buyers")
                                                or now[n].get("funds_holding") != prev[n].get("funds_holding"))]

    today = datetime.date.today().isoformat()
    lines = [f"# 13F consensus digest, {today}", "",
             f"Filers: {len(read_funds())} (funds.txt). Source: SEC EDGAR 13F via DataSignals Lab. "
             "13F is quarterly with a 45 day lag, so most nights nothing changes; a change here means a new filing landed.", "",
             "## Top 10 by number of funds buying", "",
             "| # | Issuer | Funds buying | Funds holding | Total value (USD) | Conviction |", "|---|---|---|---|---|---|"]
    for i, p in enumerate(picks, 1):
        lines.append(f"| {i} | {p['issuer']} | {p.get('buyers', 0)} | {p.get('funds_holding', 0)} | "
                     f"{int(p.get('total_value', 0)):,} | {p.get('conviction', 0):.0f} |")
    lines += ["", "## Changed since the previous digest", ""]
    if not prev:
        lines.append("First run, nothing to compare against.")
    elif not (entered or dropped or changed):
        lines.append("No change.")
    else:
        for n in entered:
            lines.append(f"- Entered the top {TOP}: {n} ({now[n].get('buyers', 0)} funds buying)")
        for n in dropped:
            lines.append(f"- Left the top {TOP}: {n}")
        for n in changed:
            lines.append(f"- {n}: buyers {prev[n].get('buyers', 0)} -> {now[n].get('buyers', 0)}, "
                         f"holders {prev[n].get('funds_holding', 0)} -> {now[n].get('funds_holding', 0)}")
    lines += ["", f"Billed this call: ${result.get('billed_usd', 0)} (first 50 MCP calls a month are free).", ""]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(lines))
    json.dump(picks, open(PREV, "w"))
    print(f"wrote {OUT}: {len(picks)} picks, {len(entered)} in, {len(dropped)} out, {len(changed)} changed")


if __name__ == "__main__":
    main()
