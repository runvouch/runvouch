#!/usr/bin/env python3
"""
Verify a RunVouch run proof without trusting RunVouch. Python 3 standard library only.

  python3 verify_proof.py proof.json              (fetches the public day file from proof["verify_url"])
  python3 verify_proof.py proof.json day.json     (fully offline: the day file you saved or downloaded earlier)

proof.json is what GET /v1/runs/{run_id}/proof (or `rv proof RUN_ID`) returned.

Checks, in order:
  1. leaf_hash == sha256(canonical JSON of proof["record"])          the record was not altered
  2. walking merkle_path from the leaf reproduces proof["root"]       the leaf belongs to that root
  3. the day file lists the same leaf under the same run_id            and its own root, recomputed from all
     leaves in the file, equals proof["root"]                         its leaves, is that root
  4. chain_hash == sha256(prev + ":" + date + ":" + root)             the day sits in the chain

What this does NOT check: the Bitcoin anchor. For that, download the .ots file next to the day file and run
`ots verify DATE.json.ots -f DATE.json` with the OpenTimestamps client (pip install opentimestamps-client).
Exit code 0 means every check passed; 1 means at least one failed.
"""
import hashlib
import json
import sys
import urllib.request


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


def merkle_root(leaves):
    if not leaves:
        return sha256("")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [sha256(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    proof = json.load(open(argv[1]))
    if len(argv) > 2:
        day = json.load(open(argv[2]))
    else:
        print("fetching", proof["verify_url"])
        day = json.loads(urllib.request.urlopen(proof["verify_url"], timeout=20).read())
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail and not cond else ""))

    leaf = sha256(canonical(proof["record"]))
    check("leaf hash matches the record", leaf == proof["leaf_hash"], f"computed {leaf}")
    h = leaf
    for sib, side in proof["merkle_path"]:
        h = sha256(sib + h) if side == "left" else sha256(h + sib)
    check("merkle path leads to the root", h == proof["root"], f"computed {h}")
    mine = [x for x in day["leaves"] if x["run_id"] == proof["run_id"]]
    check("day file lists this run with this leaf", mine and mine[0]["leaf"] == leaf)
    day_root = merkle_root([x["leaf"] for x in day["leaves"]])
    check("day file root recomputed from its leaves", day_root == day["root"] == proof["root"], f"computed {day_root}")
    ch = sha256(f"{day['prev']}:{day['date']}:{day['root']}")
    check("chain hash of the day", ch == day["chain_hash"] and (proof.get("chain_hash") in (None, ch)), f"computed {ch}")
    print("date", day["date"], "runs", day["n_runs"], "chain", day["chain_hash"][:16] + "...", "ots", proof.get("ots_status"))
    print("VERIFIED" if ok else "NOT VERIFIED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
