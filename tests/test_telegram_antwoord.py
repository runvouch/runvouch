"""The Telegram loop the owner works from his phone: which persona a message gets and which thread it is hung on.

No network and no Claude call: S.thread and S.draft are replaced, so what is tested is the routing, not the wording.
The routing is what went wrong in production, where every pasted GitHub mail came back as a Reddit comment in the
first person because pasted text without a link defaulted to Reddit.
"""
import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def laad():
    spec = importlib.util.spec_from_file_location("ta", os.path.join(ROOT, "deploy", "telegram-antwoord.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def T(tmp_path):
    mod = laad()
    mod.THREAD_STATE = str(tmp_path / "thread.json")
    mod.S.HISTORY = str(tmp_path / "drafts.jsonl")
    mod.gezien = []
    mod.S.thread = lambda url: mod.gezien.append(("thread", url)) or f"POST a: inhoud van {url}"
    mod.S.draft = lambda t, bron="reddit", followup=None, ours="": mod.gezien.append(("draft", bron, t[:200], ours)) or "CONCEPT"
    mod.mail_reply = lambda t: mod.gezien.append(("mail",)) or ["MAILCONCEPT"]
    return mod


GH_MAIL = """runvouch left a comment (openclaw/openclaw#143757)

Per our runbook the holdMs takes the max of a per job span and a service wide one, so the window never shrinks.

Reply to this email directly, view it on GitHub, or unsubscribe."""
RD_TEKST = ("Anyone else running fifty cron jobs and finding out three days later that one of them silently stopped "
            "writing its output file")
KLANTMAIL = "From: someone@acme.com\nSubject: quote\n\nCan we get a price for ten seats, we run a lot of nightly jobs here"


@pytest.mark.parametrize("tekst,bron", [
    (GH_MAIL, "github"),
    ("Github Re: the coalescing rule we shipped last week, what do you think about the schedule that wins here", "github"),
    ("gh: " + GH_MAIL, "github"),
    ("someone commented on this pull request: the retry loop should back off, we saw the same on a nightly build", "github"),
    (RD_TEKST, "reddit"),
])
def test_bron_uit_geplakte_tekst(T, tekst, bron):
    T.handle(tekst)
    assert [g for g in T.gezien if g[0] == "draft"][0][1] == bron


def test_klantmail_gaat_niet_naar_github(T):
    T.handle(KLANTMAIL)
    assert ("mail",) in T.gezien


def test_github_notificatie_is_geen_klantmail(T):
    """notifications@github.com is an address, so the mail test used to answer the robot instead of the person."""
    T.handle(GH_MAIL)
    assert ("mail",) not in T.gezien


def test_link_wordt_vastgezet_en_daarna_geplakt(T):
    url = "https://github.com/openclaw/openclaw/issues/143757#issuecomment-561910"
    uit = T.handle("Runvouch: " + url)
    assert "vastgezet" in uit[1]
    assert json.load(open(T.THREAD_STATE))["url"] == url
    T.gezien.clear()
    uit = T.handle(GH_MAIL)
    assert ("thread", url) in T.gezien                      # de hele thread is opnieuw gelezen
    d = [g for g in T.gezien if g[0] == "draft"][0]
    assert d[1] == "github" and url in d[2]                 # concept staat op de thread, niet op het fragment
    assert d[3] == "CONCEPT"                                # ons eigen eerdere antwoord in deze thread gaat mee
    assert T.kort(url) in uit[1]


def test_andere_bron_pakt_de_vastgezette_thread_niet(T):
    T.handle("https://github.com/openclaw/openclaw/issues/1 kijk hier")
    T.gezien.clear()
    T.handle(RD_TEKST)
    assert not [g for g in T.gezien if g[0] == "thread"]


def test_nieuw_koppelt_los(T):
    T.handle("https://github.com/openclaw/openclaw/issues/1 kijk hier")
    assert "Losgekoppeld" in T.handle("nieuw")[0]
    assert not os.path.exists(T.THREAD_STATE)
    T.gezien.clear()
    T.handle(GH_MAIL)
    assert not [g for g in T.gezien if g[0] == "thread"]


def test_thread_toont_wat_vaststaat(T):
    assert "Geen thread" in T.handle("thread")[0]
    T.handle("https://github.com/openclaw/openclaw/issues/1 kijk hier")
    assert "openclaw/openclaw#1" in T.handle("thread")[0]


def test_draadlink_wint_van_de_eerste_de_beste_link(T):
    """A notification mail opens with a profile or unsubscribe address; the thread address is the one that counts."""
    T.handle("See https://github.com/openclaw/openclaw and https://github.com/openclaw/openclaw/discussions/88 for more")
    assert ("thread", "https://github.com/openclaw/openclaw/discussions/88") in T.gezien


def test_scout_leest_issue_pull_en_discussion():
    S = laad().S
    for soort in ("issues", "pull", "discussions"):
        m = S.GH_THREAD_RE.search(f"https://github.com/a/b/{soort}/12#issuecomment-9")
        assert m and m.group(3) == soort and m.group(4) == "12"
    assert not S.GH_THREAD_RE.search("https://github.com/a/b")
    with pytest.raises(ValueError):
        S.thread_github("https://github.com/openclaw/openclaw")


def test_ja_plaatst_het_klaargezette_github_antwoord(T, tmp_path, monkeypatch):
    """De sessie schrijft, de eigenaar drukt af. Dat is het hele verschil met een bot die zelf praat."""
    import json as _j
    T.PR_STATE = str(tmp_path / "pr.json")
    open(T.PR_STATE, "w").write(_j.dumps({"url": "https://github.com/a/b/pull/1", "repo": "a/b",
                                          "tekst": "Done, pushed to the same branch."}))
    gedaan = []

    class R:
        returncode = 0
        stdout = "https://github.com/a/b/pull/1#issuecomment-1"
        stderr = ""

    monkeypatch.setattr(T.subprocess, "run", lambda *a, **k: gedaan.append(a[0]) or R())
    uit = T.handle("ja")
    assert "Geplaatst" in uit[0]
    assert gedaan[0][1:3] == ["pr", "comment"], "moet via gh pr comment gaan"
    assert _j.load(open(T.PR_STATE)) == {}, "na plaatsen hoort het concept weg te zijn"


def test_nee_gooit_het_concept_weg_zonder_te_plaatsen(T, tmp_path, monkeypatch):
    import json as _j
    T.PR_STATE = str(tmp_path / "pr.json")
    open(T.PR_STATE, "w").write(_j.dumps({"url": "https://github.com/a/b/pull/1", "repo": "a/b", "tekst": "x"}))
    monkeypatch.setattr(T.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("mag niet plaatsen")))
    uit = T.handle("nee")
    assert "Weggegooid" in uit[0] and "GitHub" in uit[0]
    assert _j.load(open(T.PR_STATE)) == {}


def test_ja_zonder_klaargezet_antwoord_doet_niets(T, tmp_path):
    T.PR_STATE = str(tmp_path / "leeg.json")
    assert "geen GitHub-antwoord" in T.handle("ja")[0]


def test_een_klantmail_wordt_klaargezet_om_te_versturen(T, tmp_path, monkeypatch):
    """Vroeger eindigde dit met 'kopieer dit en verstuur het in Gmail'. Dat kostte tijd en het faalde op DMARC:
    geen van beide domeinen noemt Google in zijn SPF."""
    import json as _j
    T = laad()          # een verse module, want de fixture vervangt mail_reply door een stub
    T.MAIL_STATE = str(tmp_path / "mail.json")
    T.S.HISTORY = str(tmp_path / "drafts.jsonl")
    monkeypatch.setattr(T.subprocess, "run", lambda *a, **k: type("R", (), {
        "stdout": _j.dumps({"result": "COMPANY: RunVouch\n\nThanks for writing, the free plan covers 20 agents."}),
        "returncode": 0})())
    uit = T.mail_reply("From: someone@acme.com\nSubject: How many agents on the free plan?\n\nHi, quick question.")
    assert "20 agents" in uit[0]
    assert "someone@acme.com" in uit[1] and "ja" in uit[1]
    d = _j.load(open(T.MAIL_STATE))
    assert d["naar"] == "someone@acme.com" and d["company"] == "RunVouch"
    assert d["onderwerp"] == "Re: How many agents on the free plan?"


def test_ons_eigen_adres_wordt_nooit_de_ontvanger(T):
    """Een doorgestuurde mail staat vol met support@runvouch.com. Daar antwoorden we niet naartoe."""
    assert T._aan_wie("From: support@runvouch.com\nTo: keith\n\nfwd van iemand@klant.nl") == "iemand@klant.nl"
    assert T._aan_wie("geen enkel adres hier") == ""


def test_ja_verstuurt_de_klaargezette_mail(T, tmp_path, monkeypatch):
    import json as _j
    T.MAIL_STATE = str(tmp_path / "mail.json")
    T.PR_STATE = str(tmp_path / "pr.json")
    open(T.MAIL_STATE, "w").write(_j.dumps({"naar": "someone@acme.com", "company": "RunVouch",
                                            "onderwerp": "Re: vraag", "tekst": "Het antwoord."}))
    monkeypatch.setattr(T, "_resend_sleutel", lambda pad: "re_test")
    verstuurd = {}

    class Antwoord:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"id":"abc"}'

    def nep(req, timeout=0):
        verstuurd["body"] = _j.loads(req.data)
        return Antwoord()

    monkeypatch.setattr(T.urllib.request, "urlopen", nep)
    uit = T.handle("ja")
    assert "Verstuurd aan someone@acme.com" in uit[0]
    assert verstuurd["body"]["from"].endswith("<support@runvouch.com>")
    assert verstuurd["body"]["subject"] == "Re: vraag"
    assert _j.load(open(T.MAIL_STATE)) == {}
