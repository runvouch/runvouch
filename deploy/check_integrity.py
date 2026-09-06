#!/usr/bin/env python3
"""Read-only integrity check for a RunVouch database. Safe to run while the server is live.

Answers three questions:
  1. is every run and tool event attached to an account (the per-account run id namespace)
  2. does the account on a run still match the account of its agent
  3. does every sealed proof day still recompute to the root that was stamped

Usage:  python3 deploy/check_integrity.py [path/to/runvouch.db]
Exit code 0 when everything holds, 1 otherwise.
"""
import calendar
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from runvouch import proof as pf  # stdlib only, no database, no side effects

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "runvouch.db")


def day_leaves(db, date):
    """Mirrors server._day_leaves: the day's leaves, live rows and purged ones, ordered by id and hash."""
    t0 = calendar.timegm(time.strptime(date, "%Y-%m-%d"))
    return [r[0] for r in db.execute(
        "SELECT leaf_hash FROM (SELECT id, leaf_hash, ended FROM runs WHERE leaf_hash IS NOT NULL "
        "UNION SELECT id, leaf_hash, ended FROM run_leaves) WHERE ended>=? AND ended<? ORDER BY id, leaf_hash",
        (t0, t0 + 86400))]


def main():
    if not os.path.exists(DB):
        print(f"no database at {DB}")
        return 1
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cols = {t: [r[1] for r in db.execute(f"PRAGMA table_info({t})")] for t in ("runs", "run_leaves", "tool_events")}
    migrated = all("account_id" in c for c in cols.values())
    print(f"database    {DB}")
    print(f"schema      {'run ids are namespaced per account' if migrated else 'OLD: run ids are still global, the server has not started on this database yet'}")
    runs = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    print(f"runs        {runs}")
    bad = 0
    if migrated:
        for table in ("runs", "run_leaves", "tool_events"):
            n = db.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id IS NULL").fetchone()[0]
            print(f"{table + ' without account':<28}{n}")
            bad += n
        n = db.execute("SELECT COUNT(*) FROM runs r JOIN agents g ON g.id=r.agent_id WHERE r.account_id!=g.account_id").fetchone()[0]
        print(f"{'runs on the wrong account':<28}{n}")
        bad += n
    days = db.execute("SELECT date, root, n_runs FROM proof_days ORDER BY date").fetchall()
    ok = 0
    for date, root, n_runs in days:
        leaves = day_leaves(db, date)
        if pf.merkle_root(leaves) == root and len(leaves) == n_runs:
            ok += 1
        else:
            print(f"  day {date}: root or leaf count changed ({len(leaves)} leaves, expected {n_runs})")
    print(f"sealed days {ok} of {len(days)} still recompute to their stamped root")
    bad += len(days) - ok
    print("OK" if not bad else f"NOT OK: {bad} problem(s)")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
