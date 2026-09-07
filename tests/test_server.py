import os, sys, time, json
import tempfile
os.environ["RUNVOUCH_DB"] = os.path.join(tempfile.mkdtemp(prefix="runvouch-test-"), "test.db")
os.environ["RUNVOUCH_NO_SWEEP"] = "1"
os.environ["RUNVOUCH_ADMIN_TOKEN"] = "adm"
os.environ["RUNVOUCH_STORM_THRESHOLD"] = "5"
for f in (os.environ["RUNVOUCH_DB"], os.environ["RUNVOUCH_DB"] + "-wal", os.environ["RUNVOUCH_DB"] + "-shm"):
    if os.path.exists(f): os.remove(f)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from runvouch import server

c = TestClient(server.app)
KEY = c.post("/admin/accounts", params={"name": "t", "plan": "team"}, headers={"X-Admin-Token": "adm"}).json()["api_key"]
H = {"X-API-Key": KEY}


def alerts(kind=None):
    a = c.get("/v1/alerts", headers=H).json()
    return [x for x in a if not kind or x["kind"] == kind]


def test_auth():
    assert c.get("/v1/agents").status_code == 401
    assert c.get("/v1/agents", headers={"X-API-Key": "nope"}).status_code == 401


def test_failed_and_evidence():
    c.post("/v1/agents", json={"name": "nightly", "cadence_s": 3600, "evidence_required": True}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "nightly"}, headers=H).json()["run_id"]
    r = c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "evidence": {"report_written": False}}, headers=H).json()
    assert r["evidence_ok"] is False
    assert alerts("NO_EVIDENCE"), "green run without evidence must alert"
    rid = c.post("/v1/runs/start", json={"agent": "nightly"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "fail", "meta": {"error": "boom"}}, headers=H)
    assert any("boom" in a["message"] for a in alerts("FAILED"))
    rid = c.post("/v1/runs/start", json={"agent": "nightly"}, headers=H).json()["run_id"]
    r = c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "evidence": {"report_written": True}}, headers=H).json()
    assert r["evidence_ok"] is True


def test_retry_storm():
    c.post("/v1/agents", json={"name": "looper"}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "looper"}, headers=H).json()["run_id"]
    for _ in range(4):
        c.post("/v1/runs/tool", json={"run_id": rid, "tool": "cat", "input": {"f": "missing.txt"}}, headers=H)
    assert not alerts("RETRY_STORM")
    c.post("/v1/runs/tool", json={"run_id": rid, "tool": "cat", "input": {"f": "missing.txt"}}, headers=H)
    assert alerts("RETRY_STORM")
    # different inputs are not a storm
    rid2 = c.post("/v1/runs/start", json={"agent": "looper"}, headers=H).json()["run_id"]
    for i in range(10):
        c.post("/v1/runs/tool", json={"run_id": rid2, "tool": "cat", "input": {"f": f"{i}.txt"}}, headers=H)
    assert len([a for a in alerts("RETRY_STORM") if a["run_id"] == rid2]) == 0


def test_budget():
    c.post("/v1/agents", json={"name": "spender", "cap_run_cost": 1.0, "cap_day_cost": 2.5}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "spender"}, headers=H).json()["run_id"]
    c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": 1, "cost": 0.6}, headers=H)
    assert not alerts("BUDGET_RUN")
    c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": 2, "cost": 0.6}, headers=H)
    assert alerts("BUDGET_RUN")
    c.post("/v1/runs/end", json={"run_id": rid, "status": "ok"}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "spender"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "cost": 0.9}, headers=H)
    assert not alerts("BUDGET_DAY")
    rid = c.post("/v1/runs/start", json={"agent": "spender"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "cost": 0.9}, headers=H)
    assert alerts("BUDGET_DAY")


def test_missed_and_stalled():
    c.post("/v1/agents", json={"name": "hourly", "cadence_s": 3600, "grace_s": 60, "max_runtime_s": 600}, headers=H)
    server.sweep_once(now=time.time() + 3000)
    assert not alerts("MISSED")
    server.sweep_once(now=time.time() + 3700)
    assert alerts("MISSED")
    mine = lambda: [a for a in alerts("MISSED") if a["agent"] == "hourly"]
    n = len(mine())
    for extra in (7300, 10900, 14500):   # sweeps keep passing, the agent stays silent
        server.sweep_once(now=time.time() + extra)
    assert len(mine()) == n, "the same missed run must alert once, not every sweep"
    rid = c.post("/v1/runs/start", json={"agent": "hourly"}, headers=H).json()["run_id"]
    server.sweep_once(now=time.time() + 700)
    assert alerts("STALLED")


def test_drift():
    c.post("/v1/agents", json={"name": "stable"}, headers=H)
    for i in range(6):
        rid = c.post("/v1/runs/start", json={"agent": "stable"}, headers=H).json()["run_id"]
        c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "output_bytes": 10000 + i * 10}, headers=H)
    assert not alerts("DRIFT")
    rid = c.post("/v1/runs/start", json={"agent": "stable"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "output_bytes": 120}, headers=H)
    assert alerts("DRIFT"), "output collapsed to 1% of baseline must alert"


def test_plan_limit_and_state():
    fk = c.post("/admin/accounts", params={"name": "free"}, headers={"X-Admin-Token": "adm"}).json()["api_key"]
    for n in ("a1", "a2", "a3"):
        assert c.post("/v1/agents", json={"name": n}, headers={"X-API-Key": fk}).status_code == 200
    assert c.post("/v1/agents", json={"name": "one-too-many"}, headers={"X-API-Key": fk}).status_code == 402
    st = {a["name"]: a["state"] for a in c.get("/v1/agents", headers=H).json()}
    assert st["stable"] == "alert" and st["hourly"] in ("alert", "running")
    aid = alerts()[0]["id"]
    c.post(f"/v1/alerts/{aid}/ack", headers=H)
    assert aid not in [a["id"] for a in alerts()]


def test_keys_hashed_and_signup():
    row = server.q1("SELECT api_key FROM accounts LIMIT 1")
    assert not row["api_key"].startswith("rv_") and len(row["api_key"]) == 64
    r = c.post("/signup", json={"email": "New.User@Example.com"})
    assert r.status_code == 200 and r.json()["api_key"].startswith("rv_")
    k = r.json()["api_key"]
    assert c.get("/v1/me", headers={"X-API-Key": k}).json()["email"] == "new.user@example.com"
    r2 = c.post("/signup", json={"email": "new.user@example.com"})
    assert r2.status_code == 200 and r2.json()["sent"] is True          # re-signup mails a fresh key, old key dies
    assert c.get("/v1/me", headers={"X-API-Key": k}).status_code == 401
    k = c.post("/admin/accounts", params={"name": "t2", "plan": "free"}, headers={"X-Admin-Token": "adm"}).json()["api_key"]
    assert c.post("/signup", json={"email": "not-an-email"}).status_code == 422
    nk = c.post("/v1/me/rotate-key", headers={"X-API-Key": k}).json()["api_key"]
    assert c.get("/v1/me", headers={"X-API-Key": k}).status_code == 401
    assert c.get("/v1/me", headers={"X-API-Key": nk}).status_code == 200


def test_ls_webhook():
    import hmac, hashlib
    server.LS_WEBHOOK_SECRET = "s3"
    server.LS_VARIANT_PLANS = {"111": "team"}
    def send(name, email, variant="111", status="active"):
        body = json.dumps({"meta": {"event_name": name}, "data": {"id": "sub1", "attributes": {"user_email": email, "variant_id": variant, "status": status, "updated_at": name}}}).encode()
        sig = hmac.new(b"s3", body, hashlib.sha256).hexdigest()
        return c.post("/webhooks/lemonsqueezy", content=body, headers={"X-Signature": sig, "Content-Type": "application/json"})
    assert c.post("/webhooks/lemonsqueezy", content=b"{}", headers={"X-Signature": "bad"}).status_code == 401
    r = send("subscription_created", "new.user@example.com")
    assert r.status_code == 200 and r.json()["plan"] == "team" and r.json()["matched"]
    assert server.q1("SELECT plan FROM accounts WHERE email='new.user@example.com'")["plan"] == "team"
    assert send("subscription_created", "new.user@example.com").json().get("dup") is True
    send("subscription_cancelled", "new.user@example.com", status="cancelled")
    assert server.q1("SELECT plan FROM accounts WHERE email='new.user@example.com'")["plan"] == "free"
    send("order_created", "paid.first@example.com", status="paid")
    assert server.q1("SELECT plan FROM accounts WHERE email='paid.first@example.com'")["plan"] == "team"


