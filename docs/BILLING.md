# Kassa (Solo $9 / Team $29)

Stand 26 aug 2026: Lemon Squeezy wees de aparte RunVouch-store af (mail 08:44, geen reden gegeven).
Niet in de DataSignals-store hangen: dat model is nu expliciet afgekeurd en die store verdient wel.
Stripe kan niet zonder KvK. Route: **Polar.sh** (merchant of record, particulieren welkom, btw geregeld,
4% + $0,40). Stripe blijft ingebouwd voor als er ooit een KvK komt (docs/STRIPE.md).

De server ondersteunt drie kassa's naast elkaar; de site kiest op basis van `.env`:
`POLAR_LIVE=1` > `STRIPE_LIVE=1` > `LS_LIVE=1`. Zonder een van die drie staan de knoppen op
"paid plans open Sept 2026" (contactformulier).

## Polar - eenmalig (Keith, ~10 min, geen KvK nodig)
1. https://polar.sh -> Sign in with GitHub (account `runvouch`) -> organisatie `runvouch` aanmaken.
2. Onboarding: land Nederland, "individual", uitbetaling via Stripe Connect (IBAN + ID).
3. Settings -> Developers -> New token: scopes products:write, checkout_links:write, webhooks:write.
4. Plakken:  `echo 'POLAR_TOKEN=polar_oat_...' >> ~/runvouch/.env`

## Polar - eenmalig (script)
    POLAR_TOKEN=... .venv/bin/python deploy/polar-setup.py
Maakt producten, checkout-links en de webhook aan (idempotent) en print de regels voor .env:
POLAR_SOLO_URL, POLAR_TEAM_URL, POLAR_PRODUCT_PLANS, POLAR_WEBHOOK_SECRET, POLAR_LIVE=1.
Daarna `site/build.py` opnieuw draaien en `systemctl --user restart runvouch`.
Eerst met echt geld een Solo kopen en weer opzeggen (zie [[live-pas-bij-honderd-procent]]).

## Hoe de webhook werkt (`/webhooks/polar`)
- Standard Webhooks-handtekening (webhook-id, webhook-timestamp, webhook-signature v1, base64 HMAC).
- `order.paid` (eerste betaling) -> plan op basis van product-id; account gematcht op e-mail,
  bestaat het niet dan wordt het aangemaakt op het betaalde plan. Verlengingen (`subscription_cycle`) doen niets.
- `subscription.updated/active` -> plan volgt het product; `subscription.revoked` -> free.
  `subscription.canceled` met een einddatum laat het plan staan tot `revoked` komt.
- Dubbele events (zelfde webhook-id) worden genegeerd. Test: `tests/test_server.py::test_polar_webhook`.
