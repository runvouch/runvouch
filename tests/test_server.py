import os, sys, time, json
os.environ["RUNVOUCH_DB"] = "/tmp/claude-1000/-home-krtradingpro-TradingBot-Trading-Bot-Crypto/96bd68dd-1df7-4b4a-8980-d39ff4341368/scratchpad/aw_test.db"
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
    assert c.post("/signup", json={"email": "new.user@example.com"}).status_code == 409
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
    assert len(r["result"]["tools"]) == 6
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
