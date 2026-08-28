# Self-hosting RunVouch

RunVouch is one Python process (FastAPI) with one SQLite file. No queue, no Redis, no
Postgres. The same code runs the hosted service at runvouch.com; self-hosting gives you
every detector, every alert channel and the verifiable-run proofs, on your own machine.

## Ten minutes to a running server

### With Docker (recommended)

```
git clone https://github.com/runvouch/runvouch.git && cd runvouch
cp .env.example .env
# edit .env: set RUNVOUCH_ADMIN_TOKEN (openssl rand -hex 24) and RUNVOUCH_PUBLIC_URL
docker compose up -d
curl -s localhost:8787/health
```

Data lives in the named volume `runvouch-data` (mounted at `/data`: the SQLite file and
the daily proof files). The port is bound to 127.0.0.1 only; put a reverse proxy with TLS
in front of it (Caddy, nginx, a Cloudflare tunnel) and set `RUNVOUCH_PUBLIC_URL` to that
address.

### Without Docker

```
git clone https://github.com/runvouch/runvouch.git && cd runvouch
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env    # set RUNVOUCH_ADMIN_TOKEN
./run.sh                # http://127.0.0.1:8787
```

`run.sh` loads `.env` and starts uvicorn on 127.0.0.1:8787. For a service that survives
reboots, wrap that command in a systemd unit (user or system); the server needs Python
3.10 or newer and write access to the directory in `RUNVOUCH_DB`.

### Create your first account and API key

Accounts are created through the admin endpoint (there is no public signup form in
self-host unless you expose the dashboard on a public host). The plan name only decides
limits; `team` means no limits.

```
curl -X POST "localhost:8787/admin/accounts?name=me&plan=team" \
  -H "X-Admin-Token: $RUNVOUCH_ADMIN_TOKEN"
# -> {"api_key": "rv_...", ...}
```

### Point a client at it

The `rv` client (pip install runvouch, or npm install -g runvouch) reads two variables:

```
export RUNVOUCH_URL=http://localhost:8787
export RUNVOUCH_KEY=rv_...
rv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence
rv run nightly-report --evidence-file out/report.html -- your-command-here
rv status ; rv alerts
```

The dashboard is at `http://localhost:8787/app`; paste the API key once and it stays in
the browser. The MCP server (`integrations/mcp/runvouch_mcp.py`), the Claude Code plugin,
the n8n node and the GitHub Action all take the same two variables.

## Configuration

Every variable the server reads is listed with its default in `.env.example`. The short
version:

| Variable | Purpose |
|---|---|
| `RUNVOUCH_ADMIN_TOKEN` | required; guards `/admin/*` |
| `RUNVOUCH_DB` | SQLite path (`/data/runvouch.db` in Docker) |
| `RUNVOUCH_PUBLIC_URL` | the address in alert links and proofs |
| `RESEND_API_KEY`, `ALERT_FROM` | e-mail alerts; blank means e-mail is skipped, other channels still work |
| `RUNVOUCH_OTS` | path to the OpenTimestamps client for Bitcoin stamps; optional |
| `RUNVOUCH_STORM_THRESHOLD`, `RUNVOUCH_DRIFT_K`, `RUNVOUCH_ALERT_COOLDOWN` | detector tuning |

## Backups

Everything is in one SQLite file plus the proof directory. A consistent copy while the
server is running:

```
docker compose exec runvouch python -c \
  "import sqlite3; sqlite3.connect('/data/runvouch.db').execute('VACUUM INTO ?', ('/data/backup.db',))"
docker compose cp runvouch:/data/backup.db ./runvouch-backup.db
```

`backup.sh` in the repo does the same for a non-Docker install and keeps 30 days.

## Upgrading

```
git pull
docker compose build && docker compose up -d
```

Schema changes are applied by the server on start (`CREATE TABLE IF NOT EXISTS` and
additive `ALTER TABLE`). Take a backup first anyway.

## What the hosted service has that self-host does not

| Hosted (runvouch.com) | Self-host |
|---|---|
| Paid plans, checkout, invoices (Polar, Stripe, Lemon Squeezy webhooks) | not needed: create accounts with any plan through `/admin/accounts`. The billing webhook routes exist in the code but do nothing without their secrets |
| Public status page at runvouch.com/status with fleet uptime | your own `/health` and `/status.json` on your server; nothing is published anywhere |
| Public proof archive at api.runvouch.com/proof/, stamped in Bitcoin daily | day files are written to `RUNVOUCH_PROOF_DIR` and served from your own `/proof/`; Bitcoin stamping only if you install the `ots` client |
| Outbound e-mail from a verified domain | bring your own Resend key and sender domain |
| "Add to Slack" OAuth button | paste a Slack incoming webhook URL instead (same alerts); or register your own Slack app and set `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` |
| Backups, monitoring, EU hosting | yours to run |

Everything else, including all seven detectors, Telegram, Slack, webhook and PagerDuty
alerts, the dashboard, the MCP server and per-run proofs, is identical.

## Moving to the hosted service later

There is no migration tool and none is needed: agents are declared by name, and the
history you care about is the proof chain, which is verifiable offline.

1. Sign up at https://runvouch.com and copy the new API key.
2. Re-declare your agents: `rv agent NAME --cadence ... --evidence` for each (or a script
   over `GET /v1/agents` on your server).
3. Change `RUNVOUCH_URL` to `https://api.runvouch.com` and `RUNVOUCH_KEY` to the new key
   wherever your runs start. Nothing else in your scripts changes.
4. Keep the old proof directory; `templates/verify_proof.py` verifies those runs against
   the day files without a server.

Going the other way (hosted to self-host) is the same steps in reverse.

## Getting help

Open an issue on GitHub or write to support@runvouch.com.
