# Stripe (kassa voor Solo $9 / Team $29)

Lemon Squeezy wees de RunVouch-store af op 26 aug 2026. Stripe is nu de route: geen keuring
van het businessmodel, Stripe Tax voor btw, Payment Links + 1 webhook.

## Eenmalig (Keith)
1. Stripe-account activeren (KvK-gegevens, bankrekening).
2. Dashboard -> Developers -> API keys -> Secret key (sk_live_...).
3. Stripe Tax aanzetten (Settings -> Tax) zodat Payment Links btw kunnen rekenen.

## Eenmalig (script)
    STRIPE_SECRET_KEY=sk_live_... .venv/bin/python deploy/stripe-setup.py
Maakt producten, prijzen, Payment Links en de webhook aan (idempotent) en print de regels voor .env:
STRIPE_SOLO_URL, STRIPE_TEAM_URL, STRIPE_PRICE_PLANS, STRIPE_WEBHOOK_SECRET, STRIPE_LIVE=1.
Daarna: site/build.py opnieuw draaien (kassaknoppen aan) en `systemctl --user restart runvouch`.

## Hoe het werkt
- Payment Link -> `checkout.session.completed` -> account op plan (gematcht op e-mail; bestaat het
  account nog niet, dan wordt het aangemaakt op het betaalde plan).
- `customer.subscription.updated/deleted` -> plan omhoog/omlaag, gematcht op `stripe_customer_id`.
- Handtekening: `Stripe-Signature` (t + v1, HMAC-SHA256 over "t.body", 5 min tolerantie). Dubbele events worden genegeerd.
- Test: `tests/test_server.py::test_stripe_webhook`.