def test_rate_limit():
    server.RATE_PER_MIN = 5
    k = c.post("/signup", json={"email": "rl@example.com"}).json()["api_key"]
    codes = [c.get("/v1/me", headers={"X-API-Key": k}).status_code for _ in range(7)]
    assert 429 in codes and codes[0] == 200
    server.RATE_PER_MIN = 600


def test_remote_mcp():
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).json()
    assert r["result"]["serverInfo"]["name"] == "runvouch"
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
    assert len(r["result"]["tools"]) == 7
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "runvouch_status", "arguments": {}}}, headers=H).json()
    assert "nightly" in r["result"]["content"][0]["text"]
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "runvouch_status", "arguments": {}}}, headers={"Authorization": "Bearer nope"}).json()
    assert r["result"].get("isError")


def test_weekly_report_gating():
    import calendar
    # a Wednesday → nothing sent; a Monday 08:00 UTC → runs (no telegram configured → 0 delivered, but no crash)
    wed = calendar.timegm((2026, 8, 26, 8, 0, 0, 0, 0, 0)); mon = calendar.timegm((2026, 8, 31, 8, 0, 0, 0, 0, 0))
    assert server.weekly_report(wed) == 0
    assert server.weekly_report(mon) == 0
    assert server.q1("SELECT COUNT(*) n FROM reports_sent")["n"] >= 0


def test_stripe_webhook():
    import hmac, hashlib
    server.STRIPE_WEBHOOK_SECRET = "whsec_test"
    server.STRIPE_PRICE_PLANS = {"price_solo": "solo", "price_team": "team"}
    n = [0]
    def send(typ, obj):
        n[0] += 1
        body = json.dumps({"id": f"evt_{n[0]}", "type": typ, "data": {"object": obj}}).encode()
        ts = str(int(time.time()))
        sig = hmac.new(b"whsec_test", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        return c.post("/webhooks/stripe", content=body, headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"})
    assert c.post("/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"}).status_code == 401
    # signup first, then pay with the same email
    c.post("/signup", json={"email": "stripe.user@example.com"})
    r = send("checkout.session.completed", {"customer": "cus_1", "subscription": "sub_1", "payment_status": "paid",
                                            "customer_details": {"email": "Stripe.User@example.com"}, "metadata": {"plan": "team", "price": "price_team"}})
    assert r.status_code == 200 and r.json()["plan"] == "team" and r.json()["matched"]
    assert server.q1("SELECT plan, stripe_customer_id FROM accounts WHERE email='stripe.user@example.com'")["stripe_customer_id"] == "cus_1"
    # later events carry only the customer id
    send("customer.subscription.updated", {"id": "sub_1", "customer": "cus_1", "status": "active", "items": {"data": [{"price": {"id": "price_solo"}}]}})
    assert server.q1("SELECT plan FROM accounts WHERE email='stripe.user@example.com'")["plan"] == "solo"
    send("customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1", "status": "canceled"})
    assert server.q1("SELECT plan FROM accounts WHERE email='stripe.user@example.com'")["plan"] == "free"
    # paid before signing up: account is created on the paid plan
    send("checkout.session.completed", {"customer": "cus_2", "payment_status": "paid", "customer_details": {"email": "first.pay@example.com"},
                                        "line_items": {"data": [{"price": {"id": "price_solo"}}]}})
    assert server.q1("SELECT plan FROM accounts WHERE email='first.pay@example.com'")["plan"] == "solo"


