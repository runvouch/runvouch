"""Wat er in de cumulatieve bouwlijst belandt.

Op 30 september 2026 opende het rapport met de zin "BOUWLIJST-onderzoek is klaar. Hieronder het rapport."
De filing zocht met index() naar het woord BOUWLIJST, vond dat op positie 0 en schreef alle zestig regels van
het rapport in data/marktwacht/bouwlijst.md onder het kopje van die dag. Het ene document dat het gat met de
markt laat zien werd daarmee onleesbaar, dus leggen deze tests vast dat alleen een losse regel BOUWLIJST de
sectie opent en dat de laatste zo'n regel wint.
"""
import importlib.util
import json
import os

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "marktwacht", os.path.join(os.path.dirname(HIER), "deploy", "marktwacht.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def wacht(monkeypatch, tmp_path, rapport):
    class Af:
        stdout = json.dumps({"result": rapport, "total_cost_usd": 3.29})
        stderr = ""
    monkeypatch.setattr(M, "OUT", str(tmp_path))
    monkeypatch.setattr(M, "telegram", lambda tekst: None)
    monkeypatch.setattr(M.subprocess, "run", lambda *a, **k: Af())
    assert M.main() == 0
    bl = tmp_path / "bouwlijst.md"
    return bl.read_text() if bl.exists() else ""


def test_bouwlijst_krijgt_alleen_de_sectie_en_niet_het_hele_rapport(monkeypatch, tmp_path):
    lijst = wacht(monkeypatch, tmp_path, "BOUWLIJST-onderzoek is klaar. Hieronder het rapport.\n\n"
                                         "1. Wijzigingen\nCronitor: geen wijziging gevonden.\n\n"
                                         "BOUWLIJST\nDiscord als alertkanaal. Healthchecks.io, 2 dagen.")
    assert "Discord als alertkanaal" in lijst
    assert "onderzoek is klaar" not in lijst
    assert "Cronitor" not in lijst


def test_zonder_losse_markerregel_blijft_de_bouwlijst_ongemoeid(monkeypatch, tmp_path):
    assert wacht(monkeypatch, tmp_path, "De BOUWLIJST van vorige keer is nog actueel, niets nieuws.") == ""


def test_rapport_zelf_wordt_wel_altijd_weggeschreven(monkeypatch, tmp_path):
    wacht(monkeypatch, tmp_path, "BOUWLIJST\ngeen")
    rapporten = [p for p in os.listdir(tmp_path) if p.endswith(".md") and p != "bouwlijst.md"]
    assert len(rapporten) == 1
    assert (tmp_path / rapporten[0]).read_text().startswith("BOUWLIJST")
