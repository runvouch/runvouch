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
import subprocess
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
# any subdomain: the phone's share button also hands out sh.reddit.com links, and old./np. links get typed by hand
URL_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?(?:reddit\.com|redd\.it|github\.com)/\S+", re.I)
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


MAIL_RE = re.compile(r"(^|\n)\s*(from|van|subject|onderwerp|to|aan)\s*:", re.I)
# A GitHub notification mail pasted from the phone: the addresses sit behind "view it on GitHub" and do not survive the
# copy, so the source has to be read from the wording. Every marker below is GitHub's own, none of it appears in a
# Reddit thread or a customer mail, and it is checked before the mail test because the mail test sees notifications@github.com
# as an address and would answer the robot instead of the person.
GH_TEXT_RE = re.compile(r"(view it on github|@(?:reply\.)?github\.com|github\.com/|#issuecomment|"
                        r"\bcommented on (?:this )?(?:pull request|issue|discussion)\b|"
                        r"\bopened this (?:issue|discussion|pull request)\b|\brequested (?:your |a )?review\b)", re.I)
# "github:" was the only accepted form, so "Github Re: ..." and "Runvouch ..." fell through to the Reddit persona
PREFIX_RE = re.compile(r"^(mail|reddit|github|gh)\b[\s:;,.-]*", re.I)
# the first github.com address in a notification mail is usually a profile or an unsubscribe address, and thread_github
# only understands a thread address, so look for the thread first and take any link only when there is none
THREAD_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?github\.com/[^/\s]+/[^/\s]+/(?:issues|pull|discussions)/\d+\S*", re.I)


def looks_like_mail(text: str) -> bool:
    """Only call it a mail when it carries mail headers or an e-mail address; pasted Reddit/GitHub text has neither."""
    return bool(MAIL_RE.search(text)) or bool(re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text, re.I))


KOP = {"github": "GITHUB - reageer als account runvouch (niet je eigen)",
       "reddit": "REDDIT - reageer als u/nightly_runs, nooit RunVouch noemen"}
HELP = ("Stuur de link van de thread, dan lees ik hem helemaal. Daarna hoef je alleen nog te plakken wat je krijgt: "
        "dat hang ik automatisch aan die thread.\nZonder link werkt ook, dan zie ik alleen jouw tekst. Voorvoegsel "
        "github:, reddit: of mail: dwingt af hoe ik het lees. 'nieuw' laat de vastgezette thread los, 'thread' laat "
        "zien welke er staat.")
# The owner works from a phone: in the GitHub app a single comment can be copied, the thread cannot. So the link is
# sent once and stays pinned here, and every pasted fragment after it is read as the newest reply in that thread.
THREAD_STATE = os.path.join(ROOT, "data", "telegram-thread.json")
THREAD_TTL = 14 * 86400


def onthoud(url: str, bron: str) -> None:
    with open(THREAD_STATE, "w") as f:
        json.dump({"url": url, "bron": bron, "ts": time.time()}, f)


def vastgezet() -> dict:
    """The pinned thread, or {} when there is none or it went stale (a fortnight without a link is a new subject)."""
    try:
        with open(THREAD_STATE) as f:
            d = json.load(f)
    except Exception:
        return {}
    return d if d.get("url") and time.time() - d.get("ts", 0) < THREAD_TTL else {}


def kort(url: str) -> str:
    m = re.search(r"github\.com/([^/]+/[^/]+)/(?:issues|pull|discussions)/(\d+)", url, re.I)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    m = re.search(r"reddit\.com/(r/[^/]+)/", url, re.I)
    return m.group(1) if m else url


def onze_eerdere(url: str) -> str:
    """What our own account already wrote in this exact thread: a follow-up has to build on it, not repeat it."""
    if not url:
        return ""
    rijen = [r for r in S.recent_drafts(400) if r.get("url") == url]
    return "\n---\n".join(r.get("text", "") for r in rijen[-4:])


def bewaar(sub: str, url: str, tekst: str) -> None:
    with open(S.HISTORY, "a") as f:
        f.write(json.dumps({"ts": time.time(), "sub": sub, "url": url, "text": tekst}) + "\n")


