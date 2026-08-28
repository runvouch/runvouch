# Contributing to RunVouch

Thanks for looking. RunVouch is small on purpose: one server file, one client file, one
proof module, and a test suite that runs in under a minute. Keep it that way.

## Set up

```
git clone https://github.com/runvouch/runvouch.git && cd runvouch
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

All tests must be green before and after your change. Tests use a temporary SQLite file
and never touch the network.

## Where things live

| Path | What |
|---|---|
| `runvouch/server.py` | FastAPI app, SQLite schema, all detectors, alert delivery, dashboard |
| `runvouch/cli.py` | the `rv` client; stdlib only, no dependencies allowed |
| `runvouch/proof.py` | per-run hashing, Merkle day roots, chain, OpenTimestamps |
| `integrations/` | MCP server, Claude Code plugin, n8n node, Slack, Grafana, Home Assistant |
| `packaging/` | PyPI, npm and GitHub Action packages built from the same client |
| `templates/` | ready-to-run agent examples and the offline proof verifier |
| `docs/SELF_HOSTING.md` | how to run it yourself |

## Rules of the road

- The client (`cli.py`, `integrations/python`, `integrations/node`) stays dependency-free.
  If a change needs a library there, it is the wrong change.
- A new detector or alert channel needs a test in `tests/test_server.py` that triggers it.
- Schema changes are additive only (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN`
  guarded by a try). Existing databases must keep working after `git pull`.
- No secrets, tokens, personal names or local paths in the tree. `tests/test_open_source_hygiene.py`
  fails the build if one slips in; see `docs/OPEN_SOURCE_CHECK.md`.
- Plain ASCII in docs and messages. Short sentences. Explain the why in a comment when the
  code alone does not say it.

## Sending a change

1. Fork, branch, make the change, run the tests.
2. Open a pull request with a short description of what changed and why. Link the issue if
   there is one.
3. Small pull requests get merged fast; large ones get questions first.

## Reporting a security issue

Do not open a public issue. Write to support@runvouch.com and you will get an answer within
two working days.

## License

By contributing you agree that your contribution is licensed under the same license as the
project (see `LICENSE`).
