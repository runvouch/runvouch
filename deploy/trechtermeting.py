#!/usr/bin/env python3
"""trechtermeting.py - the four numbers that say whether anyone wants this, once a week.

Everything else we measure says whether the machine works: tests, sweeps, watchdogs, proof days. None of it
moves when nobody signs up, so for three weeks after launch nothing looked wrong while nothing was happening
either (16 September 2026). This writes one line a week: signups, accounts that got as far as a first run,
accounts that pay, and what changed since last week. Visitors are not in here on purpose; that number lives in
GoatCounter behind a login, and a number nobody can reproduce is worse than no number.

State: data/trechter.jsonl, one JSON line per run. Telegram goes to the owner account, same path as the other
ops scripts. Wrapped in rv run by the systemd timer.
"""
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("RUNVOUCH_DB", os.path.join(ROOT, "data", "runvouch.db"))
LOG = os.path.join(ROOT, "data", "trechter.jsonl")
UA = "runvouch-trechtermeting/0.1"
BETAALD = ("solo", "team")


def meet(db: sqlite3.Connection, now: float) -> dict:
    """Counts as of `now`: totals, plus what came in over the last seven days.

    Our own accounts carry source='owner' and are left out of every number. They are on paid plans because that
    is how we dogfood, and counting them would have printed an MRR of $118 on a week with no customers at all.
    """
    week = now - 7 * 86400
    EIGEN = "(source IS NULL OR source != 'owner')"

    def n(sql, *args):
        return db.execute(sql, args).fetchone()[0]

    return {
        "ts": now,
        "accounts": n(f"SELECT COUNT(*) FROM accounts WHERE {EIGEN}"),
        "accounts_7d": n(f"SELECT COUNT(*) FROM accounts WHERE created > ? AND {EIGEN}", week),
        "activated": n(f"SELECT COUNT(DISTINCT account_id) FROM runs WHERE account_id IN (SELECT id FROM accounts WHERE {EIGEN})"),
        "activated_7d": n(f"SELECT COUNT(DISTINCT account_id) FROM runs WHERE started > ? AND account_id IN "
                          f"(SELECT id FROM accounts WHERE {EIGEN})", week),
        "paying": n(f"SELECT COUNT(*) FROM accounts WHERE plan IN ({','.join('?' * len(BETAALD))}) AND {EIGEN}", *BETAALD),
        "mrr": n(f"SELECT COALESCE(SUM(CASE plan WHEN 'solo' THEN 19 WHEN 'team' THEN 99 ELSE 0 END), 0) "
                 f"FROM accounts WHERE {EIGEN}"),
    }


def regel(nu: dict, vorig: dict | None) -> str:
    def delta(sleutel):
        if not vorig:
            return ""
        d = nu[sleutel] - vorig[sleutel]
        return f" ({d:+d})" if d else ""

    return (f"Trechter: {nu['accounts']} accounts{delta('accounts')}, {nu['accounts_7d']} nieuw deze week, "
            f"{nu['activated']} met een eerste run{delta('activated')}, {nu['paying']} betalend{delta('paying')}, "
            f"MRR ${nu['mrr']}{delta('mrr')}.")


def telegram(tekst: str) -> None:
    try:
        db = sqlite3.connect(DB)
        row = db.execute("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL "
                         "ORDER BY id LIMIT 1").fetchone()
        if not row:
            return
        data = urllib.parse.urlencode({"chat_id": row[1], "text": tekst[:3900]}).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{row[0]}/sendMessage", data, {"User-Agent": UA}), timeout=15)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def main() -> int:
    db = sqlite3.connect(DB)
    nu = meet(db, time.time())
    vorig = None
    if os.path.exists(LOG):
        regels = [l for l in open(LOG).read().splitlines() if l.strip()]
        vorig = json.loads(regels[-1]) if regels else None
    tekst = regel(nu, vorig)
    with open(LOG, "a") as f:
        f.write(json.dumps(nu) + "\n")
    print(tekst)
    telegram(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
