# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RunVouch: a watchdog for unattended AI agents. One FastAPI server with SQLite, a zero-dependency
`rv` client, a proof module that hashes every finished run into a daily Merkle root chained across
days and stamped with OpenTimestamps. The same repo serves the hosted product (runvouch.com and
api.runvouch.com run from this checkout) and the MIT self-host distribution. Keep it small on
purpose: one server file, one client file, one proof module (see CONTRIBUTING.md).

## Commands

```
.venv/bin/pip install -r requirements-dev.txt        # fastapi, uvicorn, pytest, httpx
.venv/bin/python -m pytest -q tests                   # full suite, 49 tests, under 10 s, no network
.venv/bin/python -m pytest -q tests/test_server.py -k drift   # one test
./run.sh                                              # loads .env, uvicorn on 127.0.0.1:8787
.venv/bin/python site/build.py                        # regenerate site/public/ from site/build.py + site/integrations.py + site/articles.json
python3 runvouch/cli.py status                        # the rv client straight from source (RUNVOUCH_URL, RUNVOUCH_KEY)
```

Production runs as systemd user units on this machine: `runvouch.service` (the API, wraps run.sh),
`runvouch-site.timer` (weekly site rebuild), `statuswacht.timer` (external check of the status page
every minute), `pushwacht.timer` (hourly: pushes main to GitHub when the whole suite is green),
`prwacht.timer` (daily 08:40: open pull requests where the ball is with us),
`prantwoord.timer` (08:50 and 17:50: drafts the reply, the owner approves it with one word in Telegram),
`cloudflared.service` (tunnel). After a server change: `systemctl --user restart runvouch`.
A site change needs `site/build.py` and no restart; the server serves `site/public/` from disk.
Deploy details in deploy/DEPLOY.md.

Packaging (`packaging/pypi/build.sh`, `packaging/npm/build.sh`) copies the client sources at build time
and rewrites the default URL to the hosted API. Publishing is a separate explicit step; never do it
from a session. `git push` is denied by .claude/settings.json, so a session commits and never pushes; `deploy/pushwacht.py` pushes main hourly, but only with the whole test suite green, and it stops and reports when this machine is behind origin. Tags and releases stay manual.

## Architecture

**runvouch/server.py** is the whole backend. Reading order:

- Env config at the top; every `os.getenv` name must also appear in `.env.example` (a test enforces it).
- SQLite schema in `_connect()`: accounts, agents, runs, tool_events, alerts, proof_days, run_leaves,
  heartbeats, public_fleets, public_agents, viewer_keys. Schema changes are additive only
  (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN` inside a try). Existing databases must
  survive `git pull`.
- Auth: `account_from_key` (X-API-Key, keys stored hashed), `require_plan` (free / solo / team gates),
  `require_admin` (X-Admin-Token). Viewer keys are read-only accounts.
- Detectors: `check_drift`, `check_budget`, `check_storm` fire inline from `/v1/runs/tool` and
  `/v1/runs/end`; `evaluate_evidence` decides NO_EVIDENCE; `sweep_once` finds MISSED and STALLED.
  All go through `raise_alert`, which dedupes and queues; `_deliverer` sends (email via Resend,
  Telegram, Slack, webhook, PagerDuty on Team).
- Background thread `_sweeper` (every RUNVOUCH_SWEEP_SECONDS): sweep, heartbeat, owner digest,
  proof maintenance (seal yesterday, OTS stamp and upgrade), retention purge, weekly report.
  Tests set `RUNVOUCH_NO_SWEEP=1` and call `sweep_once(now=...)` directly with a shifted clock.
- Billing webhooks: Polar (current provider), Stripe, Lemon Squeezy; each verifies its signature and
  maps a product or price id to a plan via env.
- Slack OAuth install flow, remote MCP over HTTP at `/mcp`, public JSON at `/status.json`,
  `/public/fleet/{slug}.json` and `/public/status/{slug}.json`, proof files at `/proof/days/`.
- Host routing at the bottom: requests with host runvouch.com get the static site from `site/public`
  (`_serve_site`, with path traversal guard and a 404 page); every other host gets the dashboard
  (`DASH`, inline HTML) at `/` and `/app`.

**runvouch/proof.py** holds only the hashing rules (leaf, Merkle root and path, chain hash), stdlib
only. `templates/verify_proof.py` and `verify_proof()` in cli.py repeat those rules on purpose so a
reader can verify without importing anything from here. Change one, change all three, and
`test_leaf_determinism` / `test_merkle_root_and_path` / `test_chain_two_days_and_proof_endpoint`.

**runvouch/cli.py** is the `rv` client: stdlib only, no dependencies, ever. `rv run NAME -- CMD`
wraps a command, posts start and end, derives file evidence from mtime and size, and fails open
(`soft=True`: monitoring can never break the job). Same rule for `integrations/python/runvouch.py`
and `integrations/node/runvouch.js`, which are the sources copied into the PyPI and npm packages.

**integrations/** are thin clients of the same API: `mcp/runvouch_mcp.py` (stdio JSON-RPC, no SDK),
`claude-code-plugin` (SessionStart / PostToolUse / Stop hooks, active only when RUNVOUCH_KEY and
RUNVOUCH_AGENT are set), n8n node, Slack manifest, Grafana, Home Assistant, OpenClaw skills.

**site/** is a generator, not a static folder. `build.py` holds CSS, layout, home, pricing, docs and
the vs pages; `integrations.py` is a list of dicts, one per integration page, hand-written per
platform (a test checks every field and uniqueness of intros); `articles.json` is the blog,
appended by `blogmotor.py` (weekly, drives the local Claude CLI, only publishes with two verified
source links). Adding an integration page means adding a dict to `INTEGRATIONS`. The build reads
`.env` for billing switches (POLAR_LIVE, STRIPE_LIVE, LS_LIVE) and analytics.json for the counter.

**Operational scripts** (`remediator.py`, `deploy/statuswacht.py`, `deploy/marktwacht.py`,
`deploy/koperswandeling.py`, `deploy/reddit-scout.py`, `deploy/telegram-antwoord.py`, `deploy/prwacht.py`, `deploy/prantwoord.py`) run the
business around the product and dogfood RunVouch via `rv run`. `remediator.py` re-runs failed cron
jobs and hands persistent failures to the local Claude CLI with a repair brief; it has a never-list
for jobs that send mail or touch money. `data/` is the production database, proof files, logs and
state; gitignored, never read into a tracked file.

## Rules that tests enforce

- `tests/test_open_source_hygiene.py` fails on: tracked private files, token-shaped strings, absolute
  home paths (`/home/<user>/`), personal mail providers, and a hashed list of forbidden words
  (the local username and personal names). Nothing tracked may contain any of these, this file included.
- `tests/test_site.py` and the tail of `site/build.py` refuse any em dash in site output. The only
  allowed one is the literal quote from the Claude Code docs. Use a comma, colon or full stop.
- A new detector or alert channel needs a test in `tests/test_server.py` that triggers it.
- `.env` is denied to the session by .claude/settings.json; read `.env.example` instead.

## Conventions

- Docs, commit messages and site text: plain ASCII, short sentences, byline "RunVouch", never a
  personal name. Commit author is the company address.
- Alerts and Telegram messages from the ops scripts follow one format (statuswacht is the reference).
- The dashboard, emails and site copy are customer-facing: no AI look, no emoji in product text.
- Site, docs, dashboard and commit messages are in English. Emails follow the language of the recipient (Dutch or English). Chat with the owner in Dutch.
- This project overrides the global metadata rule: no personal name in any tracked file, commit or generated document. Byline and author are always "RunVouch".
