"""The site: every integration page is specific and complete, and the built output has no em dashes."""
import sys, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
import integrations as I


def test_every_integration_is_complete_and_unique():
    slugs = [i["slug"] for i in I.INTEGRATIONS]
    assert len(slugs) == len(set(slugs))
    intros = [i["intro"] for i in I.INTEGRATIONS]
    assert len(intros) == len(set(intros)), "two pages share an intro"
    for i in I.INTEGRATIONS:
        for k in ("slug", "name", "group", "title", "desc", "h1", "intro", "where", "key", "snippet", "silent", "missing", "mode"):
            assert i.get(k), f"{i['slug']}: {k} missing"
        assert i["group"] in I.GROUPS
        assert i["mode"] in ("wrap", "http")
        assert re.fullmatch(r"[a-z0-9-]+", i["slug"])
        assert "rv run" in i["snippet"] or '"rv", "run"' in i["snippet"] or "--command rv" in i["snippet"] or "/v1/runs/start" in i["snippet"] or "runvouch.vouch(" in i["snippet"] or "rv.vouch(" in i["snippet"], i["slug"]
        assert "<li>" in i["silent"], f"{i['slug']}: silent-failure list missing"
        assert i["missing"].startswith("<p>") and 120 < len(re.sub("<[^>]+>", "", i["missing"])) < 1200, f"{i['slug']}: missing-section length"
        assert "—" not in str(i), f"{i['slug']}: em dash"


def test_no_client_calls_that_do_not_exist():
    for i in I.INTEGRATIONS:
        assert "runvouch.start(" not in i["snippet"] and "run.cost(" not in i["snippet"], i["slug"]


def test_built_site_has_no_em_dash_except_the_quote():
    pub = ROOT / "site" / "public"
    if not pub.exists():
        return
    for f in pub.rglob("*.html"):
        t = f.read_text(encoding="utf-8").replace("the routine ran — it does not mean", "")
        assert "—" not in t, f.relative_to(pub)
