# Open source readiness check

Date of the scan: 2026-08-28. Scope: every tracked file, every untracked file present in the
working tree (including deploy/ and data/), and the full git history of the current branch
(`git log -p --all`, 109 commits). History was not rewritten; findings there are listed so
the decision can be taken with full knowledge.

What was searched for: API tokens and secrets (Stripe, Polar, Lemon Squeezy, Resend,
GitHub, npm, PyPI, Slack, AWS, Telegram, private keys), passwords, e-mail addresses,
the local Unix username, personal names, absolute home paths, IP addresses, tunnel and
chat identifiers.

## Result in one line

No live secret has ever been committed. The tracked tree is clean of the username and of
personal names after two small edits made during this check. The history carries local
home paths and one personal first name in a mail signature from commits that were later
corrected; nothing in it grants access to anything.

## Findings

Status column: `done` = fixed during this check, `keep` = intentional and fine to publish,
`decide` = needs a decision before publishing.

| # | Where | What | Action | Status |
|---|---|---|---|---|
| 1 | `deploy/npm-recovery-codes.txt` (untracked, gitignored) | npm 2FA recovery codes on disk inside the repo directory | Moved to `~/runvouch-private/` with a README; `.gitignore` entry kept; `tests/test_open_source_hygiene.py` fails if the file comes back | done |
| 2 | `integrations/slack/README.md` | a personal first name in a heading | Replaced by "the maintainer" | done |
| 3 | `deploy/DEPLOY.md` | the public IPv4 address of the production server | Replaced by `<server IP>` | done |
| 4 | `.env` (untracked, gitignored) | 25 live variables: admin token, Resend, Cloudflare, GitHub, PyPI, npm, Polar, Lemon Squeezy, Smithery, IndexNow | Never tracked. Stays where it is because `run.sh` loads it. Covered by `.gitignore` and the hygiene test | keep |
| 5 | `deploy/mcp-registry/key.pem`, `privkey.hex` (untracked, gitignored) | signing key for the MCP registry publisher | Never tracked. Left in place because `mcp-publisher` reads them from there. Better home: `~/runvouch-private/`, then point the publish command at that path | decide |
| 6 | `deploy/mcp-registry/mcp-publisher`, `mp.tgz` (untracked, gitignored) | 27 MB of downloaded binaries | Not secret; delete or leave, they are ignored | keep |
| 7 | `data/` (untracked, gitignored) | production SQLite with customer API keys and Telegram tokens, backups, Reddit drafts, crontab copies, logs | Never tracked. Docker and venv both accept `RUNVOUCH_DB` elsewhere | keep |
| 8 | `docs/BILLING.md`, `docs/STRIPE.md`, `docs/LEMONSQUEEZY.md`, `docs/BUSINESS.md`, `docs/MARKET.md`, `docs/SEO.md`, `docs/LAUNCH_*.md`, `docs/PRODUCT_HUNT.md`, `docs/DIRECTORIES.md` (untracked, gitignored) | internal business notes; the billing ones show token prefixes as placeholders (`sk_live_...`), not real keys | Never held a real key. Were tracked in commits `efdb308`, `8027b8b`, `425bd1a` and removed in `68d3076`; the historic versions also contain only placeholders. Keep ignored | keep |
| 9 | Git history, 24 lines | absolute paths `/home/<username>/...` in `backup.sh`, `remediator.py`, `deploy/cloudflared-config.yml`, `deploy/statuswacht.py`, `deploy/DEPLOY.md`, `shot.py` and tests; removed in commit `0de0ff8` | Reveals the Unix username and that a trading-bot project lives next to this one. Not a credential. Options: (a) publish as is, (b) squash history into one "initial public release" commit before the first push (loses blame, keeps the tree), (c) `git filter-repo --replace-text`. Recommendation: (b), the simplest and it also removes item 10 | decide |
| 10 | Git history, commit `a6c7b87` | billing e-mail signature with a personal first name; replaced by the team signature in `0de0ff8` | Same fix as item 9 | decide |
| 11 | Git history, one line | a temporary test database path under `/tmp/claude-1000/-home-<username>-TradingBot-...` | Same fix as item 9 | decide |
| 12 | Commit authors | 108 commits as `RunVouch <launch@runvouch.com>`, 1 as `runvouch <hello@runvouch.com>` | Both are company addresses; fine | keep |
| 13 | `deploy/koperswandeling.py`, `marktwacht.py`, `kwartaalmeting.py`, `reddit-scout.py`, `telegram-antwoord.py`, `remediator.py`, `site/blogmotor.py`, `deploy/DEPLOY.md` (tracked) | operational scripts for running the business: market watch, buyer walk-through, Reddit scouting, Telegram replies, self-healing crons. Dutch in places, and they name the second company (19 references to datasignals outside `site/public`) | Not secrets, but they are not part of the product and they tell the world how the shop is run. Recommendation: move to a private repo or to `~/runvouch-private/ops/` and keep in the public tree only `deploy/statuswacht.py`, `polar-setup.py`, `stripe-setup.py`, `nginx-runvouch.conf`, `cloudflared-config.yml`, `cloudflared.service`, `backup.sh` | decide |
| 14 | `site/` (tracked) | the marketing site generator with pricing, checkout URLs and blog articles | Public information by definition. Could be split into its own repo so the product repo stays small, not required | decide |
| 15 | E-mail addresses in the tree | `support@`, `hello@`, `launch@`, `alerts@`, `koperswandeling@` at runvouch.com; `support@datasignalslab.com`; `you@company.com`, `ops@company.com` placeholders; one npm author address inside `package-lock.json` | All company or placeholder addresses. The `koperswandeling@` and `datasignalslab.com` ones disappear with item 13 | keep |
| 16 | Token-shaped strings | `whsec_test`, `polar-test-secret`, `R0123456789ABCDEF...` (PagerDuty example key), `sk_live_...` and `polar_oat_...` as documentation placeholders | Test fixtures and documentation. The hygiene test's minimum lengths are set so these pass and real keys fail | keep |
| 17 | `shot.py`, `site/public/ph/` (untracked, gitignored) | screenshot helper with a machine-specific library path; Product Hunt screenshots | Were tracked in `5c783ec`, ignored since `425bd1a`. Historic version has the home path (item 9) | keep |
| 18 | `deploy/cloudflared-config.yml` | tunnel name `runvouch` and `~/.cloudflared/runvouch.json` | The credentials file itself is outside the repo; the config is harmless | keep |
| 19 | `.git/config`, remote `origin` | the GitHub fine-grained personal access token is embedded in the remote URL (`https://runvouch:github_pat_...@github.com/...`) | Not part of the tree and never published with a push, but it sits in plain text in a file many tools read, and a `git remote -v` in a shared terminal or log shows it. Fix: `git remote set-url origin https://github.com/runvouch/runvouch.git` and let a credential helper or `gh auth` supply the token. Not changed here because pushing is off limits in this session and the token also lives in `.env` as `GITHUB_TOKEN` | decide |