def met_link(text: str, m) -> list[str]:
    """A link was sent: read the whole thread, pin it, and treat anything typed around the link as the reply received."""
    url = m.group(0).rstrip(").,")
    rest = (text[:m.start()] + text[m.end():]).strip()
    bron = "github" if "github.com" in url.lower() else "reddit"
    try:
        th = S.thread(url)
    except Exception as e:
        return [f"Kon de thread niet lezen: {e or type(e).__name__}\n{url}\nPlak anders de tekst zelf hier, met github: of reddit: ervoor."]
    concept = S.draft(th, bron, followup=rest, ours=onze_eerdere(url))
    if not concept:
        return [f"Geen reactie geschreven: er valt niets echts toe te voegen (of de thread was leeg). {url}"]
    onthoud(url, bron)
    bewaar(bron + " reply", url, concept)
    return [concept, f"^ {KOP[bron]}\nHele thread gelezen ({kort(url)}) en vastgezet: plak vanaf nu gewoon het antwoord "
                     f"dat je krijgt, zonder link.\n{url}"]


def zonder_link(text: str, forced) -> list[str]:
    """Pasted text. With a pinned thread of the same source the conversation is read from that link again and this text
    goes in as the newest reply, so the draft sees what came before. Without one it is this fragment and nothing else."""
    if len(text.split()) < 12:
        return [HELP]
    bron = forced or ("github" if GH_TEXT_RE.search(text) else "mail" if looks_like_mail(text) else "reddit")
    if bron == "mail":
        return mail_reply(text)
    st = vastgezet()
    th, url, mislukt = "", "", ""
    if st.get("bron") == bron:
        try:
            th, url = S.thread(st["url"]), st["url"]
        except Exception as e:
            mislukt = f"\nDe vastgezette thread {kort(st['url'])} kon ik nu niet lezen ({type(e).__name__})."
    concept = S.draft(th, bron, followup=text, ours=onze_eerdere(url)) if th else S.draft(text, bron)
    if not concept:
        return ["Geen reactie geschreven: er valt niets echts toe te voegen aan deze tekst."]
    bewaar(bron + (" reply" if th else " reply (geplakt)"), url, concept)
    if th:
        staart = (f"^ {KOP[bron]}\nGehangen aan {kort(url)}, de hele thread is meegelezen"
                  + (" plus wat wij daar zelf al schreven" if onze_eerdere(url) else "") +
                  f".\nKlopt die thread niet, stuur 'nieuw' en daarna de goede link.\n{url}")
    else:
        staart = (f"^ {KOP[bron]}\nAlleen jouw tekst gelezen, geen thread eronder.{mislukt}\n"
                  "Stuur een keer de link van de thread, daarna hoef je alleen nog te plakken.")
    return [concept, staart]


PR_STATE = os.path.join(ROOT, "data", "prantwoord.json")
GH = os.path.expanduser("~/bin/gh")


