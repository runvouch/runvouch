<p align="center"><img src="https://runvouch.com/logo-400.png" width="96" alt="RunVouch"></p>
<h1 align="center">RunVouch</h1>
<p align="center"><b>The watchdog for unattended AI agents — proof they did the job, and an alert the moment they don't (or start spending), with a tamper-evident proof per run.</b><br>Claude Code Routines · headless <code>claude -p</code> · OpenClaw · n8n · cron</p>
<p align="center"><a href="https://runvouch.com">Website</a> · <a href="https://runvouch.com/docs/">Docs</a> · <a href="https://runvouch.com/blog/">Field notes</a> · <a href="https://registry.modelcontextprotocol.io/v0.1/servers?search=runvouch">MCP Registry</a> · <a href="https://www.producthunt.com/products/runvouch">Product Hunt</a></p>
<p align="center"><a href="https://pypi.org/project/runvouch/"><img src="https://img.shields.io/pypi/v/runvouch?label=pypi" alt="PyPI"></a> <a href="https://www.npmjs.com/package/runvouch"><img src="https://img.shields.io/npm/v/runvouch?label=npm" alt="npm"></a> <a href="https://github.com/runvouch/vouch-action"><img src="https://img.shields.io/badge/GitHub%20Action-vouch--action%40v1-2ea44f" alt="GitHub Action"></a> <a href="https://registry.modelcontextprotocol.io/?search=runvouch"><img src="https://img.shields.io/badge/MCP%20Registry-com.runvouch%2Frunvouch-4c8dff" alt="MCP Registry"></a> <a href="https://smithery.ai/servers/runvouch/runvouch"><img src="https://img.shields.io/badge/Smithery-runvouch%2Frunvouch-orange" alt="Smithery"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a></p>

A green run means the scheduler worked, not that the task got done. RunVouch alerts within minutes when a scheduled agent is missing, failed, looping, over budget, drifting — or reported success without evidence.

```
pip install runvouch     # or: npm install -g runvouch  (zero-dependency client + rv CLI)
rv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence
rv run nightly-report --evidence-file out/report.html -- claude -p "build tonight's report"
```

## Verifiable runs
Every finished run gets a sha256 record, every UTC day a Merkle root chained to the previous day and stamped in Bitcoin with OpenTimestamps. The day files are public at https://api.runvouch.com/proof/ and `templates/verify_proof.py` (stdlib only) checks a proof without our code. On every plan, Free included.
```
rv proof RUN_ID --verify     # recomputes leaf + Merkle path against the public day file, exit 0 or 1
```
Mechanism and limits: https://runvouch.com/docs/proof · who needs it: https://runvouch.com/verifiable-agent-runs

## Detectors

| Alert | Meaning |
|---|---|
| `MISSED` | expected run never started (dead scheduler, expired auth, crash before first line) |
| `FAILED` | run ended non-zero / status=fail |
| `NO_EVIDENCE` | run said ok but required proof (file written, URL 200, assertion) is missing — *green ≠ done* |
| `RETRY_STORM` | same tool + identical input ≥ N times in one run (the invisible loop that costs $437) |
| `BUDGET_RUN` / `BUDGET_DAY` | cost or tokens over the cap you set |
| `DRIFT` | duration / output size off its 7-run baseline (robust MAD) — silently doing something else |
| `STALLED` | started, no end and no heartbeat past max runtime |

Alerts go to e-mail, Telegram, Slack, any JSON webhook, PagerDuty (Team) and the dashboard.

## Layout
```
runvouch/server.py            FastAPI + SQLite, all detectors, dashboard at /
runvouch/cli.py               `aw` — stdlib-only client: rv agent / rv run -- CMD / rv status / rv alerts
integrations/claude-code-plugin Claude Code plugin: SessionStart/PostToolUse/Stop hooks → RunVouch
integrations/mcp                MCP server (stdio): runvouch_status/alerts/ack/runs/run_start/run_end
site/index.html                 landing page
tests/                          7 detector tests (pytest)
docs/BUSINESS.md                what it does, what it can earn, go-to-market
```

## Run (self-host)
```
python3 -m venv .venv && .venv/bin/pip install fastapi "uvicorn[standard]"
cp .env.example .env   # set RUNVOUCH_ADMIN_TOKEN
./run.sh               # http://127.0.0.1:8787   (systemd unit: ~/.config/systemd/user/runvouch.service)
curl -X POST "localhost:8787/admin/accounts?name=me&plan=team" -H "X-Admin-Token: $ADMIN"   # → api_key
```

## Use
```
export RUNVOUCH_KEY=rv_... RUNVOUCH_URL=http://localhost:8787
rv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence
rv run nightly-report --evidence-file out/report.html -- claude -p "build tonight's report"
rv status ; rv alerts
```
Claude Code plugin: see `integrations/claude-code-plugin/README.md`.
MCP: `claude mcp add runvouch -e RUNVOUCH_KEY=... -- python3 integrations/mcp/runvouch_mcp.py`

## Test
```
.venv/bin/python -m pytest -q tests
```

## Hosted vs self-host
Hosted at [runvouch.com](https://runvouch.com): free for 3 agents, $9 Solo, $29 Team — alerts, dashboard, backups, EU hosting. Self-host: this repo, MIT. Same code.

## Compare
[vs Healthchecks.io](https://runvouch.com/vs/healthchecks) · [vs Cronitor](https://runvouch.com/vs/cronitor) · [vs Langfuse](https://runvouch.com/vs/langfuse)

## License
MIT.