def test_polar_webhook():
    import hmac, hashlib, base64
    server.POLAR_WEBHOOK_SECRET = "polar-test-secret"  # Polar: raw secret string is the HMAC key
    server.POLAR_PRODUCT_PLANS = {"prod-solo": "solo", "prod-team": "team"}
    n = [0]
    def send(typ, obj):
        n[0] += 1
        body = json.dumps({"type": typ, "data": obj}).encode()
        wid, ts = f"msg_{n[0]}", str(int(time.time()))
        sig = base64.b64encode(hmac.new(b"polar-test-secret", f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
        return c.post("/webhooks/polar", content=body, headers={"webhook-id": wid, "webhook-timestamp": ts, "webhook-signature": "v1," + sig, "Content-Type": "application/json"})
    assert c.post("/webhooks/polar", content=b"{}", headers={"webhook-id": "x", "webhook-timestamp": str(int(time.time())), "webhook-signature": "v1,bad"}).status_code == 401
    c.post("/signup", json={"email": "polar.user@example.com"})
    r = send("order.paid", {"id": "o1", "status": "paid", "paid": True, "billing_reason": "purchase", "product_id": "prod-team", "subscription_id": "s1",
                            "customer": {"id": "c1", "email": "Polar.User@example.com"}})
    assert r.status_code == 200 and r.json()["plan"] == "team" and r.json()["matched"]
    assert server.q1("SELECT polar_customer_id FROM accounts WHERE email='polar.user@example.com'")["polar_customer_id"] == "c1"
    send("subscription.updated", {"id": "s1", "status": "active", "product_id": "prod-solo", "customer": {"id": "c1"}})
    assert server.q1("SELECT plan FROM accounts WHERE email='polar.user@example.com'")["plan"] == "solo"
    send("order.paid", {"id": "o2", "status": "paid", "paid": True, "billing_reason": "subscription_cycle", "product_id": "prod-solo", "customer": {"id": "c1"}})
    assert server.q1("SELECT plan FROM accounts WHERE email='polar.user@example.com'")["plan"] == "solo"
    send("subscription.revoked", {"id": "s1", "status": "canceled", "product_id": "prod-solo", "customer": {"id": "c1"}})
    assert server.q1("SELECT plan FROM accounts WHERE email='polar.user@example.com'")["plan"] == "free"
    send("order.paid", {"id": "o3", "status": "paid", "paid": True, "product_id": "prod-solo", "customer": {"id": "c2", "email": "polar.first@example.com"}})
    assert server.q1("SELECT plan FROM accounts WHERE email='polar.first@example.com'")["plan"] == "solo"
    send("order.refunded", {"id": "o3", "status": "refunded", "total_amount": 900, "refunded_amount": 900, "product_id": "prod-solo", "customer": {"id": "c2", "email": "polar.first@example.com"}})
    assert server.q1("SELECT plan FROM accounts WHERE email='polar.first@example.com'")["plan"] == "free"


def test_polar_billing_mails(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "_send_billing", lambda kind, to, plan, ends_at=None, api_key=None: sent.append((kind, to, plan, ends_at, bool(api_key))))
    import hmac, hashlib, base64
    server.POLAR_WEBHOOK_SECRET = "polar-test-secret"; server.POLAR_PRODUCT_PLANS = {"prod-solo": "solo", "prod-team": "team"}
    n = [100]
    def send(typ, obj):
        n[0] += 1
        body = json.dumps({"type": typ, "data": obj}).encode(); wid, ts = f"msg_{n[0]}", str(int(time.time()))
        sig = base64.b64encode(hmac.new(b"polar-test-secret", f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
        return c.post("/webhooks/polar", content=body, headers={"webhook-id": wid, "webhook-timestamp": ts, "webhook-signature": "v1," + sig}).json()
    cust = {"id": "c9", "email": "mail.test@example.com"}
    assert send("order.paid", {"id": "m1", "paid": True, "billing_reason": "purchase", "product_id": "prod-solo", "subscription_id": "s9", "customer": cust})["mail"] == "welcome"
    assert sent[-1][0] == "welcome" and sent[-1][4] is True          # paid before signup: key goes in the mail
    assert send("order.paid", {"id": "m2", "paid": True, "billing_reason": "subscription_cycle", "product_id": "prod-solo", "customer": cust})["mail"] is None  # renewal: no mail
    assert send("subscription.canceled", {"id": "s9", "status": "active", "cancel_at_period_end": True, "ends_at": "2026-09-26T07:54:23Z", "product_id": "prod-solo", "customer": cust})["mail"] == "canceled"
    assert sent[-1][3] == "2026-09-26T07:54:23Z"
    assert send("subscription.revoked", {"id": "s9", "status": "canceled", "product_id": "prod-solo", "customer": cust})["mail"] == "ended"
    assert server.q1("SELECT plan FROM accounts WHERE email='mail.test@example.com'")["plan"] == "free"
    subj, text = server.billing_email("canceled", "x@y.z", "solo", "2026-09-26T07:54:23Z")
    assert "26 September 2026" in text and "Solo" in subj
    assert all(ord(ch) < 128 for ch in text)  # plain ASCII mail body


def test_health_json():
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["checks"]["database"] == "ok"


def test_email_html_wrapper():
    h = server._email_html("x", "Hi <you>,\nline two")
    assert "logo-400.png" in h and "&lt;you&gt;" in h and "Hi &lt;you&gt;,<br>line two" in h


def test_signup_mails_key_and_reissues(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "SIGNUP_PER_IP_PER_DAY", 1000)
    monkeypatch.setattr(server, "_send_billing", lambda kind, to, plan, ends_at=None, api_key=None: sent.append((kind, to, api_key)))
    r = c.post("/signup", json={"email": "Fresh.User@example.com"}).json()
    assert r["api_key"].startswith("rv_") and sent[-1][0] == "signup" and sent[-1][2] == r["api_key"]
    assert c.get("/v1/agents", headers={"X-API-Key": r["api_key"]}).status_code == 200
    r2 = c.post("/signup", json={"email": "fresh.user@example.com"})
    assert r2.status_code == 200 and r2.json()["sent"] is True and sent[-1][0] == "key"
    assert c.get("/v1/agents", headers={"X-API-Key": r["api_key"]}).status_code == 401      # old key revoked
    assert c.get("/v1/agents", headers={"X-API-Key": sent[-1][2]}).status_code == 200        # mailed key works


def test_owner_digest_once_per_day(monkeypatch):
    msgs = []
    monkeypatch.setattr(server, "_telegram", lambda tok, chat, text: msgs.append(text) or True)
    with server.tx() as db:
        db.execute("UPDATE accounts SET telegram_token='t', telegram_chat='c' WHERE id=(SELECT MIN(id) FROM accounts)")
    noon = time.time() - (time.time() % 86400) + 12 * 3600
    assert server.owner_digest(noon) is True and "dagstand" in msgs[-1]
    assert server.owner_digest(noon + 60) is False


# ───────────────────────────── verifiable runs ─────────────────────────────
from runvouch import proof as pf


def test_leaf_determinism():
    rec = {"run_id": "r1", "agent": "a", "cost": 0.5, "evidence": {"x": True}, "started": 1.0, "ended": 2.0}
    assert pf.leaf_hash(rec) == pf.leaf_hash(dict(reversed(list(rec.items()))))
    assert pf.leaf_hash(rec) != pf.leaf_hash({**rec, "cost": 0.51})
    assert pf.tool_events_hash([("cat", "abc", 1, 1.5)]) == pf.tool_events_hash([("cat", "abc", True, 1.5)])
    assert pf.tool_events_hash([]) != pf.tool_events_hash([("cat", "abc", 1, 1.5)])


def test_merkle_root_and_path():
    s = pf.sha256
    assert pf.merkle_root([]) == s("")
    assert pf.merkle_root(["a"]) == "a" and pf.merkle_path(["a"], 0) == []
    assert pf.merkle_root(["a", "b"]) == s("ab")
    assert pf.merkle_root(["a", "b", "c"]) == s(s("ab") + s("cc"))
    five = [s(str(i)) for i in range(5)]
    root5 = s(s(s(five[0] + five[1]) + s(five[2] + five[3])) + s(s(five[4] + five[4]) + s(five[4] + five[4])))
    assert pf.merkle_root(five) == root5
    for n in (1, 2, 3, 5):
        leaves = [s(str(i)) for i in range(n)]
        for i in range(n):
            assert pf.apply_path(leaves[i], pf.merkle_path(leaves, i)) == pf.merkle_root(leaves)
    assert pf.apply_path("zz", pf.merkle_path(five, 2)) != root5


def _run(agent, ended_at, **end):
    rid = c.post("/v1/runs/start", json={"agent": agent}, headers=H).json()["run_id"]
    c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": {"q": rid}, "cost": 0.1}, headers=H)
    c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", "evidence": {"file": True}, "meta": {"exit": 0}, **end}, headers=H)
    with server.tx() as db:  # move the run into the wanted UTC day (the API always stamps "now")
        db.execute("UPDATE runs SET started=?, ended=? WHERE id=?", (ended_at - 5, ended_at, rid))
    return rid


def test_chain_two_days_and_proof_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "PROOF_DIR", tmp_path)
    monkeypatch.setattr(server, "OTS_BIN", str(tmp_path / "no-ots"))
    c.post("/v1/agents", json={"name": "prover"}, headers=H)
    d1 = server._day_ts("2026-01-10"); d2 = d1 + 86400
    a = _run("prover", d1 + 100); b = _run("prover", d1 + 200); x = _run("prover", d2 + 50)
    with server.tx() as db:  # started/ended are part of the record, so recompute the leaves after moving the runs

        for rid in (a, b, x):
            r = server.q1("SELECT * FROM runs WHERE id=?", rid); ag = server.q1("SELECT * FROM agents WHERE id=?", r["agent_id"])
            db.execute("UPDATE runs SET leaf_hash=? WHERE id=?", (pf.leaf_hash(server.leaf_record(r, ag)), rid))
    assert server.seal_days(now=d2 + 2 * 86400) == 2
    assert server.seal_days(now=d2 + 2 * 86400) == 0  # idempotent
    day1 = server.q1("SELECT * FROM proof_days WHERE date='2026-01-10'"); day2 = server.q1("SELECT * FROM proof_days WHERE date='2026-01-11'")
    assert day1["prev"] == pf.GENESIS and day1["n_runs"] == 2 and day2["prev"] == day1["chain_hash"] and day2["n_runs"] == 1
    assert day1["chain_hash"] == pf.chain_hash(pf.GENESIS, "2026-01-10", day1["root"])
    assert day1["ots_status"] == "ots missing"
    leaves = [server.q1("SELECT leaf_hash FROM runs WHERE id=?", i)["leaf_hash"] for i in sorted((a, b))]  # day leaves sorted by run_id
    assert day1["root"] == pf.merkle_root(leaves)
    # API proof for run a
    p = c.get(f"/v1/runs/{a}/proof", headers=H).json()
    assert p["sealed"] and p["leaf_hash"] == p["stored_leaf_hash"] and p["root"] == day1["root"] and p["chain_hash"] == day1["chain_hash"]
    assert pf.apply_path(p["leaf_hash"], [tuple(s) for s in p["merkle_path"]]) == day1["root"]
    assert set(p["record"]) == set(pf.LEAF_KEYS) and p["record"]["exit"] == 0 and p["record"]["evidence"] == {"file": True}
    assert "meta" not in p["record"] and "prompt" not in json.dumps(p)
    assert c.get(f"/v1/runs/{a}/proof").status_code == 401
    # public day file and index, no auth
    dj = c.get("/proof/days/2026-01-10.json").json()
    assert dj["root"] == day1["root"] and dj["chain_hash"] == day1["chain_hash"] and {l["run_id"] for l in dj["leaves"]} == {a, b}
    assert c.get("/proof/days/2026-01-10.ots").status_code == 404
    assert c.get("/proof/days/2026-01-12.json").status_code == 404 and c.get("/proof/days/../x.json").status_code in (404, 422)
    idx = c.get("/proof/").json()
    assert [d["date"] for d in idx["days"]] == ["2026-01-11", "2026-01-10"] and idx["days"][1]["ots_status"] == "ots missing"
    # unsealed run: live root, not sealed
    y = _run("prover", time.time())
    p2 = c.get(f"/v1/runs/{y}/proof", headers=H).json()
    assert p2["sealed"] is False and p2["chain_hash"] is None and "note" in p2
    # MCP tool
    m = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "runvouch_run_proof", "arguments": {"run_id": a}}}, headers=H).json()
    assert json.loads(m["result"]["content"][0]["text"])["leaf_hash"] == p["leaf_hash"]
    # standalone verifier: passes on the sealed day, fails on one changed byte
    import subprocess
    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "verify_proof.py")
    pj = tmp_path / "proof.json"; pj.write_text(json.dumps(p))
    dayf = tmp_path / "2026-01-10.json"
    r = subprocess.run([sys.executable, script, str(pj), str(dayf)], capture_output=True, text=True)
    assert r.returncode == 0 and "VERIFIED" in r.stdout, r.stdout
    bad = dict(p); bad["record"] = {**p["record"], "cost": p["record"]["cost"] + 0.001}
    pj.write_text(json.dumps(bad))
    r = subprocess.run([sys.executable, script, str(pj), str(dayf)], capture_output=True, text=True)
    assert r.returncode == 1 and "FAIL leaf" in r.stdout
    # and the CLI verifier, against the public day file served by the app
    from runvouch import cli
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda url, timeout=20: __import__("io").BytesIO(dayf.read_bytes()))
    assert cli.verify_proof(p) is True and cli.verify_proof(bad) is False


