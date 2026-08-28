# RunVouch for Slack

What RunVouch already does today: every alert (MISSED, FAILED, NO_EVIDENCE, STALLED, RETRY_STORM, BUDGET_RUN, BUDGET_DAY, DRIFT) and the weekly digest are posted to a Slack **incoming webhook** as Block Kit messages: a header with kind and agent, two fields, the message, and a link to the dashboard. The webhook URL is set once with `PUT /v1/settings {"slack_webhook_url": "https://hooks.slack.com/services/..."}` or on https://runvouch.com/app. That works on every plan and needs no app listing.

This folder is what a **Slack App Directory listing** needs on top of that, so a workspace admin can find RunVouch inside Slack and install it with one click instead of copying a webhook URL.

## Files

- `manifest.json`: the app manifest. One bot scope, `incoming-webhook`, nothing else; the app never reads messages. Paste it at https://api.slack.com/apps, Create New App, From a manifest.
- `listing.md`: the texts for the directory listing form (short description, long description, categories, support and privacy URLs).

## How the install flow works with only `incoming-webhook`

When a user clicks Add to Slack, Slack runs the OAuth flow, asks which channel to post to, and redirects to `https://api.runvouch.com/oauth/slack/callback?code=...&state=...`. The callback exchanges the code at `https://slack.com/api/oauth.v2.access` (client id and secret from the app settings) and the response contains `incoming_webhook.url` for the chosen channel. That URL is exactly what `slack_webhook_url` in the account settings holds today, so the callback stores it on the account identified by `state` and the existing alert code needs no change.

That callback does not exist yet. It is small (one GET route, one POST to Slack, one UPDATE on accounts) and is the only code change the listing requires. Until it exists, the manifest still works for a private app: Slack shows the webhook URL in the app's Incoming Webhooks page and the user pastes it into RunVouch, which is the documented flow on https://runvouch.com/docs/alerts.

## What Keith does once (in the browser, with the RunVouch Slack account)

1. **Create the app.** https://api.slack.com/apps, Create New App, From a manifest, pick a workspace (a RunVouch test workspace, not a customer's), paste `manifest.json`. Slack validates the manifest; the redirect URL is accepted even before the callback exists.
2. **Icon and colour.** Basic Information, Display Information: upload `site/public/logo-400.png` (512 by 512 is required; scale it once), background `#0b1020`.
3. **Incoming Webhooks.** Features, Incoming Webhooks, switch on. This is where the manifest's scope becomes visible.
4. **Credentials.** Basic Information, App Credentials: copy Client ID and Client Secret into the API host's environment as `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET` for the callback (step 6).
5. **Test the webhook path as it is today.** Add to Workspace from the Incoming Webhooks page, choose a channel, copy the webhook URL, `PUT /v1/settings` with it, then `POST /v1/settings/test-alert`. A TEST alert must land in the channel.
6. **Callback.** Have the `/oauth/slack/callback` route added to `runvouch/server.py` (see the section above; the `state` parameter should carry a short-lived token bound to the logged-in account, not the API key). Deploy. Test Add to Slack end to end from a second workspace.
7. **Directory submission.** Under Submit to App Directory, fill the form with `listing.md`: support URL https://runvouch.com/contact, privacy policy https://runvouch.com/privacy, terms https://runvouch.com/terms, pricing https://runvouch.com/pricing, security https://runvouch.com/security. Slack requires: an Add to Slack button on a public page (the docs/alerts page qualifies once the callback exists), a working support address, and that the requested scopes match the described use. Review by Slack takes days to a few weeks; they reply by e-mail to the account that submitted.

Nothing in this folder contains a secret. The client secret and the signing secret stay in the app settings and the API host environment.

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
