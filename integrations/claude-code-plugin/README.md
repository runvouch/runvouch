# RunVouch plugin for Claude Code

Turns every headless / scheduled Claude Code run into a watched run:
`SessionStart → run start`, `PostToolUse → tool event (retry-storm + cost detection)`, `Stop → run end (+ evidence)`.

Every finished run gets a tamper-evident proof (hashed record, public daily chain, Bitcoin anchor): `rv proof RUN_ID --verify`, see https://runvouch.com/docs/proof

## Install
```
/plugin marketplace add runvouch/claude-plugin
/plugin install runvouch
```
or copy this folder and `claude --plugin-dir ./claude-code-plugin`.

## Use in a Routine / cron
```
export RUNVOUCH_KEY=rv_...           # from runvouch.com
export RUNVOUCH_AGENT=nightly-report # must exist: rv agent nightly-report --cadence 24h --evidence
export RUNVOUCH_EVIDENCE='{"report":{"type":"url","url":"https://example.com/reports/latest.html"}}'
claude -p "Generate tonight's report and publish it" --dangerously-skip-permissions
```
Interactive sessions without `RUNVOUCH_AGENT` are ignored — the hook is a no-op and never blocks Claude.
