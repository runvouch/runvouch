# nightly-13f-consensus-digest

A nightly agent that asks DataSignals Lab which stocks the funds you follow are buying (SEC 13F, cross-fund consensus), writes `out/13f-digest.md` with the top 10 and what changed since yesterday, and is watched by RunVouch: MISSED if it does not start, FAILED if it exits non-zero, NO_EVIDENCE if it finishes green without rewriting the digest, BUDGET_RUN if a run costs more than the cap.

Two ways to run it. Both write the same file and use the same RunVouch agent.

- `digest.py`: plain Python, standard library only, no Claude needed. Deterministic.
- `prompt.md` with headless `claude -p`: Claude Code does the same work through the MCP server. Use this if you already run Claude Code Routines.

## What you need

- A RunVouch key (free for 3 agents): `export RUNVOUCH_KEY=rv_...`
- An Apify token (free account, no card) for the DataSignals MCP server: `export APIFY_TOKEN=apify_api_...`
  The 13F tool is free for the first 50 MCP calls a month, which covers one call a night. After that it is $0.20 per result on your Apify account. `--spend-cap 5` makes the server refuse calls once your ledger reaches $5.
- `rv`: `pip install runvouch` or `curl -fsSL https://runvouch.com/rv -o ~/bin/rv && chmod +x ~/bin/rv`

## Setup (two minutes)

```
cp -r templates/nightly-13f-consensus-digest ~/templates/ && cd ~/templates/nightly-13f-consensus-digest
rv agent nightly-13f-digest --cadence 24h --grace 2h --cap-run-cost 1 --evidence
```

Edit `funds.txt` if you want other filers (one CIK per line; the three defaults are Berkshire, Scion and Pershing Square, the actor's own defaults). Then run it once by hand:

```
rv run nightly-13f-digest --evidence-file out/13f-digest.md -- python3 digest.py --spend-cap 5
cat out/13f-digest.md
```

Install the crontab line from `crontab.txt` (`crontab -e`). Done.

## Claude Code version

Register the MCP server once and use the prompt file instead of the script:

```
claude mcp add --transport http datasignals https://datasignalslab--datasignals-mcp.apify.actor/mcp --header "Authorization: Bearer $APIFY_TOKEN"
rv run nightly-13f-digest --evidence-file out/13f-digest.md -- claude -p "$(cat prompt.md)" --dangerously-skip-permissions
```

`rv run` reports start, exit code, duration and the evidence check, but not the Claude cost. If you want cost per run and the `--cap-run-cost 1` cap to bite, install the RunVouch Claude Code plugin and let it report instead of `rv run` (do not use both, you would get two runs per night):

```
/plugin marketplace add runvouch/claude-plugin
/plugin install runvouch
export RUNVOUCH_AGENT=nightly-13f-digest
export RUNVOUCH_EVIDENCE=out/13f-digest.md
claude -p "$(cat prompt.md)" --dangerously-skip-permissions
```

As a Claude Code Routine: paste the contents of `prompt.md` as the routine prompt, set the three environment variables above, schedule it daily.

## What the digest looks like

```
# 13F consensus digest, 2026-08-26

## Top 10 by number of funds buying
| # | Issuer | Funds buying | Funds holding | Total value (USD) | Conviction |
...
## Changed since the previous digest
- Entered the top 10: ...
- ACME CORP: buyers 1 -> 2, holders 2 -> 3
```

13F filings are quarterly with a 45 day lag, so most nights say "No change." That is the point: the night a new filing lands you see it, and every other night RunVouch confirms the agent ran and wrote the file.

## Files

- `digest.py`: fetch, rank, diff, write. `--input saved.json` replays a saved MCP result offline.
- `ds_mcp.py`: 40 line MCP client (streamable HTTP, one POST per call). Try `python3 ds_mcp.py usage`.
- `prompt.md`: the same steps for `claude -p`.
- `funds.txt`: the filers.
- `crontab.txt`: the cron line.
- `out/`: `13f-digest.md` (evidence file) and `13f-digest.prev.json` (yesterday's top 10 for the diff).

## Tested

`ds_mcp.py` against the live MCP server (free tools `resolve_company` and `usage`), `digest.py --input` with a saved result in the actor's output shape, the `rv agent` / `rv run` lines against a RunVouch instance including the NO_EVIDENCE path. The live `hedge_fund_13f` call was not made from the template repo to avoid spending; it is the actor's documented tool with its default inputs.
