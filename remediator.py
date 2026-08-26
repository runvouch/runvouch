#!/usr/bin/env python3
"""remediator.py — self-healing for our own cron jobs (dogfood).
Every 15 min: for each OPEN alert of kind FAILED/MISSED/NO_EVIDENCE on an agent that is a crontab job,
re-run that job ONCE (same command, via rv run so the retry is itself vouched), then ack the alert.
Never retries blogmotor; never retries the same alert twice; max 3 retries per run of this script.
"""
import json, os, re, subprocess, sys, time, urllib.request
REPO = os.path.dirname(os.path.abspath(__file__))
env = {l.split("=",1)[0]: l.split("=",1)[1].strip() for l in open(os.path.join(REPO, ".env")) if "=" in l and not l.startswith("#")}
KEY, URL = env["RUNVOUCH_KEY"], "http://127.0.0.1:8787"
def api(m, path, body=None):
    req = urllib.request.Request(URL+path, json.dumps(body).encode() if body else None, {"X-API-Key": KEY, "Content-Type": "application/json", "User-Agent": "rv-remediator"}, method=m)
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")
STATE = os.path.join(REPO, "data", "remediated.json")
seen = set(json.load(open(STATE))) if os.path.exists(STATE) else set()
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
jobs = {}
for l in cron:
    m = re.search(r"/home/krtradingpro/bin/rv run (\S+) (.*)$", l)
    if m: jobs[m.group(1)] = m.group(2)
alerts = [a for a in api("GET", "/v1/alerts") if a["kind"] in ("FAILED", "MISSED", "NO_EVIDENCE") and a["agent"] in jobs and a["agent"] != "blogmotor" and a["id"] not in seen]
done = 0
for a in alerts[:3]:
    args = jobs[a["agent"]].replace("--source cron", "--source remediator")
    print(f"retrying {a['agent']} (alert #{a['id']} {a['kind']})"); t0 = time.time()
    r = subprocess.run("/home/krtradingpro/bin/rv run " + a["agent"] + " " + args, shell=True, capture_output=True, text=True, timeout=3600)
    api("POST", f"/v1/alerts/{a['id']}/ack"); seen.add(a["id"]); done += 1
    print(f"  exit {r.returncode} in {int(time.time()-t0)}s")
json.dump(sorted(seen)[-500:], open(STATE, "w"))
print(f"remediated {done} of {len(alerts)} open alerts")
