# form-d-raises-in-my-sector

A nightly cron job that reads new SEC Form D capital raises from the DataSignals Events API, keeps the ones whose industry or issuer matches your keywords, appends them to `out/raises.jsonl`, and sends a Telegram message when something matched. RunVouch watches it: MISSED if the cron stops firing, FAILED if the API or the script breaks, NO_EVIDENCE if it exits green without advancing the cursor.

Form D is the filing a company makes when it raises private money. It is public on EDGAR one to fifteen days before any press release, and the Events API parses the amounts, industry group, state and related persons out of the XML for you.

## What you need

- A DataSignals Events API key. There is a permanent free plan: one stream, 250 events a month, 24 hours behind. No card, no Apify account. Ask for a key with the stream `private_raise`: [mail support@datasignalslab.com](mailto:support@datasignalslab.com?subject=Events%20API%20free%20key&body=Stream%3A%20private_raise) and put it in `DATASIGNALS_KEY`. Paid plans (from $29 a month) give all twelve streams, more volume and webhooks: https://datasignalslab.com/events-api.html
  Two endpoints need no key at all, so you can look before you ask: `curl https://datasignalslab.com/v1/event-types` and `curl https://datasignalslab.com/v1/health`.
- A RunVouch key (free for 3 agents): `RUNVOUCH_KEY`.
- Optional: a Telegram bot token and chat id (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Without them the script prints the message.

Roughly 5 to 30 Form D raises a day pass the actor's fund filter, so 250 events a month on the free plan does not cover every night. The script stops at the quota and keeps the cursor, nothing is skipped: raise `limit` in `fetch()` on a paid plan, or narrow to what you need by upgrading. Check `quota` in the script output.

## Setup

```
cp -r templates/form-d-raises-in-my-sector ~/templates/ && cd ~/templates/form-d-raises-in-my-sector
rv agent form-d-raises --cadence 24h --grace 2h --evidence
export DATASIGNALS_KEY=ds_live_...
rv run form-d-raises --evidence-file out/cursor.txt -- python3 raises.py --dry-run
```

Edit `keywords.txt` (lowercase substrings matched against the SEC industry group and the issuer name). Install the line from `crontab.txt`.

Why the evidence file is `out/cursor.txt` and not the jsonl: the script writes the cursor on every successful run, and appends to `out/raises.jsonl` only when something matched. A quiet night must still count as a proven run, otherwise you get a NO_EVIDENCE alert for the wrong reason. If you would rather be alerted when nothing matches for a day, use `--evidence-file out/raises.jsonl` instead.

## n8n version

`n8n-workflow.json` is an importable workflow: Schedule trigger, HTTP Request `POST https://api.runvouch.com/v1/runs/start` (header `X-API-Key`, body `{"agent":"form-d-raises","source":"n8n"}`), HTTP Request `GET https://datasignalslab.com/v1/events?event_type=private_raise&limit=100&since=<cursor>` (header `Authorization: Bearer <key>`, retry 3 times 15 s apart because the API scales to zero and answers 503 with Retry-After while it wakes), a Code node that filters on the keywords and stores the cursor in workflow static data, an If node, a Telegram node, and HTTP Request `POST https://api.runvouch.com/v1/runs/end` with the `run_id` from the first node and evidence `{"events_fetched": true, "cursor_saved": true}`.

Import it, set `RUNVOUCH_KEY`, `DATASIGNALS_KEY` and `TELEGRAM_CHAT_ID` as n8n environment variables (or paste the values into the nodes), pick your Telegram credential on the Telegram node, and register the agent once with `rv agent form-d-raises --cadence 24h --grace 2h --evidence`. Keywords live in the Code node (`const words = [...]`).

## Record shape

Every event is the same envelope: `event_id`, `event_type`, `occurred_at`, `company{name,cik,ticker}`, `score`, `score_inputs`, `source{url,accession,form}`, `proof`, and `data`. For `private_raise` the `data` fields are `amount_offered_usd`, `amount_sold_usd`, `amount_remaining_usd`, `exemptions`, `first_sale`, `industry`, `investors_count`, `is_fund`, `minimum_investment_usd`, `related_persons`, `securities`, `state`, `year_of_inc` (from `GET /v1/event-types`).

## Files

- `raises.py`: fetch since cursor, filter, append, notify. `--input page.json --dry-run` replays a saved response.
- `keywords.txt`: your sector words.
- `crontab.txt`: the cron line.
- `n8n-workflow.json`: the same job as an n8n workflow.
- `out/`: `cursor.txt` (evidence), `raises.jsonl` (the matches), `run.log`.

## Tested

The two keyless endpoints live (`/v1/health`, `/v1/event-types`), the 401 path without a key, the filter and jsonl logic with a saved response in the documented envelope, and the `rv` lines against a RunVouch instance. `GET /v1/events` itself needs a key (free plan, by mail) and was not called from here.
