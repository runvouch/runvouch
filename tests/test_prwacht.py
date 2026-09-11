"""Wie is aan zet bij een open pull request, en vooral: wanneer zegt de wacht niets.

Op 11 september meldde deze wacht twee PR's waarvan de laatste reactie van Vercel kwam ("een teamlid moet de
preview goedkeuren") en van Qodo ("onze reviews staan uit wegens een abonnement"). Daar kun je niets mee, en een
dagelijkse melding die je niets laat doen leer je binnen een week wegkijken. Diezelfde dag vroeg een bot bij
punkpeye wel iets echts: verander dat ene teken. Botberichten allemaal doorlaten is dus net zo fout als ze
allemaal negeren, en deze tests leggen vast waar de grens ligt.
"""
import importlib.util
import os
import time

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("prwacht", os.path.join(os.path.dirname(HIER), "deploy", "prwacht.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

ONS = {"runvouch"}
VERS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def pr(comments=(), reviews=(), checks=(), draft=False, bijgewerkt=VERS):
    return {"isDraft": draft, "updatedAt": bijgewerkt, "comments": list(comments),
            "reviews": list(reviews), "statusCheckRollup": list(checks)}


def reactie(login, body="iets", id_="c1"):
    return {"id": id_, "author": {"login": login}, "body": body}


def test_een_bouwbot_die_als_laatste_schrijft_is_geen_melding():
    d = pr(comments=[reactie("runvouch", "ingediend"), reactie("vercel", "A member of the Team must authorize")])
    reden, _ = P.aan_zet(d, ONS)
    assert reden == "", "Vercel vraagt niets van ons en hoort geen dagelijkse melding te zijn"


def test_een_gepauzeerde_reviewbot_ook_niet():
    d = pr(comments=[reactie("runvouch", "ingediend"), reactie("qodo-code-review", "Reviews are paused for this user")])
    assert P.aan_zet(d, ONS)[0] == ""


def test_een_bot_die_wel_iets_vraagt_meldt_wel():
    """github-actions droeg het enige echte verzoek van die dag: verander de marker."""
    d = pr(comments=[reactie("runvouch", "ingediend"),
                     reactie("github-actions", "The auth marker does not match. Please correct it.", "c9")])
    reden, _ = P.aan_zet(d, ONS)
    assert "github-actions" in reden and "auth marker" in reden


def test_ruis_bovenop_een_echt_verzoek_verbergt_het_verzoek_niet():
    """Een bouwbot die na de beheerder schrijft mag het verzoek niet uit beeld duwen."""
    d = pr(comments=[reactie("punkpeye", "Please update the entry and push.", "c7"),
                     reactie("vercel", "deployment status", "c8")])
    reden, stempel = P.aan_zet(d, ONS)
    assert "punkpeye" in reden
    assert "c7" in stempel, "de stempel hoort bij de laatste zinvolle reactie, niet bij de ruis erna"


def test_een_rode_controle_van_een_bouwbot_telt_niet():
    d = pr(comments=[reactie("runvouch", "ingediend")],
           checks=[{"name": "Vercel", "conclusion": "FAILURE"}])
    assert P.aan_zet(d, ONS)[0] == "", "een niet-goedgekeurde preview is geen fout in onze wijziging"


def test_een_rode_controle_van_de_repo_zelf_telt_wel():
    d = pr(comments=[reactie("runvouch", "ingediend")],
           checks=[{"name": "lint", "conclusion": "FAILURE"}])
    assert "lint" in P.aan_zet(d, ONS)[0]


def test_wijzigingen_gevraagd_blijft_staan():
    d = pr(comments=[reactie("runvouch", "ingediend")],
           reviews=[{"state": "CHANGES_REQUESTED", "author": {"login": "punkpeye"}}])
    assert "vraagt wijzigingen" in P.aan_zet(d, ONS)[0]


def test_wij_schreven_het_laatst_en_het_is_vers():
    d = pr(comments=[reactie("punkpeye", "thanks"), reactie("runvouch", "gedaan", "c2")])
    assert P.aan_zet(d, ONS)[0] == ""


def test_wij_schreven_het_laatst_maar_het_staat_te_lang_stil():
    oud = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 20 * 86400))
    d = pr(comments=[reactie("runvouch", "gedaan")], bijgewerkt=oud)
    assert "dagen stil" in P.aan_zet(d, ONS)[0]


def test_een_concept_zegt_nooit_iets():
    d = pr(comments=[reactie("punkpeye", "graag aanpassen")], draft=True)
    assert P.aan_zet(d, ONS)[0] == ""
