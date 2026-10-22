# Deploy: how RunVouch runs in production

One server, one process. `runvouch/server.py` (FastAPI, SQLite) serves the API on
`api.runvouch.com` and the static site on `runvouch.com` and `www.runvouch.com` from
`site/public/`, which `site/build.py` generates. Nothing is hosted elsewhere.

| Part | Where | How to change it |
|---|---|---|
| API (`runvouch/server.py`) | this server, port 8787, `runvouch.service` (systemd user unit, wraps `run.sh`) | edit, run the tests, `systemctl --user restart runvouch` |
| Site (`site/`) | same process, served from `site/public/` | edit `site/build.py`, `site/integrations.py` or `site/articles.json`, then `.venv/bin/python site/build.py`, no restart |
| HTTPS and DNS | Cloudflare Tunnel, `cloudflared.service` (systemd user unit) | `deploy/cloudflared-config.yml` routes all three hostnames to 127.0.0.1:8787 |
| Billing | Polar (subscriptions Solo $19 and Team $99) | `deploy/polar-setup.py` creates products, checkout links and the webhook and prints the environment lines |
| Backups | `backup.sh`, nightly, `data/backups/` on this server | set `RUNVOUCH_BACKUP_CMD` in the environment file to ship each artefact off the machine |

No root is needed. `nginx-runvouch.conf` is the alternative for a host with sudo and a
public IP (certbot for TLS). It is not in use.

## Tunnel (one time, by the owner, needs a browser login)

    cloudflared tunnel login
    cloudflared tunnel create runvouch
    cloudflared tunnel route dns runvouch api.runvouch.com
    cloudflared tunnel route dns runvouch runvouch.com
    cloudflared tunnel route dns runvouch www.runvouch.com
    cp deploy/cloudflared-config.yml ~/.cloudflared/config.yml   # set the credentials-file path
    cp deploy/cloudflared.service ~/.config/systemd/user/ && systemctl --user enable --now cloudflared

Binary: `curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/bin/cloudflared && chmod +x ~/bin/cloudflared`.
`cloudflared service install` needs root, hence the user unit.

## Environment file on the server

Every name must also appear in the example file next to it (a test enforces it). The ones
that matter for a public deployment:

    RUNVOUCH_PUBLIC_URL=https://api.runvouch.com
    RUNVOUCH_CORS=https://runvouch.com,https://www.runvouch.com
    RUNVOUCH_ADMIN_TOKEN=<long random string, file mode 600>
    POLAR_WEBHOOK_SECRET=<from polar-setup.py>
    POLAR_PRODUCT_PLANS=<product id>:solo,<product id>:team

Then `systemctl --user restart runvouch` and `curl https://api.runvouch.com/health`.

## Billing (Polar)

    POLAR_TOKEN=polar_oat_... .venv/bin/python deploy/polar-setup.py            # production
    POLAR_TOKEN=... .venv/bin/python deploy/polar-setup.py --prices             # only move the amounts

The webhook is `https://api.runvouch.com/webhooks/polar`. A customer is matched on the
e-mail address of the signup, so a purchase with the same address moves the plan up or down
without manual work. The checkout page text (agent counts, history) is edited in the Polar
dashboard and must match `PLAN_LIMITS` in `server.py` and the pricing page.

## Releases

`packaging/pypi/build.sh` and `packaging/npm/build.sh` build from the canonical sources and
rewrite the default URL to the hosted API. Publishing is explicit and manual:
`twine upload packaging/pypi/dist/*` and `npm publish` in `packaging/npm/`. The version in
`packaging/pypi/pyproject.toml` is the one `/health`, the FastAPI app and the MCP server
report, so bump it there and in `packaging/npm/package.json`, the mcpb manifest and the
Claude Code plugin together, and add the line to `RELEASES` in `site/build.py`.

## Other timers on this machine

`runvouch-site.timer` (weekly site rebuild), `statuswacht.timer` (external check of the
status page every minute), `pushwacht.timer` (hourly push of main to GitHub when the suite
is green), `prwacht.timer` and `prantwoord.timer` (pull request follow-up). Unit files live
in `deploy/`.

## Checklist before a change goes live

- [ ] `.venv/bin/python -m pytest -q tests` green
- [ ] `curl https://api.runvouch.com/health` reports ok and the expected version
- [ ] site rebuilt if `site/` changed, spot-check one page
- [ ] environment file and `data/` not in git
