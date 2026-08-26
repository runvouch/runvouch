# RunVouch GitHub Action

Wrap a scheduled workflow step so RunVouch can tell you when it was **MISSED** (the schedule didn't fire),
**FAILED**, finished green **without evidence**, looped, or overspent — via Telegram, Slack, e-mail or webhook.
Free for 3 agents: https://runvouch.com

```yaml
name: nightly-report
on:
  schedule: [{ cron: "0 3 * * *" }]
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: runvouch/vouch-action@v1
        with:
          agent: nightly-report
          key: ${{ secrets.RUNVOUCH_KEY }}
          cadence: 24h                 # MISSED alert if no run starts in 24h + grace
          cap-run-cost: 2              # optional: BUDGET_RUN alert
          evidence-file: out/report.html
          run: python report.py --out out/report.html
```

Why not just rely on the workflow's own failure e-mail? Because the two failure modes that hurt are the
ones GitHub can't see: the schedule silently not firing (disabled after 60 days without commits, or a
paused cron), and the job exiting 0 without doing the work. RunVouch checks both.

| input | required | notes |
|---|---|---|
| `agent` | yes | name in RunVouch, created on first use |
| `key` | yes | `rv_…` key from https://runvouch.com/app — keep it in a secret |
| `run` | yes | the command; runs with `bash -eo pipefail` |
| `evidence-file` | no | must exist, be non-empty and be touched by the run |
| `evidence-url` | no | must return 200 after the run |
| `cadence` | no | e.g. `24h`, `1h`, `7d` — enables MISSED detection |
| `cap-run-cost` | no | USD; report cost with the Python/Node client for BUDGET alerts |
| `url` | no | self-hosted API base URL |

Fails open: if RunVouch is unreachable, your job still runs and the step logs a warning.
MIT — https://github.com/runvouch/runvouch
