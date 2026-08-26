#!/usr/bin/env python3
"""One-time Polar.sh setup for RunVouch (stdlib only). Idempotent: looks products up by name first.

  POLAR_TOKEN=polar_oat_... .venv/bin/python deploy/polar-setup.py            # production
  POLAR_TOKEN=... POLAR_API=https://sandbox-api.polar.sh .venv/bin/python deploy/polar-setup.py   # sandbox

Token: polar.sh -> Settings -> Developers -> New token, scopes: products:read/write, checkout_links:read/write,
webhooks:read/write. Creates Solo ($9/mo) + Team ($29/mo), two checkout links, and the webhook endpoint
https://api.runvouch.com/webhooks/polar. Prints the lines to append to .env.
Written against the Polar API docs (Aug 2026); if a field name changed, the error message names it.
"""
import json, os, sys, urllib.request

TOKEN = os.getenv("POLAR_TOKEN") or sys.exit("POLAR_TOKEN not set")
API = os.getenv("POLAR_API", "https://api.polar.sh").rstrip("/")
WEBHOOK_URL = os.getenv("POLAR_WEBHOOK_URL", "https://api.runvouch.com/webhooks/polar")
PLANS = [("solo", "RunVouch Solo", 900, "15 agents, 90-day history, weekly cost report, priority alerts"),
         ("team", "RunVouch Team", 2900, "100 agents, Slack & PagerDuty, shared dashboard, API export")]


def call(method, path, data=None):
    req = urllib.request.Request(API + path, json.dumps(data).encode() if data is not None else None,
                                 {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json", "User-Agent": "runvouch-setup/0.3"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Polar {e.code} on {method} {path}: {e.read().decode()[:800]}")


def items(path):
    out, page = [], 1
    while True:
        r = call("GET", f"{path}{'&' if '?' in path else '?'}page={page}&limit=100")
        out += r.get("items", [])
        if len(out) >= (r.get("pagination") or {}).get("total_count", 0) or not r.get("items"):
            return out
        page += 1


env, product_plans = {}, []
for plan, name, cents, desc in PLANS:
    found = [p for p in items("/v1/products/?is_archived=false") if p["name"] == name]
    product = found[0] if found else call("POST", "/v1/products/", {
        "name": name, "description": desc, "recurring_interval": "month",
        "prices": [{"amount_type": "fixed", "price_amount": cents, "price_currency": "usd"}],
        "metadata": {"plan": plan}})
    links = [l for l in items("/v1/checkout-links/") if (l.get("metadata") or {}).get("plan") == plan]
    link = links[0] if links else call("POST", "/v1/checkout-links/", {
        "payment_processor": "stripe", "products": [product["id"]], "allow_discount_codes": True,
        "success_url": "https://runvouch.com/app?upgraded=" + plan, "metadata": {"plan": plan}})
    product_plans.append(f"{product['id']}:{plan}")
    env[f"POLAR_{plan.upper()}_URL"] = link["url"]
    print(f"{plan}: product {product['id']} link {link['url']}")

hooks = [h for h in items("/v1/webhooks/endpoints") if h["url"] == WEBHOOK_URL]
if hooks:
    print(f"webhook exists: {hooks[0]['id']} (secret shown at creation only; keep POLAR_WEBHOOK_SECRET from .env)")
else:
    hook = call("POST", "/v1/webhooks/endpoints", {"url": WEBHOOK_URL, "format": "raw", "events": [
        "order.paid", "order.refunded", "subscription.active", "subscription.updated", "subscription.canceled", "subscription.revoked"]})
    env["POLAR_WEBHOOK_SECRET"] = hook["secret"]
    print(f"webhook created: {hook['id']}")

env["POLAR_PRODUCT_PLANS"] = ",".join(product_plans)
env["POLAR_LIVE"] = "1"
print("\n# append to .env, then rebuild the site (site/build.py) and restart runvouch:")
for k, v in env.items():
    print(f"{k}={v}")
