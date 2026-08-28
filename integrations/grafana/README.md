# RunVouch dashboard for Grafana

One dashboard JSON that puts RunVouch next to the rest of your monitoring:

- **Your agents** (needs your key): agents not ok, open alerts, cost in the last 24 hours, a table of every agent with its RunVouch state (`ok`, `unproven`, `failed`, `alert`, `running`, `waiting`, `paused`), last run and evidence, and a table of open alerts.
- **Public fleet** (no key): the opted-in public status of a fleet at `/public/fleet/<slug>.json`, for a customer status page or a partner's agents.
- **RunVouch itself** (no key): detector uptime per window, incidents, and the age of the last detector heartbeat from `status.json`. If that age passes 150 seconds, MISSED alerts are late; the panel turns orange.

The judgement (is this agent ok) is made by RunVouch from cadence, evidence and caps; Grafana displays the `state` field and can alert on it as a second channel.

## Requirements

- Grafana 10 or 11.
- The [Infinity datasource](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) plugin (`grafana-cli plugins install yesoreyeram-infinity-datasource`, or install from the catalog). The JSON API datasource works for the public panels too, but the dashboard file targets Infinity.
- Outbound HTTPS from the Grafana server to `api.runvouch.com`. Infinity queries run server-side, so browser CORS does not apply.

## Install (five minutes)

1. **Datasource.** Connections, Data sources, Add, Infinity. Name it `RunVouch`. Under Authentication choose **API Key**, key `X-API-Key`, value your RunVouch key, add to **Header**. Under Security, add `https://api.runvouch.com` to the allowed hosts. Save and test.
2. **Import.** Dashboards, New, Import, upload `runvouch-dashboard.json` (or paste it). When asked for the `RunVouch (Infinity)` datasource, pick the one from step 1. Import.
3. **Variables.** At the top of the dashboard: `RunVouch API` stays `https://api.runvouch.com` unless you self-host; `Public fleet slug` is optional and only fills the fleet table.

The dashboard refreshes every minute. RunVouch's detectors run every minute as well, so a faster refresh gains nothing.

## Alerting from Grafana (optional)

RunVouch already sends every alert to the channels set on https://runvouch.com/app (e-mail, Telegram, Slack, webhook, PagerDuty). If you want Grafana to page as well, create an alert rule on the **Agents not ok** query with a threshold of `> 0`, or on **RunVouch detector heartbeat age** with `> 150`. Both queries are plain Infinity queries and can be copied from the panels into a rule.

## Endpoints used

| URL | Auth | What |
| --- | --- | --- |
| `GET /v1/agents` | X-API-Key | name, state, cadence_s, paused, open_alerts, cost_24h, last_run |
| `GET /v1/alerts` | X-API-Key | open alerts: ts, kind, agent, message |
| `GET /public/fleet/<slug>.json` | none | agents of an opted-in fleet: label, kind, cadence_s, late, last_run, rates, open_alert |
| `GET /status.json` | none | windows (24h, 7d, 30d, 90d), incidents, last_heartbeat_age_s, sealed_days |

Public fleets are enabled per account; ask via https://runvouch.com/contact with the agents you want listed. Full API: https://runvouch.com/docs/api. Integration page: https://runvouch.com/integrations/grafana