# ───────────────────────────── plan features: channels, priority, retention, export, viewer keys ─────────────────────────────
def _acct(plan):
    k = c.post("/admin/accounts", params={"name": "p-" + plan, "plan": plan}, headers={"X-Admin-Token": "adm"}).json()["api_key"]
    return k, {"X-API-Key": k}


def test_slack_channel(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "_webhook", lambda url, payload: sent.append((url, payload)) or True)
    assert c.put("/v1/settings", json={"slack_webhook_url": "https://example.com/not-slack"}, headers=H).status_code == 422
    assert c.put("/v1/settings", json={"slack_webhook_url": "https://hooks.slack.com/services/T0/B0/x"}, headers=H).status_code == 200
    assert c.get("/v1/me", headers=H).json()["channels"]["slack"] is True
    c.post("/v1/agents", json={"name": "slacky"}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "slacky"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "fail", "meta": {"error": "kaput"}}, headers=H)
    aid = [a for a in alerts("FAILED") if a["run_id"] == rid][0]["id"]
    server._deliver(aid)
    slack = [p for u, p in sent if u.startswith("https://hooks.slack.com/")]
    assert slack and "kaput" in slack[0]["text"] and slack[0]["blocks"][0]["type"] == "header"
    assert "FAILED" in slack[0]["blocks"][0]["text"]["text"] and "slacky" in json.dumps(slack[0]["blocks"][1])
    assert "runvouch.com/app" in json.dumps(slack[0]["blocks"][-1])
    assert server.q1("SELECT delivered FROM alerts WHERE id=?", aid)["delivered"] == 1
    with server.tx() as db:
        db.execute("UPDATE accounts SET slack_webhook_url=NULL WHERE id=(SELECT account_id FROM alerts WHERE id=?)", (aid,))


def test_pagerduty_team_only_trigger_and_resolve(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_pagerduty", lambda rk, action, dedup, summary="", severity="error", details=None: calls.append((rk, action, dedup, severity)) or True)
    fk, fh = _acct("free")
    r = c.put("/v1/settings", json={"pagerduty_routing_key": "R" * 32}, headers=fh)
    assert r.status_code == 402 and "Team" in r.json()["detail"]
    assert c.put("/v1/settings", json={"pagerduty_routing_key": "R" * 32}, headers=H).status_code == 200
    assert c.get("/v1/me", headers=H).json()["channels"]["pagerduty"] is True
    c.post("/v1/agents", json={"name": "pager"}, headers=H)
    rid = c.post("/v1/runs/start", json={"agent": "pager"}, headers=H).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "fail"}, headers=H)
    aid = [a for a in alerts("FAILED") if a["run_id"] == rid][0]["id"]
    server._deliver(aid)
    assert calls[-1] == ("R" * 32, "trigger", "runvouch:pager:FAILED", "error")
    # DRIFT is not a paging kind
    n = len(calls)
    with server.tx() as db:
        db.execute("INSERT INTO alerts(account_id, agent_id, run_id, ts, kind, message) VALUES((SELECT account_id FROM alerts WHERE id=?), (SELECT agent_id FROM alerts WHERE id=?), ?, ?, 'DRIFT', 'x')", (aid, aid, rid, time.time()))
    server._deliver(server.q1("SELECT MAX(id) m FROM alerts")["m"])
    assert len(calls) == n
    # ack resolves the same dedup key (background thread)
    c.post(f"/v1/alerts/{aid}/ack", headers=H)
    for _ in range(50):
        if any(x[1] == "resolve" for x in calls):
            break
        time.sleep(0.02)
    assert ("R" * 32, "resolve", "runvouch:pager:FAILED", "error") in calls
    # test-alert exercises PagerDuty like the other channels
    c.post("/v1/settings/test-alert", headers=H)
    tid = server.q1("SELECT id FROM alerts WHERE kind='TEST' ORDER BY id DESC LIMIT 1")["id"]
    server._deliver(tid)
    assert calls[-1][1] == "trigger" and calls[-1][2].endswith(":TEST") and calls[-1][3] == "info"
    with server.tx() as db:
        db.execute("UPDATE accounts SET pagerduty_routing_key=NULL WHERE api_key=?", (server.key_hash(KEY),))


def test_pagerduty_payload_shape(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "_webhook", lambda url, payload: sent.append((url, payload)) or True)
    assert server._pagerduty("rk", "trigger", "runvouch:a:MISSED", "sum", "error", {"agent": "a"}) is True
    url, p = sent[-1]
    assert url == server.PD_URL and p["event_action"] == "trigger" and p["dedup_key"] == "runvouch:a:MISSED" and p["payload"]["severity"] == "error"
    server._pagerduty("rk", "resolve", "runvouch:a:MISSED")
    assert sent[-1][1] == {"routing_key": "rk", "event_action": "resolve", "dedup_key": "runvouch:a:MISSED"}


def test_priority_alerts_skip_cooldown_on_paid_plans():
    def two_failures(h, name):
        c.post("/v1/agents", json={"name": name}, headers=h)
        ids = []
        for _ in range(2):
            rid = c.post("/v1/runs/start", json={"agent": name}, headers=h).json()["run_id"]
            c.post("/v1/runs/end", json={"run_id": rid, "status": "fail"}, headers=h)
            ids.append(server.q1("SELECT delivered FROM alerts WHERE run_id=? AND kind='FAILED'", rid)["delivered"])
        return ids
    fk, fh = _acct("free")
    assert two_failures(fh, "flaky") == [0, -1]        # free: second FAILED inside the 10-minute cooldown is stored, not sent
    sk, sh = _acct("solo")
    assert two_failures(sh, "flaky") == [0, 0]         # paid: every MISSED / FAILED is queued for delivery immediately


