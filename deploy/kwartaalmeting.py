#!/usr/bin/env python3
"""kwartaalmeting.py: are we measurably the best at the three things that matter? Runs on the first day of each quarter.

Three numbers, from our own production database and the site, nothing estimated:
  1. time to alert: median seconds between the end of a failed or evidence-less run and its alert (last 90 days)
  2. silent failures caught: alerts that a heartbeat monitor cannot produce (NO_EVIDENCE, RETRY_STORM, DRIFT, STALLED,
     BUDGET_RUN, BUDGET_DAY), as a count and as a share of all runs (last 90 days)
  3. runtimes covered: integration pages plus the six dedicated guides
Each quarter is written to data/kwartaalmeting/YYYY-Qn.md and compared with the previous one. Use --dry to print only.
"""
import glob, os, re, sqlite3, statistics, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "kwartaalmeting")
SILENT = ("NO_EVIDENCE", "RETRY_STORM", "DRIFT", "STALLED", "BUDGET_RUN", "BUDGET_DAY")


def env():
    return {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}


def telegram(text):
    try:
        row = sqlite3.connect(env()["RUNVOUCH_DB"]).execute(
            "SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        if row:
            data = urllib.parse.urlencode({"chat_id": row[1], "text": text[:3900]}).encode()
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{row[0]}/sendMessage", data), timeout=10)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def meet():
    c = sqlite3.connect(f"file:{env()['RUNVOUCH_DB']}?mode=ro", uri=True)
    d90 = time.time() - 90 * 86400
    runs = c.execute("select count(*) from runs where ended is not null and ended > ?", (d90,)).fetchone()[0]
    lags = [r[0] for r in c.execute("select a.ts - r.ended from alerts a join runs r on r.id = a.run_id "
                                    "where a.kind in ('FAILED','NO_EVIDENCE') and a.ts > ? and r.ended is not null", (d90,)) if r[0] is not None and r[0] >= 0]
    silent = c.execute(f"select count(*) from alerts where ts > ? and kind in ({','.join('?' * len(SILENT))})", (d90, *SILENT)).fetchone()[0]
    sys.path.insert(0, os.path.join(ROOT, "site"))
    from integrations import INTEGRATIONS
    return {"runs": runs, "alerttijd_s": round(statistics.median(lags), 2) if lags else None,
            "stille_fouten": silent, "stille_fouten_per_100_runs": round(100 * silent / runs, 2) if runs else None,
            "runtimes": len(INTEGRATIONS) + 6}


def vorige():
    files = sorted(glob.glob(os.path.join(OUT, "*.md")))
    if not files:
        return None
    m = {}
    for regel in open(files[-1]):
        k = re.match(r"- (\w+): ([\d.]+|geen)", regel)
        if k:
            m[k.group(1)] = None if k.group(2) == "geen" else float(k.group(2))
    return os.path.basename(files[-1])[:-3], m


def main():
    dry = "--dry" in sys.argv
    t = time.gmtime()
    kwartaal = f"{t.tm_year}-Q{(t.tm_mon - 1) // 3 + 1}"
    nu = meet()
    vg = vorige()
    regels = [f"KWARTAALMETING {kwartaal} (laatste 90 dagen, eigen productiedata)", ""]
    for k, label in (("alerttijd_s", "seconden van stille fout tot alarm (mediaan)"), ("stille_fouten", "stille fouten gevangen die een heartbeat-monitor niet ziet"),
                     ("stille_fouten_per_100_runs", "daarvan per 100 runs"), ("runtimes", "runtimes met een eigen pagina"), ("runs", "runs gemeten")):
        v = nu[k]
        oud = vg[1].get(k) if vg else None
        delta = "" if oud is None or v is None else f"  (vorige {vg[0]}: {oud:g})"
        regels.append(f"- {k}: {'geen' if v is None else f'{v:g}'}  {label}{delta}")
    regels += ["", "Wat de beste zijn hier betekent: sneller weten, meer stille fouten vangen, overal draaien. "
                   "Een getal dat een kwartaal niet beweegt is een keuze, geen toeval."]
    tekst = "\n".join(regels)
    print(tekst)
    if not dry:
        os.makedirs(OUT, exist_ok=True)
        open(os.path.join(OUT, kwartaal + ".md"), "w").write(tekst + "\n")
        telegram(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
