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
_st = json.load(open(STATE)) if os.path.exists(STATE) else []
seen = set(_st if isinstance(_st, list) else _st.get("seen", []))
last = {} if isinstance(_st, list) else _st.get("last", {})   # agent -> unix time of last retry
RETRY_EVERY = 24 * 3600  # one retry per agent per day: a retry that fails raises a new alert, and retrying THAT is a loop
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
jobs = {}
for l in cron:
    m = re.search(r"/home/krtradingpro/bin/rv run (\S+) (.*)$", l)
    if m: jobs[m.group(1)] = m.group(2)
alerts = [a for a in api("GET", "/v1/alerts") if a["kind"] in ("FAILED", "MISSED", "NO_EVIDENCE") and a["agent"] in jobs and a["agent"] != "blogmotor" and a["id"] not in seen]
done = 0
for a in alerts:
    if time.time() - last.get(a["agent"], 0) < RETRY_EVERY:
        api("POST", f"/v1/alerts/{a['id']}/ack"); seen.add(a["id"])   # already retried today: the human has the first alert
        print(f"skip {a['agent']} (alert #{a['id']}): retried {int((time.time()-last[a['agent']])/60)} min ago")
        continue
    if done >= 3:
        break
    last[a["agent"]] = time.time()
    args = jobs[a["agent"]].replace("--source cron", "--source remediator")
    print(f"retrying {a['agent']} (alert #{a['id']} {a['kind']})"); t0 = time.time()
    r = subprocess.run("/home/krtradingpro/bin/rv run " + a["agent"] + " " + args, shell=True, capture_output=True, text=True, timeout=3600)
    api("POST", f"/v1/alerts/{a['id']}/ack"); seen.add(a["id"]); done += 1
    print(f"  exit {r.returncode} in {int(time.time()-t0)}s")
json.dump({"seen": sorted(seen)[-500:], "last": last}, open(STATE, "w"))
print(f"remediated {done} of {len(alerts)} open alerts")
