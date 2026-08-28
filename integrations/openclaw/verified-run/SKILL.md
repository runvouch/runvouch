---
name: verified-run
description: Wrap a scheduled OpenClaw task in a RunVouch run. Reports start and end, attaches the output file as evidence, and alerts on Telegram, Slack or e-mail when the task is missed, fails, or ends without the file it was supposed to write.
homepage: https://runvouch.com/docs/openclaw
user-invocable: true
metadata: {"openclaw": {"emoji": "shield", "requires": {"bins": ["curl"], "env": ["RUNVOUCH_KEY"]}, "primaryEnv": "RUNVOUCH_KEY"}}
---

# verified-run

Use this skill for any task that runs on a schedule (cron jobs, heartbeat tasks, nightly digests) and is supposed to produce something: a file, a reply, a row. It turns "the task ran" into "the task ran and here is the evidence", and turns silence into an alert.

## What it does

1. `POST /v1/runs/start` on RunVouch with the agent name (registers the agent on first use, with the cadence you give).
2. Runs the task: a shell command, or the steps you carry out yourself.
3. `POST /v1/runs/end` with `status` (ok or fail), the size of the evidence file and evidence checks: `{"evidence_file": true|false}`. If the file is missing or empty the run is reported as `fail` with `evidence_file: false`, and RunVouch raises FAILED. If the run does not start at all within cadence plus grace, RunVouch raises MISSED.

## Setup (once)

- Get a free key at https://runvouch.com (three agents free).
- Put the key in the OpenClaw environment or in `~/.openclaw/openclaw.json` under `skills.entries.verified-run.apiKey`; it is injected as `RUNVOUCH_KEY`.
- Optional: `RUNVOUCH_URL` (default https://api.runvouch.com).

## How to run a task through it

Shell form, the normal case. The script is in this skill folder:

```
scripts/verified-run.sh NAME --every 24h --evidence-file /path/out.md -- COMMAND ARGS...
```

Options:

- `NAME`: agent name in RunVouch, one per scheduled task (for example `inbox-digest`).
- `--every 15m|1h|24h`: how often the task is expected. Used at first registration.
- `--grace 5m`: how late a run may be before MISSED (default 15m).
- `--evidence-file PATH`: the file the task must write. Missing or zero bytes means failure.
- `--cost USD`: what the task cost, if known; enables the daily cap.
- `--source openclaw`: shown in the dashboard (default openclaw).

Exit code is the task's exit code, so cron and OpenClaw see the real result.

Example for an OpenClaw cron task that writes a digest:

```
0 7 * * * ~/.openclaw/skills/verified-run/scripts/verified-run.sh inbox-digest --every 24h --grace 30m --evidence-file ~/out/digest.md -- openclaw task run inbox-digest
```

## When you (the agent) do the task yourself

If there is no single shell command, do the three calls directly:

1. Start: `curl -sS -X POST $RUNVOUCH_URL/v1/runs/start -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" -d '{"agent":"NAME","source":"openclaw"}'` and keep `run_id`.
2. Do the task. Write the result to the evidence file.
3. End: `curl -sS -X POST $RUNVOUCH_URL/v1/runs/end -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" -d '{"run_id":"RUN_ID","status":"ok","evidence":{"evidence_file":true}}'`.

Rules:

- Evidence must be something true about the outcome: a file with content, a message id, a URL that answers 200. Never report `true` because you believe it worked.
- If the evidence file is missing after the task, report `status: fail` and `evidence_file: false`. Do not retry the whole task more than once.
- If RunVouch itself is unreachable, carry on with the task and say so in your summary; the skill never blocks the work.

## Reporting to the user

After a run, tell the user in one line: agent name, status, evidence file and size, and the run id. If the end call returned `evidence_ok: false`, say that the task finished without evidence and what is missing.
