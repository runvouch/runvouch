#!/usr/bin/env python3
"""mailronde.py: one outreach mail at a time, from an address the receiving server will believe.

The first attempt at this went out of Gmail with support@runvouch.com in the From line. The SPF record of
runvouch.com lists only Cloudflare Email Routing, which forwards and cannot send, so Google's servers are not
authorised for this domain; Gmail would sign as gmail.com, that does not align, and DMARC on this domain says
p=quarantine. In other words: straight to the spam folder at the other end, and a second round of "nobody answered"
for a reason that has nothing to do with the message. Mail to yourself proves nothing here, because Gmail to Gmail
inside one account never takes the outside path: the test message had no DKIM-Signature at all.

Resend is already verified for runvouch.com, which is how alerts and billing mail leave. This sends through the same
path, so the message is signed as runvouch.com and aligns.

Plain text only, no HTML, no logo, no tracking pixel. These go to people who write comparison articles; a branded
template reads as a campaign and belongs in the folder it would end up in.

  python3 deploy/mailronde.py data/directories/mails/1-hyperping.txt           preview, sends nothing
  python3 deploy/mailronde.py data/directories/mails/1-hyperginge.txt --stuur  actually sends

A mail file is: first line "To: ...", second line "Subject: ...", a blank line, then the body.
Every send is written to data/mailronde.jsonl, so a follow-up knows what went out and when, and the same address is
never mailed twice by accident.
"""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data", "mailronde.jsonl")
VAN = "RunVouch <support@runvouch.com>"


def sleutel() -> str:
    env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
    k = env.get("RESEND_API_KEY", "")
    if not k:
        sys.exit("geen RESEND_API_KEY in .env")
    return k


def lees(pad: str) -> tuple[str, str, str]:
    regels = open(pad, encoding="utf-8").read().split("\n")
    if not regels[0].startswith("To:") or not regels[1].startswith("Subject:"):
        sys.exit(f"{pad}: eerste regel moet 'To:' zijn en de tweede 'Subject:'")
    return regels[0][3:].strip(), regels[1][8:].strip(), "\n".join(regels[2:]).strip() + "\n"


def eerder(naar: str) -> list[dict]:
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG) if l.strip() and json.loads(l).get("naar") == naar]


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pad = sys.argv[1]
    naar, onderwerp, tekst = lees(pad)
    al = eerder(naar)
    print(f"Van      {VAN}\nNaar     {naar}\nOnderwerp {onderwerp}\n{'-' * 72}\n{tekst}{'-' * 72}")
    print(f"{len(tekst.split())} woorden, {len(tekst)} tekens")
    if al:
        print(f"LET OP: dit adres kreeg al {len(al)} bericht(en), laatste op "
              + time.strftime('%Y-%m-%d %H:%M', time.localtime(al[-1]['ts'])))
    if "--stuur" not in sys.argv:
        print("\nDroogloop. Voeg --stuur toe om echt te versturen.")
        return 0
    body = json.dumps({"from": VAN, "to": [naar], "subject": onderwerp, "text": tekst,
                       "reply_to": "support@runvouch.com"}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", body,
                                 {"Authorization": "Bearer " + sleutel(), "Content-Type": "application/json",
                                  "User-Agent": "runvouch-mailronde/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            antwoord = json.load(r)
    except Exception as e:
        detail = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else ""
        sys.exit(f"versturen mislukt: {type(e).__name__} {detail}")
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": time.time(), "naar": naar, "onderwerp": onderwerp,
                            "bestand": os.path.basename(pad), "id": antwoord.get("id")}) + "\n")
    print("verstuurd, id", antwoord.get("id"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