def test_retention_purge_keeps_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "PROOF_DIR", tmp_path)
    monkeypatch.setattr(server, "OTS_BIN", str(tmp_path / "no-ots"))
    fk, fh = _acct("free")
    c.post("/v1/agents", json={"name": "old"}, headers=fh)
    now = time.time()
    day_old = server._day_of(now - 20 * 86400)
    t_old = server._day_ts(day_old) + 3600
    def run(ended_at, **end):
        rid = c.post("/v1/runs/start", json={"agent": "old"}, headers=fh).json()["run_id"]
        c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": {"q": rid}}, headers=fh)
        c.post("/v1/runs/end", json={"run_id": rid, "status": "ok", **end}, headers=fh)
        with server.tx() as db:
            db.execute("UPDATE runs SET started=?, ended=? WHERE id=?", (ended_at - 5, ended_at, rid))
            r = server.q1("SELECT * FROM runs WHERE id=?", rid); ag = server.q1("SELECT * FROM agents WHERE id=?", r["agent_id"])
            db.execute("UPDATE runs SET leaf_hash=? WHERE id=?", (pf.leaf_hash(server.leaf_record(r, ag)), rid))
        return rid
    a, b = run(t_old), run(t_old + 60)
    fresh = run(now - 3600)
    team_old = _run("prover", t_old + 120)  # same day, team account: 90-day window, must survive
    assert server.seal_days(now=now) >= 1
    day = server.q1("SELECT * FROM proof_days WHERE date=?", day_old)
    before = c.get(f"/v1/runs/{a}/proof", headers=fh).json()
    assert before["sealed"] and before["root"] == day["root"]
    # an old acked alert and an old open one
    agent_id = server.q1("SELECT id FROM agents WHERE name='old'")["id"]; acc_id = server.q1("SELECT account_id FROM agents WHERE id=?", agent_id)["account_id"]
    with server.tx() as db:
        db.execute("INSERT INTO alerts(account_id, agent_id, ts, kind, message, acked) VALUES(?,?,?,?,?,1)", (acc_id, agent_id, t_old, "FAILED", "old acked"))
        db.execute("INSERT INTO alerts(account_id, agent_id, ts, kind, message, acked) VALUES(?,?,?,?,?,0)", (acc_id, agent_id, t_old, "MISSED", "old open"))
    out = server.purge_once(now)
    assert out["runs"] >= 2 and out["tool_events"] >= 2 and out["alerts"] >= 1
    assert server.q1("SELECT id FROM runs WHERE id=?", a) is None and server.q1("SELECT id FROM runs WHERE id=?", fresh) is not None
    assert server.q1("SELECT COUNT(*) n FROM tool_events WHERE run_id=?", a)["n"] == 0
    assert server.q1("SELECT message FROM alerts WHERE message='old acked'") is None and server.q1("SELECT message FROM alerts WHERE message='old open'") is not None
    lv = server.q1("SELECT * FROM run_leaves WHERE id=?", a)
    assert lv and lv["leaf_hash"] == before["leaf_hash"] and lv["ended"] == t_old
    # the team account (90 days) keeps its 20-day-old run
    assert server.q1("SELECT id FROM runs WHERE id=?", team_old) is not None
    # proof after purge: same leaf, same path, same sealed root; day file unchanged
    after = c.get(f"/v1/runs/{a}/proof", headers=fh).json()
    assert after["purged"] is True and after["leaf_hash"] == before["leaf_hash"] and after["root"] == day["root"] and after["merkle_path"] == before["merkle_path"]
    assert pf.apply_path(after["leaf_hash"], [tuple(s) for s in after["merkle_path"]]) == day["root"]
    assert after["record"] is None and after["chain_hash"] == day["chain_hash"]
    dj = c.get(f"/proof/days/{day_old}.json").json()
    assert {l["run_id"] for l in dj["leaves"]} == {a, b, team_old} and dj["root"] == day["root"]
    assert {r["id"] for r in server._day_leaves(day_old)} == {a, b, team_old}
    # a day sealed after the purge still sees the moved leaves
    with server.tx() as db:
        db.execute("DELETE FROM proof_days")
    assert server.seal_days(now=now) >= 1
    assert server.q1("SELECT root FROM proof_days WHERE date=?", day_old)["root"] == day["root"]
    # second purge on the same day is a no-op; the daily wrapper runs once per UTC day
    assert server.purge_once(now)["runs"] == 0
    server._last_purge_day = ""
    assert server.purge_daily(now) is not None and server.purge_daily(now) is None


def test_export_team_only():
    fk, fh = _acct("free")
    r = c.get("/v1/export", params={"from": "2026-01-01", "to": "2026-12-31"}, headers=fh)
    assert r.status_code == 402 and "API export" in r.json()["detail"]
    assert c.get("/v1/export", params={"from": "2026-01-10", "to": "2026-01-09"}, headers=H).status_code == 422
    assert c.get("/v1/export", params={"from": "nope", "to": "2026-01-09"}, headers=H).status_code == 422
    assert c.get("/v1/export", params={"from": "2026-01-10", "to": "2026-01-11", "format": "xml"}, headers=H).status_code == 422
    c.post("/v1/agents", json={"name": "exp"}, headers=H)
    day = server._day_of(time.time() - 10 * 86400); t0 = server._day_ts(day)
    ids = sorted([_run("exp", t0 + 100), _run("exp", t0 + 200), _run("exp", t0 + 86400 + 50)])
    r = c.get("/v1/export", params={"from": day, "to": day, "format": "csv"}, headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "agent,run_id,started,ended,status,cost,tokens,tool_calls,evidence_ok,leaf_hash" and len(lines) == 3 and lines[1].startswith("exp,")
    j = c.get("/v1/export", params={"from": day, "to": server._day_of(t0 + 86400)}, headers=H).json()
    assert [x["run_id"] for x in j if x["agent"] == "exp"] == sorted(ids, key=lambda i: server.q1("SELECT started FROM runs WHERE id=?", i)["started"])
    assert set(j[0]) == set(server.EXPORT_COLS) and len(j[0]["leaf_hash"]) == 64 and j[0]["evidence_ok"] == 1
    assert c.get("/v1/export", params={"from": "2020-01-01", "to": "2020-01-02"}, headers=H).json() == []


def test_viewer_keys_read_only():
    fk, fh = _acct("free")
    assert c.post("/v1/me/viewer-keys", json={"name": "wall"}, headers=fh).status_code == 402
    r = c.post("/v1/me/viewer-keys", json={"name": "wall"}, headers=H).json()
    vk = r["viewer_key"]; vh = {"X-API-Key": vk}
    assert vk.startswith("rvv_") and r["id"]
    assert [k["name"] for k in c.get("/v1/me/viewer-keys", headers=H).json()] == ["wall"]
    me = c.get("/v1/me", headers=vh).json()
    assert me["viewer"] is True and me["plan"] == "team"
    assert c.get("/v1/agents", headers=vh).status_code == 200
    assert c.get("/v1/agents/prover/runs", headers=vh).status_code == 200
    assert c.get("/v1/alerts", headers=vh).status_code == 200
    assert c.get("/v1/export", params={"from": "2026-01-10", "to": "2026-01-11"}, headers=vh).status_code == 200  # read-only GET is allowed
    assert c.post("/v1/agents", json={"name": "nope"}, headers=vh).status_code == 403
    assert c.post("/v1/runs/start", json={"agent": "prover"}, headers=vh).status_code == 403
    assert c.put("/v1/settings", json={"alert_email": "x@y.z"}, headers=vh).status_code == 403
    assert c.post("/v1/me/viewer-keys", json={"name": "x"}, headers=vh).status_code == 403
    assert c.delete("/v1/agents/prover", headers=vh).status_code == 403
    aid = alerts()[0]["id"]
    assert c.post(f"/v1/alerts/{aid}/ack", headers=vh).status_code == 200
    m = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "runvouch_run_start", "arguments": {"agent": "prover"}}}, headers=vh).json()
    assert m["result"].get("isError") and "read-only" in m["result"]["content"][0]["text"]
    m = c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "runvouch_status", "arguments": {}}}, headers=vh).json()
    assert not m["result"].get("isError")
    assert c.get("/v1/me/viewer-keys", headers=H).json()[0]["last_used"] is not None
    assert c.delete(f"/v1/me/viewer-keys/{r['id']}", headers=H).status_code == 200
    assert c.get("/v1/agents", headers=vh).status_code == 401
    assert c.delete(f"/v1/me/viewer-keys/{r['id']}", headers=H).status_code == 404
    # a viewer key dies with the plan
    r2 = c.post("/v1/me/viewer-keys", headers=H).json()
    with server.tx() as db:
        db.execute("UPDATE accounts SET plan='solo' WHERE api_key=?", (server.key_hash(KEY),))
    assert c.get("/v1/agents", headers={"X-API-Key": r2["viewer_key"]}).status_code == 401
    with server.tx() as db:
        db.execute("UPDATE accounts SET plan='team' WHERE api_key=?", (server.key_hash(KEY),))


