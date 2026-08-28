#!/usr/bin/env python3
"""statuswacht.py: the watchdog for the status page itself.

runvouch.com/status is the shop window: it must always resolve, always green, always fresh. RunVouch cannot vouch
for itself when it is down, so this runs OUTSIDE it: a plain systemd timer every minute, no rv run, its own
Telegram path. It checks from the public side (through Cloudflare, like a visitor), repairs what it can (restart
the API or the tunnel, at most once per 30 minutes per component), and sends one Telegram line only when a repair
happened or when something stays broken. Every :00 and :30 it also renders the page in a headless browser and
requires every status cell to be green. State in data/statuswacht.json, log in data/statuswacht.log.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "statuswacht.json")
PUBLIC_API = "https://api.runvouch.com"
LOCAL_API = "http://127.0.0.1:8787"
SITE = "https://runvouch.com/status"
UA = "Mozilla/5.0 (compatible; runvouch-statuswacht/0.1)"
REPAIR_EVERY = 1800
MAX_HEARTBEAT_AGE = 150


def get(url: str, timeout: int = 20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, type(e).__name__


def checks(browser: bool) -> dict:
    """name -> None when fine, else a short reason."""
    out = {}
    st, body = get(PUBLIC_API + "/health")
    out["api"] = None if st == 200 and '"status":"ok"' in body else f"public /health {st} {body[:60]}"
    st, body = get(LOCAL_API + "/health", 8)
    out["api_local"] = None if st == 200 and '"status":"ok"' in body else f"local /health {st} {body[:60]}"
    st, body = get(PUBLIC_API + "/status.json")
    try:
        age = json.loads(body).get("last_heartbeat_age_s")
        out["heartbeat"] = None if age is not None and age < MAX_HEARTBEAT_AGE else f"heartbeat age {age}"
    except Exception:
        out["heartbeat"] = f"status.json {st} {body[:60]}"
    st, body = get(SITE)
    out["site"] = None if st == 200 and "SAPI" in body and "status.json" in body else f"status page {st}"
    if browser:
        out["render"] = render()
    return out


def render():
    """Load the page like a visitor and require every status cell to be green; None when fine."""
    script = r"""
from playwright.sync_api import sync_playwright
import json
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)[:80]))
    pg.goto("https://runvouch.com/status", wait_until="networkidle"); pg.wait_for_timeout(3000)
    cells={i: pg.evaluate("(document.getElementById('%s')||{innerText:'MISSING'}).innerText" % i) for i in ("s-api","s-det","s-alerts","s-app","u-det-24h","s-meta")}
    print(json.dumps({"cells":cells,"errs":errs})); b.close()
"""
    env = dict(os.environ, LD_LIBRARY_PATH="/home/krtradingpro/chromelibs/root/usr/lib/x86_64-linux-gnu")
    try:
        r = subprocess.run([os.path.join(ROOT, ".venv", "bin", "python"), "-c", script], capture_output=True, text=True, timeout=120, env=env)
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        return f"render failed: {type(e).__name__} {(r.stderr if 'r' in dir() else '')[-120:]}"
    bad = {k: v for k, v in j["cells"].items() if v in ("MISSING", "checking", "-") or re.search(r"degraded|unreachable|unknown|could not", v)}
    if j["errs"]:
        return "script errors: " + "; ".join(j["errs"])
    return ("cells not green: " + json.dumps(bad)) if bad else None


def telegram(text: str) -> None:
    tok = chat = None
    try:  # the RunVouch account first, the shared DataSignals token as fallback (a broken DB must not silence the alarm)
        env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
        tok, chat = sqlite3.connect(env["RUNVOUCH_DB"]).execute("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
    except Exception:
        try:
            env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip().strip('"') for l in open("/home/krtradingpro/TradingBot/Trading_Bot_Crypto/config/API_keys_bitvavo.env") if "=" in l and not l.startswith("#")}
            tok, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
        except Exception:
            pass
    if not tok:
        print("geen telegram-token", file=sys.stderr)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900]}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data, {"User-Agent": UA}), timeout=15)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def restart(unit: str) -> None:
    subprocess.run(["systemctl", "--user", "restart", unit], timeout=60)


def main() -> int:
    now = time.time()
    minute = int(time.strftime("%M"))
    browser = "--browser" in sys.argv or minute in (0, 30)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"repairs": {}, "broken": {}}
    res = checks(browser)
    problems = {k: v for k, v in res.items() if v}
    done = []
    if problems:
        # repair, then measure again: a restart that did not help is not a repair
        if res["api_local"] or res["heartbeat"]:
            if now - st["repairs"].get("runvouch", 0) > REPAIR_EVERY:
                restart("runvouch.service"); st["repairs"]["runvouch"] = now; done.append("runvouch.service herstart"); time.sleep(20)
        elif res["api"] or res["site"]:
            if now - st["repairs"].get("cloudflared", 0) > REPAIR_EVERY:
                restart("cloudflared.service"); st["repairs"]["cloudflared"] = now; done.append("cloudflared.service herstart"); time.sleep(20)
        if done:
            res = checks(browser)
            problems = {k: v for k, v in res.items() if v}
    stamp = time.strftime("%Y-%m-%d %H:%M")
    if problems:
        line = f"{stamp} PROBLEEM " + "; ".join(f"{k}: {v}" for k, v in problems.items()) + ((" | gedaan: " + ", ".join(done)) if done else "")
        print(line)
        fresh = {k: v for k, v in problems.items() if k not in st["broken"]}
        if fresh or done:  # a new problem, or a repair that did not help: say it once, not every 5 minutes
            telegram("Statuspagina runvouch.com: " + line + "\nDit is de onafhankelijke wacht; RunVouch zelf kan dit niet melden.")
        st["broken"] = {k: st["broken"].get(k, now) for k in problems}
    else:
        line = f"{stamp} ok" + ((" | hersteld: " + ", ".join(done)) if done else "") + (" (browser)" if browser else "")
        print(line)
        if done:
            telegram(f"Statuspagina runvouch.com: zelf hersteld ({', '.join(done)}), alles weer groen.")
        elif st["broken"]:
            telegram(f"Statuspagina runvouch.com: weer groen na {', '.join(st['broken'])} (stond sinds {time.strftime('%H:%M', time.localtime(min(st['broken'].values())))}).")
        st["broken"] = {}
    json.dump(st, open(STATE, "w"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
