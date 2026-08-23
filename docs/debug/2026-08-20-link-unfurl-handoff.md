# Handoff: tcsc.ski link unfurls never fire (Slack not delivering events)

Written 2026-08-20 ~19:05 UTC by the outgoing debugging session. Untracked file, not committed.

## The symptom

Pasting a tcsc.ski trip link (e.g. `https://tcsc.ski/cuyuna`, `https://tcsc.ski/birkie`) into Slack shows only Slack's generic OpenGraph preview. The app's signup card (built by `build_trip_unfurls` in `app/slack/bolt_app.py`, shipped in PR #238, merge `2d01150`) never appears.

## Read this first: where the investigation landed

The failure is NOT in our code, config, scopes, or deploy. Every one of those is verified below. The evidence says **Slack is not delivering any `events_api` envelopes to this app at all**, and this is not specific to `link_shared`. A forced `reaction_added` event (a long-subscribed type, in a channel the bot is in) also produced nothing. Interactivity (buttons, modals, slash commands) still works over the same socket, so this has gone unnoticed.

CAVEAT: the final confirming log read was interrupted. **Do step 1 of Next steps before trusting the conclusion.**

## Verified working (and how it was proven)

1. **Handler code end to end.** A synthetic `link_shared` event, signed with the real `SLACK_SIGNING_SECRET` and POSTed to `https://tcsc.ski/slack/events`, made production build the cuyuna card and attach it via `chat_unfurl`. So intake, `build_trip_unfurls`, prod DB data, and `chat_unfurl` scopes all work in production.
2. **Bot token scopes.** `x-oauth-scopes` response header on `auth.test` includes `links:read` and `links:write`.
3. **App manifest** (pasted by Rob, in the conversation): `link_shared` present in BOTH `settings.event_subscriptions.bot_events` and `user_events`; `features.unfurl_domains: ["tcsc.ski"]`; `socket_mode_enabled: true`. App id `A06FYPU3FTN`.
4. **Not an enterprise install** (`auth.test` shows no enterprise id), so `org_deploy_enabled: true` in the manifest is inert.
5. **Reinstalls happened.** `team.integrationLogs` (Rob's user token has `admin` scope) shows the TCSC app "expanded" at 11:54:27Z and 12:03:16Z on 2026-08-20. Test pastes at 12:28Z, 12:36Z, and 18:50Z all failed, so propagation delay is ruled out.
6. **Prod socket connection is up.** "⚡️ Bolt app is running!" in Render logs at 12:19:20Z and again 18:56:51Z (after the logging deploy). No socket errors logged.
7. **No competing consumers.** With Socket Mode enabled in the app config, Slack routes all events over sockets and `/slack/events` gets no organic traffic (Render access logs confirm: the only POST ever is the synthetic one). No stray local processes hold a connection (checked `pgrep` on the Unraid container; the lone `python3 app.py` is the wedding planning app with no Slack env). Local listeners opened during the day received zero envelopes of any type, consistent with prod being the sole (and starved) consumer.

## The instrumentation now in prod

PR #239 (squash `eccdab0`, deployed 18:56Z) added:
- a Bolt middleware logging `slack event received: <type>` at INFO for every delivered event;
- `link_shared` receipt logging: "no trip match for [urls]" when nothing matches, "trip unfurl sent for [urls]" on success.

After that deploy, a forced `reaction_added` (via Rob's user token, `#testbois`, 19:01:19Z) produced **zero** log lines. Rob also added reactions manually around 19:02Z; the log read covering those was the interrupted step.

## Next steps, in order

1. **Re-run the interrupted verification.** Render logs 18:59 to 19:04 UTC should contain `slack event received: reaction_added` lines if delivery works. Command below. If lines ARE there, the middleware works and events ARE arriving; re-test a link paste and look for the `link_shared` log lines before anything else.
2. **Sanity-check the middleware locally** so hypothesis "logging is broken" dies cleanly: start dev flask, POST the synthetic event (script below) at `http://127.0.0.1:5001/slack/events`, confirm both the `slack event received: link_shared` line and the unfurl in `#testbois`.
3. **Have Rob open api.slack.com/apps → TCSC → Event Subscriptions** and look for a warning or disabled state. Leading hypothesis: Slack disables event deliveries app-wide after sustained Request URL failures (this app predates its Socket Mode setup and has an HTTP events route). Slack emails app collaborators when it does this; have Rob search email for "event" notices from Slack.
4. **Check whether real-time reaction handling in practices actually works in prod.** `_delegate_reaction_event` in bolt_app.py handles attendance reactions via events. If that is also dead in prod (may be masked by scheduled polling jobs), events have been broken for a long time, which supports hypothesis 3.
5. If the config UI looks healthy: **Slack support ticket**. App `A06FYPU3FTN`, workspace Twin Cities Ski Club. Evidence: subscribed event types not delivered over an established Socket Mode connection, timeline as above.
6. Optional isolation: create a scratch Slack app in the same workspace (socket mode + link_shared + tcsc.ski unfurl domain), run a listener, paste a link. Distinguishes app-specific wedging from anything workspace-wide. (An asset-management test app was planned anyway; see memory.)

## Access and tooling

- **Render API**: key is stored in `/home/node/.claude.json` as the `Authorization: Bearer` header of the `render` MCP server (registered; tools appear after a session restart, but plain REST works now). Service `srv-csgsnvbqf0us739q2kpg` (tcsc-registration), owner `tea-csp5uhjgbbvc73fpnge0`.

  ```bash
  RKEY=$(grep -o '"Authorization": *"Bearer [^"]*"' /home/node/.claude.json | head -1 | sed 's/.*Bearer //;s/"//')
  curl -s -H "Authorization: Bearer $RKEY" "https://api.render.com/v1/logs?ownerId=tea-csp5uhjgbbvc73fpnge0&resource=srv-csgsnvbqf0us739q2kpg&startTime=2026-08-20T18:59:00Z&endTime=2026-08-20T19:04:00Z&limit=100"
  ```

- **Slack tokens** in `/workspace/tcsc-trips/.env`: `SLACK_BOT_TOKEN` (bot), `SLACK_USER_TOKEN` (Rob's user, has `admin`, used for posting/reacting as a human-ish actor and for `team.integrationLogs`), `SLACK_APP_TOKEN` (socket), `SLACK_SIGNING_SECRET` (signs synthetic events).
- **Prod DB, read access works from this box**: `PROD_DATABASE_URL` in `.env`.
- **Test channel**: `#testbois`, id `C07G9RTMRT3`, private, bot and Rob are members.
- **Dev quirks**: `localhost:5432` needs the pgforward relay (memory note `pgforward-safe-relay`; a clean-half-close implementation is required or Postgres kills backends). `./run-tests.sh` is the canonical test runner. Start the forwarder detached with `setsid` or the harness reaps it.

- **Synthetic signed event script** (proves the HTTP intake path and, locally, the middleware):

  ```python
  import os, time, json, hmac, hashlib, urllib.request
  body = json.dumps({
      "token": "synthetic", "team_id": "T000", "api_app_id": "A000",
      "type": "event_callback", "event_id": "EvSyn", "event_time": int(time.time()),
      "event": {"type": "link_shared", "channel": "C07G9RTMRT3",
                "user": "U02JS0R7ZG8", "message_ts": "<ts of a real message>",
                "source": "conversations_history",
                "links": [{"domain": "tcsc.ski", "url": "https://tcsc.ski/cuyuna"}]},
  }).encode()
  now = str(int(time.time()))
  sig = "v0=" + hmac.new(os.environ["SLACK_SIGNING_SECRET"].encode(),
                         f"v0:{now}:".encode() + body, hashlib.sha256).hexdigest()
  req = urllib.request.Request("https://tcsc.ski/slack/events", data=body, headers={
      "Content-Type": "application/json",
      "X-Slack-Request-Timestamp": now, "X-Slack-Signature": sig})
  print(urllib.request.urlopen(req, timeout=30).status)
  ```

  Note: Slack never fires `link_shared` for links posted by the app itself (both bot and user token posts count as the app). Only a human paste from a Slack client is a valid organic test.

## Residual state a new debugger should know

- `#testbois`: Rob's cuyuna message (`ts 1787228909.010599`) carries a card that was attached MANUALLY via `chat_unfurl`, not organically. Rob's birkie paste (`ts 1787251841.880729`) has probe reactions on it (`:ski:` from the script, more from Rob).
- Dev DB test artifacts (harmless, delete when wanted): user `robrutscher@gmail.com` (id 6432) linked to Rob's Slack id `U02JS0R7ZG8`, series `test-trip-manual-verify`, registration 794 (confirmed, $10 test-mode charge captured).
- All 8 prod `trip_series` rows have `slack_channel_name` set; the bot is a member of all 8 channels. Registration DMs and the payment lifecycle were verified live earlier today (dev, real Stripe test mode + real Slack DMs).
- Slack app manifest is in the conversation transcript of session `1fff13b8` (this one) if needed again; Rob can re-export it from the App Manifest tab.

## RESOLVED: root cause found 2026-08-20 ~19:3x UTC (follow-up session)

Step 1 re-ran clean: Render logs 18:59-19:04 UTC contain zero
`slack event received:` lines (only a port-detection line at 19:00:51 and a
favicon GET from Rob's phone Slack client). Events confirmed not arriving.

Step 3's hypothesis was correct, confirmed via Rob's Gmail: two emails from
developers@slack.com, subject **"Events were disabled for your app"**, dated
**2025-12-21** (still unread) and **2026-05-12**:

> Something's not working with TCSC, so we've temporarily stopped sending
> events to it. Try logging in to see what the issue is. Once you've fixed
> the issue with your app, turn on the Enable Events setting.

So Slack disabled event delivery app-wide, and the disabled flag survives
reinstalls (the 11:54Z/12:03Z reinstalls changed nothing, as observed).
Events have been dead since at least 2025-12-21, which also answers step 4:
real-time reaction handling has been broken for ~8 months, masked by the
polling jobs.

**Fix (Rob, one click):** log in and turn Events back on at
https://api.slack.com/apps/A06FYPU3FTN/event-subscriptions
(the 2026-05-12 email has a tokenized "Enable Events" button link).

**Verification after the toggle:**
1. Add a reaction in #testbois → Render logs show
   `slack event received: reaction_added`.
2. Hand-paste a tcsc.ski trip link → expect `slack event received: link_shared`
   then `trip unfurl sent for [...]` and the signup card in-channel.

**Watch after re-enable:** Slack disabled this twice, presumably from
sustained Request URL failures before Socket Mode was set up. Socket Mode is
now enabled and prod holds a healthy connection that acks envelopes, so it
should stick — but if a third "Events were disabled" email arrives, look at
whether anything is still failing to ack.

## CLOSED: verified working 2026-08-20 ~19:08 UTC

Rob toggled Enable Events. His fresh birkie paste in #testbois
(ts 1787252887.695829, 19:08:07Z) carries `is_app_unfurl: true` from app
A06FYPU3FTN with our 3-block card — attached ORGANICALLY (the only manual
chat_unfurl remains the older cuyuna message). link_shared → handler →
chat_unfurl works end to end.

Second finding: the PR #239 instrumentation never logged, even for this
handled event. Root cause: nothing in the app or gunicorn sets a log level,
so root sits at WARNING with no handlers, and slack_bolt copies the base
logger's settings onto every listener logger — all the INFO lines were
dropped. (The "Bolt app is running!" banner only appeared because slack_bolt
falls back to print() when its logger won't emit INFO.) Fixed in PR #240 by
passing an INFO base logger with a stdout StreamHandler to App(logger=...).
After #240 deploys, re-verify that a link paste produces
"slack event received: link_shared" and "trip unfurl sent" in Render logs.
