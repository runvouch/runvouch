#!/usr/bin/env python3
"""remediator.py — 24/7 self-healing for our own cron jobs (dogfood for RunVouch, production for DataSignals).

Every 15 min (cron, wrapped in rv run): for each OPEN alert of kind FAILED / MISSED / NO_EVIDENCE on an agent
that is a crontab job:
  1. re-run the job once (transient failures end here);
  2. if it still fails, hand the log and the command to the local Claude Code CLI with a repair brief: find the
     cause, fix it minimally in the right repo, run the tests / quality gate, commit and push (hub for the landing
     site, origin elsewhere), never deploy, never touch secrets or the crontab;
  3. run the job once more; report on Telegram what was changed, or the diagnosis when a human is needed.
Limits: one repair attempt per agent per day, three repairs per day in total, never for blogmotor, one instance at a time.
"""
import fcntl, json, os, re, sqlite3, subprocess, sys, time, urllib.parse, urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
env = {l.split("=", 1)[0]: l.split("=", 1)[1].strip() for l in open(os.path.join(REPO, ".env")) if "=" in l and not l.startswith("#")}
KEY, URL = env["RUNVOUCH_KEY"], "http://127.0.0.1:8787"
CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")
STATE = os.path.join(REPO, "data", "remediated.json")
LOCK = os.path.join(REPO, "data", "remediator.lock")
RETRY_EVERY = 24 * 3600          # one retry + one repair attempt per agent per day
MAX_REPAIRS_PER_DAY = 3
NEVER = {"blogmotor", "blog-writer", "blog-queue", "reddit-scout", "clawhub-publish"}   # content jobs: a human decides
# where a job's code lives -> which git repo to fix and how to publish the fix
REPOS = [
    ("/home/krtradingpro/apify/landing-live/", "/home/krtradingpro/apify/landing", "git fetch -q hub && git rebase -q hub/main && git push -q hub HEAD:main"),
    ("/home/krtradingpro/apify/landing/", "/home/krtradingpro/apify/landing", "git fetch -q hub && git rebase -q hub/main && git push -q hub HEAD:main"),
    ("/home/krtradingpro/runvouch/", "/home/krtradingpro/runvouch", "git push -q origin main"),
    ("/home/krtradingpro/apify/", "/home/krtradingpro/apify", "git push -q origin HEAD"),
]


def api(m, path, body=None):
    req = urllib.request.Request(URL + path, json.dumps(body).encode() if body else None,
                                 {"X-API-Key": KEY, "Content-Type": "application/json", "User-Agent": "rv-remediator"}, method=m)
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")


def telegram(text: str) -> None:
    try:
        row = sqlite3.connect(env["RUNVOUCH_DB"]).execute(
            "SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        if row:
            data = urllib.parse.urlencode({"chat_id": row[1], "text": text[:3900]}).encode()
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{row[0]}/sendMessage", data,
                                                          {"User-Agent": "rv-remediator"}), timeout=10)
    except Exception as e:
        print("telegram:", e, file=sys.stderr)


def jobs_from_crontab() -> dict:
    out = {}
    for l in subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines():
        m = re.search(r"/home/krtradingpro/bin/rv run (\S+) (.*)$", l)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def run_job(agent: str, args: str) -> subprocess.CompletedProcess:
    args = args.replace("--source cron", "--source remediator")
    return subprocess.run("/home/krtradingpro/bin/rv run " + agent + " " + args, shell=True, capture_output=True, text=True, timeout=3600)


def job_context(args: str) -> dict:
    """Log tail, script path and the repo to fix, derived from the crontab arguments."""
    log = re.search(r"--log (\S+)", args)
    cmd = args.split(" -- ", 1)[1] if " -- " in args else args
    script = next((t for t in cmd.split() if t.startswith("/home/krtradingpro/") and not t.startswith("-")), "")
    if "run_live.sh" in cmd:                       # landing-live/scripts/run_live.sh scripts/x.py -> the real source is landing/scripts/x.py
        tail = cmd.split("run_live.sh", 1)[1].strip().split()[0] if "run_live.sh" in cmd else ""
        script = os.path.join("/home/krtradingpro/apify/landing", tail) if tail else script
    repo, publish = "", ""
    for prefix, r, p in REPOS:
        if script.startswith(prefix) or (script.startswith("/home/krtradingpro/apify/landing/") and prefix.endswith("landing/")):
            repo, publish = r, p
            break
    tail_txt = ""
    if log:
        try:
            tail_txt = subprocess.run(["tail", "-n", "120", log.group(1)], capture_output=True, text=True).stdout
        except Exception:
            pass
    return {"cmd": cmd, "script": script, "repo": repo, "publish": publish, "log": log.group(1) if log else "", "tail": tail_txt[-8000:]}


