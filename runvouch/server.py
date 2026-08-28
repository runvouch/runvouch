"""
RunVouch: reliability + cost watchdog for autonomous / scheduled AI agents.

Single-file FastAPI service. SQLite storage. No external deps beyond fastapi/uvicorn.

Core model
----------
account  : API key holder (multi-tenant via X-API-Key)
agent    : a named scheduled job ("nightly-report"), with expected cadence + budgets
run      : one execution: start -> (tool events) -> end{status, evidence, cost}
alert    : something the human must see (missed, failed, no-evidence, budget, storm, drift)

Detectors (the part Healthchecks/Cronitor don't have)
-----------------------------------------------------
MISSED       expected run did not start within cadence + grace
FAILED       run ended with status != ok
NO_EVIDENCE  run said "ok" but required evidence assertions were not satisfied ("green != done")
BUDGET_RUN   cost/tokens of one run exceeded the per-run cap
BUDGET_DAY   cumulative cost today exceeded the daily cap
RETRY_STORM  same tool+input hash repeated >= N times within one run
DRIFT        output size / duration deviates > k*MAD from trailing 7-run baseline
STALLED      run started but no end/heartbeat for > max_runtime
"""
from __future__ import annotations

import calendar
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
from datetime import datetime
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from runvouch import proof as _pf

DB_PATH = Path(os.getenv("RUNVOUCH_DB", Path(__file__).resolve().parent.parent / "data" / "runvouch.db"))
ADMIN_TOKEN = os.getenv("RUNVOUCH_ADMIN_TOKEN", "")
PUBLIC_URL = os.getenv("RUNVOUCH_PUBLIC_URL", "http://localhost:8787")
STORM_THRESHOLD = int(os.getenv("RUNVOUCH_STORM_THRESHOLD", "8"))
DRIFT_K = float(os.getenv("RUNVOUCH_DRIFT_K", "4.0"))
SWEEP_SECONDS = int(os.getenv("RUNVOUCH_SWEEP_SECONDS", "30"))
LS_WEBHOOK_SECRET = os.getenv("LS_WEBHOOK_SECRET", "")
LS_VARIANT_PLANS = {k: v for k, v in (x.split(":") for x in os.getenv("LS_VARIANT_PLANS", "").split(",") if ":" in x)}  # "123:solo,456:team"
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
POLAR_WEBHOOK_SECRET = os.getenv("POLAR_WEBHOOK_SECRET", "")
POLAR_PRODUCT_PLANS = {k: v for k, v in (x.split(":") for x in os.getenv("POLAR_PRODUCT_PLANS", "").split(",") if ":" in x)}  # "product-uuid:solo,..."
STRIPE_PRICE_PLANS = {k: v for k, v in (x.split(":") for x in os.getenv("STRIPE_PRICE_PLANS", "").split(",") if ":" in x)}  # "price_x:solo,price_y:team"
RATE_PER_MIN = int(os.getenv("RUNVOUCH_RATE_PER_MIN", "1500"))
SIGNUP_PER_IP_PER_DAY = int(os.getenv("RUNVOUCH_SIGNUPS_PER_IP", "5"))
CORS_ORIGINS = [o for o in os.getenv("RUNVOUCH_CORS", "").split(",") if o]
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
ALERT_FROM = os.getenv("ALERT_FROM", "RunVouch alerts <alerts@runvouch.com>")

app = FastAPI(title="RunVouch", version="0.2.0")
if CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── simple in-memory sliding-window rate limiter (per api-key-hash or ip) ──
_rl: dict[str, list[float]] = {}


def rate_check(bucket: str, limit: int, window: float = 60.0) -> None:
    now = time.time()
    with _lock:
        hits = [t for t in _rl.get(bucket, []) if now - t < window]
        if len(hits) >= limit:
            raise HTTPException(429, "rate limit")
        hits.append(now)
        _rl[bucket] = hits

# ───────────────────────────── storage ─────────────────────────────
_lock = threading.RLock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


_db = _connect()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY, name TEXT, api_key TEXT UNIQUE, created REAL, email TEXT UNIQUE, ls_customer_id TEXT, ls_subscription_id TEXT,
  telegram_token TEXT, telegram_chat TEXT, webhook_url TEXT, plan TEXT DEFAULT 'free');
CREATE TABLE IF NOT EXISTS agents(
  id INTEGER PRIMARY KEY, account_id INTEGER, name TEXT, created REAL,
  cadence_s INTEGER, grace_s INTEGER DEFAULT 900, max_runtime_s INTEGER DEFAULT 3600,
  cap_run_cost REAL, cap_day_cost REAL, cap_run_tokens INTEGER,
  evidence_required INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
  UNIQUE(account_id, name));
