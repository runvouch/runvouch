#!/usr/bin/env python3
"""One-time Stripe setup for RunVouch (stdlib only). Idempotent: looks products up by name before creating.

  STRIPE_SECRET_KEY=sk_live_... .venv/bin/python deploy/stripe-setup.py

Creates: products Solo ($9/mo) + Team ($29/mo) with recurring USD prices, two Payment Links
(tax collected automatically, promotion codes allowed), and the webhook endpoint
https://api.runvouch.com/webhooks/stripe. Prints the lines to append to .env.
"""
import base64, json, os, sys, urllib.parse, urllib.request

KEY = os.getenv("STRIPE_SECRET_KEY") or sys.exit("STRIPE_SECRET_KEY not set")
API = "https://api.stripe.com/v1"
WEBHOOK_URL = os.getenv("STRIPE_WEBHOOK_URL", "https://api.runvouch.com/webhooks/stripe")
PLANS = [("solo", "RunVouch Solo", 900, "15 agents, 90-day history, weekly cost report, priority alerts"),
         ("team", "RunVouch Team", 2900, "100 agents, Slack & PagerDuty, shared dashboard, API export")]


def call(method, path, data=None):
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    req = urllib.request.Request(API + path, body, {"Authorization": "Basic " + base64.b64encode((KEY + ":").encode()).decode(),
                                                    "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "runvouch-setup/0.3"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Stripe {e.code} on {method} {path}: {e.read().decode()[:600]}")


def flat(prefix, d):  # {"a": {"b": 1}} -> {"a[b]": 1}
    out = {}
    for k, v in d.items():
        kk = f"{prefix}[{k}]" if prefix else k
        out.update(flat(kk, v) if isinstance(v, dict) else {kk: v})
    return out


env = {}
price_plans = []
for plan, name, cents, desc in PLANS:
    found = [p for p in call("GET", "/products?active=true&limit=100")["data"] if p["name"] == name]
    product = found[0] if found else call("POST", "/products", {"name": name, "description": desc, "metadata[plan]": plan})
    prices = [p for p in call("GET", f"/prices?product={product['id']}&active=true")["data"]
              if p["unit_amount"] == cents and p["currency"] == "usd" and (p.get("recurring") or {}).get("interval") == "month"]
    price = prices[0] if prices else call("POST", "/prices", {"product": product["id"], "unit_amount": cents, "currency": "usd",
                                                              "recurring[interval]": "month", "tax_behavior": "exclusive", "metadata[plan]": plan})
    links = [l for l in call("GET", "/payment_links?active=true&limit=100")["data"] if (l.get("metadata") or {}).get("plan") == plan]
    link = links[0] if links else call("POST", "/payment_links", flat("", {
        "line_items[0]": {"price": price["id"], "quantity": 1},
        "automatic_tax": {"enabled": "true"}, "allow_promotion_codes": "true", "billing_address_collection": "auto",
        "tax_id_collection": {"enabled": "true"},
        "after_completion": {"type": "redirect", "redirect[url]": "https://runvouch.com/app?upgraded=" + plan},
        "metadata": {"plan": plan, "price": price["id"]},
        "subscription_data": {"metadata[plan]": plan},
    }))
    price_plans.append(f"{price['id']}:{plan}")
    env[f"STRIPE_{plan.upper()}_URL"] = link["url"]
    print(f"{plan}: product {product['id']} price {price['id']} link {link['url']}")

hooks = [h for h in call("GET", "/webhook_endpoints?limit=100")["data"] if h["url"] == WEBHOOK_URL]
if hooks:
    print(f"webhook exists: {hooks[0]['id']} (secret only shown at creation; reuse STRIPE_WEBHOOK_SECRET from .env)")
else:
    hook = call("POST", "/webhook_endpoints", flat("", {"url": WEBHOOK_URL, "enabled_events": [
        "checkout.session.completed", "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"]}))
    env["STRIPE_WEBHOOK_SECRET"] = hook["secret"]
    print(f"webhook created: {hook['id']}")

env["STRIPE_PRICE_PLANS"] = ",".join(price_plans)
env["STRIPE_LIVE"] = "1"
print("\n# append to .env, then rebuild the site (site/build.py) and restart runvouch:")
for k, v in env.items():
    print(f"{k}={v}")