## What is now in place

- `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `requirements-dev.txt`
- `.env.example` with every variable `server.py` reads (a test enforces this)
- `docs/SELF_HOSTING.md`, `CONTRIBUTING.md`, a Self-hosting section in `README.md`
- `tests/test_open_source_hygiene.py`: fails on private files being tracked, on the recovery
  codes file existing on disk, on lost `.gitignore` entries, on token-shaped strings, on
  home paths and personal mail providers, and on the username or personal names (stored as
  sha256 hashes so the test does not carry them)
- `~/runvouch-private/` with a README, holding the npm recovery codes

Docker itself is not installed on this machine, so `docker build` and `docker compose up`
were not run. The image recipe was tested the equivalent way: a fresh venv with only the
files the Dockerfile copies (`runvouch/`, `requirements.txt`, `templates/verify_proof.py`,
`LICENSE`, `README.md`), `pip install -r requirements.txt`, uvicorn on 0.0.0.0 with
`RUNVOUCH_DB` and `RUNVOUCH_PROOF_DIR` pointing at an empty data directory. `/health`
returned ok, `/admin/accounts` produced a key, an agent was created and `/app` served the
dashboard. The first `docker build` should be run on a machine with Docker before the
compose file goes into the README as tested.

## License proposal

Current: MIT, `Copyright (c) 2026 RunVouch`, already referenced in the README badge, the
PyPI and npm packages and the GitHub Action (each of those copies `LICENSE` at build time).

| | MIT (current) | Apache-2.0 | AGPL-3.0 |
|---|---|---|---|
| Used by | Healthchecks.io (BSD-3, same family), most Python tooling | Cronitor SDKs, Grafana agent, many infra tools | Langfuse core, Plausible, Grafana server, Sentry (before BSL) |
| Effect on a cloud that forks it | none; a competitor may host it as a service | none for hosting; adds an explicit patent grant and requires listing changes | must publish their modifications when they offer it as a network service |
| Adoption friction | lowest; every company allows it | low; some avoid it in GPL projects | highest; many companies ban AGPL, and some registries and directories flag it |
| Fits the "free self-host, paid hosted" funnel | yes if the moat is the hosted service, not the code | same as MIT | yes if the fear is a hyperscaler reselling it |
| Cost to switch later | can move MIT to anything later (contributors so far: one) | can move to AGPL later | moving from AGPL to MIT later is a public step backwards |

Recommendation: keep MIT. The moat of RunVouch is the hosted proof archive, the Bitcoin
stamps, the status page, the alert delivery and the integrations directory presence, none
of which a fork gets by copying the code; and the audience (people wiring cron and Claude
Code hooks at small companies) is exactly the group that installs an MIT tool without asking
legal and skips an AGPL one. Healthchecks.io proves the model works with a permissive
license, while AGPL would shut the door on the Smithery, MCP Registry and enterprise
directory listings that are the current distribution plan; if a large host ever forks it,
that is a problem worth having and can be answered then with a dual-license on new
enterprise features.

If AGPL is chosen anyway: the packaging copies of `LICENSE` (`packaging/pypi`, `packaging/npm`,
`packaging/github-action`) are generated from the root file, so one edit propagates; the
README badge text and `packaging/pypi/pyproject.toml` `license` field need the same change.

## Decisions before publishing

1. History: publish as is, or squash into one initial commit (items 9 to 11). Recommendation: squash.
2. Operational scripts (item 13): move to a private place or accept that they are public.
3. MCP registry signing key (item 5): move to `~/runvouch-private/` or leave.
4. License (above): confirm MIT.
5. Run `docker build .` once on a machine with Docker before calling the Docker path tested.
6. Token in the remote URL (item 19): switch to a credential helper before anyone else touches this clone.
7. Which GitHub repository: `runvouch/runvouch` is already the URL in the README, the PyPI
   metadata and the docs, so that name is taken by this decision.
