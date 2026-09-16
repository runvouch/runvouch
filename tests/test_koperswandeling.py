"""Wat er gebeurt als de wandeling niet uitloopt op een rapport.

Op 14 september 2026 liep een tweede wandeling over de 40 minuten heen. De TimeoutExpired kwam ongevangen naar
buiten: geen rapportbestand, geen Telegram, alleen een FAILED-alarm zonder tekst. Een wacht die stil faalt is
erger dan geen wacht, dus leggen deze tests vast dat elke afloop een bericht en een bestand oplevert.
"""
import importlib.util
import json
import os
import subprocess

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "koperswandeling", os.path.join(os.path.dirname(HIER), "deploy", "koperswandeling.py"))
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)


def wandeling(monkeypatch, tmp_path, draai):
    verstuurd = []
    monkeypatch.setattr(K, "OUT", str(tmp_path))
    monkeypatch.setattr(K, "telegram", lambda tekst: verstuurd.append(tekst))
    monkeypatch.setattr(K.subprocess, "run", draai)
    code = K.main()
    bestanden = sorted(p for p in os.listdir(tmp_path) if p.endswith(".md"))
    return code, verstuurd, (tmp_path / bestanden[0]).read_text() if bestanden else ""


def test_tijdslimiet_levert_toch_een_bericht_en_een_bestand(monkeypatch, tmp_path):
    def draai(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=K.TIJD)
    code, verstuurd, rapport = wandeling(monkeypatch, tmp_path, draai)
    assert code == 1
    assert len(verstuurd) == 1 and "40 minutes" in verstuurd[0]
    assert rapport.startswith("Koperswandeling kon niet worden afgerond")


def test_gewone_wandeling_meldt_ok_en_valt_niet_om(monkeypatch, tmp_path):
    class Af:
        stdout = json.dumps({"result": "OK", "total_cost_usd": 1.23})
        stderr = ""
    code, verstuurd, rapport = wandeling(monkeypatch, tmp_path, lambda *a, **k: Af())
    assert code == 0
    assert len(verstuurd) == 1 and verstuurd[0].endswith("OK, beide sites zonder defecten.")
    assert rapport.strip() == "OK"


def test_defecten_zijn_werk_en_geen_storing(monkeypatch, tmp_path):
    class Af:
        stdout = json.dumps({"result": "DEFECTEN: 1\nrunvouch.com /pricing knop doet niets", "total_cost_usd": 1.0})
        stderr = ""
    code, verstuurd, rapport = wandeling(monkeypatch, tmp_path, lambda *a, **k: Af())
    assert code == 0
    assert "DEFECTEN: 1" in verstuurd[0] and "DEFECTEN: 1" in rapport
