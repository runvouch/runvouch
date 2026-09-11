#!/usr/bin/env python3
"""pushwacht.py: keep github.com/runvouch/runvouch level with this machine, on its own.

On 11 September main was eleven commits ahead of origin and nobody knew. Three directories had just been told the
source lives there, so a reviewer following that link saw a repo where nothing had happened for days, and the first
GitHub release did not exist at all, which is the clock every awesome-list counts from. Pushing was a thing a human
remembered, and a thing a human remembers is a thing that eventually does not happen.

This runs hourly. It pushes main only when the whole test suite is green, because tests/test_open_source_hygiene.py
is what stands between a commit and publishing a token, a home path or a personal name. A red suite never pushes and
says so once, not once per hour. It never forces, it never pushes a branch other than main, and it never touches a
tag: a release stays a deliberate act.

State in data/pushwacht.json, so a failure that lasts all day costs one message. Wrapped in rv run by its service
unit, so RunVouch watches the job that publishes RunVouch.

  python3 deploy/pushwacht.py --droog    everything except the push, to see what it would do
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "pushwacht.json")
PYTEST = [os.path.join(ROOT, ".venv", "bin", "python"), "-m", "pytest", "-q", "tests"]
UA = "runvouch-pushwacht/0.1"
TAK = "main"


def git(*args, timeout=180):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def telegram(text: str) -> None:
    try:
        env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
        tok, chat = sqlite3.connect(env["RUNVOUCH_DB"]).execute(
            "SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
    except Exception as e:
        print("geen telegram-token:", type(e).__name__, file=sys.stderr)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data, {"User-Agent": UA}), timeout=15)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def stand() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def bewaar(**kv) -> None:
    d = stand()
    d.update(kv, ts=time.time())
    with open(STATE, "w") as f:
        json.dump(d, f)


def eenmalig(sleutel: str, tekst: str) -> None:
    """One message per state, not one per hour: a red suite on a Friday must not shout 60 times over a weekend."""
    if stand().get("laatste") != sleutel:
        telegram(tekst)
        bewaar(laatste=sleutel)


def main() -> int:
    code, uit = git("fetch", "--quiet", "origin", TAK)
    if code:
        eenmalig("fetch-stuk", f"pushwacht: kan origin niet bereiken.\n{uit[:300]}")
        return 1
    _, telling = git("rev-list", "--left-right", "--count", f"origin/{TAK}...{TAK}")
    achter, voor = (int(x) for x in telling.split())
    if achter:
        # iemand anders pushte, of een tak liep uiteen: samenvoegen is mensenwerk, hier stopt het
        eenmalig(f"achter-{achter}", f"pushwacht: deze machine loopt {achter} commits ACHTER op origin/{TAK} "
                                     f"en {voor} voor. Niets gepusht, dit moet met de hand samen.")
        return 1
    if not voor:
        bewaar(laatste="gelijk")
        print("gelijk met origin, niets te doen")
        return 0

    r = subprocess.run(PYTEST, capture_output=True, text=True, timeout=900, cwd=ROOT)
    if r.returncode:
        staart = [l for l in (r.stdout or "").splitlines() if l.startswith("FAILED") or " passed" in l or " failed" in l]
        eenmalig("tests-rood", f"pushwacht: {voor} commits klaar maar de tests zijn rood, niets gepusht.\n"
                               + "\n".join(staart[-6:])[:600])
        return 1

    _, laatste = git("log", "-1", "--format=%h %s", TAK)
    if "--droog" in sys.argv:
        print(f"droogloop: zou {voor} commits pushen, tests groen, laatste {laatste[:80]}")
        return 0
    code, uit = git("push", "origin", TAK)
    if code:
        eenmalig("push-stuk", f"pushwacht: push geweigerd.\n{uit[:400]}")
        return 1
    bewaar(laatste="gepusht", gepusht=voor)
    telegram(f"pushwacht: {voor} commit{'s' if voor > 1 else ''} naar github.com/runvouch/runvouch, tests groen.\n{laatste[:200]}")
    print(f"{voor} commits gepusht")
    return 0


if __name__ == "__main__":
    sys.exit(main())
