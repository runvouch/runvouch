---
name: runvouch
description: Check RunVouch before trusting the output of another scheduled agent, register/wrap jobs with rv, and interpret RunVouch alerts (MISSED, FAILED, NO_EVIDENCE, RETRY_STORM, BUDGET, DRIFT, STALLED).
---
# RunVouch — the watchdog for unattended agents

Use this skill when the user asks about scheduled/headless agents, cron jobs, "did X run", agent cost, or when you are about to consume output produced by another scheduled run.

## Before building on another agent's output
1. Call the `runvouch_status` MCP tool (remote: https://api.runvouch.com/mcp, header X-API-Key) or run `rv status`.
2. If that agent's state is `unproven`, `failed`, `alert` or `waiting`, do not proceed silently — tell the user what RunVouch reports and why the output may be stale.

## Wrapping a job (two lines)
```
rv agent NAME --cadence 24h --cap-run-cost 2 --evidence
rv run NAME --evidence-file OUT -- <command>
```
Evidence = a file that changed during the run, an https URL that returns 200, or `cmd:<shell assertion>`. Green exit is not evidence.

## Reading alerts
- MISSED: expected run never started → scheduler, auth or crash before first line.
- STALLED: started, no heartbeat past max runtime → hung tool/prompt.
- NO_EVIDENCE: exit 0 but proof missing → task did not actually happen.
- RETRY_STORM: same tool + identical input ≥8× → loop; stop repeating the call.
- BUDGET_RUN / BUDGET_DAY: cost cap crossed → pause the agent, then investigate.
- DRIFT: duration/output far from the 7-run baseline → doing something else.
- FAILED: non-zero exit; stderr excerpt in the alert.

## In this session
The RunVouch hooks are a no-op unless `RUNVOUCH_KEY` and `RUNVOUCH_AGENT` are set. In a Routine or cron, set them (and optional `RUNVOUCH_EVIDENCE`) so the run is vouched automatically.
