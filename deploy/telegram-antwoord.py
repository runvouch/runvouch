#!/usr/bin/env python3
"""telegram-antwoord.py: the owner talks back to the bot from the phone.

Runs as a small daemon (telegram-antwoord.service). It long-polls the same Telegram bot the scout sends to and
only listens to the owner's chat. Send a Reddit or GitHub link, with the reply you received pasted under it if
you like, and within a minute a follow-up comment comes back as two messages: first the text alone (long-press,
Copy), then the link. Reddit drafts speak as u/nightly_runs, GitHub drafts as the runvouch account; the rules live
in reddit-scout.py so both paths write the same way. Anything without a link gets a one-line how-to.
"""
import importlib.util
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("scout", os.path.join(HERE, "reddit-scout.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
OFFSET = os.path.join(ROOT, "data", "telegram-antwoord.offset")
URL_RE = re.compile(r"https?://(?:www\.)?(?:reddit\.com|redd\.it|github\.com)/\S+")
UA = "runvouch-telegram-antwoord/0.1"


def creds() -> tuple[str, str]:
    env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
    c = sqlite3.connect(env["RUNVOUCH_DB"])
    tok, chat = c.execute("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
    return tok, str(chat)


def send(tok: str, chat: str, text: str) -> None:
    for chunk in [text[i:i + 3800] for i in range(0, len(text), 3800)]:
        data = urllib.parse.urlencode({"chat_id": chat, "text": chunk, "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data, {"User-Agent": UA}), timeout=15)


def handle(text: str) -> list[str]:
    """One incoming message -> the messages to send back. Pure: no Telegram inside, so it is testable."""
    m = URL_RE.search(text or "")
    if not m:
        return ["Stuur een Reddit- of GitHub-link, met daaronder (mag) het antwoord dat je kreeg. Je krijgt een reactie terug: eerst de tekst, dan de link."]
    url = m.group(0).rstrip(").,")
    rest = (text[:m.start()] + text[m.end():]).strip()
    bron = "github" if "github.com" in url else "reddit"
    try:
        th = S.thread(url)
    except Exception as e:
        return [f"Kon de thread niet lezen ({type(e).__name__}): {url}"]
    draft = S.draft(th, bron, followup=rest)
    if not draft:
        return [f"Geen reactie geschreven: er valt niets echts toe te voegen (of de thread was leeg). {url}"]
    with open(S.HISTORY, "a") as f:
        f.write(json.dumps({"ts": time.time(), "sub": bron + " reply", "url": url, "text": draft}) + "\n")
    kop = "GITHUB - reageer als account runvouch (niet je eigen)" if bron == "github" else "REDDIT - reageer als u/nightly_runs"
    return [draft, f"^ {kop}\nKopieer het bericht hierboven, tik de link, plak als reply:\n{url}"]


def main() -> int:
    if "--test" in sys.argv:
        for m in handle(sys.argv[sys.argv.index("--test") + 1]):
            print("---\n" + m)
        return 0
    tok, chat = creds()
    offset = int(open(OFFSET).read() or 0) if os.path.exists(OFFSET) else 0
    print("luistert op chat", chat, flush=True)
    while True:
        try:
            q = urllib.parse.urlencode({"timeout": 50, "offset": offset, "allowed_updates": json.dumps(["message"])})
            r = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/getUpdates?{q}", headers={"User-Agent": UA}), timeout=70))
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                open(OFFSET, "w").write(str(offset))
                msg = u.get("message") or {}
                if str(msg.get("chat", {}).get("id")) != chat:
                    continue  # only the owner
                text = msg.get("text") or ""
                if not text or text.startswith("Reddit en GitHub vandaag") or text.startswith("^ "):
                    continue
                print(time.strftime("%H:%M"), "bericht:", text[:80], flush=True)
                for out in handle(text):
                    send(tok, chat, out)
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print("fout:", type(e).__name__, str(e)[:200], flush=True)
            time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
