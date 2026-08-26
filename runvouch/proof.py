"""
Verifiable runs: the hashing rules, nothing else (stdlib only, no DB, no HTTP).

leaf     = sha256(canonical_json(record))         record = the run's facts, never prompts/outputs/inputs
root     = Merkle root over the day's leaves       sorted by run_id; pairwise sha256(left + right) of the hex strings;
                                                   odd count -> last node paired with itself; empty day -> sha256("")
chain    = sha256(prev + ":" + date + ":" + root)  prev = chain hash of the previous sealed day, genesis = 64 zeros

templates/verify_proof.py repeats these rules on purpose, so a reader can check them without importing anything of ours.
"""
import hashlib
import json

GENESIS = "0" * 64
LEAF_KEYS = ("run_id", "agent", "account_id", "started", "ended", "status", "cost", "tokens", "tool_calls",
             "output_bytes", "evidence", "evidence_ok", "source", "exit", "tool_events_hash")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(s) -> str:
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def leaf_hash(record: dict) -> str:
    return sha256(canonical(record))


def tool_events_hash(events) -> str:
    """events: ordered list of (tool, input_hash, ok, ts)."""
    return sha256(canonical([[t, h, bool(ok), ts] for t, h, ok, ts in events]))


def merkle_root(leaves: list) -> str:
    if not leaves:
        return sha256("")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [sha256(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def merkle_path(leaves: list, index: int) -> list:
    """[(sibling_hash, side)] from leaf to root; side is where the SIBLING sits."""
    path, level, i = [], list(leaves), index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        if i % 2:
            path.append((level[i - 1], "left"))
        else:
            path.append((level[i + 1], "right"))
        level = [sha256(level[j] + level[j + 1]) for j in range(0, len(level), 2)]
        i //= 2
    return path


def apply_path(leaf: str, path: list) -> str:
    h = leaf
    for sib, side in path:
        h = sha256(sib + h) if side == "left" else sha256(h + sib)
    return h


def chain_hash(prev: str, date: str, root: str) -> str:
    return sha256(f"{prev}:{date}:{root}")
