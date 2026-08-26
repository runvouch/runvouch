#!/usr/bin/env python3
"""
rv — RunVouch client CLI. Zero dependencies (stdlib only) so it runs in any cron/agent environment.

  rv agent  NAME [--cadence 24h] [--cap-run-cost 2] [--cap-day-cost 10] [--evidence]
  rv run    NAME [--evidence-file PATH] [--evidence-url URL] [--source cron] -- CMD ARGS...
  rv start  NAME            -> prints run_id
  rv tool   RUN_ID TOOL [--input JSON] [--cost X] [--tokens N] [--fail]
  rv end    RUN_ID [--status ok|fail] [--cost X] [--tokens N] [--evidence JSON]
  rv status                 -> table of agents
  rv alerts [--ack ID]
  rv proof  RUN_ID [--verify]  -> tamper-evident proof of a finished run; --verify recomputes it against the public day file

Env: RUNVOUCH_URL (default http://localhost:8787), RUNVOUCH_KEY
"""
import argparse, hashlib, json, os, subprocess, sys, time, urllib.request

URL = os.getenv("RUNVOUCH_URL", "http://localhost:8787").rstrip("/")
KEY = os.getenv("RUNVOUCH_KEY", "")


def api(method, path, body=None, params=None, soft=False, _retries=3):
    """soft=True: never raise/exit (used by `rv run` so monitoring can't break the job)."""
    if not KEY:
        if soft:
            sys.stderr.write("runvouch: RUNVOUCH_KEY not set, running unmonitored\n"); return None
        sys.exit("RUNVOUCH_KEY not set")
    url = URL + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"X-API-Key": KEY, "Content-Type": "application/json", "User-Agent": "runvouch-cli/0.2"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except Exception as e:
        msg = f"RunVouch {getattr(e, 'code', '')}: {getattr(e, 'reason', e)}"
        if soft and _retries > 0 and getattr(e, 'code', 0) in (0, 502, 503, 504):
            time.sleep(3); return api(method, path, body, params, soft, _retries - 1)
        if soft:
            sys.stderr.write("runvouch: " + msg + " (running unmonitored)\n"); return None
        sys.exit(msg)


def dur(s):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return int(float(s[:-1]) * units[s[-1]]) if s and s[-1] in units else int(s)


