# RunVouch for Slack

What RunVouch already does today: every alert (MISSED, FAILED, NO_EVIDENCE, STALLED, RETRY_STORM, BUDGET_RUN, BUDGET_DAY, DRIFT) and the weekly digest are posted to a Slack **incoming webhook** as Block Kit messages: a header with kind and agent, two fields, the message, and a link to the dashboard. The webhook URL is set once with `PUT /v1/settings {"slack_webhook_url": "https://hooks.slack.com/services/..."}` or on https://runvouch.com/app. That works on every plan and needs no app listing. Since the OAuth routes exist, the one-click Add to Slack flow on https://runvouch.com/integrations/slack ends in the same field.

This folder is what a **Slack App Directory listing** needs on top of that, so a workspace admin can find RunVouch inside Slack and install it with one click instead of copying a webhook URL.

## Files

- `manifest.json`: the app manifest. One bot scope, `incoming-webhook`, nothing else; the app never reads messages. Paste it at https://api.slack.com/apps, Create New App, From a manifest.
- `listing.md`: the texts for the directory listing form (short description, long description, categories, support and privacy URLs).

## How the install flow works (built, in `runvouch/server.py`)

Three routes, all on the API host:

| Route | What it does |
|---|---|
| `GET /integrations/slack/status` | `{"configured": true/false, "install_url": ..., "scope": "incoming-webhook"}`. The site page reads this to enable or grey out the button. |
| `GET /integrations/slack/install?token=<RunVouch API key>` | Checks the key, builds a signed state (`<account_id>.<expiry>.<hmac>`, HMAC-SHA256 with the client secret, valid 10 minutes) and redirects to `https://slack.com/oauth/v2/authorize` with `client_id`, `scope=incoming-webhook`, `redirect_uri` and that state. The API key never reaches Slack. Viewer keys (`rvv_`) are refused. |
| `GET /integrations/slack/callback?code&state` | Verifies the state, exchanges the code at `oauth.v2.access` (client id and secret from the environment), stores `incoming_webhook.url` as `slack_webhook_url` on the account, posts a CONNECTED message to the channel with the normal `_slack()` block format, and redirects to `https://runvouch.com/integrations/slack/installed?channel=...`. On a Slack error (`access_denied`, `invalid_code`, ...) it redirects to the same page with `?error=...` and changes nothing. |

If `SLACK_CLIENT_ID` or `SLACK_CLIENT_SECRET` is missing, install and callback answer `503 Slack app not configured`; the site page then shows the webhook route instead of a working button. Nothing else in the service depends on those variables.

Tests: `tests/test_server.py`, the three `test_slack_*` tests at the end (Slack's token endpoint is mocked; the state signing, expiry and tampering are checked for real).

Public page with the button: https://runvouch.com/integrations/slack (built by `site/build.py`). Confirmation page: https://runvouch.com/integrations/slack/installed. The dashboard's Slack field also has an Add to Slack link.

## What remains to be done once, in the browser (with the RunVouch Slack account, not a personal one)

1. **Create the app.** https://api.slack.com/apps, Create New App, From a manifest, pick a workspace (a RunVouch test workspace, not a customer's), paste `manifest.json`. The redirect URL in it is `https://api.runvouch.com/integrations/slack/callback`; it must match exactly what the server sends, which is `RUNVOUCH_PUBLIC_URL + /integrations/slack/callback`.
2. **Icon and colour.** Basic Information, Display Information: upload `site/public/logo-400.png` scaled to 512 by 512, background `#0b1020`.
3. **Incoming Webhooks.** Features, Incoming Webhooks, switch on.
4. **Credentials into the service.** Basic Information, App Credentials: copy Client ID and Client Secret. Add two lines to `~/runvouch/.env` (mode 600, loaded by `run.sh`):
   ```
   SLACK_CLIENT_ID=...
   SLACK_CLIENT_SECRET=...
   ```
   then `systemctl --user restart runvouch` and check `curl https://api.runvouch.com/health` and `curl https://api.runvouch.com/integrations/slack/status` (must say `"configured": true`).
5. **Test end to end.** Open https://runvouch.com/integrations/slack, enter a test account's key, Add to Slack, pick a channel in the test workspace. Expect: a CONNECTED message in the channel, the confirmation page, and `channels.slack: true` on `GET /v1/me`. Then `POST /v1/settings/test-alert`. Repeat once from a second workspace to be sure the consent screen and the redirect work outside the app's home workspace. (Until the app is approved for the directory, only workspaces where an admin accepts the install can add it, which is enough for testing.)
6. **Distribution.** Manage Distribution, Activate Public Distribution (requires: redirect URL set, no hard-coded secrets, and that the checklist there is ticked).
7. **Directory submission.** Submit to App Directory, fill the form with `listing.md`: support URL https://runvouch.com/contact, privacy policy https://runvouch.com/privacy, terms https://runvouch.com/terms, pricing https://runvouch.com/pricing, security https://runvouch.com/security, install landing page https://runvouch.com/integrations/slack. Slack requires an Add to Slack button on a public page (that page), a working support address, and that the requested scope matches the described use. Review by Slack takes days to a few weeks; they reply by e-mail to the account that submitted.

Nothing in this folder contains a secret. The client secret stays in the app settings and in the service's `.env`.

## Message format (unchanged)

```json
{
  "text": "RunVouch MISSED: nightly-report ...",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "RunVouch MISSED: nightly-report"}},
    {"type": "section", "fields": [{"type": "mrkdwn", "text": "*Kind*\nMISSED"}, {"type": "mrkdwn", "text": "*Agent*\nnightly-report"}]},
    {"type": "section", "text": {"type": "mrkdwn", "text": "cadence 24h + grace 30m passed without a start"}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "<https://runvouch.com/app|Open the dashboard>"}]}
  ]
}
```

Source: `_slack()` in `runvouch/server.py`.
