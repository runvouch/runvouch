# competitor-hiring-watch

A weekly job that counts the open roles of the companies you name, straight from their own career sites (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Teamtailor, Breezy, Rippling) through the DataSignals MCP tool `job_openings`. It writes `out/hiring-YYYY-WW.md` with the counts, the top departments and the change versus last week, and sends a Telegram alert when a company's count is up more than 25 percent. RunVouch watches it with a 7 day cadence: MISSED if a Monday passes without a run, FAILED on a broken call, NO_EVIDENCE if the week's file was not written.

## What you need

- An Apify token (free account, no card): `APIFY_TOKEN`. `job_openings` is free within the first 50 MCP calls a month; this job makes one call per company per week, so up to twelve companies stay free. Beyond that it is $0.20 per job row returned, capped by `MAX_JOBS` (200) in the script; `--spend-cap 10` makes the server refuse further calls once your ledger reaches $10.
- A RunVouch key (free for 3 agents): `RUNVOUCH_KEY`.
- Optional: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for the alert. Without them the alert is printed.

## Setup

```
cp -r templates/competitor-hiring-watch ~/templates/ && cd ~/templates/competitor-hiring-watch
rv agent competitor-hiring --cadence 7d --grace 6h --max-runtime 30m --cap-run-cost 5 --evidence
export APIFY_TOKEN=apify_api_...
rv run competitor-hiring --evidence-file "out/hiring-$(date +%G-%V).md" -- python3 hiring.py --spend-cap 10
cat out/hiring-latest.md
```

Put your competitors in `companies.txt`, one career-board slug per line (`boards.greenhouse.io/stripe` is `stripe`, `jobs.ashbyhq.com/Ramp` is `Ramp`). A company that is not on one of the eight platforms is skipped with a warning in the tool result; the rest still runs. Install the line from `crontab.txt`.

## What the report looks like

```
# Competitor hiring, week 2026-W35 (2026-08-31)

| Company | Open roles | Last week | Change | Top departments |
|---|---|---|---|---|
| stripe | 187 | 171 | +9% | Engineering 64, Sales 31, ... |
| Ramp | 96 | 70 | +37% | ... |

## Alerts (count up more than 25%)
- Ramp: 70 -> 96 open roles (+37%)
```

The first week says "no comparison yet". The comparison is against the most recent earlier `hiring-*.json` in `out/`, so a skipped week compares against the last one that ran.

## Alternative: the hiring_signal stream

If you already have a DataSignals Events API key, the `hiring_signal` stream (`GET /v1/events?event_type=hiring_signal`) carries `roles_opened`, `roles_closed`, `net_change` and `window_days` per company career site, computed nightly by DataSignals. That gives you deltas without counting yourself, but the free plan is fixed to one stream per key, so use it only if that stream is the one you asked for.

## Files

- `hiring.py`: one MCP call per company, count, diff, write, alert. `--input saved.json` replays saved results (`{slug: result}`) offline.
- `ds_mcp.py`: 40 line MCP client. `python3 ds_mcp.py usage` shows your free-tier balance.
- `companies.txt`, `crontab.txt`.
- `out/`: `hiring-YYYY-WW.md` (evidence), `hiring-YYYY-WW.json` (counts for next week's diff), `hiring-latest.md`, `run.log`.

## Tested

`ds_mcp.py` against the live MCP server (free tools), `hiring.py --input` across two weeks with saved results in the actor's row shape, including the >25% alert, and the `rv agent --cadence 7d` / `rv run` lines against a RunVouch instance. The live `job_openings` call was not made from the template repo to avoid spending; the inputs match the tool signature.