def main(argv=None):
    p = argparse.ArgumentParser(prog="rv")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("agent"); a.add_argument("name"); a.add_argument("--cadence"); a.add_argument("--grace", default="15m")
    a.add_argument("--max-runtime", default="1h"); a.add_argument("--cap-run-cost", type=float); a.add_argument("--cap-day-cost", type=float)
    a.add_argument("--cap-run-tokens", type=int); a.add_argument("--evidence", action="store_true")
    r = sub.add_parser("run"); r.add_argument("name"); r.add_argument("--evidence-file", action="append", default=[])
    r.add_argument("--evidence-url", action="append", default=[]); r.add_argument("--source", default="cron")
    r.add_argument("--log", help="append the command's stdout+stderr to this file (rv writes it, so it can double as evidence)")
    s = sub.add_parser("start"); s.add_argument("name"); s.add_argument("--source", default="custom")
    t = sub.add_parser("tool"); t.add_argument("run_id"); t.add_argument("tool"); t.add_argument("--input"); t.add_argument("--cost", type=float, default=0)
    t.add_argument("--tokens", type=int, default=0); t.add_argument("--fail", action="store_true")
    e = sub.add_parser("end"); e.add_argument("run_id"); e.add_argument("--status", default="ok"); e.add_argument("--cost", type=float, default=0)
    e.add_argument("--tokens", type=int, default=0); e.add_argument("--evidence"); e.add_argument("--output-bytes", type=int)
    sub.add_parser("status")
    al = sub.add_parser("alerts"); al.add_argument("--ack", type=int)
    pr = sub.add_parser("proof"); pr.add_argument("run_id"); pr.add_argument("--verify", action="store_true")
    argv = list(sys.argv[1:] if argv is None else argv)
    tail = []
    if argv and argv[0] == "run" and "--" in argv:
        i = argv.index("--"); tail = argv[i + 1:]; argv = argv[:i]
    args = p.parse_args(argv)

    if args.cmd == "agent":
        print(api("POST", "/v1/agents", {"name": args.name, "cadence_s": dur(args.cadence) if args.cadence else None,
                                         "grace_s": dur(args.grace), "max_runtime_s": dur(args.max_runtime),
                                         "cap_run_cost": args.cap_run_cost, "cap_day_cost": args.cap_day_cost,
                                         "cap_run_tokens": args.cap_run_tokens, "evidence_required": args.evidence}))
    elif args.cmd == "start":
        print(api("POST", "/v1/runs/start", {"agent": args.name, "source": args.source})["run_id"])
    elif args.cmd == "tool":
        inp = json.loads(args.input) if args.input else None
        api("POST", "/v1/runs/tool", {"run_id": args.run_id, "tool": args.tool, "input": inp, "cost": args.cost, "tokens": args.tokens, "ok": not args.fail})
    elif args.cmd == "end":
        ev = json.loads(args.evidence) if args.evidence else {}
        print(api("POST", "/v1/runs/end", {"run_id": args.run_id, "status": args.status, "cost": args.cost, "tokens": args.tokens,
                                           "evidence": ev, "output_bytes": args.output_bytes}))
    elif args.cmd == "run":
        cmd = tail
        if not cmd:
            sys.exit("rv run NAME -- CMD ...")
        args.evidence_file = [os.path.abspath(f) for f in args.evidence_file]
        r0 = api("POST", "/v1/runs/start", {"agent": args.name, "source": args.source, "meta": {"cmd": " ".join(cmd)}}, soft=True)
        rid = r0.get("run_id") if r0 else None
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")
        if args.log:
            with open(args.log, "a") as lf:
                lf.write(out)
        else:
            sys.stdout.write(proc.stdout or ""); sys.stderr.write(proc.stderr or "")
        evidence = {}
        for f in args.evidence_file:  # evidence = file exists AND was modified during the run AND non-empty
            ok = os.path.exists(f) and os.path.getsize(f) > 0 and os.path.getmtime(f) >= t0 - 1
            evidence[f"file:{os.path.basename(f)}"] = bool(ok)
        for u in args.evidence_url:
            evidence[f"url:{u}"] = {"type": "url", "url": u, "expect": 200}
        res = rid and api("POST", "/v1/runs/end", {"run_id": rid, "status": "ok" if proc.returncode == 0 else "fail",
                                           "output_bytes": len(out.encode()), "evidence": evidence,
                                           "meta": {"exit": proc.returncode, "error": (proc.stderr or "")[-500:] if proc.returncode else ""}}, soft=True)
        sys.exit(proc.returncode)
    elif args.cmd == "status":
        for ag in api("GET", "/v1/agents"):
            l = ag["last_run"]
            print(f"{ag['name']:24s} {ag['state']:9s} last={time.strftime('%m-%d %H:%M', time.localtime(l['started'])) if l else '—':12s} "
                  f"cost24h={ag['cost_24h']:<8} alerts={ag['open_alerts']}")
    elif args.cmd == "alerts":
        if args.ack:
            api("POST", f"/v1/alerts/{args.ack}/ack"); print("acked")
        else:
            for x in api("GET", "/v1/alerts"):
                print(f"#{x['id']} {time.strftime('%m-%d %H:%M', time.localtime(x['ts']))} {x['agent']} [{x['kind']}] {x['message']}")
    elif args.cmd == "proof":
        pf = api("GET", f"/v1/runs/{args.run_id}/proof")
        print(json.dumps(pf, indent=1))
        if args.verify:
            sys.exit(0 if verify_proof(pf) else 1)


def verify_proof(pf):
    """Same rules as templates/verify_proof.py: recompute leaf and path locally, then compare with the public day file."""
    sha = lambda x: hashlib.sha256(x.encode()).hexdigest()
    leaf = sha(json.dumps(pf["record"], sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    h = leaf
    for sib, side in pf["merkle_path"]:
        h = sha(sib + h) if side == "left" else sha(h + sib)
    ok = leaf == pf["leaf_hash"] and h == pf["root"]
    print("leaf", "ok" if leaf == pf["leaf_hash"] else "MISMATCH", "| path to root", "ok" if h == pf["root"] else "MISMATCH")
    if not pf.get("sealed"):
        print("day not sealed yet: the root above is live and may still change; run again after the UTC day ends")
        return False
    try:
        day = json.loads(urllib.request.urlopen(urllib.request.Request(pf["verify_url"], headers={"User-Agent": "runvouch-cli/0.3"}), timeout=20).read())
    except Exception as e:
        print("could not fetch day file:", e); return False
    lv = [x["leaf"] for x in day["leaves"]]
    level = list(lv) or [sha("")]
    while len(level) > 1:
        if len(level) % 2: level.append(level[-1])
        level = [sha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    in_day = any(x["run_id"] == pf["run_id"] and x["leaf"] == leaf for x in day["leaves"])
    root_ok = level[0] == day["root"] == pf["root"]
    chain_ok = sha(f"{day['prev']}:{day['date']}:{day['root']}") == day["chain_hash"] == pf["chain_hash"]
    print("day file", "lists this leaf" if in_day else "DOES NOT list this leaf", "| day root", "ok" if root_ok else "MISMATCH", "| chain", "ok" if chain_ok else "MISMATCH", "| ots", pf.get("ots_status"))
    ok = ok and in_day and root_ok and chain_ok
    print("VERIFIED" if ok else "NOT VERIFIED")
    return ok


if __name__ == "__main__":
    main()