def test_remediator_retry_failure_is_stored_but_not_sent():
    sk, sh = _acct("solo")
    c.post("/v1/agents", json={"name": "retry-job"}, headers=sh)
    rid = c.post("/v1/runs/start", json={"agent": "retry-job", "source": "remediator"}, headers=sh).json()["run_id"]
    c.post("/v1/runs/end", json={"run_id": rid, "status": "fail"}, headers=sh)
    row = server.q1("SELECT delivered FROM alerts WHERE run_id=? AND kind='FAILED'", rid)
    assert row["delivered"] == -1  # the remediator reports the outcome itself; the alert is only on the dashboard


def test_status_json_is_public_and_counts_heartbeats():
    now = time.time()
    for m in range(0, 30):
        if m in (10, 11, 12, 13, 14, 15, 16):
            continue  # a 7-minute hole: one incident
        server.record_heartbeat(now - (29 - m) * 60)
    r = c.get("/status.json")  # no key needed
    assert r.status_code == 200
    j = r.json()
    assert j["measured_since"] and "windows" in j and "24h" in j["windows"]
    assert 70 < j["windows"]["24h"]["detectors"] < 100
    assert any(i["minutes"] >= 6 for i in j["incidents"])
    assert "accounts" not in json.dumps(j)


def test_public_fleet_only_shows_opted_in_agents():
    sk, sh = _acct("solo")
    for name in ("nightly-build", "secret-job"):
        c.post("/v1/agents", json={"name": name, "cadence_s": 86400}, headers=sh)
        rid = c.post("/v1/runs/start", json={"agent": name}, headers=sh).json()["run_id"]
        c.post("/v1/runs/end", json={"run_id": rid, "status": "ok"}, headers=sh)
    acc = server.q1("SELECT id FROM agents WHERE name='nightly-build' ORDER BY id DESC LIMIT 1")
    with server.tx() as db:
        db.execute("INSERT OR REPLACE INTO public_fleets(slug, account_id, title) VALUES('demo', (SELECT account_id FROM agents WHERE id=?), 'Demo')", (acc["id"],))
        db.execute("INSERT OR REPLACE INTO public_agents(agent_id, label, kind) VALUES(?, 'Nightly build', 'pipeline')", (acc["id"],))
    j = c.get("/public/fleet/demo.json").json()  # no key
    names = [a["name"] for a in j["agents"]]
    assert names == ["nightly-build"] and "secret-job" not in json.dumps(j)
    assert j["agents"][0]["last_run"]["status"] == "ok" and j["agents"][0]["rates"]["7d"]["ok"] == 1
    assert c.get("/public/fleet/nope.json").status_code == 404


# ───────────────────────────── Slack: Add to Slack (OAuth v2, incoming-webhook) ─────────────────────────────
def test_slack_install_unconfigured_is_503(monkeypatch):
    monkeypatch.setattr(server, "SLACK_CLIENT_ID", "")
    monkeypatch.setattr(server, "SLACK_CLIENT_SECRET", "")
    r = c.get("/integrations/slack/install", params={"token": KEY}, follow_redirects=False)
    assert r.status_code == 503 and "Slack app not configured" in r.json()["detail"]
    r = c.get("/integrations/slack/callback", params={"code": "x", "state": "y"}, follow_redirects=False)
    assert r.status_code == 503
    assert c.get("/integrations/slack/status").json()["configured"] is False


