#!/usr/bin/env python3
"""kostenmeting.py: is er inmiddels genoeg kostendata om er een pagina op te bouwen?

Op 12 september meldden 2 van 4.098 runs wat ze kostten. Dat waren twee gaten, niet een kapot mechanisme, en die
zijn diezelfde dag gedicht. Maar een gat dichten levert pas cijfers op als er een week overheen is gegaan, en de
vraag "wat kost het om een agent onbewaakt te laten draaien" is er een waar kopers op zoeken en waar vrijwel
niemand een eerlijk antwoord op publiceert, omdat vrijwel niemand het meet.

Deze meting kijkt een week later of het genoeg is, en stuurt de cijfers zodat de pagina te schrijven valt. Genoeg
is: minstens 20 runs met een bedrag erop, verdeeld over minstens 2 taken. Onder die grens is het geen meting maar
een anekdote, en een pagina met een anekdote erop is precies wat de rest van deze markt al doet.

Eenmalig. Draait op 19 september en daarna nooit meer; de timer mag daarna weg.
"""
import importlib.util
import os
import sqlite3
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
spec = importlib.util.spec_from_file_location("prwacht", os.path.join(HIER, "prwacht.py"))
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
DREMPEL_RUNS, DREMPEL_TAKEN = 20, 2


def main() -> int:
    env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip()
           for l in open(os.path.join(ROOT, ".env")) if "=" in l and not l.startswith("#")}
    c = sqlite3.connect(f"file:{env['RUNVOUCH_DB']}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sinds = time.time() - 7 * 86400
    rijen = c.execute(
        "SELECT g.name, COUNT(*) n, SUM(r.cost) som, AVG(r.cost) gem, MAX(r.cost) piek "
        "FROM runs r JOIN agents g ON g.id = r.agent_id "
        "WHERE r.cost > 0 AND r.started > ? GROUP BY g.name ORDER BY som DESC", (sinds,)).fetchall()
    runs = sum(r["n"] for r in rijen)
    totaal = sum(r["som"] for r in rijen)
    alle = c.execute("SELECT COUNT(*) n FROM runs WHERE ended IS NOT NULL AND ended > ?", (sinds,)).fetchone()["n"]

    regels = [f"{r['name']}: {r['n']}x, samen ${r['som']:.2f}, gemiddeld ${r['gem']:.4f}, duurste ${r['piek']:.4f}"
              for r in rijen[:8]]
    kop = (f"Kostenmeting, 7 dagen: {runs} van {alle} runs meldden een bedrag, samen ${totaal:.2f} "
           f"over {len(rijen)} taken.")
    if runs >= DREMPEL_RUNS and len(rijen) >= DREMPEL_TAKEN:
        slot = ("Genoeg om de kostenpagina op te bouwen. Vraag de sessie om "
                "'schrijf de kostenpagina' en plak deze regels erbij.")
    else:
        slot = (f"Nog te weinig (drempel {DREMPEL_RUNS} runs over {DREMPEL_TAKEN} taken). Kijk of de taken die "
                f"Claude aanroepen wel draaien, of geef het nog een week.")
    W.telegram(kop + ("\n\n" + "\n".join(regels) if regels else "") + "\n\n" + slot)
    print(kop)
    for r in regels:
        print("  " + r)
    print(slot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