BRIEF = """You are the on-call engineer for a scheduled job that failed. Diagnose and, if it is a code or data-handling bug,
fix it. You have Read/Edit/Write/Grep/Glob/Bash inside the repository below. Work in Dutch for commit messages, English in code.

Job (RunVouch agent): {agent}   alert: {kind}: {message}
Cron command: {cmd}
Script: {script}
Repository to fix: {repo}
Last lines of the job log:
----
{tail}
----

Rules, all hard:
- First find the real cause from the log and the code. Do not guess; run the script yourself if that is safe and fast (it is
  a read-only or idempotent job; if it deploys, sends mail, or spends money, do NOT run it - read the code instead).
- If the cause is external or transient (source unreachable, rate limit, timeout, upstream 5xx) change nothing and answer TRANSIENT.
- If the cause needs a human decision (a real data problem the checker correctly reports, a threshold that is intentionally
  strict, a page that must be added to a register by hand, missing credentials) change nothing and answer NEEDS_HUMAN with the
  exact thing to decide or do.
- Otherwise fix the root cause with the smallest change in the style of the surrounding code. Never invent names or numbers.
  Never touch: .env, secrets, crontab, systemd units, anything that deploys (netlify, deploy_*.sh, cron_refresh_deploy.sh),
  data/ directories, git history (no force push, no reset --hard). Do not rebuild or deploy the site.
- Verify: run the relevant tests. Landing repo: `python3 scripts/quality_gates.py --check` must be green. RunVouch repo:
  `.venv/bin/python -m pytest -q tests` must pass. Then `git add` only the files you changed and commit with a clear Dutch
  message that names the job and the cause. Then publish with: {publish}
- Finish with exactly one line at the end:  RESULT: FIXED|TRANSIENT|NEEDS_HUMAN|FAILED - <one sentence, human tone, no dashes>
"""


def repair(agent: str, alert: dict, ctx: dict) -> tuple[str, str]:
    """Returns (verdict, sentence). Runs the local Claude Code CLI inside the repo; 15-minute budget."""
    if not ctx["repo"]:
        return "NEEDS_HUMAN", "geen repository bekend voor dit script, dus niets aangeraakt"
    prompt = BRIEF.format(agent=agent, kind=alert["kind"], message=alert.get("message", ""), **ctx)
    try:
        r = subprocess.run([CLAUDE, "-p", prompt, "--output-format", "json", "--max-turns", "60",
                            "--allowedTools", "Read,Edit,Write,Grep,Glob,Bash"],
                           cwd=ctx["repo"], capture_output=True, text=True, timeout=900)
        out = json.loads(r.stdout or "{}").get("result", "") or r.stderr[-800:]
    except subprocess.TimeoutExpired:
        return "FAILED", "de herstelpoging duurde langer dan 15 minuten en is afgebroken"
    except Exception as e:
        return "FAILED", f"herstelpoging kon niet starten: {type(e).__name__}"
    m = re.search(r"RESULT:\s*(FIXED|TRANSIENT|NEEDS_HUMAN|FAILED)\s*-\s*(.+)", out)
    if not m:
        return "FAILED", (out.strip().splitlines() or ["geen uitkomst"])[-1][:300]
    return m.group(1), m.group(2).strip()[:400]


def main() -> int:
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another remediator is still running; skipping this round")
        return 0
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    st = {"seen": st, "last": {}, "repairs": []} if isinstance(st, list) else st
    seen, last, repairs = set(st.get("seen", [])), st.get("last", {}), [t for t in st.get("repairs", []) if t > time.time() - 86400]
    jobs = jobs_from_crontab()
    alerts = [a for a in api("GET", "/v1/alerts")
              if a["kind"] in ("FAILED", "MISSED", "NO_EVIDENCE") and a["agent"] in jobs and a["agent"] not in NEVER and a["id"] not in seen]
    done = 0
    for a in alerts:
        agent = a["agent"]
        if time.time() - last.get(agent, 0) < RETRY_EVERY:
            api("POST", f"/v1/alerts/{a['id']}/ack"); seen.add(a["id"])
            print(f"skip {agent} (alert #{a['id']}): handled {int((time.time() - last[agent]) / 60)} min ago")
            continue
        last[agent] = time.time()
        print(f"retrying {agent} (alert #{a['id']} {a['kind']})"); t0 = time.time()
        r = run_job(agent, jobs[agent])
        print(f"  exit {r.returncode} in {int(time.time() - t0)}s")
        ok = r.returncode == 0 and a["kind"] != "NO_EVIDENCE"
        if not ok and len(repairs) < MAX_REPAIRS_PER_DAY:
            ctx = job_context(jobs[agent])
            print(f"  repairing in {ctx['repo'] or '?'} ...")
            verdict, sentence = repair(agent, a, ctx)
            repairs.append(time.time())
            print(f"  {verdict}: {sentence}")
            if verdict == "FIXED":
                r2 = run_job(agent, jobs[agent])
                if r2.returncode == 0:
                    telegram(f"Hersteld: {agent}. {sentence} De job draait weer (exit 0).")
                else:
                    telegram(f"Herstel geprobeerd voor {agent}: {sentence} Maar de job faalt nog (exit {r2.returncode}). Kijk mee: {ctx['log'] or 'log onbekend'}")
            elif verdict == "TRANSIENT":
                telegram(f"{agent}: tijdelijke storing, niets veranderd. {sentence} Volgende geplande run pakt het op.")
            elif verdict == "NEEDS_HUMAN":
                telegram(f"{agent} heeft jou nodig: {sentence}")
            else:
                telegram(f"{agent}: herstel niet gelukt. {sentence} Log: {ctx['log'] or 'onbekend'}")
        elif not ok:
            telegram(f"{agent} faalt nog na een retry; de drie herstelpogingen van vandaag zijn op. Log: {job_context(jobs[agent])['log']}")
        api("POST", f"/v1/alerts/{a['id']}/ack"); seen.add(a["id"]); done += 1
    json.dump({"seen": sorted(seen)[-500:], "last": last, "repairs": repairs}, open(STATE, "w"))
    print(f"handled {done} of {len(alerts)} open alerts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
