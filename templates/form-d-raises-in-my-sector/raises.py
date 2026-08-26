#!/usr/bin/env python3
"""New SEC Form D raises in your sector, from the DataSignals Events API. Standard library only.

Reads the private_raise stream since the last cursor, keeps the raises whose industry or
issuer name matches your keywords, appends them to out/raises.jsonl and sends one Telegram
message when something matched.

    DATASIGNALS_KEY=ds_live_... python3 raises.py
    python3 raises.py --input page.json --dry-run       # offline test with a saved response

State: out/cursor.txt (the cursor of the last event seen). Delete it to start over.
"""
import argparse, datetime, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "raises.jsonl")
CURSOR = os.path.join(HERE, "out", "cursor.txt")
API = os.getenv("DATASIGNALS_API", "https://datasignalslab.com/v1")


def keywords():
    words = []
    for line in open(os.path.join(HERE, "keywords.txt")):
        line = line.split("#")[0].strip().lower()
        if line:
            words.append(line)
    return words


def fetch(since, limit=100):
    key = os.getenv("DATASIGNALS_KEY", "")
    if not key:
        sys.exit("DATASIGNALS_KEY not set (free key: see README)")
    q = {"event_type": "private_raise", "limit": limit}
    if since:
        q["since"] = since
    req = urllib.request.Request(API + "/events?" + urllib.parse.urlencode(q),
                                 headers={"Authorization": "Bearer " + key, "User-Agent": "runvouch-template/1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            if e.code in (503, 429) and attempt < 2:      # API waking up from idle; Retry-After says how long
                import time; time.sleep(int(e.headers.get("Retry-After", "15"))); continue
            sys.exit(f"events api {e.code}: {body}")
    sys.exit("events api: gave up")


def matches(ev, words):
    d = ev.get("data", {})
    hay = " ".join([str(d.get("industry", "")), str((ev.get("company") or {}).get("name", "")),
                    " ".join(d.get("related_persons", []) if isinstance(d.get("related_persons"), list) else [])]).lower()
    return [w for w in words if w in hay]


def telegram(text):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, printing instead\n" + text); return
    body = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", body, timeout=20).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="saved /v1/events response instead of a live call")
    ap.add_argument("--dry-run", action="store_true", help="print the message instead of sending it")
    a = ap.parse_args()
    words = keywords()
    since = open(CURSOR).read().strip() if os.path.exists(CURSOR) else ""
    page = json.load(open(a.input)) if a.input else fetch(since)
    events = page.get("events", [])
    if page.get("notice"):
        print("notice:", page["notice"])
    hits = []
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a") as f:
        for ev in events:
            why = matches(ev, words)
            if not why:
                continue
            row = {"seen": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                   "event_id": ev.get("event_id"), "occurred_at": ev.get("occurred_at"),
                   "issuer": (ev.get("company") or {}).get("name"), "industry": ev.get("data", {}).get("industry"),
                   "amount_sold_usd": ev.get("data", {}).get("amount_sold_usd"),
                   "amount_offered_usd": ev.get("data", {}).get("amount_offered_usd"),
                   "state": ev.get("data", {}).get("state"), "score": ev.get("score"),
                   "matched": why, "url": (ev.get("source") or {}).get("url")}
            f.write(json.dumps(row) + "\n"); hits.append(row)
    if page.get("cursor") is not None and not a.input:
        open(CURSOR, "w").write(str(page["cursor"]))
    print(f"{len(events)} new private_raise events, {len(hits)} matched, quota {page.get('quota')}")
    if hits:
        msg = [f"Form D: {len(hits)} new raise(s) in your sector"]
        for h in hits[:15]:
            amt = h["amount_sold_usd"] or h["amount_offered_usd"] or 0
            msg.append(f"- {h['issuer']} ({h['industry']}, {h['state']}): ${int(amt):,} sold/offered, matched {', '.join(h['matched'])}\n  {h['url']}")
        text = "\n".join(msg)
        print(text) if a.dry_run else telegram(text)


if __name__ == "__main__":
    main()
