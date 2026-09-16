# RunVouch for Home Assistant

Show the state of your RunVouch agents inside Home Assistant, and report a Home Assistant automation as a RunVouch run. No custom component: everything here is the built-in `rest` and `rest_command` integrations, so it survives core updates and needs no HACS.

What you get:

| Entity | Source | State |
| --- | --- | --- |
| `sensor.runvouch_<agent>` | `GET /v1/agents` (your key) | `ok`, `unproven`, `failed`, `alert`, `running`, `waiting`, `paused`; attributes: cadence, open alerts, cost last 24 h, last run |
| `sensor.runvouch_agents_not_ok` | same response | number of agents that are not `ok` or `paused` |
| `sensor.runvouch_cost_24h` | same response | USD spent by all agents in the last 24 h |
| `sensor.runvouch_open_alerts` | `GET /v1/alerts` (your key) | number of unacknowledged alerts; attributes of the newest one |
| `sensor.runvouch_api_heartbeat_age` | `GET /status.json` (public) | seconds since RunVouch's detector loop last ran; above 150 means your MISSED alerts are late |
| `sensor.runvouch_api_uptime_30d` | `GET /status.json` (public) | detector uptime in the last 30 days, percent |

The judgement in the state field is made by RunVouch (cadence, evidence, caps); Home Assistant only displays it and lets you automate on it.

## Install

1. Get a free key at https://runvouch.com (3 agents, no card) and put it in `secrets.yaml`:

       runvouch_key: rv_...

2. Copy the blocks you want from `configuration.yaml` in this folder into your own `configuration.yaml` (or a package file). For each agent you want as a sensor, copy one sensor block and change the agent name in `name`, `unique_id`, `value_template` and `json_attributes_path`.
3. Check the configuration (Developer tools, YAML, Check configuration) and restart, or reload the REST entities.
4. The entities appear under Settings, Devices and services, Entities, filtered on `runvouch`.

`scan_interval` is 300 seconds for agents and 120 for alerts. RunVouch's own detectors run every minute; polling faster than that gains nothing.

## Report an automation as a run

The `rest_command.runvouch_start` and `rest_command.runvouch_end` services in the example post the two calls RunVouch needs. In an automation:

1. call `runvouch_start` with `agent: <name>` and `response_variable: rv`
2. do the work
3. call `runvouch_end` with `run_id: "{{ rv.content.run_id }}"`, a `status` and an `evidence` object of booleans

Register the cadence once, from any machine with the key:

    rv agent nightly-backup --cadence 24h --grace 30m --evidence

Now a time-triggered automation that stops firing (disabled after an update, instance restarting at 02:00) is MISSED, and a shell command that ran and did nothing is NO_EVIDENCE. The alert goes to the channels set on https://runvouch.com/app: e-mail, Telegram, Slack, webhook, PagerDuty. The second automation in the example turns a `failed` or `unproven` sensor into a persistent notification inside Home Assistant as well.

## Notes

- The API answers over HTTPS only. Home Assistant needs outbound access to `api.runvouch.com`.
- `json_attributes_path` uses JSONPath as supported by the `rest` integration; `$[?(@.name=='x')]` selects the agent by name.
- Keys stay in `secrets.yaml`; nothing in this folder needs to be committed with a key in it.
- Self-hosting RunVouch: replace `https://api.runvouch.com` with your own URL in every `resource` and `url`.

Integration page with the same example and what Home Assistant does not tell you: https://runvouch.com/integrations/home-assistant