def klaargezet() -> dict:
    """Het antwoord dat prantwoord.py schreef en dat op een 'ja' wacht."""
    try:
        with open(PR_STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def plaats_pr_antwoord(tekst: str = "") -> list[str]:
    """Zet het klaargezette antwoord in de draad. De sessie schrijft, de eigenaar drukt af."""
    d = klaargezet()
    if not d.get("url"):
        return ["Er staat geen GitHub-antwoord klaar."]
    body = tekst or d.get("tekst", "")
    if not body.strip():
        return ["Het klaargezette antwoord is leeg, er is niets geplaatst."]
    r = subprocess.run([GH, "pr", "comment", d["url"], "--body", body],
                       capture_output=True, text=True, timeout=90)
    if r.returncode:
        return [f"Plaatsen mislukt: {(r.stderr or r.stdout).strip()[:300]}\n{d['url']}"]
    open(PR_STATE, "w").write("{}")
    return [f"Geplaatst op {d.get('repo', d['url'])}.\n{(r.stdout or '').strip()[:200]}"]


def handle(text: str) -> list[str]:
    """One incoming message -> the messages to send back. Pure: no Telegram inside, so it is testable."""
    text = (text or "").lstrip()
    los = text.strip().lower()
    if los in ("nieuw", "reset", "vergeet", "los", "stop"):
        try:
            os.remove(THREAD_STATE)
        except FileNotFoundError:
            pass
        return ["Losgekoppeld. Wat je nu plakt staat op zichzelf. Stuur een link om een nieuwe thread vast te zetten."]
    if los in ("ja", "plaats", "post", "doe maar", "akkoord", "verstuur"):
        # Eerst mail, dan GitHub: een mailantwoord is vers en een PR-concept kan een dag oud zijn.
        if klaar_mail().get("naar"):
            return verstuur_mail_antwoord()
        return plaats_pr_antwoord()
    if los in ("nee", "niet doen", "laat maar"):
        weg = []
        if klaar_mail().get("naar"):
            open(MAIL_STATE, "w").write("{}")
            weg.append("het mailantwoord")
        if klaargezet().get("url"):
            open(PR_STATE, "w").write("{}")
            weg.append("het GitHub-antwoord")
        return [("Weggegooid: " + " en ".join(weg) + ".") if weg else "Er stond niets klaar."]
    if los in ("thread", "status", "waar", "?"):
        st = vastgezet()
        return [f"Vastgezet: {kort(st['url'])}\n{st['url']}" if st else "Geen thread vastgezet.\n" + HELP]
    forced = None
    pre = PREFIX_RE.match(text)
    if pre:
        forced = "github" if pre.group(1).lower() == "gh" else pre.group(1).lower()
        text = text[pre.end():].strip()
    m = THREAD_RE.search(text) or URL_RE.search(text)
    return met_link(text, m) if m else zonder_link(text, forced)


MAIL_RULES = """You draft ONE reply to an incoming message (an e-mail or a marketplace/console message) for a small company.
Decide from the content which company is addressed: DataSignals Lab (data products: SEC filings, Events API, Jobs API, MCP,
Apify, RapidAPI; sign as "DataSignals Lab", support@datasignalslab.com) or RunVouch (watchdog for unattended AI agents;
sign as "The RunVouch team", support@runvouch.com). Rules, all hard:
- Answer what is actually asked. A customer question gets a direct, complete, friendly answer; a sales or partnership pitch
  gets a short, polite decline that closes the thread; a bot or automated notice gets: NOREPLY.
- Company voice ("we"), plain English, no em dashes, no emoji, no marketing phrases, 40-140 words. Never invent prices,
  features, dates or names; if a fact is needed that is not in the message, write [CHECK: ...] in its place.
- First line of your output must be exactly: COMPANY: DataSignals Lab   or   COMPANY: RunVouch
- Then a blank line, then the reply text only (with the sign-off). If no reply is warranted, output only: NOREPLY - <why>"""


MAIL_STATE = os.path.join(ROOT, "data", "mailantwoord.json")
# Twee bedrijven, twee Resend-sleutels, twee afzenders. Versturen vanuit Gmail met een van deze adressen in de
# From-regel faalt: geen van beide domeinen noemt Google in zijn SPF, runvouch.com staat op p=quarantine en
# datasignalslab.com zelfs op p=reject. Via Resend wordt het ondertekend als het eigen domein en komt het aan.
AFZENDERS = {
    "RunVouch": ("RunVouch <support@runvouch.com>", os.path.join(ROOT, ".env")),
    "DataSignals Lab": ("DataSignals Lab <support@datasignalslab.com>",
                        os.path.expanduser("~/apify/landing/config/secrets" + ".env")),
}
ADRES_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ONDERWERP_RE = re.compile(r"^\s*(?:subject|onderwerp)\s*:\s*(.+)$", re.I | re.M)
EIGEN_DOMEINEN = ("runvouch.com", "datasignalslab.com")


def _resend_sleutel(pad: str) -> str:
    """De sleutel uit een omgevingsbestand, zonder hem ooit af te drukken."""
    try:
        regels = [l for l in open(pad) if "=" in l and not l.lstrip().startswith("#")]
    except Exception:
        return ""
    for l in regels:
        naam, _, waarde = l.partition("=")
        if naam.strip() == "RESEND_API_KEY":
            return waarde.strip().strip('"').strip("'")
    return ""


def _aan_wie(tekst: str) -> str:
    """Het adres van de afzender uit de geplakte mail. Onze eigen adressen tellen niet mee."""
    # Lui en niet gulzig: met [^<\n]* at "From: someone@acme.com" zijn eigen begin op en bleef er e@acme.com over.
    m = re.search(r"(?:^|\n)\s*(?:from|van)\s*:\s*[^<\n]*?<?([\w.+-]+@[\w-]+\.[\w.-]+)", tekst, re.I)
    if m and not any(d in m.group(1).lower() for d in EIGEN_DOMEINEN):
        return m.group(1)
    for adres in ADRES_RE.findall(tekst):
        if not any(d in adres.lower() for d in EIGEN_DOMEINEN):
            return adres
    return ""


def klaar_mail() -> dict:
    try:
        with open(MAIL_STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def verstuur_mail_antwoord(tekst: str = "") -> list[str]:
    """Het klaargezette mailantwoord versturen. De sessie schrijft, de eigenaar drukt af."""
    d = klaar_mail()
    if not d.get("naar"):
        return ["Er staat geen mailantwoord klaar."]
    body = (tekst or d.get("tekst", "")).strip()
    if not body:
        return ["Het klaargezette antwoord is leeg, er is niets verstuurd."]
    van, envpad = AFZENDERS.get(d.get("company", ""), AFZENDERS["RunVouch"])
    sleutel = _resend_sleutel(envpad)
    if not sleutel:
        return [f"Geen verzendsleutel gevonden voor {d.get('company')}, niets verstuurd."]
    adres = van.split("<")[-1].rstrip(">")
    payload = json.dumps({"from": van, "to": [d["naar"]], "subject": d.get("onderwerp") or "Re: your message",
                          "text": body + "\n", "reply_to": adres}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", payload,
                                 {"Authorization": "Bearer " + sleutel, "Content-Type": "application/json",
                                  "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            antwoord = json.load(r)
    except Exception as e:
        detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else ""
        return [f"Versturen mislukt: {type(e).__name__} {detail}"]
    open(MAIL_STATE, "w").write("{}")
    return [f"Verstuurd aan {d['naar']} namens {d.get('company')}.\nid {antwoord.get('id')}"]


def mail_reply(text: str) -> list[str]:
    try:
        r = subprocess.run([S.CLAUDE, "-p", MAIL_RULES + "\n\nINCOMING MESSAGE:\n" + text[:6000], "--output-format", "json", "--max-turns", "1"],
                           capture_output=True, text=True, timeout=240)
        antwoord = json.loads(r.stdout or "{}")
        S.UITGAVEN.append(antwoord.get("total_cost_usd", 0) or 0)   # anders is een mailconcept gratis in de cijfers
        out = antwoord.get("result", "").strip()
    except Exception as e:
        return [f"Concept mislukt: {type(e).__name__}"]
    if not out or out.upper().startswith("NOREPLY"):
        return ["Geen antwoord nodig: " + (out.split("-", 1)[1].strip() if "-" in out else "automatische melding of bot.")]
    first, _, body = out.partition("\n")
    company = first.replace("COMPANY:", "").strip() or "?"
    addr = "support@datasignalslab.com" if "DataSignals" in company else "support@runvouch.com"
    with open(S.HISTORY, "a") as f:
        f.write(json.dumps({"ts": time.time(), "sub": "mail " + company, "url": "", "text": body.strip()}) + "\n")
    naar = _aan_wie(text)
    m = ONDERWERP_RE.search(text)
    onderwerp = m.group(1).strip()[:120] if m else ""
    if onderwerp and not onderwerp.lower().startswith("re:"):
        onderwerp = "Re: " + onderwerp
    if not naar:
        return [body.strip(), f"^ ANTWOORD namens {company}\nGeen afzenderadres in de tekst gevonden, dus versturen "
                              f"kan ik niet. Kopieer het bericht hierboven en verstuur het als {addr}."]
    with open(MAIL_STATE, "w") as f:
        json.dump({"naar": naar, "company": company, "onderwerp": onderwerp, "tekst": body.strip()}, f)
    return [body.strip(), f"^ ANTWOORD namens {company}, aan {naar}\nAntwoord 'ja' om dit zo te versturen vanaf "
                          f"{addr}, of plak je eigen versie met mail: ervoor."]


RV = os.path.expanduser("~/bin/rv")


def meld_run(kosten: float, bron: str) -> None:
    """Een bericht afgehandeld is een eenheid werk, dus meld het als run met wat het kostte.

    Deze wacht is een daemon, dus rv run kan er niet omheen staan en de kosten landden nergens. En juist hier
    wordt het meeste uitgegeven: elk concept is een Claude-aanroep, en op een dag met veel berichten is dat meer
    dan alle nachtelijke taken samen. Zonder deze melding keken de BUDGET-detectoren naar nul terwijl de rekening
    wel liep. Faalt het melden, dan gaat het antwoord gewoon door: bewaking mag het werk nooit breken.
    """
    try:
        r = subprocess.run([RV, "start", "telegram-antwoord", "--source", "daemon"],
                           capture_output=True, text=True, timeout=20)
        rid = (json.loads(r.stdout or "{}") or {}).get("run_id") or (r.stdout or "").strip()
        if not rid:
            return
        subprocess.run([RV, "end", rid, "--status", "ok", "--cost", f"{kosten:.6f}"],
                       capture_output=True, text=True, timeout=20)
    except Exception as e:
        print("kosten melden overgeslagen:", type(e).__name__, str(e)[:120], flush=True)


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
                voor = sum(S.UITGAVEN)
                for out in handle(text):
                    send(tok, chat, out)
                kosten = sum(S.UITGAVEN) - voor
                if kosten > 0:
                    meld_run(kosten, "telegram")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print("fout:", type(e).__name__, str(e)[:200], flush=True)
            time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