def test_slack_install_redirects_without_api_key_in_url(monkeypatch):
    monkeypatch.setattr(server, "SLACK_CLIENT_ID", "cid123")
    monkeypatch.setattr(server, "SLACK_CLIENT_SECRET", "csecret")
    assert c.get("/integrations/slack/install", follow_redirects=False).status_code == 401
    assert c.get("/integrations/slack/install", params={"token": "rv_nope"}, follow_redirects=False).status_code == 401
    r = c.get("/integrations/slack/install", params={"token": KEY}, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://slack.com/oauth/v2/authorize?")
    qs = dict(x.split("=", 1) for x in loc.split("?", 1)[1].split("&"))
    assert qs["client_id"] == "cid123" and qs["scope"] == "incoming-webhook"
    assert KEY not in loc and server.key_hash(KEY) not in loc
    acc_id = server.q1("SELECT id FROM accounts WHERE api_key=?", server.key_hash(KEY))["id"]
    assert server.slack_state_verify(qs["state"]) == acc_id
    assert server.slack_state_verify(qs["state"], now=time.time() + 601) is None, "state must expire"
    assert server.slack_state_verify(qs["state"][:-1] + ("0" if qs["state"][-1] != "0" else "1")) is None, "tampered state"


def test_slack_callback_stores_webhook_and_posts_test(monkeypatch):
    monkeypatch.setattr(server, "SLACK_CLIENT_ID", "cid123")
    monkeypatch.setattr(server, "SLACK_CLIENT_SECRET", "csecret")
    sent, asked = [], []
    monkeypatch.setattr(server, "_webhook", lambda url, payload: sent.append((url, payload)) or True)
    monkeypatch.setattr(server, "_slack_oauth_exchange", lambda code: asked.append(code) or
                        {"ok": True, "incoming_webhook": {"url": "https://hooks.slack.com/services/T1/B1/oauth", "channel": "#agents"}})
    acc_id = server.q1("SELECT id FROM accounts WHERE api_key=?", server.key_hash(KEY))["id"]
    state = server.slack_state_sign(acc_id)
    r = c.get("/integrations/slack/callback", params={"code": "c0de", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/integrations/slack/installed?channel=%23agents")
    assert asked == ["c0de"]
    assert server.q1("SELECT slack_webhook_url FROM accounts WHERE id=?", acc_id)["slack_webhook_url"] == "https://hooks.slack.com/services/T1/B1/oauth"
    assert sent and sent[0][0] == "https://hooks.slack.com/services/T1/B1/oauth" and "CONNECTED" in sent[0][1]["blocks"][0]["text"]["text"]
    # bad state and Slack-side errors never crash and never store anything
    assert c.get("/integrations/slack/callback", params={"code": "c", "state": "1.2.3"}, follow_redirects=False).status_code == 400
    monkeypatch.setattr(server, "_slack_oauth_exchange", lambda code: {"ok": False, "error": "invalid_code"})
    r = c.get("/integrations/slack/callback", params={"code": "bad", "state": server.slack_state_sign(acc_id)}, follow_redirects=False)
    assert r.status_code == 302 and "error=invalid_code" in r.headers["location"]
    r = c.get("/integrations/slack/callback", params={"error": "access_denied", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and "error=access_denied" in r.headers["location"]
    assert server.q1("SELECT slack_webhook_url FROM accounts WHERE id=?", acc_id)["slack_webhook_url"] == "https://hooks.slack.com/services/T1/B1/oauth"
    with server.tx() as db:
        db.execute("UPDATE accounts SET slack_webhook_url=NULL WHERE id=?", (acc_id,))


# ───────────────────────────── tenant isolation: a run belongs to one account ─────────────────────────────
def test_runs_are_scoped_to_the_owning_account():
    """Knowing a run_id must not be enough: run ids travel in exports, webhooks and the public proof files."""
    ak, ah = _acct("team")          # A, the victim
    bk, bh = _acct("team")          # B, any other valid key
    c.post("/v1/agents", json={"name": "nachtrun", "cap_run_cost": 1.0}, headers=ah)
    c.post("/v1/agents", json={"name": "eigen-job"}, headers=bh)
    rid = c.post("/v1/runs/start", json={"agent": "nachtrun"}, headers=ah).json()["run_id"]

    # B cannot write to A's run through any of the three run endpoints
    assert c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": 1, "cost": 99.0}, headers=bh).status_code == 404
    assert c.post("/v1/runs/heartbeat", params={"run_id": rid}, headers=bh).status_code == 404
    assert c.post("/v1/runs/end", json={"run_id": rid, "status": "fail", "meta": {"error": "door B"}}, headers=bh).status_code == 404

    run = server.q1("SELECT * FROM runs WHERE id=?", rid)
    assert run["ended"] is None and run["status"] == "running" and run["cost"] == 0 and run["tool_calls"] == 0
    assert server.q1("SELECT COUNT(*) n FROM tool_events WHERE run_id=?", rid)["n"] == 0
    assert c.get("/v1/alerts", headers=ah).json() == [], "no alert of A may be raised by another account"

    # a run_id that does not exist at all is a 404 too, not a silent ok
    assert c.post("/v1/runs/heartbeat", params={"run_id": "bestaat-niet"}, headers=ah).status_code == 404

    # A keeps working on its own run
    assert c.post("/v1/runs/tool", json={"run_id": rid, "tool": "llm", "input": 1, "cost": 0.1}, headers=ah).status_code == 200
    assert c.post("/v1/runs/heartbeat", params={"run_id": rid}, headers=ah).status_code == 200
    assert c.post("/v1/runs/end", json={"run_id": rid, "status": "ok"}, headers=ah).status_code == 200


def test_two_accounts_can_use_the_same_run_id_without_touching_each_other():
    """Run ids live per account. A shared name like "nightly-2026-09-06" is not a first-come resource,
    so B claiming it can neither overwrite A's run nor lock A out of its own id."""
    ak, ah = _acct("team")
    bk, bh = _acct("team")
    c.post("/v1/agents", json={"name": "evening-run"}, headers=ah)
    c.post("/v1/agents", json={"name": "evening-run"}, headers=bh)   # same agent name, different account
    a_agent = server.q1("SELECT id FROM agents WHERE name='evening-run' AND account_id=(SELECT account_id FROM agents WHERE id=(SELECT MIN(id) FROM agents WHERE name='evening-run'))")["id"]
    shared = "nightly-2026-09-06"
    assert c.post("/v1/runs/start", json={"agent": "evening-run", "run_id": shared}, headers=ah).json()["run_id"] == shared
    assert c.post("/v1/runs/start", json={"agent": "evening-run", "run_id": shared}, headers=bh).json()["run_id"] == shared
    rows = server.qa("SELECT agent_id FROM runs WHERE id=?", shared)
    assert len(rows) == 2 and a_agent in [r["agent_id"] for r in rows], "both accounts keep their own row"

    # what B does to its own run stays with B
    c.post("/v1/runs/tool", json={"run_id": shared, "tool": "llm", "input": {"q": 1}, "cost": 5.0}, headers=bh)
    c.post("/v1/runs/end", json={"run_id": shared, "status": "fail", "meta": {"error": "kapot bij B"}}, headers=bh)
    a_run = c.get("/v1/agents/evening-run/runs", headers=ah).json()
    b_run = c.get("/v1/agents/evening-run/runs", headers=bh).json()
    assert [x["id"] for x in a_run] == [shared] and [x["id"] for x in b_run] == [shared]
    assert a_run[0]["status"] == "running" and a_run[0]["ended"] is None and a_run[0]["cost"] == 0
    assert a_run[0]["tool_calls"] == 0, "tool events of another account must not count towards this run"
    assert b_run[0]["status"] == "fail" and b_run[0]["cost"] == 5.0
    assert c.get("/v1/alerts", headers=ah).json() == []
    assert [x["kind"] for x in c.get("/v1/alerts", headers=bh).json()] == ["FAILED"]

    # A finishes its own run under the same id, and gets its own proof
    assert c.post("/v1/runs/end", json={"run_id": shared, "status": "ok"}, headers=ah).status_code == 200
    pa = c.get(f"/v1/runs/{shared}/proof", headers=ah).json()
    pb = c.get(f"/v1/runs/{shared}/proof", headers=bh).json()
    assert pa["leaf_hash"] != pb["leaf_hash"] and pa["record"]["status"] == "ok" and pb["record"]["status"] == "fail"
    assert pa["record"]["tool_calls"] == 0 and pb["record"]["tool_calls"] == 1
    assert pa["leaf_hash"] == pa["stored_leaf_hash"] and pb["leaf_hash"] == pb["stored_leaf_hash"]

    # restarting your own run id stays allowed (a retry of the same job reuses it)
    assert c.post("/v1/runs/start", json={"agent": "evening-run", "run_id": shared}, headers=ah).status_code == 200
    assert server.q1("SELECT COUNT(*) n FROM runs WHERE id=?", shared)["n"] == 2


def test_run_start_is_atomic_under_concurrency():
    """The ownership check and the insert must be one step. With a lookup first and an INSERT OR REPLACE
    after, two simultaneous starts of the same run_id both see a free id and the second takes the first
    one's row, agent_id included."""
    from concurrent.futures import ThreadPoolExecutor
    ak, ah = _acct("team")
    bk, bh = _acct("team")
    c.post("/v1/agents", json={"name": "race-a"}, headers=ah)
    c.post("/v1/agents", json={"name": "race-b"}, headers=bh)
    a_agent = server.q1("SELECT id FROM agents WHERE name='race-a'")["id"]
    b_agent = server.q1("SELECT id FROM agents WHERE name='race-b'")["id"]
    for i in range(40):
        rid = f"nightly-race-{i}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(lambda: c.post("/v1/runs/start", json={"agent": "race-a", "run_id": rid}, headers=ah))
            fb = pool.submit(lambda: c.post("/v1/runs/start", json={"agent": "race-b", "run_id": rid}, headers=bh))
            ra, rb = fa.result(), fb.result()
        assert (ra.status_code, rb.status_code) == (200, 200), f"round {i}: both accounts own this run_id"
        got = sorted(r["agent_id"] for r in server.qa("SELECT agent_id FROM runs WHERE id=?", rid))
        assert got == sorted([a_agent, b_agent]), f"round {i}: a run was taken over, rows {got}"


def test_mcp_run_tools_are_scoped_to_the_account():
    ak, ah = _acct("team")
    bk, bh = _acct("team")
    c.post("/v1/agents", json={"name": "mcp-job"}, headers=ah)
    c.post("/v1/agents", json={"name": "mcp-job"}, headers=bh)
    rid = c.post("/v1/runs/start", json={"agent": "mcp-job"}, headers=ah).json()["run_id"]

    def call(tool, args, headers):
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                 "params": {"name": tool, "arguments": args}}, headers=headers).json()
        return r["result"]

    out = call("runvouch_run_end", {"run_id": rid, "status": "fail"}, bh)
    assert out.get("isError") and "404" in out["content"][0]["text"]
    out = call("runvouch_run_proof", {"run_id": rid}, bh)
    assert out.get("isError") and "404" in out["content"][0]["text"]
    assert server.q1("SELECT status FROM runs WHERE id=?", rid)["status"] == "running"

    # B does the same thing on its own run and that works
    own = call("runvouch_run_start", {"agent": "mcp-job"}, bh)
    own_id = json.loads(own["content"][0]["text"])["run_id"]
    assert not call("runvouch_run_end", {"run_id": own_id, "status": "ok"}, bh).get("isError")
    assert not call("runvouch_run_proof", {"run_id": own_id}, bh).get("isError")
    assert not call("runvouch_run_end", {"run_id": rid, "status": "ok"}, ah).get("isError")


def test_a_sealed_day_keeps_both_runs_that_share_a_run_id(monkeypatch, tmp_path):
    """Namespacing run ids means one day can hold the same id twice. The day root must cover both leaves
    and each account must get the path of its own leaf, not the first one with a matching id."""
    monkeypatch.setattr(server, "PROOF_DIR", tmp_path)
    monkeypatch.setattr(server, "OTS_BIN", str(tmp_path / "no-ots"))
    ak, ah = _acct("team")
    bk, bh = _acct("team")
    c.post("/v1/agents", json={"name": "sealed-job"}, headers=ah)
    c.post("/v1/agents", json={"name": "sealed-job"}, headers=bh)
    shared = "nightly-2026-08-01"
    now = time.time()
    first = server.q1("SELECT MIN(date) d FROM proof_days")["d"]          # the suite seals every day from
    day = server._day_of(server._day_ts(first) - 86400) if first else server._day_of(now - 40 * 86400)
    assert not server._day_leaves(day), "this test needs a day of its own to seal"
    t_old = server._day_ts(day) + 3600
    for h, size in ((ah, 100), (bh, 200)):
        c.post("/v1/runs/start", json={"agent": "sealed-job", "run_id": shared}, headers=h)
        c.post("/v1/runs/end", json={"run_id": shared, "status": "ok", "output_bytes": size}, headers=h)
    with server.tx() as db:  # move both into a day that is over, then refresh the leaves the way run_end does
        db.execute("UPDATE runs SET started=?, ended=? WHERE id=?", (t_old - 5, t_old, shared))
    for r in server.qa("SELECT * FROM runs WHERE id=?", shared):
        ag = server.q1("SELECT * FROM agents WHERE id=?", r["agent_id"])
        with server.tx() as db:
            db.execute("UPDATE runs SET leaf_hash=? WHERE id=? AND account_id=?",
                       (pf.leaf_hash(server.leaf_record(r, ag)), r["id"], r["account_id"]))
    d = server.seal_day(day)
    assert d["n_runs"] == 2

    pa = c.get(f"/v1/runs/{shared}/proof", headers=ah).json()
    pb = c.get(f"/v1/runs/{shared}/proof", headers=bh).json()
    assert pa["leaf_hash"] != pb["leaf_hash"], "same id, different account, different leaf"
    for p in (pa, pb):
        assert p["sealed"] and p["root"] == d["root"]
        assert pf.apply_path(p["leaf_hash"], [tuple(x) for x in p["merkle_path"]]) == d["root"]
    dj = json.loads((tmp_path / f"{day}.json").read_text())
    assert sorted(l["leaf"] for l in dj["leaves"]) == sorted([pa["leaf_hash"], pb["leaf_hash"]])


def test_undelivered_alert_is_retried_and_gives_up():
    """Een mislukte bezorging moet terugkomen, met backoff en een bovengrens.

    Waarom deze test bestaat: op 4 en 6 september 2026 bleven twee DRIFT-alerts op
    delivered=0 staan zonder tweede poging, en de statuspagina meldde ruim drie uur
    falende bezorging zonder dat iemand bericht kreeg.
    """
    acc = server.q1("SELECT id FROM accounts ORDER BY id LIMIT 1")["id"]
    ag = server.q1("SELECT id FROM agents ORDER BY id LIMIT 1")["id"]
    with server.tx() as db:
        cur = db.execute("INSERT INTO alerts(account_id, agent_id, run_id, ts, kind, message, delivered, attempts, next_try)"
                         " VALUES(?,?,?,?,?,?,0,0,0)", (acc, ag, None, time.time(), "FAILED", "bezorging faalde"))
        aid = cur.lastrowid

    geleverd = []
    server._deliver_q.put = lambda x: geleverd.append(x)   # de echte bezorging niet aanroepen
    try:
        assert server.retry_undelivered() >= 1
        assert aid in geleverd, "de onbezorgde alert werd niet opnieuw aangeboden"
        # meteen daarna niet opnieuw: next_try staat vooruit
        geleverd.clear()
        server.retry_undelivered()
        assert aid not in geleverd, "dezelfde alert werd binnen de backoff nog een keer aangeboden"

        # na genoeg pogingen geeft hij het op in plaats van eeuwig te blijven proberen
        with server.tx() as db:
            db.execute("UPDATE alerts SET attempts=?, next_try=0 WHERE id=?", (server.RETRY_MAX_ATTEMPTS, aid))
        geleverd.clear()
        server.retry_undelivered()
        assert aid not in geleverd, "alert werd na de bovengrens nog steeds opnieuw geprobeerd"

        # en een alert in de afkoelperiode (delivered=-1) blijft er buiten
        with server.tx() as db:
            db.execute("UPDATE alerts SET delivered=-1, attempts=0, next_try=0 WHERE id=?", (aid,))
        geleverd.clear()
        server.retry_undelivered()
        assert aid not in geleverd, "een afgekoelde alert hoort niet verstuurd te worden"
    finally:
        del server._deliver_q.put


def _vul_heartbeats(paren):
    """paren: lijst van (minuut_offset_vanaf_nu, alerts_ok). Negatieve offsets liggen in het verleden."""
    cur = int(time.time() // 60)
    with server.tx() as db:
        db.execute("DELETE FROM heartbeats")
        for offset, ok in paren:
            db.execute("INSERT OR REPLACE INTO heartbeats(minute, alerts_ok) VALUES(?,?)", (cur + offset, ok))
    return cur


def _alert_incidenten():
    return [i for i in server.status_summary()["incidents"] if i["component"] == "alerts"]


def test_status_lists_alert_delivery_outage():
    """96 procent bezorging naast 'No outages' is een tegenspraak; die mag niet terugkomen."""
    _vul_heartbeats([(-200 + i, 0 if 20 <= i < 80 else 1) for i in range(120)])
    inc = _alert_incidenten()
    assert inc, "een aaneengesloten gat in de bezorging levert geen incident op"
    assert max(i["minutes"] for i in inc) >= 55
    assert all(i["start"].endswith("Z") for i in inc)


def test_short_delivery_outage_is_not_swallowed():
    """De oude drempel verstopte reeksen van drie minuten of korter, en juist die maakten
    het beeld dat de koperswandeling afkeurde: een laag percentage naast 'No outages'."""
    _vul_heartbeats([(-100 + i, 0 if i in (10, 11, 12) else 1) for i in range(100)] )
    inc = _alert_incidenten()
    assert len(inc) == 1 and inc[0]["minutes"] == 3, f"korte storing niet gemeld: {inc}"
    # en een losse minuut ook niet wegmoffelen, want hij zit wel in het percentage
    _vul_heartbeats([(-100 + i, 0 if i == 40 else 1) for i in range(100)])
    assert [i["minutes"] for i in _alert_incidenten()] == [1]


def test_ongoing_delivery_outage_is_flagged():
    """Loopt de storing nu nog, dan moet de pagina dat zeggen en niet 'hersteld' suggereren."""
    _vul_heartbeats([(-40 + i, 0 if i >= 35 else 1) for i in range(41)])
    inc = _alert_incidenten()
    assert inc and inc[-1].get("ongoing"), f"lopende storing niet als ongoing gemeld: {inc}"


def test_missing_heartbeat_splits_delivery_outage():
    """Een ontbrekende minuut breekt de reeks: over die minuut is geen meting, dus die telt
    in geen van beide helften mee. Dat mag, maar de twee helften moeten wel gemeld worden."""
    paren = [(-100 + i, 1) for i in range(100)]
    paren = [(o, 0 if 10 <= o + 100 <= 19 else ok) for o, ok in paren]
    paren = [(o, ok) for o, ok in paren if o + 100 != 15]      # minuut 15 ontbreekt
    _vul_heartbeats(paren)
    inc = _alert_incidenten()
    assert len(inc) == 2, f"verwacht twee helften, kreeg {inc}"
    assert sum(i["minutes"] for i in inc) == 9, f"gemeten minuten kloppen niet: {inc}"


def test_status_reports_total_when_list_is_capped():
    """Twintig regels op de pagina mogen niet lezen als 'dit was alles'."""
    paren = []
    for i in range(300):
        paren.append((-400 + i, 0 if i % 10 == 0 else 1))
    _vul_heartbeats(paren)
    s = server.status_summary()
    assert s["incidents_total"] >= 25
    assert len(s["incidents"]) <= 20
    assert s["incidents_total"] > len(s["incidents"])
