# Slack App Directory listing texts for RunVouch

Copy these into the submission form. All plain ASCII, no em dashes.

## App name

RunVouch

## Short description (max 140 characters)

Alerts when a scheduled job or AI agent is missed, fails, produces nothing, loops or overspends.

## Long description

RunVouch is a dead man's switch, evidence check and cost cap for scheduled jobs and AI agents. It works with cron, Kubernetes CronJobs, GitHub Actions, Vercel cron, Airflow, Prefect, n8n, Claude Code routines, OpenClaw and 40 more runtimes: wrap the command with one line, or make two HTTP calls.

Each run reports a start and an end with evidence: a file that was written, a URL that is live, rows that were inserted. RunVouch watches from outside and posts to the Slack channel you choose when something is wrong:

- MISSED: the schedule stopped and no run started within cadence plus grace
- FAILED: non-zero exit or a reported failure, with the stderr excerpt
- NO_EVIDENCE: the run said ok but the file, URL or assertion you required is missing
- STALLED: a run started and never ended within max runtime
- RETRY_STORM: the same tool called with identical input many times in one run
- BUDGET_RUN and BUDGET_DAY: a cost cap was crossed and the agent is paused
- DRIFT: duration or output size far off its 7-run baseline

A weekly digest summarises every agent. Every run has a hash and every day a Merkle root anchored in Bitcoin, so a run can be verified offline.

Free for 3 agents, no card. Paid plans from $9 a month. Setup: add RunVouch to a channel, done; the same alerts also go to e-mail, Telegram, webhooks and PagerDuty if you want them there.

## Categories

Developer Tools; Productivity (Notifications)

## URLs

- Website: https://runvouch.com
- Support: https://runvouch.com/contact
- Privacy policy: https://runvouch.com/privacy
- Terms of service: https://runvouch.com/terms
- Pricing: https://runvouch.com/pricing
- Security: https://runvouch.com/security
- Setup instructions: https://runvouch.com/docs/alerts

## Scopes requested and why

- incoming-webhook: post alert messages to one channel chosen by the installing user. The app does not read messages, users, or channels.

## Data handling (for the security questionnaire)

RunVouch stores the webhook URL for the chosen channel on the customer's account. Messages contain the alert kind, the agent name, and the alert message (which may include a stderr excerpt from the customer's own job). No Slack user data is requested or stored. Data is stored on RunVouch servers in the EU (see https://runvouch.com/security for the hosting details). Removing the app from the workspace invalidates the webhook; the customer can also clear it on https://runvouch.com/app.
