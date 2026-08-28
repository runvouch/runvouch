# n8n-nodes-runvouch

Heartbeat monitoring for scheduled n8n workflows. This community node reports each run of a workflow to [RunVouch](https://runvouch.com) and RunVouch alerts you (Telegram, Slack, e-mail, webhook, PagerDuty) when:

- a Schedule Trigger stops firing (n8n down, workflow deactivated, trigger edited, timezone change): **MISSED**
- a run reports failure: **FAILED**
- a run finishes green but the evidence you attach says the work did not happen: **NO_EVIDENCE**
- a run costs more than the cap you set: **BUDGET_RUN** / **BUDGET_DAY**

Three agents are free. Every finished run also gets a tamper-evident proof record; see [runvouch.com/docs/proof](https://runvouch.com/docs/proof).

## The problem this solves

n8n's Error Workflow fires when a node errors. It does not fire when the workflow never starts, and it does not fire when the workflow runs, does nothing, and exits green. The n8n community thread [Cron job monitoring aka heartbeat monitoring](https://community.n8n.io/t/cron-job-monitoring-aka-heartbeat-monitoring/19930) asks exactly this: "how do I get notified when a scheduled workflow stops running, or when my n8n instance is down?" The answers there are an HTTP Request node pinging a heartbeat URL on every run.

This node is that pattern with two additions: you do not have to build the request by hand, and the end-of-run call carries **evidence** (did rows get written? did the message get sent?) so a workflow that runs but produces nothing is also caught. The dead-man's-switch part works the same way as a heartbeat URL: if the run does not arrive within the expected interval plus a grace period, you get an alert.

## Installation

In n8n: **Settings > Community Nodes > Install**, enter `n8n-nodes-runvouch`, accept the risk prompt, install.

Requirements: n8n 1.0 or later with community nodes enabled (they are by default on self-hosted n8n; on n8n Cloud, verified community nodes only). Self-hosted with Docker: no extra steps.

Manual install (self-hosted, when the UI route is not available):

```
cd ~/.n8n/nodes
npm install n8n-nodes-runvouch
# restart n8n
```

## Credentials

1. Get a free key at [runvouch.com](https://runvouch.com/#start).
2. In n8n: **Credentials > Add credential > RunVouch API**, paste the key (it starts with `rv_`). Leave the API URL at `https://api.runvouch.com` unless you self-host RunVouch.
3. Click **Test**; it calls `GET /v1/agents` with your key.

## Operations

| Operation | What it does |
|---|---|
| **Start Run** | `POST /v1/runs/start`. Returns `run_id`. On the first run of a new agent name it registers the agent with the cadence and grace period from the node. |
| **End Run** | `POST /v1/runs/end` with `run_id`, status (`ok` or `fail`), evidence, optional cost and tokens. |
| **Heartbeat** | Start and End in one step. Use this when you only want the dead-man's-switch and do not need to measure the work in between. |

All operations accept **Additional Fields**: Cost (USD), Tokens, Meta (JSON) and Source (default `n8n`). The n8n execution ID and workflow name are added to `meta` automatically so you can find the execution from the alert.

### Evidence

Evidence is a JSON object of named checks that you evaluate in n8n, each `true` or `false`:

```
={{ { "leads_fetched": $json.count > 0, "sheet_updated": $('Google Sheets').item.json.updatedRows > 0 } }}
```

Any `false` raises NO_EVIDENCE: the run was green but the work did not happen. If you mark an agent as `evidence_required` (dashboard or `rv agent NAME --evidence`), an End Run without evidence raises it too. A server-side check that a web address answers is also accepted: `{"page_live": {"type": "url", "url": "https://example.com/report.html", "expect": 200}}`.

## Example workflow: Schedule Trigger -> RunVouch Start -> work -> RunVouch End

Import `examples/schedule-start-work-end.json` (Workflow menu > Import from File), pick your RunVouch credential in both RunVouch nodes, activate. The JSON in short:

```json
{
  "nodes": [
    { "name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
      "parameters": { "rule": { "interval": [ { "field": "hours", "hoursInterval": 1 } ] } } },
    { "name": "RunVouch Start", "type": "n8n-nodes-runvouch.runVouch", "typeVersion": 1,
      "parameters": { "operation": "start", "agent": "lead-enricher", "cadenceMinutes": 60, "graceMinutes": 15 } },
    { "name": "Do the work", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
      "parameters": { "url": "https://example.com/api/leads?since=1h" } },
    { "name": "RunVouch End", "type": "n8n-nodes-runvouch.runVouch", "typeVersion": 1,
      "parameters": { "operation": "end", "runId": "={{ $('RunVouch Start').item.json.run_id }}",
                      "status": "ok", "evidence": "={{ { \"leads_fetched\": $json.count > 0 } }}" } }
  ],
  "connections": {
    "Schedule Trigger": { "main": [[ { "node": "RunVouch Start", "type": "main", "index": 0 } ]] },
    "RunVouch Start":   { "main": [[ { "node": "Do the work", "type": "main", "index": 0 } ]] },
    "Do the work":      { "main": [[ { "node": "RunVouch End", "type": "main", "index": 0 } ]] }
  }
}
```

What you get from this:

- The hour the Schedule Trigger stops firing (n8n restarted without the workflow active, instance down, trigger changed), MISSED arrives after 60 + 15 minutes.
- The run where the API returns an empty list, NO_EVIDENCE arrives within a minute, even though every node was green.
- For FAILED on a node error: set the workflow's Error Workflow to one that contains a single RunVouch **End Run** node with status `fail` and `runId` taken from the execution data, or add an **Error Trigger** branch in the same workflow. The simplest option is to enable "Continue on fail" on the work node and set status with an expression: `={{ $json.error ? "fail" : "ok" }}`.

### Heartbeat only

Schedule Trigger -> RunVouch (operation Heartbeat, agent name, expected every N minutes). That is the same as the HTTP-Request-to-a-ping-URL recipe from the forum thread, with the node doing the request.

## Cost caps for AI workflows

If the workflow calls an LLM, pass the cost into End Run (Additional Fields > Cost) from the model node's usage output, and set a cap once:

```
rv agent lead-enricher --cadence 1h --cap-day-cost 5
```

A workflow that loops through an expensive model gets stopped by an alert the same day, not by the invoice.

## Development

```
npm install --ignore-scripts   # n8n-workflow pulls in a native module you do not need for building
npm run build                  # tsc + icon copy into dist/
npm run lint                   # eslint-plugin-n8n-nodes-base
```

Local test in n8n: `npm link` in this folder, then `npm link n8n-nodes-runvouch` in `~/.n8n/nodes` and restart n8n.

## Publishing (maintainer steps)

These steps are done by the RunVouch maintainer, not by users:

1. `npm login` with the RunVouch npm account (the same account that publishes the `runvouch` package).
2. In this folder: `npm run build && npm run lint && npm publish --access public`.
3. Submit the package for n8n verification so it appears on n8n Cloud: https://docs.n8n.io/integrations/creating-nodes/deploy/submit-community-nodes/ (requirements: MIT license, no runtime dependencies, name starts with `n8n-nodes-`, keyword `n8n-community-node-package`, lint passes; all met here).
4. Post an answer in the forum thread linked above that points to the node.

## License

MIT. RunVouch is a product of RunVouch, https://runvouch.com, support@runvouch.com.

## Releasing (maintainers)

Verified community nodes must be published from GitHub Actions with provenance.
Bump `version` in package.json, commit, then push a matching tag:

    git tag n8n-nodes-runvouch-0.1.1 && git push origin n8n-nodes-runvouch-0.1.1

The workflow `.github/workflows/publish-n8n-node.yml` builds, lints and publishes.
