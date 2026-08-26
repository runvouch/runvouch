# runvouch

The watchdog for unattended AI agents. Alerts within minutes when a scheduled agent is
MISSED, FAILED, reported success without evidence, stuck in a retry storm, over budget,
drifting or stalled. Telegram, Slack, e-mail or webhook. Free for 3 agents.
Every finished run gets a tamper-evident proof (hashed record, public daily chain, Bitcoin anchor): `rv proof RUN_ID --verify`, see https://runvouch.com/docs/proof

```bash
pip install runvouch
export RUNVOUCH_KEY=rv_...        # free key at https://runvouch.com/app

# wrap any cron job / agent command
rv run nightly-report --evidence-file out/report.html -- python report.py
```

```python
import os, runvouch
with runvouch.vouch("nightly-report", evidence=lambda: {"report": os.path.exists("out.html")}) as run:
    run.tool("openai.chat", {"model": "gpt-5"}, cost=0.01)
```

Zero dependencies, fails open (monitoring can never break your job). Docs: https://runvouch.com/docs
