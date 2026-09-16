# RunVouch for OpenClaw

Two skills that make scheduled OpenClaw tasks accountable: a run is reported to [RunVouch](https://runvouch.com) when it starts and when it ends, with evidence, and you get an alert (Telegram, Slack, e-mail, webhook) when a task is missed, fails, loops, overspends, or finishes without the file it was supposed to write. Three agents are free; every finished run gets a tamper-evident proof record.

| Skill | Use it for |
|---|---|
| `verified-run` | Wrap one scheduled task: start-run, task, end-run with the output file as evidence. Missing or empty file means FAILED; no run at all means MISSED. Ships a shell script for cron and a set of instructions for the agent. |
| `runvouch` | Teach the agent to check in on its own during long sessions: per tool call (retry-storm detection), heartbeats, cost, and to refuse to build on another agent whose last run is unproven. |

## Install

Option A, copy the skill folders (works on every OpenClaw version):

```
git clone --depth 1 https://github.com/runvouch/runvouch
mkdir -p ~/.openclaw/skills
cp -r runvouch/integrations/openclaw/verified-run runvouch/integrations/openclaw/runvouch ~/.openclaw/skills/
```

Or put them in `<workspace>/skills/` for one workspace only. OpenClaw picks up the `SKILL.md` in each folder; `verified-run` is user-invocable, so `/verified-run` works as a slash command.

Option B, as a plugin: this folder ships `openclaw.plugin.json` with `"skills": ["."]`, so pointing OpenClaw's plugin loader at `integrations/openclaw` (or a copy of it under `~/.openclaw/extensions/runvouch`) loads both skills at once.

Then set the key. Either in the environment OpenClaw runs in:

```
export RUNVOUCH_KEY=rv_...            # free key from https://runvouch.com
```

or in `~/.openclaw/openclaw.json`, which injects it for the skill:

```json
{ "skills": { "entries": { "verified-run": { "apiKey": "rv_..." }, "runvouch": { "apiKey": "rv_..." } } } }
```

The `verified-run` skill declares `requires.env: RUNVOUCH_KEY` and `requires.bins: curl`, so it stays hidden until the key is present.

## Use

Cron on the OpenClaw host, one line per scheduled task:

```
0 7 * * * ~/.openclaw/skills/verified-run/scripts/verified-run.sh inbox-digest --every 24h --grace 30m --evidence-file ~/out/digest.md -- openclaw task run inbox-digest
```

What happens:

1. `POST /v1/runs/start` (first time: registers the agent `inbox-digest` with cadence 24h, grace 30m, evidence required).
2. Runs `openclaw task run inbox-digest`. A stale evidence file is removed first so yesterday's output cannot pass as today's.
3. `POST /v1/runs/end` with the exit code, the file size and `{"evidence_file": true|false}`.

Resulting alerts:

- 7:30 and no run: MISSED.
- Non-zero exit: FAILED with the exit code in the alert.
- Exit 0 but `digest.md` missing or empty: reported as `fail` with `evidence_file: false`, so FAILED fires for a "green run, no output".
- RunVouch unreachable: the task still runs, a warning goes to stderr, nothing is blocked.

The script is bash plus curl and was tested against the RunVouch server in this repository for the ok, missing-evidence, failing-command and no-key paths.

## Files

```
integrations/openclaw/
  openclaw.plugin.json           plugin manifest, loads both skills
  README.md                      this file
  verified-run/SKILL.md          the skill (frontmatter + instructions for the agent)
  verified-run/scripts/verified-run.sh   the wrapper, bash + curl, no other dependencies
  runvouch/SKILL.md              the check-in skill for long sessions
```

## Listing on awesome-openclaw

Line for the Skills section of https://github.com/rohitg00/awesome-openclaw (submit as a PR from the runvouch GitHub account):

```
- **[RunVouch verified-run](https://github.com/runvouch/runvouch/tree/main/integrations/openclaw)** - Watchdog skill for scheduled tasks: start/end runs with the output file as evidence, alerts on missed, failed or empty runs, free for 3 agents, proof record per run.
```

## Docs and support

https://runvouch.com/docs/openclaw, support@runvouch.com. MIT license.
