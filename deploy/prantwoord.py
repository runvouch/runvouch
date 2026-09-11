#!/usr/bin/env python3
"""prantwoord.py: staat er iets open op een van onze pull requests, schrijf dan het antwoord en leg het klaar.

prwacht ziet dat de bal bij ons ligt. Dat is de helft: op 11 september wisten we om 04:15 wat er moest gebeuren en
stond het om 15:55 nog steeds stil. Niet omdat het moeilijk was, maar omdat er een tabblad open moest, de draad
teruggelezen en een antwoord getypt. Deze wacht doet dat deel, en laat de beslissing waar hij hoort.

Het concept komt in Telegram te staan met de vraag erboven. Antwoord je `ja`, dan plaatst telegram-antwoord.py het
in de draad. Antwoord je iets anders, dan gebeurt er niets en schrijf je het zelf. Jij blijft degene die naar
buiten treedt, alleen kost het twee seconden in plaats van tien minuten.

Eén concept tegelijk. Een stapel open vragen die allemaal met `ja` beantwoord kunnen worden is precies hoe je per
ongeluk het verkeerde antwoord in de verkeerde draad zet.

State in data/prantwoord.json: de PR, de laatste reactie waarop dit antwoord slaat, en de tekst.
"""
import importlib.util
import json
import os
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
STATE = os.path.join(ROOT, "data", "prantwoord.json")
spec = importlib.util.spec_from_file_location("prwacht", os.path.join(HIER, "prwacht.py"))
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
spec2 = importlib.util.spec_from_file_location("scout", os.path.join(HIER, "reddit-scout.py"))
S = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(S)

# Wat dit antwoord moet zijn, en vooral wat het niet mag zijn. Elke regel hier staat er omdat een tekst zonder die
# regel te herkennen is als machinewerk, en op een lijst van een vreemde is dat het einde van het gesprek.
REGELS = """You write ONE reply in a GitHub pull request thread. The pull request is ours: we submitted an entry and
a maintainer, a contributor or a bot has said something. Write what the person who did the work would write.

Answer the actual question in the first sentence. Not a greeting that repeats the question back, not a compliment,
not a summary of the thread. If they asked for a change, say whether it is done, being done, or why not.

Hard rules on the writing, all of them:
- No opener like "Great question", "Thanks for the detailed review", "You're absolutely right", "Happy to help".
- No closer like "Let me know if you need anything else", "Hope this helps", "Looking forward to your thoughts".
- No "Additionally", "Moreover", "Furthermore", "That said", "In conclusion", "Overall".
- No em dashes. A comma, a colon or a full stop.
- No bullet list unless the answer genuinely is a list of separate items. Prose by default.
- No bold for emphasis. Backticks only for code, paths, flags and endpoints.
- No emoji.
- Short sentences, one idea each, and vary the length: a four word sentence after a long one reads like a person.
- Concrete over adjective. "7,687 rows" beats "a significant number of rows".
- Never invent a fact, a number, a date or a feature. If you need something you were not given, leave it out or
  say you will check. A wrong number in a public thread is worse than a short answer.
- Say the limitation before they find it. If their point is fair, say it is fair in four words and move on, without
  apologising twice.
- If a change is needed, say concretely what you will change, not that you will "look into it".
- 40 to 140 words. A maintainer reads twenty of these a day.

Output only the reply text. No subject, no signature, no markdown headers."""


def bewaar(d: dict) -> None:
    with open(STATE, "w") as f:
        json.dump(d, f)


def openstaand() -> dict:
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def draad(url: str) -> tuple:
    """De hele draad als platte tekst, plus de id van de laatste zinvolle reactie."""
    d = W.gh("pr", "view", url, "--json", "title,body,comments,reviews,url")
    reacties = W.zinvolle_reacties(d.get("comments") or [])
    regels = [f"PULL REQUEST: {d.get('title', '')}", (d.get("body") or "")[:1200]]
    for r in (d.get("reviews") or []):
        if r.get("body"):
            regels.append(f"REVIEW {r['author']['login']} ({r.get('state')}): {r['body'][:900]}")
    for c in reacties:
        regels.append(f"COMMENT {c['author']['login']}: {(c.get('body') or '')[:900]}")
    try:
        diff = subprocess.run([W.GH, "pr", "diff", url], capture_output=True, text=True, timeout=60).stdout
        toegevoegd = "\n".join(l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        if toegevoegd:
            regels.append("OUR ENTRY AS IT STANDS:\n" + toegevoegd[:1200])
    except Exception:
        pass
    return "\n\n".join(regels), (reacties[-1]["id"] if reacties else "")


def schrijf(context: str) -> str:
    try:
        r = subprocess.run([S.CLAUDE, "-p", REGELS + "\n\nTHREAD:\n" + context[:9000],
                            "--output-format", "json", "--max-turns", "1"],
                           capture_output=True, text=True, timeout=240)
        antwoord = json.loads(r.stdout or "{}")
        # In dezelfde pot als de scout, want die wordt onderaan als RUNVOUCH_COST afgedrukt. Zonder deze regel
        # telt de som nul en is elk concept gratis in de cijfers, precies de fout die we net bij de vloot vonden.
        S.UITGAVEN.append(antwoord.get("total_cost_usd", 0) or 0)
        return antwoord.get("result", "").strip()
    except Exception as e:
        print("schrijven mislukt:", e, file=sys.stderr)
        return ""


def main() -> int:
    al = openstaand()
    if al.get("tekst") and "--opnieuw" not in sys.argv:
        print(f"er staat er al een klaar voor {al.get('url')}; beantwoord die eerst in Telegram")
        return 0
    eigenaars = {a.lower() for a in W.ACCOUNTS}
    for account in W.ACCOUNTS:
        try:
            prs = W.gh("search", "prs", "--author", account, "--state", "open", "--limit", "40",
                       "--json", "url,title,repository")
        except Exception as e:
            print(f"zoeken mislukt: {e}", file=sys.stderr)
            continue
        for pr in prs:
            url = pr["url"]
            try:
                reden, _ = W.beoordeel(url, eigenaars)
            except Exception as e:
                print(f"{url}: {e}", file=sys.stderr)
                continue
            if not reden:
                continue
            context, laatste = draad(url)
            tekst = schrijf(context)
            if not tekst:
                continue
            repo = (pr.get("repository") or {}).get("nameWithOwner", "?")
            bewaar({"url": url, "repo": repo, "reden": reden, "laatste": laatste, "tekst": tekst})
            W.telegram(f"{tekst}\n\n^ GITHUB {repo}\n{reden}\n{url}\n\nAntwoord 'ja' om dit zo te plaatsen, of "
                       f"schrijf je eigen versie en plak die hier met 'github:' ervoor.")
            # rv run leest deze regel en zet het bedrag op de run, zodat de BUDGET-detectoren ook bij
            # onze eigen schrijfwerk iets te vergelijken hebben. Zonder dit is elk concept gratis in de cijfers.
            print(f"RUNVOUCH_COST={round(sum(S.UITGAVEN), 6)}")
            print(f"concept klaar voor {url}")
            return 0
    print("niets openstaand")
    return 0


if __name__ == "__main__":
    sys.exit(main())
