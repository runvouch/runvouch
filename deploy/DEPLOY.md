# Deploy — hoe RunVouch publiek komt

Twee helften, zoals bij datasignalslab:

| Helft | Waar | Hoe |
|---|---|---|
| **Landing** (`site/`) | **zelfde server**, via de tunnel (FastAPI serveert `site/index.html` op host runvouch.com) | geen Netlify nodig; aanpassen = bestand wijzigen + `systemctl --user restart runvouch` |
| **API** (`runvouch/server.py`) | **deze server**, poort 8787 (systemd user-service) | moet bereikbaar op `https://api.runvouch.com` — 2 routes hieronder |

Netlify kan de API niet hosten (langlopend proces + SQLite + achtergrond-sweeper). De landing praat via CORS met `api.runvouch.com`.

## Route A — zonder root (aanbevolen nu; geen sudo op deze server)
Cloudflare Tunnel: gratis HTTPS + DNS zonder poorten te openen, draait als gewone user.
1. Domein bij Cloudflare (registrar of alleen DNS, gratis plan).
2. Eenmalig door eigenaar (login = browser): `cloudflared tunnel login` → `cloudflared tunnel create runvouch` → `cloudflared tunnel route dns runvouch api.runvouch.com`.
3. `~/.cloudflared/config.yml`: `tunnel: runvouch` / `ingress: [{hostname: api.runvouch.com, service: http://127.0.0.1:8787}, {service: http_status:404}]`.
4. `cloudflared service install` werkt niet zonder root → gebruik `deploy/cloudflared.service` (systemd --user).
Binary: `curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/bin/cloudflared && chmod +x ~/bin/cloudflared`.

## Route B — met sudo
`deploy/nginx-runvouch.conf` → `/etc/nginx/sites-available/`, symlink, `sudo certbot --nginx -d api.runvouch.com`. DNS A-record api → <server IP>.

## .env op de server (na domein)
```
RUNVOUCH_PUBLIC_URL=https://api.runvouch.com
RUNVOUCH_CORS=https://runvouch.com,https://www.runvouch.com
LS_WEBHOOK_SECRET=<uit Lemon Squeezy → Settings → Webhooks, URL https://api.runvouch.com/webhooks/lemonsqueezy>
LS_VARIANT_PLANS=<solo-variant-id>:solo,<team-variant-id>:team
```
Daarna `systemctl --user restart runvouch`.

## Lemon Squeezy (bestaande store "DataSignals Lab" of nieuwe store onder merknaam)
Producten: "RunVouch Solo" $9/mnd en "RunVouch Team" $29/mnd (subscription). Webhook-events aanvinken:
subscription_created/updated/cancelled/expired/resumed/paused, order_created/refunded. Signing secret → `.env`.
Koppeling gebeurt op e-mailadres: klant koopt met hetzelfde e-mailadres als de signup → plan gaat automatisch omhoog/omlaag.

## Checklist vóór "live"
- [ ] domein + api.runvouch.com werkt via HTTPS (`curl https://api.runvouch.com/health` → ok)
- [ ] landing op Netlify, signup-formulier geeft key
- [ ] LS-producten + webhook-test (LS heeft "Send test event")
- [ ] `RUNVOUCH_ADMIN_TOKEN` geroteerd, `.env` chmod 600
- [ ] GitHub-repo (MIT) onder merk-account, zonder `data/`/`.env`
