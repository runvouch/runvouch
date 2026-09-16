#!/usr/bin/env python3
"""opvolgwacht.py - remind the owner to follow up on outreach that got no reply.

Six messages went out on 16 September 2026 about a gap in published comparisons of agent monitoring tools.
A first mail with no follow-up is half a mail, and the follow-up is the part that gets forgotten, because
nothing in the system knows it is due. One shot, five working days later, one message, then it is done.

Reply or no reply is a human judgement, so this does not guess: it lists what went out and asks.
"""
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.getenv("RUNVOUCH_DB", os.path.join(ROOT, "data", "runvouch.db"))
UA = "runvouch-opvolgwacht/0.1"
VERSTUURD = "16 september 2026"
DOELEN = [
    ("Console", "hello@console.dev", "tool submission"),
    ("Dash0", "hi@dash0.com", "artikel Ayooluwa Isaiah, acht Claude Code-tools"),
    ("Torii", "contactus@toriihq.com", "artikel Chris Shuptrine, vijf dashboards"),
    ("Metoro", "press@metoro.io", "artikel Opemipo Disu, agent-observability"),
    ("MintMCP", "hello@mintmcp.com", "artikel Claude Code-analytics"),
    ("Septim Labs", "hello@septim.studio", "gids kostenmonitoring"),
]


def telegram(tekst: str) -> bool:
    try:
        row = sqlite3.connect(DB).execute(
            "SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL "
            "ORDER BY id LIMIT 1").fetchone()
        if not row:
            return False
        data = urllib.parse.urlencode({"chat_id": row[1], "text": tekst[:3900]}).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{row[0]}/sendMessage", data, {"User-Agent": UA}), timeout=15)
        return True
    except Exception as e:
        print("telegram:", e, file=sys.stderr)
        return False


def bericht() -> str:
    regels = "\n".join(f"- {naam} ({adres}): {wat}" for naam, adres, wat in DOELEN)
    return (f"Opvolging vergelijkingsartikelen. Verstuurd op {VERSTUURD}, vijf werkdagen geleden:\n\n{regels}\n\n"
            "Wie niet antwoordde krijgt een opvolging van drie regels, daarna stoppen. Tekst staat in "
            "data/strategie/mails.html. Wie wel antwoordde: antwoord vandaag, dat is de hele winst.")


def main() -> int:
    tekst = bericht()
    print(tekst)
    return 0 if telegram(tekst) else 1


if __name__ == "__main__":
    sys.exit(main())
