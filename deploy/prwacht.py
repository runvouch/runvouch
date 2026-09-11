#!/usr/bin/env python3
"""prwacht.py: open pull requests waar de bal bij ons ligt, een keer per dag in Telegram.

Op 11 september stond er een PR bij awesome-remote-mcp-servers waarin de beheerder om 04:15 vroeg een teken te
veranderen. Om 07:53 is toegezegd dat het gepusht zou worden. Om 15:55 kwam de herinnering dat het er nog niet was.
Twaalf uur stilstand op twee tekens, in precies het soort lijst waar iemand je vindt die je zelf nooit bereikt.

Niemand was nalatig: een PR bij een vreemde repo staat nergens meer op een scherm zodra je hem hebt ingediend. Deze
wacht zet hem terug op dat scherm, en alleen als er iets van ons wordt gevraagd.

Aan zet zijn wij als:
  - de laatste reactie in de draad van iemand anders is (ook van een bot, want die meldt wat er mis is)
  - een beoordelaar wijzigingen vraagt
  - een controle rood staat op onze eigen commit

Aan zet zijn zij als wij het laatst schreven. Dan zegt de wacht niets, tot er iets verandert of tot hij veertien
dagen stil staat: dat is lang genoeg om te weten dat het niet meer vanzelf goedkomt.

State in data/prwacht.json, zodat dezelfde stand geen tweede bericht oplevert. Een nieuwe reactie is een nieuwe
stand en dus wel een bericht.
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
STATE = os.path.join(ROOT, "data", "prwacht.json")
GH = os.path.expanduser("~/bin/gh")
UA = "runvouch-prwacht/0.1"
# Alleen runvouch: het account datasignalslab is bij GitHub geflagd en publiek onzichtbaar, dus een zoek-
# opdracht op die auteur geeft een fout in plaats van een lege lijst. Zodra dat account weer zichtbaar is,
# zet het erbij met PRWACHT_ACCOUNTS="runvouch,datasignalslab".
ACCOUNTS = [a for a in os.getenv("PRWACHT_ACCOUNTS", "runvouch").split(",") if a]
STIL_DAGEN = 14


def gh(*args, timeout=90):
    r = subprocess.run([GH, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return json.loads(r.stdout or "[]")


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


def beoordeel(url: str, eigenaars: set) -> tuple:
    """(reden, stempel) voor een PR. reden is leeg als wij niet aan zet zijn."""
    d = gh("pr", "view", url, "--json", "comments,reviews,statusCheckRollup,updatedAt,isDraft,title")
    if d.get("isDraft"):
        return "", "draft"
    reacties = d.get("comments") or []
    laatste = reacties[-1] if reacties else None
    wie = ((laatste or {}).get("author") or {}).get("login", "")
    # Een beoordeling die wijzigingen vraagt blijft staan tot er een nieuwe beoordeling overheen komt.
    vraagt = [r for r in (d.get("reviews") or []) if r.get("state") == "CHANGES_REQUESTED"]
    rood = [c for c in (d.get("statusCheckRollup") or [])
            if str(c.get("conclusion", "")).upper() in ("FAILURE", "TIMED_OUT", "ACTION_REQUIRED")]
    stempel = json.dumps({"c": (laatste or {}).get("id", ""), "r": len(vraagt), "x": len(rood)}, sort_keys=True)

    if rood:
        return f"controle rood ({', '.join(c.get('name', '?') for c in rood[:3])})", stempel
    if vraagt:
        return f"{vraagt[-1]['author']['login']} vraagt wijzigingen", stempel
    if laatste and wie not in eigenaars:
        kort = " ".join((laatste.get("body") or "").split())[:110]
        return f"{wie} schreef als laatste: {kort}", stempel
    if not laatste:
        return "", stempel
    stil = (time.time() - time.mktime(time.strptime(d["updatedAt"][:19], "%Y-%m-%dT%H:%M:%S"))) / 86400
    if stil > STIL_DAGEN:
        return f"{int(stil)} dagen stil, wij schreven het laatst", stempel
    return "", stempel


def main() -> int:
    oud = stand()
    nieuw, meldingen = {}, []
    eigenaars = {a.lower() for a in ACCOUNTS}
    for account in ACCOUNTS:
        try:
            prs = gh("search", "prs", "--author", account, "--state", "open", "--limit", "40",
                     "--json", "url,title,repository")
        except Exception as e:
            print(f"zoeken voor {account} mislukt: {e}", file=sys.stderr)
            continue
        for pr in prs:
            url = pr["url"]
            try:
                reden, stempel = beoordeel(url, eigenaars)
            except Exception as e:
                print(f"{url}: {e}", file=sys.stderr)
                continue
            nieuw[url] = stempel
            if reden and oud.get(url) != stempel:
                repo = (pr.get("repository") or {}).get("nameWithOwner", "?")
                meldingen.append(f"{repo}: {reden}\n{url}")
    with open(STATE, "w") as f:
        json.dump(nieuw, f)
    if meldingen:
        kop = "PR aan zet" if len(meldingen) == 1 else f"{len(meldingen)} PR's aan zet"
        telegram(kop + ":\n\n" + "\n\n".join(meldingen[:6]))
    print(f"{len(nieuw)} open PR's bekeken, {len(meldingen)} melding(en)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
