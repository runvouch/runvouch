# runvouch

The watchdog for unattended AI agents. Alerts within minutes when a scheduled agent is
MISSED, FAILED, reported success without evidence, stuck in a retry storm, over budget,
drifting or stalled. Telegram, Slack, e-mail or webhook. Free for 3 agents.

```bash
export RUNVOUCH_KEY=rv_...        # free key at https://runvouch.com/app
npx runvouch run nightly-report --evidence-file out/report.html -- node report.js
```

```js
const rv = require('runvouch');
const run = await rv.start('nightly-report');
await run.tool('openai.chat', { model: 'gpt-5' }, { cost: 0.01 });
await run.end({ status: 'ok', evidence: { report: true } });
```

Zero dependencies, Node 18+, fails open (monitoring can never break your job). Docs: https://runvouch.com/docs
