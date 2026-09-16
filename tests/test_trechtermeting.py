"""De vier getallen die zeggen of iemand dit wil.

Waarom deze test bestaat: een meting die stilletjes nul telt is erger dan geen meting, want dan denk je dat je
meet. Deze legt vast dat een betalend account ook echt in de MRR terechtkomt en dat het verschil met vorige week
in de regel staat.
"""
import importlib.util
import os
import sqlite3
import time

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "trechtermeting", os.path.join(os.path.dirname(HIER), "deploy", "trechtermeting.py"))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

NU = time.time()


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY, created REAL, plan TEXT, source TEXT)")
    db.execute("CREATE TABLE runs(id TEXT, account_id INTEGER, started REAL)")
    return db


def test_telt_aanmeldingen_activatie_en_omzet():
    db = _db()
    for i, (plan, ouderdom) in enumerate(((("free"), 30 * 86400), ("solo", 3 * 86400), ("team", 2 * 86400), ("free", 1 * 86400)), 1):
        db.execute("INSERT INTO accounts(id, created, plan) VALUES(?,?,?)", (i, NU - ouderdom, plan))
    db.execute("INSERT INTO runs(id, account_id, started) VALUES('r1', 2, ?)", (NU - 3600,))
    db.execute("INSERT INTO runs(id, account_id, started) VALUES('r2', 2, ?)", (NU - 7200,))
    db.execute("INSERT INTO runs(id, account_id, started) VALUES('r3', 1, ?)", (NU - 40 * 86400,))

    db.execute("INSERT INTO accounts(id, created, plan, source) VALUES(9, ?, 'team', 'owner')", (NU - 5 * 86400,))
    db.execute("INSERT INTO runs(id, account_id, started) VALUES('r9', 9, ?)", (NU - 600,))

    m = T.meet(db, NU)
    assert m["accounts"] == 4 and m["accounts_7d"] == 3
    assert m["activated"] == 2, "twee accounts hebben ooit een run gepost"
    assert m["activated_7d"] == 1, "een account draaide deze week"
    assert m["paying"] == 2 and m["mrr"] == 19 + 99, "het eigen team-account telt niet mee"


def test_regel_toont_het_verschil_met_vorige_week():
    vorig = {"accounts": 4, "accounts_7d": 1, "activated": 2, "activated_7d": 1, "paying": 1, "mrr": 19}
    nu = {"accounts": 6, "accounts_7d": 2, "activated": 3, "activated_7d": 1, "paying": 2, "mrr": 118}
    r = T.regel(nu, vorig)
    assert "6 accounts (+2)" in r and "2 betalend (+1)" in r and "MRR $118 (+99)" in r
    assert "(" not in T.regel(nu, None).split("accounts")[0], "zonder vorige week geen verschil tonen"