CREATE TABLE IF NOT EXISTS runs(
  id TEXT PRIMARY KEY, agent_id INTEGER, started REAL, ended REAL, last_seen REAL,
  status TEXT, cost REAL DEFAULT 0, tokens INTEGER DEFAULT 0, tool_calls INTEGER DEFAULT 0,
  output_bytes INTEGER, evidence_ok INTEGER, evidence_json TEXT, meta_json TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS tool_events(
  id INTEGER PRIMARY KEY, run_id TEXT, ts REAL, tool TEXT, input_hash TEXT, ok INTEGER, cost REAL DEFAULT 0, tokens INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY, account_id INTEGER, agent_id INTEGER, run_id TEXT, ts REAL,
  kind TEXT, message TEXT, acked INTEGER DEFAULT 0, delivered INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_runs_agent ON runs(agent_id, started);
CREATE INDEX IF NOT EXISTS ix_tool_run ON tool_events(run_id, input_hash);
CREATE INDEX IF NOT EXISTS ix_alerts_acc ON alerts(account_id, ts);
CREATE TABLE IF NOT EXISTS signups(id INTEGER PRIMARY KEY, ip TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS ls_events(id TEXT PRIMARY KEY, ts REAL, name TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS reports_sent(account_id INTEGER, week TEXT, PRIMARY KEY(account_id, week));
CREATE TABLE IF NOT EXISTS proof_days(date TEXT PRIMARY KEY, root TEXT, prev TEXT, chain_hash TEXT, n_runs INTEGER, sealed_at REAL, ots_status TEXT, ots_path TEXT);
CREATE TABLE IF NOT EXISTS run_leaves(id TEXT PRIMARY KEY, agent_id INTEGER, ended REAL, leaf_hash TEXT);
CREATE TABLE IF NOT EXISTS heartbeats(minute INTEGER PRIMARY KEY, alerts_ok INTEGER);
CREATE INDEX IF NOT EXISTS ix_run_leaves_ended ON run_leaves(ended);
CREATE TABLE IF NOT EXISTS viewer_keys(id INTEGER PRIMARY KEY, account_id INTEGER, key_hash TEXT UNIQUE, name TEXT, created REAL, last_used REAL);
"""
with _lock:
    _db.executescript(SCHEMA)
    for col in ("email TEXT", "ls_customer_id TEXT", "ls_subscription_id TEXT", "alert_email TEXT", "stripe_customer_id TEXT", "stripe_subscription_id TEXT", "polar_customer_id TEXT", "polar_subscription_id TEXT",
                "slack_webhook_url TEXT", "pagerduty_routing_key TEXT"):
        try:
            _db.execute(f"ALTER TABLE accounts ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    try:
        _db.execute("ALTER TABLE runs ADD COLUMN leaf_hash TEXT")
    except sqlite3.OperationalError:
        pass
    for r in _db.execute("SELECT id, api_key FROM accounts WHERE api_key LIKE 'rv_%'").fetchall():
        _db.execute("UPDATE accounts SET api_key=? WHERE id=?", (hashlib.sha256(r["api_key"].encode()).hexdigest(), r["id"]))
    _db.commit()


@contextmanager
def tx():
    with _lock:
        try:
            yield _db
            _db.commit()
        except Exception:
            _db.rollback()
            raise


def q1(sql: str, *args) -> Optional[sqlite3.Row]:
    with _lock:
        return _db.execute(sql, args).fetchone()


def qa(sql: str, *args) -> list[sqlite3.Row]:
    with _lock:
        return _db.execute(sql, args).fetchall()


# ───────────────────────────── auth ─────────────────────────────
_VIEWER_WRITE_OK = re.compile(r"^/v1/alerts/\d+/ack$")


def is_viewer(acc) -> bool:
    return isinstance(acc, dict) and bool(acc.get("viewer"))


def account_from_key(x_api_key: str = Header(default=""), request: Request = None):
    """rv_ keys: the account row. rvv_ viewer keys (Team): the same account as a dict with viewer=True,
    allowed to GET and to ack alerts, nothing else."""
    if not x_api_key:
        raise HTTPException(401, "X-API-Key header required")
    h = key_hash(x_api_key)
    if x_api_key.startswith("rvv_"):
        vk = q1("SELECT * FROM viewer_keys WHERE key_hash=?", h)
        acc = q1("SELECT * FROM accounts WHERE id=?", vk["account_id"]) if vk else None
        if not acc or acc["plan"] != "team":
            raise HTTPException(401, "invalid api key")
        if request is not None and request.method != "GET" and not _VIEWER_WRITE_OK.match(request.url.path):
            raise HTTPException(403, "viewer key: read-only (GET and alert ack only)")
        rate_check("k:" + h, RATE_PER_MIN)
        with tx() as db:
            db.execute("UPDATE viewer_keys SET last_used=? WHERE id=?", (time.time(), vk["id"]))
        return {**dict(acc), "viewer": True, "viewer_key_id": vk["id"]}
    acc = q1("SELECT * FROM accounts WHERE api_key=?", h)
    if not acc:
        raise HTTPException(401, "invalid api key")
    rate_check("k:" + h, RATE_PER_MIN)
    return acc


def require_plan(acc, plan: str, feature: str) -> None:
    if acc["plan"] != plan:
        raise HTTPException(402, f"{feature} is part of the {PLAN_NAMES[plan]} plan; your account is on {PLAN_NAMES.get(acc['plan'], acc['plan'])}. Upgrade at https://runvouch.com/pricing")


def require_admin(x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(403, "admin token required")


def create_account(name: str, plan: str = "free", email: Optional[str] = None) -> dict:
    """Key is returned ONCE; only its sha256 is stored."""
    key = "rv_" + secrets.token_urlsafe(24)
    with tx() as db:
        cur = db.execute("INSERT INTO accounts(name, api_key, created, plan, email) VALUES(?,?,?,?,?)",
                         (name, key_hash(key), time.time(), plan, email))
    return {"account_id": cur.lastrowid, "api_key": key, "name": name, "plan": plan, "email": email}


def rotate_key(account_id: int) -> str:
    key = "rv_" + secrets.token_urlsafe(24)
    with tx() as db:
        db.execute("UPDATE accounts SET api_key=? WHERE id=?", (key_hash(key), account_id))
    return key


PLAN_LIMITS = {"free": 3, "solo": 15, "team": 100}
RETENTION_DAYS = {"free": 7, "solo": 90, "team": 90}  # runs, tool events and acked alerts older than this are purged daily


# ───────────────────────────── alerts ─────────────────────────────
def _telegram(token: str, chat: str, text: str) -> bool:
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10)
        return True
    except Exception:
        return False


BILLING_FROM = os.getenv("BILLING_FROM", "RunVouch <hello@runvouch.com>")
PLAN_NAMES = {"free": "Free", "solo": "Solo", "team": "Team"}


def _email_html(subject: str, text: str) -> str:
    """Plain text -> branded HTML: logo header, monospace-safe body (lines kept), quiet footer. Inline CSS only (mail clients)."""
    import html as _h
    body = _h.escape(text).replace("\n", "<br>")
    return (f'<!doctype html><html><body style="margin:0;padding:0;background:#f4f6fb;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1b2140">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6fb;padding:24px 0"><tr><td align="center">'
            f'<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e3e7f3;border-radius:12px">'
            f'<tr><td style="padding:22px 28px 6px 28px"><a href="https://runvouch.com" style="text-decoration:none;color:#1b2140">'
            f'<img src="https://runvouch.com/logo-400.png" width="28" height="28" alt="RunVouch" style="vertical-align:middle;border:0;margin-right:8px">'
            f'<span style="font-size:17px;font-weight:700;vertical-align:middle">RunVouch</span></a></td></tr>'
            f'<tr><td style="padding:8px 28px 4px 28px;font-size:15px;line-height:1.55;color:#1b2140">{body}</td></tr>'
            f'<tr><td style="padding:16px 28px 22px 28px;font-size:12px;line-height:1.5;color:#6b7390;border-top:1px solid #eef1f8">'
            f'RunVouch - the watchdog for unattended AI agents. <a href="https://runvouch.com/app" style="color:#4c8dff">Dashboard</a> &middot; '
            f'<a href="https://runvouch.com/docs" style="color:#4c8dff">Docs</a> &middot; <a href="mailto:support@runvouch.com" style="color:#4c8dff">support@runvouch.com</a></td></tr>'
            f'</table></td></tr></table></body></html>')


def _email(to: str, subject: str, text: str, sender: Optional[str] = None) -> bool:
    if not RESEND_API_KEY or not to:
        return False
    try:
        req = urllib.request.Request("https://api.resend.com/emails", json.dumps({"from": sender or ALERT_FROM, "to": [to], "subject": subject, "text": text,
                                                                               "html": _email_html(subject, text), "reply_to": "support@runvouch.com"}).encode(),
                                     {"Authorization": "Bearer " + RESEND_API_KEY, "Content-Type": "application/json", "User-Agent": "runvouch-server/0.3"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _webhook(url: str, payload: dict) -> bool:
    try:
        req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", "User-Agent": "runvouch-server/0.3"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _slack(url: str, text: str, kind: str, agent: str, message: str) -> bool:
    """Slack incoming webhook: plain text fallback plus blocks (kind, agent, message, dashboard link)."""
    payload = {"text": text, "blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": f"RunVouch {kind}: {agent}"[:150]}},
        {"type": "section", "fields": [{"type": "mrkdwn", "text": f"*Kind*\n{kind}"}, {"type": "mrkdwn", "text": f"*Agent*\n{agent}"}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": message[:2900]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "<https://runvouch.com/app|Open the dashboard>"}]}]}
    return _webhook(url, payload)


PD_KINDS = {"MISSED", "FAILED", "STALLED", "BUDGET_RUN", "BUDGET_DAY", "TEST"}
PD_URL = "https://events.pagerduty.com/v2/enqueue"


def _pagerduty(routing_key: str, action: str, dedup_key: str, summary: str = "", severity: str = "error", details: Optional[dict] = None) -> bool:
    """PagerDuty Events API v2. action: trigger | resolve. dedup_key ties our alert to one incident."""
    payload: dict = {"routing_key": routing_key, "event_action": action, "dedup_key": dedup_key}
    if action == "trigger":
        payload["payload"] = {"summary": summary[:1024], "source": "runvouch.com", "severity": severity, "custom_details": details or {}}
        payload["links"] = [{"href": "https://runvouch.com/app", "text": "RunVouch dashboard"}]
    return _webhook(PD_URL, payload)


def pd_dedup_key(agent: str, kind: str) -> str:
    return f"runvouch:{agent}:{kind}"


import queue as _queue
_deliver_q: "_queue.Queue[int]" = _queue.Queue()
ALERT_COOLDOWN = int(os.getenv("RUNVOUCH_ALERT_COOLDOWN", "600"))  # same kind+agent at most once per 10 min
PRIORITY_KINDS = {"MISSED", "FAILED"}  # paid plans: delivered immediately, no cooldown
DRIFT_MIN_MEDIAN = {"duration": 30.0, "output size": 2048.0}  # below this baseline drift is noise (a 1 s job that takes 3 s)


def raise_alert(account_id: int, agent_id: int, run_id: Optional[str], kind: str, message: str, quiet: bool = False) -> None:
    """Persist the alert and hand delivery to a background thread, never block a request on Telegram/email.
    quiet=True stores the alert (dashboard, API) without sending it."""
    if kind == "TEST":
        dup = None
    elif run_id:
        dup = q1("SELECT id FROM alerts WHERE agent_id=? AND run_id=? AND kind=?", agent_id, run_id, kind)
    else:
        dup = q1("SELECT id FROM alerts WHERE agent_id=? AND kind=? AND ts>?", agent_id, kind, time.time() - 3600)
    if dup:
        return
    if quiet:
        recent = True
    elif kind == "TEST":
        recent = None
    elif kind in PRIORITY_KINDS and (q1("SELECT plan FROM accounts WHERE id=?", account_id) or {"plan": "free"})["plan"] != "free":
        recent = None  # priority alerts: paid plans skip the cooldown for MISSED and FAILED
    else:
        recent = q1("SELECT id FROM alerts WHERE agent_id=? AND kind=? AND ts>?", agent_id, kind, time.time() - ALERT_COOLDOWN)
    with tx() as db:
        cur = db.execute("INSERT INTO alerts(account_id, agent_id, run_id, ts, kind, message, delivered) VALUES(?,?,?,?,?,?,?)",
                         (account_id, agent_id, run_id, time.time(), kind, message, -1 if recent else 0))
        alert_id = cur.lastrowid
    if not recent:  # cooldown: stored, visible in dashboard, but not re-sent
        _deliver_q.put(alert_id)


def _deliver(alert_id: int) -> None:
    a = q1("SELECT * FROM alerts WHERE id=?", alert_id)
    if not a:
        return
    acc = q1("SELECT * FROM accounts WHERE id=?", a["account_id"])
    agent = q1("SELECT name FROM agents WHERE id=?", a["agent_id"])
    name = agent["name"] if agent else str(a["agent_id"])
    text = f"⚠️ RunVouch [{a['kind']}] {name}\n{a['message']}"
    delivered = False
    if acc["telegram_token"] and acc["telegram_chat"]:
        delivered |= _telegram(acc["telegram_token"], acc["telegram_chat"], text)
    if acc["webhook_url"]:
        delivered |= _webhook(acc["webhook_url"], {"kind": a["kind"], "agent": name, "run_id": a["run_id"], "message": a["message"], "ts": a["ts"]})
    if acc["slack_webhook_url"]:
        delivered |= _slack(acc["slack_webhook_url"], text, a["kind"], name, a["message"])
    if acc["pagerduty_routing_key"] and acc["plan"] == "team" and a["kind"] in PD_KINDS:
        delivered |= _pagerduty(acc["pagerduty_routing_key"], "trigger", pd_dedup_key(name, a["kind"]), f"[{a['kind']}] {name}: {a['message']}",
                                "info" if a["kind"] == "TEST" else "error", {"agent": name, "kind": a["kind"], "run_id": a["run_id"], "alert_id": a["id"]})
    if acc["alert_email"]:
        delivered |= _email(acc["alert_email"], f"[RunVouch] {a['kind']}: {name}", a["message"] + "\n\nhttps://runvouch.com/app")
    with tx() as db:
        db.execute("UPDATE alerts SET delivered=? WHERE id=?", (1 if delivered else 0, alert_id))


def _deliverer():
    while True:
        try:
            _deliver(_deliver_q.get())
        except Exception:
            pass


if os.getenv("AGENTWATCH_NO_SWEEP") != "1" and os.getenv("RUNVOUCH_NO_SWEEP") != "1":
    threading.Thread(target=_deliverer, daemon=True).start()


# ───────────────────────────── detectors ─────────────────────────────
def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def check_drift(agent: sqlite3.Row, run: sqlite3.Row) -> None:
    """Compare this run's duration / output size against trailing successful runs (robust MAD)."""
    hist = qa("SELECT started, ended, output_bytes FROM runs WHERE agent_id=? AND status='ok' AND id!=? "
              "AND ended IS NOT NULL ORDER BY started DESC LIMIT 7", agent["id"], run["id"])
    if len(hist) < 4:
        return
    for label, cur, series in (
        ("duration", (run["ended"] or 0) - run["started"], [h["ended"] - h["started"] for h in hist]),
        ("output size", run["output_bytes"], [h["output_bytes"] for h in hist if h["output_bytes"] is not None]),
    ):
        if cur is None or len(series) < 4:
            continue
        med = _median(series)
        if med < DRIFT_MIN_MEDIAN[label]:
            continue
        # robust MAD with an absolute floor: 5 s / 512 bytes, or 10% of the median, a 1-second job
        # that takes 2 seconds, or a log line that is 60 bytes longer, is noise, not drift
        floor = 5.0 if label == "duration" else 512.0
        mad = max(_median([abs(x - med) for x in series]), med * 0.1, floor)
        if abs(cur - med) > DRIFT_K * mad and abs(cur - med) > 0.25 * max(med, 1.0):
            raise_alert(agent["account_id"], agent["id"], run["id"], "DRIFT",
                        f"{label} {cur:.0f} vs trailing median {med:.0f} (MAD {mad:.0f}). Task may be silently doing something else.")


def check_budget(agent: sqlite3.Row, run: sqlite3.Row) -> None:
    if agent["cap_run_cost"] and run["cost"] > agent["cap_run_cost"]:
        raise_alert(agent["account_id"], agent["id"], run["id"], "BUDGET_RUN",
                    f"run cost {run['cost']:.2f} > cap {agent['cap_run_cost']:.2f}")
    if agent["cap_run_tokens"] and run["tokens"] > agent["cap_run_tokens"]:
        raise_alert(agent["account_id"], agent["id"], run["id"], "BUDGET_RUN",
                    f"run tokens {run['tokens']} > cap {agent['cap_run_tokens']}")
    if agent["cap_day_cost"]:
        day0 = time.time() - 86400
        tot = q1("SELECT COALESCE(SUM(cost),0) s FROM runs WHERE agent_id=? AND started>?", agent["id"], day0)["s"]
        if tot > agent["cap_day_cost"]:
            raise_alert(agent["account_id"], agent["id"], run["id"], "BUDGET_DAY",
                        f"24h cost {tot:.2f} > daily cap {agent['cap_day_cost']:.2f}")


def check_storm(agent: sqlite3.Row, run_id: str, input_hash: str, tool: str) -> None:
    n = q1("SELECT COUNT(*) n FROM tool_events WHERE run_id=? AND input_hash=?", run_id, input_hash)["n"]
    if n >= STORM_THRESHOLD:
        raise_alert(agent["account_id"], agent["id"], run_id, "RETRY_STORM",
                    f"tool '{tool}' called {n}x with identical input in one run. Each call looks fine; together it's a loop.")


def evaluate_evidence(evidence: dict[str, Any]) -> tuple[bool, dict]:
    """
    Evidence is a dict of named assertions the CLIENT already evaluated (bool), or
    simple server-checkable specs: {"name": {"type": "url", "url": "...", "expect": 200}}.
    Server never touches client filesystems. Returns (all_ok, detail).
    """
    detail = {}
    ok_all = True
    for name, spec in (evidence or {}).items():
        if isinstance(spec, bool):
            ok = spec
        elif isinstance(spec, dict) and spec.get("type") == "url":
            try:
                r = urllib.request.urlopen(urllib.request.Request(spec["url"], method="HEAD"), timeout=10)
                ok = r.status == int(spec.get("expect", 200))
            except Exception:
                ok = False
        elif isinstance(spec, dict) and "ok" in spec:
            ok = bool(spec["ok"])
        else:
            ok = False
        detail[name] = ok
        ok_all &= ok
    return ok_all, detail


# ───────────────────────────── background sweep ─────────────────────────────
def sweep_once(now: Optional[float] = None) -> None:
    now = now or time.time()
    for agent in qa("SELECT * FROM agents WHERE paused=0"):
        last = q1("SELECT * FROM runs WHERE agent_id=? ORDER BY started DESC LIMIT 1", agent["id"])
        # MISSED
        if agent["cadence_s"]:
            ref = last["started"] if last else agent["created"]
            if now - ref > agent["cadence_s"] + agent["grace_s"]:
                raise_alert(agent["account_id"], agent["id"], None, "MISSED",
                            f"no run started for {int((now-ref)/60)} min (cadence {agent['cadence_s']//60} min + grace). Scheduler dead, auth expired, or agent crashed before first ping.")
        # STALLED
        if last and last["ended"] is None and now - (last["last_seen"] or last["started"]) > agent["max_runtime_s"]:
            raise_alert(agent["account_id"], agent["id"], last["id"], "STALLED",
                        f"run started {int((now-last['started'])/60)} min ago, no end/heartbeat for > {agent['max_runtime_s']//60} min.")


def weekly_report(now: Optional[float] = None) -> int:
    """Per account: 7-day cost, runs, alerts by kind, top agents. Sent once per ISO week (Monday >= 07:00 UTC)."""
    now = now or time.time()
    lt = time.gmtime(now)
    if not (lt.tm_wday == 0 and lt.tm_hour >= 7):
        return 0
    week = time.strftime("%G-W%V", lt)
    sent = 0
    for acc in qa("SELECT * FROM accounts WHERE telegram_token IS NOT NULL OR webhook_url IS NOT NULL OR alert_email IS NOT NULL OR slack_webhook_url IS NOT NULL"):
        if q1("SELECT 1 FROM reports_sent WHERE account_id=? AND week=?", acc["id"], week):
            continue
        t0 = now - 7 * 86400
        rows = qa("SELECT g.name, COUNT(r.id) n, COALESCE(SUM(r.cost),0) c, SUM(CASE WHEN r.status!='ok' THEN 1 ELSE 0 END) f "
                  "FROM agents g LEFT JOIN runs r ON r.agent_id=g.id AND r.started>? WHERE g.account_id=? GROUP BY g.id ORDER BY c DESC", t0, acc["id"])
        if not rows:
            continue
        alerts = qa("SELECT kind, COUNT(*) n FROM alerts WHERE account_id=? AND ts>? GROUP BY kind ORDER BY n DESC", acc["id"], t0)
        total_cost = sum(r["c"] for r in rows); total_runs = sum(r["n"] for r in rows); fails = sum(r["f"] or 0 for r in rows)
        top = ", ".join(f"{r['name']} ${r['c']:.2f}" for r in rows[:3] if r["c"] > 0) or "none"
        al = ", ".join(f"{a['kind']} {a['n']}" for a in alerts) or "none"
        text = (f"📊 RunVouch weekly, {week}\n{len(rows)} agents · {total_runs} runs · {fails} failed\n"
                f"Cost 7d: ${total_cost:.2f} · top: {top}\nAlerts: {al}\nhttps://runvouch.com/app")
        ok = False
        if acc["telegram_token"] and acc["telegram_chat"]:
            ok |= _telegram(acc["telegram_token"], acc["telegram_chat"], text)
        if acc["alert_email"]:
            ok |= _email(acc["alert_email"], f"[RunVouch] weekly report {week}", text)
        if acc["webhook_url"]:
            ok |= _webhook(acc["webhook_url"], {"kind": "WEEKLY_REPORT", "week": week, "cost_7d": round(total_cost, 4), "runs": total_runs, "failed": fails, "alerts": [dict(a) for a in alerts]})
        if acc["slack_webhook_url"]:
            ok |= _slack(acc["slack_webhook_url"], text, "WEEKLY_REPORT", f"{len(rows)} agents", text)
        with tx() as db:
            db.execute("INSERT OR IGNORE INTO reports_sent(account_id, week) VALUES(?,?)", (acc["id"], week))
        sent += int(ok)
    return sent


def owner_digest(now: Optional[float] = None) -> bool:
    """Once a day (first sweep after 07:00 UTC): one Telegram line to the owner, only when there were signups."""
    now = now or time.time()
    day = datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    if datetime.utcfromtimestamp(now).hour < 7 or q1("SELECT 1 FROM reports_sent WHERE account_id=0 AND week=?", day):
        return False
    owner = q1("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1")
    if not owner:
        return False
    new = q1("SELECT COUNT(*) n FROM accounts WHERE created>?", now - 86400)["n"]
    total = q1("SELECT COUNT(*) n FROM accounts WHERE email IS NOT NULL")["n"]
    paid = q1("SELECT COUNT(*) n FROM accounts WHERE plan!='free' AND email IS NOT NULL")["n"]
    active = q1("SELECT COUNT(DISTINCT agent_id) n FROM runs WHERE started>?", now - 86400)["n"]
    with tx() as db:
        db.execute("INSERT OR IGNORE INTO reports_sent(account_id, week) VALUES(0, ?)", (day,))
    if not new:
        return False  # nothing happened: no message (the Monday weekly report carries the totals)
    return _telegram(owner["telegram_token"], owner["telegram_chat"],
                     f"RunVouch dagstand {day}: {new} nieuwe accounts in 24u, {total} accounts totaal, {paid} betalend, {active} agents actief in 24u.")


# ───────────────────────────── verifiable runs (leaf per run, Merkle day, OpenTimestamps) ─────────────────────────────
PROOF_DIR = Path(os.getenv("RUNVOUCH_PROOF_DIR", DB_PATH.parent / "proof" / "days"))
OTS_BIN = os.path.expanduser(os.getenv("RUNVOUCH_OTS", "~/.local/bin/ots"))
SEAL_DELAY = 300  # seconds after UTC midnight before a day is sealed: a run ending at 23:59:59 must have committed


def leaf_record(run: sqlite3.Row, agent: sqlite3.Row) -> dict:
    """The facts of one finished run. Hashes only for tool inputs; never prompts, outputs or evidence content."""
    meta = json.loads(run["meta_json"] or "{}")
    events = qa("SELECT tool, input_hash, ok, ts FROM tool_events WHERE run_id=? ORDER BY id", run["id"])
    rec = {"run_id": run["id"], "agent": agent["name"], "account_id": agent["account_id"], "started": run["started"], "ended": run["ended"],
           "status": run["status"], "cost": run["cost"], "tokens": run["tokens"], "tool_calls": run["tool_calls"], "output_bytes": run["output_bytes"],
           "evidence": json.loads(run["evidence_json"] or "{}"), "evidence_ok": run["evidence_ok"], "source": run["source"],
           "tool_events_hash": _pf.tool_events_hash([(x["tool"], x["input_hash"], x["ok"], x["ts"]) for x in events])}
    if "exit" in meta:
        rec["exit"] = meta["exit"]
    return rec


def _day_of(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _day_ts(date: str) -> int:
    return calendar.timegm(time.strptime(date, "%Y-%m-%d"))  # UTC midnight


def _day_leaves(date: str) -> list[sqlite3.Row]:
    t0 = _day_ts(date)
    # purged runs live on in run_leaves (id, ended, leaf_hash), so a sealed day keeps the same leaf list after retention
    return qa("SELECT id, leaf_hash FROM (SELECT id, leaf_hash, ended FROM runs WHERE leaf_hash IS NOT NULL "
              "UNION SELECT id, leaf_hash, ended FROM run_leaves) WHERE ended>=? AND ended<? ORDER BY id", t0, t0 + 86400)


def ots_stamp(path: Path) -> str:
    if not os.path.exists(OTS_BIN):
        return "ots missing"
    try:
        r = subprocess.run([OTS_BIN, "stamp", str(path)], capture_output=True, text=True, timeout=120)
        # ots exits non-zero when one of the calendars refuses; the stamp is valid as long as the .ots file was written
        return "pending" if path.with_suffix(".json.ots").exists() else "stamp failed: " + (r.stderr or r.stdout)[:120].strip()
    except Exception as e:
        return f"stamp failed: {e}"


def ots_upgrade(path: Path) -> Optional[str]:
    """'bitcoin:<block>' once the calendar delivered the Bitcoin attestation, None while still pending."""
    ots = path.with_suffix(".json.ots")
    if not os.path.exists(OTS_BIN) or not ots.exists():
        return None
    try:
        subprocess.run([OTS_BIN, "upgrade", str(ots)], capture_output=True, text=True, timeout=60)
        info = subprocess.run([OTS_BIN, "info", str(ots)], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    m = re.search(r"BitcoinBlockHeaderAttestation\((\d+)\)", info)
    return f"bitcoin:{m.group(1)}" if m else None


def ots_upgrade_pending(days: int = 14) -> int:
    n = 0
    cutoff = _day_of(time.time() - days * 86400)
    for d in qa("SELECT date, ots_path FROM proof_days WHERE ots_status='pending' AND date>=?", cutoff):
        st = ots_upgrade(Path(d["ots_path"]))
        if st:
            with tx() as db:
                db.execute("UPDATE proof_days SET ots_status=? WHERE date=?", (st, d["date"]))
            n += 1
    return n


def seal_day(date: str) -> dict:
    """Merkle root over the day's leaves, chained to the previous sealed day, written to a public file and stamped. Idempotent."""
    have = q1("SELECT * FROM proof_days WHERE date=?", date)
    if have:
        return dict(have)
    prev_row = q1("SELECT chain_hash FROM proof_days WHERE date<? ORDER BY date DESC LIMIT 1", date)
    prev = prev_row["chain_hash"] if prev_row else _pf.GENESIS
    rows = _day_leaves(date)
    leaves = [r["leaf_hash"] for r in rows]
    root = _pf.merkle_root(leaves)
    ch = _pf.chain_hash(prev, date, root)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    path = PROOF_DIR / f"{date}.json"
    body = {"date": date, "root": root, "prev": prev, "chain_hash": ch, "n_runs": len(leaves),
            "leaves": [{"run_id": r["id"], "leaf": r["leaf_hash"]} for r in rows],
            "spec": "leaf=sha256(canonical_json(record)); root=merkle(sha256(left+right), odd: last paired with itself, empty: sha256('')); chain_hash=sha256(prev+':'+date+':'+root)"}
    path.write_text(_pf.canonical(body) + "\n")
    st = ots_stamp(path)
    with tx() as db:
        db.execute("INSERT OR IGNORE INTO proof_days(date, root, prev, chain_hash, n_runs, sealed_at, ots_status, ots_path) VALUES(?,?,?,?,?,?,?,?)",
                   (date, root, prev, ch, len(leaves), time.time(), st, str(path)))
    return dict(q1("SELECT * FROM proof_days WHERE date=?", date))


def seal_days(now: Optional[float] = None) -> int:
    """Seal every UTC day that is over (plus SEAL_DELAY) and not yet sealed, in order, so the chain has no gaps."""
    now = now or time.time()
    last = q1("SELECT date FROM proof_days ORDER BY date DESC LIMIT 1")
    if last:
        start = _day_of(_day_ts(last["date"]) + 86400)
    else:
        first = q1("SELECT MIN(m) m FROM (SELECT MIN(ended) m FROM runs WHERE leaf_hash IS NOT NULL UNION SELECT MIN(ended) FROM run_leaves)")
        if not first or not first["m"]:
            return 0  # the chain starts on the first day that has a leaf; earlier days are not sealed as if empty
        start = _day_of(first["m"])
    today = _day_of(now - SEAL_DELAY)
    n = 0
    d = start
    while d < today:
        seal_day(d)
        n += 1
        d = _day_of(_day_ts(d) + 86400)
    return n


_last_ots_day = ""


def proof_maintenance(now: Optional[float] = None) -> None:
    global _last_ots_day
    now = now or time.time()
    seal_days(now)
    if _day_of(now) != _last_ots_day:
        _last_ots_day = _day_of(now)
        ots_upgrade_pending()


def run_proof(run: sqlite3.Row, agent: sqlite3.Row) -> dict:
    rec = leaf_record(run, agent)
    leaf = _pf.leaf_hash(rec)
    date = _day_of(run["ended"])
    rows = _day_leaves(date)
    leaves = [r["leaf_hash"] for r in rows]
    idx = next((i for i, r in enumerate(rows) if r["id"] == run["id"]), None)
    day = q1("SELECT * FROM proof_days WHERE date=?", date)
    out = {"run_id": run["id"], "record": rec, "leaf_hash": leaf, "stored_leaf_hash": run["leaf_hash"], "date": date,
           "merkle_path": _pf.merkle_path(leaves, idx) if idx is not None else [], "root": _pf.merkle_root(leaves),
           "sealed": bool(day), "chain_hash": day["chain_hash"] if day else None, "prev": day["prev"] if day else None,
           "ots_status": day["ots_status"] if day else "not sealed yet (a day is sealed after it ends, UTC)",
           "verify_url": f"{PUBLIC_URL}/proof/days/{date}.json", "ots_url": f"{PUBLIC_URL}/proof/days/{date}.ots" if day and day["ots_status"] != "ots missing" and not str(day["ots_status"]).startswith("stamp failed") else None,
           "docs": "https://runvouch.com/docs/proof"}
    if not day:
        out["note"] = "root and path are computed live from today's runs and may still change until the day is sealed"
    return out



_last_purge_day = ""


def purge_once(now: Optional[float] = None) -> dict:
    """Retention per plan (RETENTION_DAYS): delete runs, their tool events and acked alerts older than the window.
    Runs that carry a leaf keep (id, agent_id, ended, leaf_hash) in run_leaves so sealed proof days stay verifiable."""
    now = now or time.time()
    out = {"runs": 0, "tool_events": 0, "alerts": 0}
    for acc in qa("SELECT id, plan FROM accounts"):
        cutoff = now - RETENTION_DAYS.get(acc["plan"], 7) * 86400
        old = qa("SELECT r.id, r.agent_id, r.ended, r.leaf_hash FROM runs r JOIN agents g ON g.id=r.agent_id "
                 "WHERE g.account_id=? AND COALESCE(r.ended, r.started)<?", acc["id"], cutoff)
        with tx() as db:
            for r in old:
                if r["leaf_hash"]:
                    db.execute("INSERT OR IGNORE INTO run_leaves(id, agent_id, ended, leaf_hash) VALUES(?,?,?,?)", (r["id"], r["agent_id"], r["ended"], r["leaf_hash"]))
                out["tool_events"] += db.execute("DELETE FROM tool_events WHERE run_id=?", (r["id"],)).rowcount
                out["runs"] += db.execute("DELETE FROM runs WHERE id=?", (r["id"],)).rowcount
            out["alerts"] += db.execute("DELETE FROM alerts WHERE account_id=? AND acked=1 AND ts<?", (acc["id"], cutoff)).rowcount
    return out


def purge_daily(now: Optional[float] = None) -> Optional[dict]:
    global _last_purge_day
    now = now or time.time()
    if _day_of(now) == _last_purge_day:
        return None
    _last_purge_day = _day_of(now)
    return purge_once(now)


def purged_proof(leaf: sqlite3.Row) -> dict:
    """After retention only the leaf survives: no record to recompute, but the Merkle path to the sealed root still holds."""
    date = _day_of(leaf["ended"])
    rows = _day_leaves(date)
    leaves = [r["leaf_hash"] for r in rows]
    idx = next((i for i, r in enumerate(rows) if r["id"] == leaf["id"]), None)
    day = q1("SELECT * FROM proof_days WHERE date=?", date)
    return {"run_id": leaf["id"], "record": None, "leaf_hash": leaf["leaf_hash"], "stored_leaf_hash": leaf["leaf_hash"], "date": date, "agent": leaf["agent"],
            "merkle_path": _pf.merkle_path(leaves, idx) if idx is not None else [], "root": _pf.merkle_root(leaves),
            "sealed": bool(day), "chain_hash": day["chain_hash"] if day else None, "prev": day["prev"] if day else None,
            "ots_status": day["ots_status"] if day else "not sealed", "verify_url": f"{PUBLIC_URL}/proof/days/{date}.json",
            "purged": True, "note": "the full run record was removed by your plan's history retention; the leaf hash and its path to the sealed day root remain",
            "docs": "https://runvouch.com/docs/proof"}


HEARTBEAT_KEEP_DAYS = 100
INCIDENT_GAP_MIN = 3  # minutes without a heartbeat that count as an outage on the public status page


def record_heartbeat(now: Optional[float] = None) -> None:
    """One row per minute the detector loop actually ran; the public status page derives uptime and incidents from it."""
    now = now or time.time()
    ok = 1 if _alert_delivery_status() in ("ok", "idle") else 0
    with tx() as db:
        db.execute("INSERT OR REPLACE INTO heartbeats(minute, alerts_ok) VALUES(?, ?)", (int(now // 60), ok))
        if int(now) % 3600 < SWEEP_SECONDS:
            db.execute("DELETE FROM heartbeats WHERE minute < ?", (int(now // 60) - HEARTBEAT_KEEP_DAYS * 1440,))


def status_summary(now: Optional[float] = None) -> dict:
    """Uptime per window and the outages, computed from heartbeats. Public: no account data in here."""
    now = now or time.time()
    cur = int(now // 60)
    first = q1("SELECT MIN(minute) m FROM heartbeats")["m"]
    if first is None:
        return {"time": datetime.utcfromtimestamp(now).isoformat(timespec="seconds") + "Z", "measured_since": None, "windows": {}, "incidents": [], "last_heartbeat_age_s": None}
    rows = qa("SELECT minute, alerts_ok FROM heartbeats WHERE minute >= ? ORDER BY minute", cur - 90 * 1440)
    windows = {}
    for label, days in (("24h", 1), ("7d", 7), ("30d", 30), ("90d", 90)):
        start = max(cur - days * 1440, first)
        expected = max(cur - start, 1)
        got = [r for r in rows if r["minute"] >= start]
        windows[label] = {"detectors": round(100 * min(len(got), expected) / expected, 2),
                          "alerts": round(100 * min(sum(r["alerts_ok"] for r in got), expected) / expected, 2), "minutes": expected}
    incidents, prev = [], None
    for r in rows:
        if prev is not None and r["minute"] - prev > INCIDENT_GAP_MIN:
            incidents.append({"start": datetime.utcfromtimestamp(prev * 60).isoformat(timespec="minutes") + "Z", "minutes": r["minute"] - prev - 1, "component": "detectors"})
        prev = r["minute"]
    if prev is not None and cur - prev > INCIDENT_GAP_MIN:
        incidents.append({"start": datetime.utcfromtimestamp(prev * 60).isoformat(timespec="minutes") + "Z", "minutes": cur - prev - 1, "component": "detectors", "ongoing": True})
    sealed = q1("SELECT COUNT(*) n, MAX(date) d FROM proof_days")
    return {"time": datetime.utcfromtimestamp(now).isoformat(timespec="seconds") + "Z",
            "measured_since": datetime.utcfromtimestamp(first * 60).strftime("%Y-%m-%d"),
            "windows": windows, "incidents": incidents[-10:], "last_heartbeat_age_s": int(now - prev * 60),
            "sealed_days": {"count": sealed["n"], "last": sealed["d"]}}


def _sweeper():
    n = 0
    while True:
        try:
            sweep_once()
            record_heartbeat()
            owner_digest()
            proof_maintenance()
            purge_daily()
            if n % 20 == 0:
                weekly_report()
        except Exception:
            pass
        n += 1
        time.sleep(SWEEP_SECONDS)


if os.getenv("RUNVOUCH_NO_SWEEP") != "1":
    threading.Thread(target=_sweeper, daemon=True).start()


# ───────────────────────────── API models ─────────────────────────────
class AgentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    cadence_s: Optional[int] = None
    grace_s: int = 900
    max_runtime_s: int = 3600
    cap_run_cost: Optional[float] = None
    cap_day_cost: Optional[float] = None
    cap_run_tokens: Optional[int] = None
    evidence_required: bool = False


class StartIn(BaseModel):
    agent: str
    run_id: Optional[str] = None
    source: Optional[str] = None  # claude-code | openclaw | cron | n8n | custom
    meta: dict = {}


class ToolIn(BaseModel):
    run_id: str
    tool: str
    input: Any = None
    input_hash: Optional[str] = None
    ok: bool = True
    cost: float = 0
    tokens: int = 0


class EndIn(BaseModel):
    run_id: str
    status: str = "ok"  # ok | fail
    cost: float = 0
    tokens: int = 0
    output_bytes: Optional[int] = None
    evidence: dict = {}
    meta: dict = {}


class SettingsIn(BaseModel):
    telegram_token: Optional[str] = None
    telegram_chat: Optional[str] = None
    webhook_url: Optional[str] = None
    alert_email: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    pagerduty_routing_key: Optional[str] = None


def _agent(acc: sqlite3.Row, name: str) -> sqlite3.Row:
    a = q1("SELECT * FROM agents WHERE account_id=? AND name=?", acc["id"], name)
    if not a:
        raise HTTPException(404, f"agent '{name}' not found; create it first via POST /v1/agents")
    return a


# ───────────────────────────── routes ─────────────────────────────
def _alert_delivery_status() -> str:
    """'ok' when the newest alert of the last 7 days was delivered, 'idle' when nothing was due, 'failing' otherwise."""
    try:
        row = q1("SELECT delivered FROM alerts WHERE ts>? ORDER BY id DESC LIMIT 1", time.time() - 7 * 86400)
    except Exception:
        return "unknown"
    if row is None:
        return "idle"
    return "ok" if row["delivered"] else "failing"


@app.get("/health")
def health():
    """Machine-readable status (UptimeRobot keyword: "ok"). DB is touched so a broken disk shows here."""
    try:
        q1("SELECT 1 AS one")
        db_ok = True
    except Exception:
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "service": "RunVouch API", "version": "0.3.3", "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "checks": {"database": "ok" if db_ok else "error", "detectors": "running" if not os.getenv("RUNVOUCH_NO_SWEEP") else "disabled", "alert_delivery": _alert_delivery_status()},
            "docs": "https://runvouch.com/docs", "status_page": "https://runvouch.com/status"}
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.get("/status.json")
def status_json():
    """Public numbers behind runvouch.com/status: uptime per window, outages, sealed proof days. Nothing account-specific."""
    return status_summary()


@app.post("/admin/accounts", dependencies=[Depends(require_admin)])
def admin_create_account(name: str, plan: str = "free"):
    return create_account(name, plan)


class SignupIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/signup")
def signup(body: SignupIn, request: Request):
    """Self-serve: email -> free account. Key shown once. Abuse-limited per IP."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    rate_check("ip:" + ip, 20)
    n = q1("SELECT COUNT(*) n FROM signups WHERE ip=? AND ts>?", ip, time.time() - 86400)["n"]
    if n >= SIGNUP_PER_IP_PER_DAY:
        raise HTTPException(429, "too many signups from this address today")
    email = body.email.lower().strip()
    existing = q1("SELECT id, plan FROM accounts WHERE email=?", email)
    if existing:
        # Lost key or second signup: rotate and mail the fresh key to the address on file. Only the mailbox
        # owner can read it, so this is safe, and it keeps the founder out of the loop.
        key = rotate_key(existing["id"])
        with tx() as db:
            db.execute("INSERT INTO signups(ip, ts) VALUES(?,?)", (ip, time.time()))
        _send_billing("key", email, existing["plan"], None, key)
        return {"sent": True, "plan": existing["plan"], "note": "This address already has an account. A fresh key is on its way to your inbox; the old key stopped working."}
    acc = create_account(email.split("@")[0], "free", email)
    with tx() as db:
        db.execute("INSERT INTO signups(ip, ts) VALUES(?,?)", (ip, time.time()))
        db.execute("UPDATE accounts SET alert_email=? WHERE id=?", (email, acc["account_id"]))
    _send_billing("signup", email, "free", None, acc["api_key"])
    return {"api_key": acc["api_key"], "plan": "free", "agents_allowed": PLAN_LIMITS["free"],
            "note": "Store this key now; it is not shown again (a copy is in your inbox)."}


class ContactIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=5, max_length=4000)
    topic: str = "support"


@app.post("/contact")
def contact(body: ContactIn, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    rate_check("contact:" + ip, 5, 3600)
    with tx() as db:
        db.execute("CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY, ts REAL, email TEXT, topic TEXT, message TEXT, ip TEXT)")
        db.execute("INSERT INTO contacts(ts,email,topic,message,ip) VALUES(?,?,?,?,?)", (time.time(), body.email, body.topic, body.message, ip))
    owner = q1("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1")
    if owner:
        _telegram(owner["telegram_token"], owner["telegram_chat"], f"📩 RunVouch contact [{body.topic}] from {body.email}:\n{body.message[:1500]}")
    return {"ok": True}


@app.get("/v1/me")
def me(acc=Depends(account_from_key)):
    return {"name": acc["name"], "email": acc["email"], "plan": acc["plan"], "agents_allowed": PLAN_LIMITS.get(acc["plan"], 3),
            "history_days": RETENTION_DAYS.get(acc["plan"], 7), "viewer": is_viewer(acc),
            "alerts_configured": bool((acc["telegram_token"] and acc["telegram_chat"]) or acc["webhook_url"] or acc["alert_email"] or acc["slack_webhook_url"] or acc["pagerduty_routing_key"]),
            "channels": {"email": bool(acc["alert_email"]), "telegram": bool(acc["telegram_token"] and acc["telegram_chat"]), "webhook": bool(acc["webhook_url"]),
                         "slack": bool(acc["slack_webhook_url"]), "pagerduty": bool(acc["pagerduty_routing_key"] and acc["plan"] == "team")}}


@app.post("/v1/me/rotate-key")
def me_rotate(acc=Depends(account_from_key)):
    return {"api_key": rotate_key(acc["id"]), "note": "old key is now invalid"}


@app.post("/webhooks/lemonsqueezy")
async def ls_webhook(request: Request):
    """Lemon Squeezy → plan changes. Verified with HMAC-SHA256 over the raw body (X-Signature)."""
    raw = await request.body()
    if not LS_WEBHOOK_SECRET:
        raise HTTPException(503, "LS_WEBHOOK_SECRET not configured")
    sig = request.headers.get("x-signature", "")
    if not hmac.compare_digest(hmac.new(LS_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest(), sig):
        raise HTTPException(401, "bad signature")
    ev = json.loads(raw or b"{}")
    name = (ev.get("meta") or {}).get("event_name", "")
    attrs = (ev.get("data") or {}).get("attributes") or {}
    ev_id = str((ev.get("data") or {}).get("id", "")) + ":" + name + ":" + str(attrs.get("updated_at", ""))
    if q1("SELECT id FROM ls_events WHERE id=?", ev_id):
        return {"ok": True, "dup": True}
    email = (attrs.get("user_email") or attrs.get("customer_email") or "").lower().strip()
    variant = str(attrs.get("variant_id") or attrs.get("first_order_item", {}).get("variant_id") or "")
    status = attrs.get("status", "")
    plan = None
    if name in ("subscription_created", "subscription_updated", "subscription_resumed", "subscription_unpaused", "order_created"):
        if status in ("", "active", "on_trial", "paid", "past_due"):
            plan = LS_VARIANT_PLANS.get(variant, "solo")
    if name in ("subscription_cancelled", "subscription_expired", "subscription_paused", "order_refunded") or status in ("expired", "cancelled"):
        plan = "free"
    acc = q1("SELECT * FROM accounts WHERE email=?", email) if email else None
    with tx() as db:
        db.execute("INSERT INTO ls_events(id, ts, name, payload) VALUES(?,?,?,?)", (ev_id, time.time(), name, raw.decode(errors="ignore")[:20000]))
        if plan and acc:
            db.execute("UPDATE accounts SET plan=?, ls_customer_id=COALESCE(?,ls_customer_id), ls_subscription_id=COALESCE(?,ls_subscription_id) WHERE id=?",
                       (plan, str(attrs.get("customer_id") or "") or None, str((ev.get("data") or {}).get("id") or "") or None, acc["id"]))
        elif plan and email and not acc:
            # paid before signing up: create the account; key delivered via dashboard rotate flow (email known)
            key = "rv_" + secrets.token_urlsafe(24)
            db.execute("INSERT INTO accounts(name, api_key, created, plan, email) VALUES(?,?,?,?,?)",
                       (email.split("@")[0], key_hash(key), time.time(), plan, email))
    return {"ok": True, "event": name, "plan": plan, "matched": bool(acc)}


def _stripe_sig_ok(raw: bytes, header: str) -> bool:
    """Stripe-Signature: t=<ts>,v1=<hmac>. HMAC-SHA256 over "<ts>.<raw>", 5-minute tolerance."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts, v1 = parts.get("t", ""), parts.get("v1", "")
    if not ts or not v1 or abs(time.time() - float(ts)) > 300:
        return False
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Stripe → plan changes. Payment Links carry the price id; the plan comes from STRIPE_PRICE_PLANS.
    checkout.session.completed sets the plan and remembers the customer; subscription deleted/unpaid drops to free."""
    raw = await request.body()
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "STRIPE_WEBHOOK_SECRET not configured")
    if not _stripe_sig_ok(raw, request.headers.get("stripe-signature", "")):
        raise HTTPException(401, "bad signature")
    ev = json.loads(raw or b"{}")
    name, ev_id = ev.get("type", ""), "stripe:" + str(ev.get("id", ""))
    if q1("SELECT id FROM ls_events WHERE id=?", ev_id):
        return {"ok": True, "dup": True}
    obj = (ev.get("data") or {}).get("object") or {}
    customer = str(obj.get("customer") or "")
    email = ((obj.get("customer_details") or {}).get("email") or obj.get("customer_email") or "").lower().strip()
    plan, sub_id = None, None
    if name == "checkout.session.completed" and obj.get("payment_status") in ("paid", "no_payment_required"):
        prices = [str(li.get("price", {}).get("id", "")) for li in ((obj.get("line_items") or {}).get("data") or [])]
        prices += [str((obj.get("metadata") or {}).get("price", ""))]
        plan = next((STRIPE_PRICE_PLANS[p] for p in prices if p in STRIPE_PRICE_PLANS), None) or (obj.get("metadata") or {}).get("plan") or "solo"
        sub_id = str(obj.get("subscription") or "") or None
    elif name in ("customer.subscription.updated", "customer.subscription.created"):
        prices = [str(it.get("price", {}).get("id", "")) for it in ((obj.get("items") or {}).get("data") or [])]
        if obj.get("status") in ("active", "trialing", "past_due"):
            plan = next((STRIPE_PRICE_PLANS[p] for p in prices if p in STRIPE_PRICE_PLANS), None)
        elif obj.get("status") in ("canceled", "unpaid", "incomplete_expired"):
            plan = "free"
        sub_id = str(obj.get("id") or "") or None
    elif name == "customer.subscription.deleted":
        plan, sub_id = "free", str(obj.get("id") or "") or None
    acc = (q1("SELECT * FROM accounts WHERE email=?", email) if email else None) or \
          (q1("SELECT * FROM accounts WHERE stripe_customer_id=?", customer) if customer else None)
    with tx() as db:
        db.execute("INSERT INTO ls_events(id, ts, name, payload) VALUES(?,?,?,?)", (ev_id, time.time(), name, raw.decode(errors="ignore")[:20000]))
        if plan and acc:
            db.execute("UPDATE accounts SET plan=?, stripe_customer_id=COALESCE(?,stripe_customer_id), stripe_subscription_id=COALESCE(?,stripe_subscription_id) WHERE id=?",
                       (plan, customer or None, sub_id, acc["id"]))
        elif plan and plan != "free" and email and not acc:
            key = "rv_" + secrets.token_urlsafe(24)
            db.execute("INSERT INTO accounts(name, api_key, created, plan, email, stripe_customer_id, stripe_subscription_id) VALUES(?,?,?,?,?,?,?)",
                       (email.split("@")[0], key_hash(key), time.time(), plan, email, customer or None, sub_id))
    return {"ok": True, "event": name, "plan": plan, "matched": bool(acc)}


def _fmt_date(iso: Optional[str]) -> str:
    """'2026-09-26T07:54:23Z' -> '26 September 2026' (UTC)."""
    try:
        return datetime.strptime((iso or "")[:10], "%Y-%m-%d").strftime("%-d %B %Y")
    except Exception:
        return "the end of your current billing period"


def billing_email(kind: str, to: str, plan: str, ends_at: Optional[str] = None, api_key: Optional[str] = None) -> tuple[str, str]:
    """Customer-facing billing mails: welcome / canceled / ended / refunded. Returns (subject, text)."""
    name, limit = PLAN_NAMES.get(plan, plan.title()), PLAN_LIMITS.get(plan, 3)
    sig = "\n\nKeith\nRunVouch - the watchdog for unattended AI agents\nhttps://runvouch.com  |  support@runvouch.com"
    if kind == "welcome":
        key_block = (f"\n\nYour API key (shown only here - store it now):\n\n    {api_key}\n\nSet it as RUNVOUCH_KEY wherever your agents run." if api_key
                     else "\n\nYour existing API key keeps working; the new limit is already active.")
        return (f"Welcome to RunVouch {name}",
                f"Hi,\n\nThank you for subscribing to RunVouch {name}. Your account now covers up to {limit} agents, with all eight detectors, "
                f"{'90-day' if plan == 'solo' else '90-day'} history and the weekly cost report.{key_block}\n\n"
                f"Getting started:\n  - Dashboard: https://runvouch.com/app\n  - Docs: https://runvouch.com/docs\n  - Wrap a job: rv run NAME --evidence-file OUT -- your-command\n\n"
                f"Your receipt comes separately from Polar, our merchant of record. Manage or cancel any time from the link in that receipt.\n\n"
                f"If anything is unclear, reply to this mail - it reaches a person." + sig)
    if kind == "signup":
        return ("Your RunVouch key and a 2-minute start",
                f"Hi,\n\nWelcome to RunVouch. Your account is on the Free plan: 3 agents, all eight detectors, alerts via Telegram, Slack, e-mail or webhook.\n\n"
                f"Your API key (keep it private):\n\n    {api_key}\n\n"
                f"Start in two minutes:\n  1. pip install runvouch   (or: npm install -g runvouch)\n  2. export RUNVOUCH_KEY={api_key}\n"
                f"  3. rv run nightly-report --evidence-file out/report.html -- your-command\n\n"
                f"Then set where alerts go: https://runvouch.com/app (paste the key). Docs per runtime: https://runvouch.com/docs\n\n"
                f"Lost the key later? Enter the same e-mail on runvouch.com again and a fresh one is mailed to you. Questions: reply to this mail." + sig)
    if kind == "key":
        return ("Your new RunVouch key",
                f"Hi,\n\nYou asked for a key with an address that already has a RunVouch account ({name} plan). Here is a fresh one; the previous key no longer works:\n\n    {api_key}\n\n"
                f"Set it as RUNVOUCH_KEY wherever your agents run, and paste it in https://runvouch.com/app. If you did not request this, reply to this mail." + sig)
    if kind == "canceled":
        return (f"Your RunVouch {name} subscription is canceled",
                f"Hi,\n\nWe have received your cancellation. Your RunVouch {name} plan stays fully active until {_fmt_date(ends_at)}; "
                f"after that your account moves to the Free plan (3 agents, all detectors) - nothing is deleted and your key keeps working.\n\n"
                f"Changed your mind? You can resume from the link in your Polar receipt before that date and nothing changes.\n\n"
                f"Thank you for using RunVouch. If something made you leave, we would honestly like to know - just reply to this mail. We hope to see you again." + sig)
    if kind == "ended":
        return (f"Your RunVouch {name} plan has ended",
                f"Hi,\n\nYour RunVouch {name} subscription ended today. Your account is now on the Free plan: 3 agents, all eight detectors, 7-day history. "
                f"Your API key and agents are untouched; if you have more than 3 agents, the oldest 3 stay monitored.\n\n"
                f"Thank you for the time you spent with us. Whenever your agents outgrow the free plan again, upgrading takes one click: https://runvouch.com/pricing\n\n"
                f"We hope to see you again." + sig)
    if kind == "refunded":
        return ("Your RunVouch refund is on its way",
                f"Hi,\n\nWe have refunded your RunVouch {name} payment in full. Polar processes the refund; it usually shows on your card within 5-10 business days.\n\n"
                f"Your account is on the Free plan and keeps working. Sorry it did not fit - if you tell us why, we will use it." + sig)
    return ("RunVouch", "")


def _send_billing(kind: str, to: str, plan: str, ends_at: Optional[str] = None, api_key: Optional[str] = None) -> None:
    subject, text = billing_email(kind, to, plan, ends_at, api_key)
    if text:
        threading.Thread(target=_email, args=(to, subject, text, BILLING_FROM), daemon=True).start()


def _polar_sig_ok(raw: bytes, headers) -> bool:
    """Standard Webhooks (Polar): webhook-id / webhook-timestamp / webhook-signature "v1,<base64>",
    HMAC-SHA256 over "<id>.<timestamp>.<raw>" with the base64 secret (whsec_ prefix stripped)."""
    import base64
    wid, ts, sigs = headers.get("webhook-id", ""), headers.get("webhook-timestamp", ""), headers.get("webhook-signature", "")
    if not wid or not ts or not sigs or abs(time.time() - float(ts)) > 300:
        return False
    # Polar signs with the secret's raw bytes (it base64-encodes the secret itself before handing it to
    # standardwebhooks); a whsec_-prefixed secret is base64 per the Standard Webhooks spec. Accept both.
    secret = POLAR_WEBHOOK_SECRET[6:] if POLAR_WEBHOOK_SECRET.startswith("whsec_") else POLAR_WEBHOOK_SECRET
    keys = [POLAR_WEBHOOK_SECRET.encode(), secret.encode()]
    try:
        keys.append(base64.b64decode(secret + "=" * (-len(secret) % 4)))
    except Exception:
        pass
    msg = f"{wid}.{ts}.".encode() + raw
    given = [s.split(",", 1)[1] for s in sigs.split() if s.startswith("v1,")]
    for key in keys:
        expected = base64.b64encode(hmac.new(key, msg, hashlib.sha256).digest()).decode()
        if any(hmac.compare_digest(expected, g) for g in given):
            return True
    return False


@app.post("/webhooks/polar")
async def polar_webhook(request: Request):
    """Polar.sh (merchant of record) → plan changes. Product ids map to plans via POLAR_PRODUCT_PLANS."""
    raw = await request.body()
    if not POLAR_WEBHOOK_SECRET:
        raise HTTPException(503, "POLAR_WEBHOOK_SECRET not configured")
    if not _polar_sig_ok(raw, request.headers):
        raise HTTPException(401, "bad signature")
    ev = json.loads(raw or b"{}")
    name, ev_id = ev.get("type", ""), "polar:" + request.headers.get("webhook-id", "")
    if q1("SELECT id FROM ls_events WHERE id=?", ev_id):
        return {"ok": True, "dup": True}
    obj = ev.get("data") or {}
    cust = obj.get("customer") or {}
    customer = str(cust.get("id") or obj.get("customer_id") or "")
    email = (cust.get("email") or obj.get("customer_email") or obj.get("user", {}).get("email") or "").lower().strip()
    product = str(obj.get("product_id") or (obj.get("product") or {}).get("id") or "")
    sub_id = str(obj.get("subscription_id") or (obj.get("id") if name.startswith("subscription.") else "") or "") or None
    plan = None
    if name in ("order.paid", "order.created") and obj.get("status", "paid") in ("paid", "") and obj.get("billing_reason", "purchase") != "subscription_cycle":
        plan = POLAR_PRODUCT_PLANS.get(product, "solo") if obj.get("paid", True) else None
    elif name in ("subscription.active", "subscription.created", "subscription.updated", "subscription.uncanceled"):
        st = obj.get("status", "active")
        if st in ("active", "trialing", "past_due"):
            plan = POLAR_PRODUCT_PLANS.get(product)
        elif st in ("canceled", "unpaid", "incomplete_expired") and not obj.get("ends_at"):
            plan = "free"
    elif name in ("subscription.revoked",) or (name == "subscription.canceled" and obj.get("status") == "canceled" and not obj.get("current_period_end")):
        plan = "free"
    elif name == "order.refunded" and (obj.get("refunded_amount") or 0) >= (obj.get("total_amount") or obj.get("amount") or 1):
        plan = "free"  # full refund: access ends now, whatever the subscription says
    acc = (q1("SELECT * FROM accounts WHERE email=?", email) if email else None) or \
          (q1("SELECT * FROM accounts WHERE polar_customer_id=?", customer) if customer else None)
    new_key, mail = None, None
    with tx() as db:
        db.execute("INSERT INTO ls_events(id, ts, name, payload) VALUES(?,?,?,?)", (ev_id, time.time(), name, raw.decode(errors="ignore")[:20000]))
        if plan and acc:
            db.execute("UPDATE accounts SET plan=?, polar_customer_id=COALESCE(?,polar_customer_id), polar_subscription_id=COALESCE(?,polar_subscription_id) WHERE id=?",
                       (plan, customer or None, sub_id, acc["id"]))
        elif plan and plan != "free" and email and not acc:
            new_key = "rv_" + secrets.token_urlsafe(24)
            db.execute("INSERT INTO accounts(name, api_key, created, plan, email, polar_customer_id, polar_subscription_id) VALUES(?,?,?,?,?,?,?)",
                       (email.split("@")[0], key_hash(new_key), time.time(), plan, email, customer or None, sub_id))
    # customer mails: one per lifecycle moment, never on renewals or on no-op updates
    to = email or (acc["email"] if acc else None)
    old_plan = acc["plan"] if acc else "free"
    if to:
        if name == "order.paid" and plan and plan != "free" and (new_key or plan != old_plan):
            mail = ("welcome", plan, None, new_key)
        elif name == "subscription.canceled" and obj.get("cancel_at_period_end"):
            mail = ("canceled", POLAR_PRODUCT_PLANS.get(product, old_plan), obj.get("ends_at") or obj.get("current_period_end"), None)
        elif name == "subscription.revoked":
            mail = ("ended", POLAR_PRODUCT_PLANS.get(product, old_plan), None, None)
        # refunds: Polar's receipt already confirms it; no second mail from us
    if mail:
        _send_billing(mail[0], to, mail[1], mail[2], mail[3])
    return {"ok": True, "event": name, "plan": plan, "matched": bool(acc), "mail": mail[0] if mail else None}


@app.put("/v1/settings")
def put_settings(s: SettingsIn, acc=Depends(account_from_key)):
    if s.pagerduty_routing_key:
        require_plan(acc, "team", "PagerDuty")
    if s.slack_webhook_url and not s.slack_webhook_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(422, "slack_webhook_url must be a Slack incoming webhook (https://hooks.slack.com/services/...)")
    with tx() as db:
        db.execute("UPDATE accounts SET telegram_token=COALESCE(?,telegram_token), telegram_chat=COALESCE(?,telegram_chat), "
                   "webhook_url=COALESCE(?,webhook_url), alert_email=COALESCE(?,alert_email), slack_webhook_url=COALESCE(?,slack_webhook_url), "
                   "pagerduty_routing_key=COALESCE(?,pagerduty_routing_key) WHERE id=?",
                   (s.telegram_token, s.telegram_chat, s.webhook_url, s.alert_email, s.slack_webhook_url, s.pagerduty_routing_key, acc["id"]))
    return {"ok": True}


@app.post("/v1/settings/test-alert")
def test_alert(acc=Depends(account_from_key)):
    a = q1("SELECT * FROM agents WHERE account_id=? LIMIT 1", acc["id"])
    if not a:
        raise HTTPException(400, "create an agent first")
    raise_alert(acc["id"], a["id"], None, "TEST", "RunVouch alert channel works.")
    return {"ok": True}


@app.post("/v1/agents")
def upsert_agent(a: AgentIn, acc=Depends(account_from_key)):
    n = q1("SELECT COUNT(*) n FROM agents WHERE account_id=?", acc["id"])["n"]
    exists = q1("SELECT id FROM agents WHERE account_id=? AND name=?", acc["id"], a.name)
    if not exists and n >= PLAN_LIMITS.get(acc["plan"], 3):
        raise HTTPException(402, f"plan '{acc['plan']}' allows {PLAN_LIMITS.get(acc['plan'],3)} agents")
    with tx() as db:
        db.execute("""INSERT INTO agents(account_id,name,created,cadence_s,grace_s,max_runtime_s,cap_run_cost,cap_day_cost,cap_run_tokens,evidence_required)
                      VALUES(?,?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(account_id,name) DO UPDATE SET cadence_s=excluded.cadence_s, grace_s=excluded.grace_s,
                      max_runtime_s=excluded.max_runtime_s, cap_run_cost=excluded.cap_run_cost, cap_day_cost=excluded.cap_day_cost,
                      cap_run_tokens=excluded.cap_run_tokens, evidence_required=excluded.evidence_required""",
                   (acc["id"], a.name, time.time(), a.cadence_s, a.grace_s, a.max_runtime_s, a.cap_run_cost, a.cap_day_cost,
                    a.cap_run_tokens, int(a.evidence_required)))
    return {"ok": True, "agent": a.name}


@app.get("/v1/agents")
def list_agents(acc=Depends(account_from_key)):
    out = []
    for a in qa("SELECT * FROM agents WHERE account_id=? ORDER BY name", acc["id"]):
        last = q1("SELECT * FROM runs WHERE agent_id=? ORDER BY started DESC LIMIT 1", a["id"])
        open_alerts = q1("SELECT COUNT(*) n FROM alerts WHERE agent_id=? AND acked=0", a["id"])["n"]
        cost24 = q1("SELECT COALESCE(SUM(cost),0) s FROM runs WHERE agent_id=? AND started>?", a["id"], time.time() - 86400)["s"]
        out.append({"name": a["name"], "cadence_s": a["cadence_s"], "paused": bool(a["paused"]),
                    "last_run": dict(last) if last else None, "open_alerts": open_alerts, "cost_24h": round(cost24, 4),
                    "state": _state(a, last, open_alerts)})
    return out


def _state(a, last, open_alerts) -> str:
    if a["paused"]:
        return "paused"
    if open_alerts:
        return "alert"
    if not last:
        return "waiting"
    if last["ended"] is None:
        return "running"
    if last["status"] != "ok":
        return "failed"
    if a["evidence_required"] and not last["evidence_ok"]:
        return "unproven"
    return "ok"


@app.post("/v1/runs/start")
def run_start(s: StartIn, acc=Depends(account_from_key)):
    a = _agent(acc, s.agent)
    rid = s.run_id or secrets.token_hex(8)
    now = time.time()
    with tx() as db:
        db.execute("INSERT OR REPLACE INTO runs(id,agent_id,started,last_seen,status,meta_json,source) VALUES(?,?,?,?,?,?,?)",
                   (rid, a["id"], now, now, "running", json.dumps(s.meta), s.source))
    return {"run_id": rid}


@app.post("/v1/runs/tool")
def run_tool(t: ToolIn, acc=Depends(account_from_key)):
    run = q1("SELECT * FROM runs WHERE id=?", t.run_id)
    if not run:
        raise HTTPException(404, "run not found")
    a = q1("SELECT * FROM agents WHERE id=?", run["agent_id"])
    h = t.input_hash or hashlib.sha1(json.dumps(t.input, sort_keys=True, default=str).encode()).hexdigest()[:16]
    with tx() as db:
        db.execute("INSERT INTO tool_events(run_id,ts,tool,input_hash,ok,cost,tokens) VALUES(?,?,?,?,?,?,?)",
                   (t.run_id, time.time(), t.tool, h, int(t.ok), t.cost, t.tokens))
        db.execute("UPDATE runs SET tool_calls=tool_calls+1, cost=cost+?, tokens=tokens+?, last_seen=? WHERE id=?",
                   (t.cost, t.tokens, time.time(), t.run_id))
    check_storm(a, t.run_id, h, t.tool)
    run = q1("SELECT * FROM runs WHERE id=?", t.run_id)
    check_budget(a, run)
    return {"ok": True}


@app.post("/v1/runs/heartbeat")
def run_heartbeat(run_id: str, acc=Depends(account_from_key)):
    with tx() as db:
        db.execute("UPDATE runs SET last_seen=? WHERE id=?", (time.time(), run_id))
    return {"ok": True}


@app.post("/v1/runs/end")
def run_end(e: EndIn, acc=Depends(account_from_key)):
    run = q1("SELECT * FROM runs WHERE id=?", e.run_id)
    if not run:
        raise HTTPException(404, "run not found")
    a = q1("SELECT * FROM agents WHERE id=?", run["agent_id"])
    ev_ok, ev_detail = evaluate_evidence(e.evidence)
    if a["evidence_required"] and not e.evidence:
        ev_ok = False
        ev_detail = {"_": "evidence required but none supplied"}
    with tx() as db:
        db.execute("UPDATE runs SET ended=?, last_seen=?, status=?, cost=cost+?, tokens=tokens+?, output_bytes=?, evidence_ok=?, "
                   "evidence_json=?, meta_json=? WHERE id=?",
                   (time.time(), time.time(), e.status, e.cost, e.tokens, e.output_bytes, int(ev_ok), json.dumps(ev_detail),
                    json.dumps({**json.loads(run["meta_json"] or "{}"), **e.meta}), e.run_id))
    run = q1("SELECT * FROM runs WHERE id=?", e.run_id)
    with tx() as db:  # the leaf is fixed here and never rewritten; the day seal later includes it
        db.execute("UPDATE runs SET leaf_hash=? WHERE id=?", (_pf.leaf_hash(leaf_record(run, a)), e.run_id))
    if e.status != "ok":
        # a retry started by the remediator reports its own outcome (Hersteld / heeft jou nodig); a second FAILED for
        # the same story every 15 minutes is noise, so it is stored but not sent
        raise_alert(a["account_id"], a["id"], e.run_id, "FAILED", f"run ended with status '{e.status}'. {e.meta.get('error','')}".strip(),
                    quiet=(run["source"] == "remediator"))
    elif (a["evidence_required"] or e.evidence) and not ev_ok:
        failed = [k for k, v in ev_detail.items() if v is not True]
        raise_alert(a["account_id"], a["id"], e.run_id, "NO_EVIDENCE",
                    f"run reported ok but evidence failed: {failed}. Green run ≠ done task.")
    check_budget(a, run)
    if e.status == "ok":
        check_drift(a, run)
    return {"ok": True, "evidence_ok": ev_ok, "evidence": ev_detail}


@app.get("/v1/alerts")
def list_alerts(acked: bool = False, acc=Depends(account_from_key)):
    return [dict(r) for r in qa("SELECT a.*, g.name agent FROM alerts a JOIN agents g ON g.id=a.agent_id WHERE a.account_id=? AND a.acked=? "
                                "ORDER BY a.ts DESC LIMIT 200", acc["id"], int(acked))]


@app.post("/v1/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, acc=Depends(account_from_key)):
    a = q1("SELECT a.kind, a.acked, g.name FROM alerts a JOIN agents g ON g.id=a.agent_id WHERE a.id=? AND a.account_id=?", alert_id, acc["id"])
    with tx() as db:
        db.execute("UPDATE alerts SET acked=1 WHERE id=? AND account_id=?", (alert_id, acc["id"]))
    if a and not a["acked"] and acc["pagerduty_routing_key"] and acc["plan"] == "team" and a["kind"] in PD_KINDS:
        threading.Thread(target=_pagerduty, args=(acc["pagerduty_routing_key"], "resolve", pd_dedup_key(a["name"], a["kind"])), daemon=True).start()
    return {"ok": True}


# ───────────────────────────── Team: export and viewer keys ─────────────────────────────
EXPORT_COLS = ("agent", "run_id", "started", "ended", "status", "cost", "tokens", "tool_calls", "evidence_ok", "leaf_hash")


def _export_rows(account_id: int, t0: float, t1: float):
    with _lock:
        cur = _db.execute("SELECT g.name agent, r.id run_id, r.started, r.ended, r.status, r.cost, r.tokens, r.tool_calls, r.evidence_ok, r.leaf_hash "
                          "FROM runs r JOIN agents g ON g.id=r.agent_id WHERE g.account_id=? AND r.started>=? AND r.started<? ORDER BY r.started", (account_id, t0, t1))
        while True:
            rows = cur.fetchmany(500)
            if not rows:
                return
            for r in rows:
                yield r


@app.get("/v1/export")
def export_runs(from_: str = Query(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"), to: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
                format: str = "json", acc=Depends(account_from_key)):
    """Team: every run of the account with started in [from, to] (UTC days), streamed as CSV or a JSON array."""
    from fastapi.responses import StreamingResponse
    require_plan(acc, "team", "API export")
    if format not in ("csv", "json"):
        raise HTTPException(422, "format must be csv or json")
    try:
        t0, t1 = _day_ts(from_), _day_ts(to) + 86400
    except ValueError:
        raise HTTPException(422, "from/to must be valid dates (YYYY-MM-DD)")
    if t1 <= t0:
        raise HTTPException(422, "to must not be before from")

    def csv_gen():
        import csv, io
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(EXPORT_COLS); yield buf.getvalue(); buf.seek(0); buf.truncate()
        for r in _export_rows(acc["id"], t0, t1):
            w.writerow([r[k] for k in EXPORT_COLS]); yield buf.getvalue(); buf.seek(0); buf.truncate()

    def json_gen():
        yield "["
        first = True
        for r in _export_rows(acc["id"], t0, t1):
            yield ("" if first else ",\n") + json.dumps({k: r[k] for k in EXPORT_COLS})
            first = False
        yield "]\n"

    fname = f"runvouch-{from_}-{to}.{format}"
    return StreamingResponse(csv_gen() if format == "csv" else json_gen(), media_type="text/csv" if format == "csv" else "application/json",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


class ViewerKeyIn(BaseModel):
    name: str = Field("viewer", min_length=1, max_length=64)


@app.post("/v1/me/viewer-keys")
def create_viewer_key(body: ViewerKeyIn = ViewerKeyIn(), acc=Depends(account_from_key)):
    """Team: a read-only key (rvv_) for a shared dashboard. Can GET and ack alerts; nothing else. Shown once."""
    require_plan(acc, "team", "Shared dashboard (viewer keys)")
    key = "rvv_" + secrets.token_urlsafe(24)
    with tx() as db:
        cur = db.execute("INSERT INTO viewer_keys(account_id, key_hash, name, created) VALUES(?,?,?,?)", (acc["id"], key_hash(key), body.name, time.time()))
    return {"id": cur.lastrowid, "name": body.name, "viewer_key": key, "note": "read-only: GET /v1/agents, /v1/runs, /v1/alerts, /v1/export and the dashboard, plus alert ack. Shown once."}


@app.get("/v1/me/viewer-keys")
def list_viewer_keys(acc=Depends(account_from_key)):
    require_plan(acc, "team", "Shared dashboard (viewer keys)")
    return [dict(r) for r in qa("SELECT id, name, created, last_used FROM viewer_keys WHERE account_id=? ORDER BY id", acc["id"])]


@app.delete("/v1/me/viewer-keys/{key_id}")
def delete_viewer_key(key_id: int, acc=Depends(account_from_key)):
    with tx() as db:
        n = db.execute("DELETE FROM viewer_keys WHERE id=? AND account_id=?", (key_id, acc["id"])).rowcount
    if not n:
        raise HTTPException(404, "viewer key not found")
    return {"ok": True, "revoked": key_id}


@app.post("/v1/agents/{name}/pause")
def pause_agent(name: str, paused: bool = True, acc=Depends(account_from_key)):
    a = _agent(acc, name)
    with tx() as db:
        db.execute("UPDATE agents SET paused=? WHERE id=?", (int(paused), a["id"]))
    return {"ok": True}


@app.delete("/v1/agents/{name}")
def delete_agent(name: str, acc=Depends(account_from_key)):
    a = _agent(acc, name)
    with tx() as db:
        db.execute("DELETE FROM tool_events WHERE run_id IN (SELECT id FROM runs WHERE agent_id=?)", (a["id"],))
        db.execute("DELETE FROM runs WHERE agent_id=?", (a["id"],)); db.execute("DELETE FROM alerts WHERE agent_id=?", (a["id"],)); db.execute("DELETE FROM agents WHERE id=?", (a["id"],))
    return {"ok": True, "deleted": name}


@app.get("/v1/agents/{name}/runs")
def agent_runs(name: str, limit: int = 30, acc=Depends(account_from_key)):
    a = _agent(acc, name)
    return [dict(r) for r in qa("SELECT * FROM runs WHERE agent_id=? ORDER BY started DESC LIMIT ?", a["id"], limit)]


@app.get("/v1/runs/{run_id}/proof")
def run_proof_api(run_id: str, acc=Depends(account_from_key)):
    run = q1("SELECT r.* FROM runs r JOIN agents g ON g.id=r.agent_id WHERE r.id=? AND g.account_id=?", run_id, acc["id"])
    if not run:
        purged = q1("SELECT l.*, g.name agent FROM run_leaves l JOIN agents g ON g.id=l.agent_id WHERE l.id=? AND g.account_id=?", run_id, acc["id"])
        if not purged:
            raise HTTPException(404, "run not found")
        return purged_proof(purged)
    if run["ended"] is None or not run["leaf_hash"]:
        raise HTTPException(409, "run has not ended; a proof exists only for finished runs")
    return run_proof(run, q1("SELECT * FROM agents WHERE id=?", run["agent_id"]))


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@app.get("/proof/")
def proof_index(limit: int = 30):
    """Public: the chain, newest first. No auth, no account data; only dates, hashes and counts."""
    days = [dict(r) for r in qa("SELECT date, root, prev, chain_hash, n_runs, sealed_at, ots_status FROM proof_days ORDER BY date DESC LIMIT ?", min(limit, 400))]
    return {"days": days, "day_url": f"{PUBLIC_URL}/proof/days/YYYY-MM-DD.json", "ots_url": f"{PUBLIC_URL}/proof/days/YYYY-MM-DD.ots",
            "spec": "leaf=sha256(canonical_json(record)); root=merkle over the day's leaves sorted by run_id; chain_hash=sha256(prev+':'+date+':'+root); genesis prev=64 zeros",
            "verify": "https://runvouch.com/docs/proof"}


@app.get("/proof/days/{name}")
def proof_day_file(name: str):
    from fastapi.responses import FileResponse
    date, ext = name[:10], name[10:]
    if not _DATE_RE.match(date) or ext not in (".json", ".ots"):
        raise HTTPException(404, "not found")
    day = q1("SELECT ots_path FROM proof_days WHERE date=?", date)
    if not day:
        raise HTTPException(404, "day not sealed")
    p = Path(day["ots_path"]) if ext == ".json" else Path(day["ots_path"] + ".ots")
    if not p.is_file():
        raise HTTPException(404, "no OpenTimestamps file for this day" if ext == ".ots" else "day file missing")
    return FileResponse(p, media_type="application/json" if ext == ".json" else "application/octet-stream",
                        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"})


# ───────────────────────────── remote MCP (Streamable HTTP, JSON-RPC 2.0) ─────────────────────────────
MCP_TOOLS = [
    {"name": "runvouch_status", "description": "Health of all watched agents: state (ok/alert/failed/unproven/running/waiting), last run, 24h cost, open alerts.", "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_alerts", "description": "Open (un-acknowledged) alerts: MISSED, FAILED, NO_EVIDENCE, BUDGET_RUN, BUDGET_DAY, RETRY_STORM, DRIFT, STALLED.", "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_ack", "description": "Acknowledge an alert by id.", "inputSchema": {"type": "object", "properties": {"alert_id": {"type": "integer"}}, "required": ["alert_id"]}},
    {"name": "runvouch_runs", "description": "Recent runs of one agent.", "inputSchema": {"type": "object", "properties": {"agent": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["agent"]}, "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_run_start", "description": "Report that a run of `agent` started. Returns run_id.", "inputSchema": {"type": "object", "properties": {"agent": {"type": "string"}, "source": {"type": "string"}}, "required": ["agent"]}},
    {"name": "runvouch_run_end", "description": "Report that a run ended, with status and evidence dict (name -> bool or {type:'url',url}). Green run without evidence alerts.", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}, "status": {"type": "string", "enum": ["ok", "fail"]}, "cost": {"type": "number"}, "tokens": {"type": "integer"}, "evidence": {"type": "object"}}, "required": ["run_id"]}},
    {"name": "runvouch_run_proof", "description": "Tamper-evident proof of a finished run: hashed record, Merkle path, day root, chain hash and OpenTimestamps status. Verify offline with templates/verify_proof.py.", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}, "annotations": {"readOnlyHint": True}},
]


def _mcp_call(acc, name: str, a: dict):
    if name == "runvouch_status":
        return list_agents(acc)
    if name == "runvouch_alerts":
        return list_alerts(False, acc)
    if name == "runvouch_ack":
        return ack_alert(int(a["alert_id"]), acc)
    if name == "runvouch_runs":
        return agent_runs(a["agent"], int(a.get("limit", 20)), acc)
    if name == "runvouch_run_start":
        return run_start(StartIn(agent=a["agent"], source=a.get("source", "mcp")), acc)
    if name == "runvouch_run_end":
        return run_end(EndIn(run_id=a["run_id"], status=a.get("status", "ok"), cost=a.get("cost", 0), tokens=a.get("tokens", 0), evidence=a.get("evidence", {})), acc)
    if name == "runvouch_run_proof":
        return run_proof_api(a["run_id"], acc)
    raise ValueError(f"unknown tool {name}")


@app.post("/mcp")
async def mcp_http(request: Request):
    """Remote MCP endpoint. Auth: X-API-Key or Authorization: Bearer <key>. One JSON-RPC message per request."""
    key = request.headers.get("x-api-key") or request.headers.get("authorization", "").replace("Bearer ", "").strip()
    try:
        msg = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}, status_code=400)
    mid, m, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if m == "initialize":
        return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}}, "serverInfo": {"name": "runvouch", "version": "0.3.0"}}})
    if m in ("notifications/initialized", "ping"):
        return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {}}) if mid is not None else PlainTextResponse("", status_code=202)
    if m == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {"tools": MCP_TOOLS}})
    if m == "tools/call":
        try:
            acc = account_from_key(key)
            if is_viewer(acc) and p["name"] not in ("runvouch_status", "runvouch_alerts", "runvouch_ack", "runvouch_runs", "runvouch_run_proof"):
                raise HTTPException(403, "viewer key: read-only")
            out = _mcp_call(acc, p["name"], p.get("arguments") or {})
            return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(out, indent=1, default=str)}]}})
        except HTTPException as e:
            return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": f"error {e.status_code}: {e.detail}"}], "isError": True}})
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}})
    return JSONResponse({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {m}"}})


@app.get("/mcp")
def mcp_info():
    return {"name": "runvouch", "transport": "streamable-http", "endpoint": PUBLIC_URL + "/mcp", "auth": "X-API-Key or Bearer", "tools": [t["name"] for t in MCP_TOOLS], "docs": "https://runvouch.com/docs/mcp"}


# ───────────────────────────── minimal dashboard ─────────────────────────────
DASH = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>RunVouch dashboard</title><meta name="robots" content="noindex"><meta name="description" content="RunVouch dashboard: your agents, their last runs, evidence and open alerts. Sign in with your API key.">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@600;700&family=Figtree:wght@400;500;600&family=Geist+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>:root{--bg:#0B1020;--bg3:#141B33;--line:rgba(169,180,214,.14);--fg:#EEF2FF;--fg2:#A9B4D6;--fg3:#6F7A9E;--grad:#4C8DFF}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 Figtree,system-ui,sans-serif}a{color:#8FB6FF}
.top{display:flex;align-items:center;gap:1rem;padding:0 1.5rem;height:64px;border-bottom:1px solid var(--line);background:rgba(7,7,11,.8);position:sticky;top:0}.top b{font-family:"Instrument Sans";font-size:1.15rem}.top a{margin-left:auto;color:var(--fg2)}
.wrap{max-width:1100px;margin:0 auto;padding:1.5rem}h2{font-family:"Instrument Sans";font-size:1.3rem;margin:1.5rem 0 .6rem}
input{padding:.7rem .9rem;width:26rem;max-width:100%;border:1px solid var(--line);border-radius:10px;background:#040308;color:var(--fg);font:inherit}button{background:var(--grad);border:0;color:#fff;font-weight:700;padding:.7rem 1rem;border-radius:10px;cursor:pointer;font:inherit}
table{border-collapse:collapse;width:100%;background:var(--bg3);border:1px solid var(--line);border-radius:12px;overflow:hidden}td,th{padding:.6rem .8rem;border-bottom:1px solid var(--line);text-align:left;font-size:.92rem}th{font-family:"Geist Mono";font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--fg2)}tr:last-child td{border:0}
.pill{font-family:"Geist Mono";font-size:.7rem;font-weight:700;padding:.2rem .55rem;border-radius:6px;letter-spacing:.06em;text-transform:uppercase}.ok{background:rgba(62,207,142,.14);color:#3ECF8E}.alert,.failed,.unproven{background:rgba(255,77,77,.14);color:#FF7A7A}.running{background:rgba(76,141,255,.18);color:#8FB6FF}.waiting,.paused{background:rgba(255,255,255,.06);color:var(--fg3)}
.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1rem 0}.kpi div{background:var(--bg3);border:1px solid var(--line);border-radius:12px;padding:.9rem 1rem}.kpi b{display:block;font-family:"Instrument Sans";font-size:1.6rem}.kpi span{color:var(--fg2);font-size:.85rem}
small{color:var(--fg3)}.err{color:#FF7A7A}@media(max-width:800px){.kpi{grid-template-columns:1fr 1fr}}</style></head><body>
<div class=top><b>RunVouch</b> <small>dashboard</small><a href="https://runvouch.com/docs/">Docs</a></div><div class=wrap>
<div id=upg style="display:none;border:1px solid #2f6b3a;background:rgba(46,160,67,.12);border-radius:10px;padding:.8rem 1rem;margin:0 0 1rem"><b>Thanks, your upgrade is in.</b> Paste the API key you got at signup to see the new agent limit. Lost it? Use <a href="/contact?topic=billing">contact</a> with the email you paid with and we will rotate it for you.</div><p><input id=k type=password placeholder="paste your API key (rv_…)" autocomplete="off"> <button onclick="load()">Load</button> <button onclick="signout()" style="background:transparent;border:1px solid var(--line);color:var(--fg2)">Sign out</button> <small id=me></small></p><p><small>Your key is kept only in this browser (local storage). Sign out removes it. Nobody else can see your agents without your key.</small></p>
<div id=out></div><div id=cfg></div></div><script>
const API=location.hostname.startsWith('api.')||location.hostname==='localhost'||location.hostname==='127.0.0.1'?'':'https://api.runvouch.com';
const qk=new URLSearchParams(location.search).get('key');if(qk){try{localStorage.setItem('rvk',qk)}catch(e){}history.replaceState({},'',location.pathname)}
if(new URLSearchParams(location.search).get('upgraded')){document.getElementById('upg').style.display='block'}
function key(){return document.getElementById('k').value.trim()}
function hdr(){return {'X-API-Key':key(),'Content-Type':'application/json'}}
function esc(x){return String(x==null?'':x).replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]))}
async function load(){const k=key();try{localStorage.setItem('rvk',k)}catch(e){}
const h={'X-API-Key':k};let me,ag,al;try{me=await (await fetch(API+'/v1/me',{headers:h})).json();ag=await (await fetch(API+'/v1/agents',{headers:h})).json();al=await (await fetch(API+'/v1/alerts',{headers:h})).json()}catch(e){document.getElementById('out').innerHTML='<p class=err>Network error: '+e+'</p>';return}
if(!Array.isArray(ag)){document.getElementById('out').innerHTML='<p class=err>'+(ag.detail||'error')+'</p>';return}
document.getElementById('me').textContent=(me.email||me.name)+' · plan '+me.plan+' · '+ag.length+'/'+me.agents_allowed+' agents · '+me.history_days+'-day history'+(me.viewer?' · viewer (read-only)':'');
const cost=ag.reduce((a,x)=>a+(x.cost_24h||0),0);const bad=ag.filter(a=>['alert','failed','unproven'].includes(a.state)).length;
let s='<div class=kpi><div><b>'+ag.length+'</b><span>agents</span></div><div><b>'+ag.filter(a=>a.state==='ok').length+'</b><span>vouched</span></div><div><b>'+bad+'</b><span>need attention</span></div><div><b>$'+cost.toFixed(2)+'</b><span>cost 24h</span></div></div>';
s+='<h2>Agents</h2><table><tr><th>agent</th><th>state</th><th>last run</th><th>status</th><th>evidence</th><th>cost 24h</th><th>alerts</th><th>proof</th></tr>';
for(const a of ag.sort((x,y)=>(x.state==='ok')-(y.state==='ok'))){const l=a.last_run;s+=`<tr><td>${esc(a.name)}</td><td><span class="pill ${a.state}">${a.state}</span></td><td>${l?new Date(l.started*1000).toLocaleString():'-'}</td><td>${l?l.status:'-'}</td><td>${l?(l.evidence_ok===null?'-':l.evidence_ok?'✓':'✗'):'-'}</td><td>$${(a.cost_24h||0).toFixed(3)}</td><td>${a.open_alerts}</td><td>${l&&l.ended?`<a href="#" onclick="proof('${l.id}');return false">proof</a>`:'-'}</td></tr>`}
s+='</table><h2>Open alerts</h2>';if(!al.length)s+='<p><small>None. Quiet night.</small></p>';else{s+='<table><tr><th>when</th><th>agent</th><th>kind</th><th>message</th><th></th></tr>';for(const x of al){s+=`<tr><td><small>${new Date(x.ts*1000).toLocaleString()}</small></td><td>${esc(x.agent)}</td><td><span class="pill alert">${x.kind}</span></td><td>${esc(x.message)}</td><td><button onclick="ack(${x.id})">ack</button></td></tr>`}s+='</table>'}
document.getElementById('out').innerHTML=s;
if(me.viewer){document.getElementById('cfg').innerHTML='<p><small>Viewer key: you can read everything and ack alerts. Settings are managed with the account key.</small></p>';return}
const ch=me.channels||{};const team=me.plan==='team';const st=n=>ch[n]?' <span class="pill ok">set</span>':' <span class="pill waiting">not set</span>';
let f='<h2>Alert channels</h2><p><small>Every alert goes to every channel you fill in. Leave a field empty to keep its current value. Full list and settings calls: <a href="https://runvouch.com/docs/alerts">docs/alerts</a>.</small></p>';
f+='<p>E-mail'+st('email')+'<br><input id=s_alert_email type=email placeholder="you@company.com" autocomplete="off"></p>';
f+='<p>Telegram'+st('telegram')+'<br><input id=s_telegram_token placeholder="bot token (from @BotFather)" autocomplete="off"> <input id=s_telegram_chat placeholder="chat id" style="width:12rem" autocomplete="off"></p>';
f+='<p>Webhook (JSON POST)'+st('webhook')+'<br><input id=s_webhook_url type=url placeholder="https://..." autocomplete="off"></p>';
f+='<p>Slack incoming webhook'+st('slack')+'<br><input id=s_slack_webhook_url type=url placeholder="https://hooks.slack.com/services/..." autocomplete="off"></p>';
f+='<p>PagerDuty (Events API v2 routing key)'+(team?st('pagerduty'):' <span class="pill waiting">team plan</span>')+'<br><input id=s_pagerduty_routing_key placeholder="32-character integration key" autocomplete="off"'+(team?'':' disabled')+'>'+(team?'':' <small>MISSED, FAILED, STALLED and BUDGET alerts open an incident; ack here resolves it. <a href="https://runvouch.com/pricing">Team plan</a>.</small>')+'</p>';
f+='<p><button onclick="saveSettings()">Save channels</button> <button onclick="testAlert()" style="background:transparent;border:1px solid var(--line);color:var(--fg2)">Send test alert</button> <small id=cfgmsg></small></p>';
if(team){f+='<h2>Shared dashboard</h2><p><small>Viewer keys (rvv_) open this dashboard read-only: agents, runs, alerts, export and alert ack. No settings, no run reporting. Hand one to a teammate or paste it in a wall display.</small></p><div id=vk></div><p><input id=vkname placeholder="name (e.g. ops wall)" style="width:14rem"> <button onclick="newViewerKey()">Create viewer key</button> <small id=vkmsg></small></p>'}
document.getElementById('cfg').innerHTML=f;if(team)loadViewerKeys()}
async function saveSettings(){const b={};for(const n of ['alert_email','telegram_token','telegram_chat','webhook_url','slack_webhook_url','pagerduty_routing_key']){const e=document.getElementById('s_'+n);if(e&&e.value.trim())b[n]=e.value.trim()}
const r=await fetch(API+'/v1/settings',{method:'PUT',headers:hdr(),body:JSON.stringify(b)});const j=await r.json();document.getElementById('cfgmsg').textContent=r.ok?'saved':(j.detail||'error');if(r.ok)load()}
async function testAlert(){const r=await fetch(API+'/v1/settings/test-alert',{method:'POST',headers:hdr()});const j=await r.json();document.getElementById('cfgmsg').textContent=r.ok?'test alert queued for every configured channel':(j.detail||'error')}
async function loadViewerKeys(){const r=await fetch(API+'/v1/me/viewer-keys',{headers:hdr()});const ks=await r.json();if(!Array.isArray(ks)){document.getElementById('vk').innerHTML='<p class=err>'+esc(ks.detail)+'</p>';return}
if(!ks.length){document.getElementById('vk').innerHTML='<p><small>No viewer keys yet.</small></p>';return}
let s='<table><tr><th>id</th><th>name</th><th>created</th><th>last used</th><th></th></tr>';for(const k of ks){s+=`<tr><td>${k.id}</td><td>${esc(k.name)}</td><td><small>${new Date(k.created*1000).toLocaleString()}</small></td><td><small>${k.last_used?new Date(k.last_used*1000).toLocaleString():'never'}</small></td><td><button onclick="revokeViewerKey(${k.id})" style="background:transparent;border:1px solid var(--line);color:var(--fg2)">revoke</button></td></tr>`}document.getElementById('vk').innerHTML=s+'</table>'}
async function newViewerKey(){const name=document.getElementById('vkname').value.trim()||'viewer';const r=await fetch(API+'/v1/me/viewer-keys',{method:'POST',headers:hdr(),body:JSON.stringify({name})});const j=await r.json();document.getElementById('vkmsg').innerHTML=r.ok?'Shown once, store it now: <code>'+esc(j.viewer_key)+'</code>':esc(j.detail||'error');if(r.ok)loadViewerKeys()}
async function revokeViewerKey(id){await fetch(API+'/v1/me/viewer-keys/'+id,{method:'DELETE',headers:hdr()});loadViewerKeys()}
function signout(){try{localStorage.removeItem('rvk')}catch(e){}document.getElementById('k').value='';document.getElementById('out').innerHTML='';document.getElementById('cfg').innerHTML='';document.getElementById('me').textContent='signed out'}
async function proof(id){const r=await fetch(API+'/v1/runs/'+id+'/proof',{headers:{'X-API-Key':key()}});const t=await r.text();window.open(URL.createObjectURL(new Blob([t],{type:'application/json'})),'_blank')}
async function ack(id){await fetch(API+'/v1/alerts/'+id+'/ack',{method:'POST',headers:{'X-API-Key':key()}});load()}
try{const k=localStorage.getItem('rvk');if(k){document.getElementById('k').value=k;load()}}catch(e){}
</script></body></html>"""


SITE_DIR = Path(__file__).resolve().parent.parent / "site" / "public"
MARKETING_HOSTS = {"runvouch.com", "www.runvouch.com"}
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".png": "image/png",
        ".xml": "application/xml", ".txt": "text/plain; charset=utf-8", "": "text/plain; charset=utf-8"}


def _is_marketing(request: Request) -> bool:
    host = request.headers.get("host", "").split(":")[0]
    return host in MARKETING_HOSTS


def _serve_site(path: str):
    from fastapi.responses import FileResponse, RedirectResponse
    p = path.strip("/")
    cand = [SITE_DIR / p / "index.html", SITE_DIR / (p + ".html"), SITE_DIR / p] if p else [SITE_DIR / "index.html"]
    for f in cand:
        try:
            f.resolve().relative_to(SITE_DIR.resolve())
        except ValueError:
            break
        if f.is_file():
            ext = f.suffix.lower()
            headers = {"Cache-Control": "public, max-age=31536000, immutable" if ext in (".css", ".png", ".svg") else "public, max-age=300"}
            if f.name == "rv":
                headers["Content-Disposition"] = "inline; filename=rv"
            return FileResponse(f, media_type=MIME.get(ext, "application/octet-stream"), headers=headers)
    nf = SITE_DIR / "404.html"
    if nf.exists():
        return HTMLResponse(nf.read_text(encoding="utf-8"), status_code=404, headers={"X-Robots-Tag": "noindex"})
    return HTMLResponse('<!doctype html><meta charset=utf-8><title>Not found | RunVouch</title><body style="font:16px system-ui;margin:4rem auto;max-width:40rem"><h1>404</h1><p>Nothing here. Try the <a href="/">home page</a>, <a href="/docs/">docs</a> or <a href="/app">dashboard</a>.</p>', status_code=404)


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """runvouch.com → landing site; api.runvouch.com / localhost → dashboard."""
    if _is_marketing(request):
        if request.headers.get("host", "").startswith("www."):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(PUBLIC_URL.replace("api.", "") + "/", status_code=301)
        return _serve_site("")
    return DASH


@app.get("/app", response_class=HTMLResponse)
def dashboard():
    return DASH


@app.get("/openapi-lite")
def openapi_lite():
    return JSONResponse({"base": PUBLIC_URL, "auth": "X-API-Key", "endpoints": [r.path for r in app.routes if r.path.startswith("/v1")]})


@app.get("/{path:path}", include_in_schema=False)
def site_catchall(path: str, request: Request):
    if _is_marketing(request):
        return _serve_site(path)
    raise HTTPException(404, "not found")
