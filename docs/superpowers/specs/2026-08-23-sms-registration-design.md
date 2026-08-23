# SMS-first season registration design

Date: 2026-08-23
Status: implemented on branch sms-registration (2026-08-23)
Scope: season registration only. Trips and events keep their email gates and adopt this layer later. Lottery-result texts are deferred to a fast follow.
Deadline: live before September season registration opens.

## Summary

Season registration becomes phone-first. A member enters their cell number, proves possession with a 6-digit SMS code, and is matched to their record by normalized phone. On a match the wizard prefills from their record. If the phone is not on file, an emailed 6-digit code proves account ownership before any prefill. New members verify their phone, fill a blank form, and on lottery acceptance get an SMS heads-up alongside the Slack invite email. Verification failures degrade to an unverified registration flagged for admin review; registration is never hard-blocked.

This introduces the first verified credential in the product. Returning-vs-new status, pricing, and Stripe capture method are derived server-side from the verified session; the self-declared returning/new radio is removed.

## Data model

`User` gains:

- `phone_e164` — `String(16)`, nullable, indexed, **not unique**. Canonical form `+1XXXXXXXXXX`. Not unique because households share numbers; a shared number must never raise a constraint error.
- `phone_verified_at` — nullable UTC timestamp, set on first successful SMS code for that number.
- `email_verified_at` — nullable UTC timestamp, set on successful emailed code.

The existing `phone` column is untouched (display/legacy). Every write path that accepts a phone (season registration, admin edit) writes both `phone` (as typed) and `phone_e164` (normalized). The admin edit path gains validation it currently lacks. Matching only ever reads `phone_e164`.

`normalize_phone_e164()` in `app/utils.py`: strip non-digits; accept 10 digits or 11 with leading 1; emit `+1XXXXXXXXXX`; else `None`. US-only by design (prod data is 100% NANP).

Migration backfills `phone_e164` from `phone` for all rows (verified against prod 2026-08-23: every non-empty value normalizes cleanly, zero duplicate numbers). Backfill does NOT set `phone_verified_at`; stored numbers were typed, never proven.

New tables:

- `VerificationCode`: id, email, code hash, created_at, expires_at (10 min), attempts, consumed_at. Email codes only; phone codes live in Twilio Verify. Six digits, hashed at rest, max 5 wrong attempts, a new request invalidates prior codes for that email.
- `VerificationAttempt`: minimal log (target, channel, ip, created_at) for rate limiting. No Redis; single instance.

`UserSeason` gains a `needs_review` flag (boolean, default false) for unverified registrations (see Degradation).

`User` gains `sms_opt_out` (boolean, default false), set from Twilio STOP webhooks or admin action.

## Verification service (`app/verify/`)

One module with a narrow interface used by the wizard now and trips/events/auth later.

- Phone: Twilio Verify. `start_verification(phone_e164)` and `check_verification(phone_e164, code)`. Twilio owns generation, storage, expiry, retry limits, fraud protection. We store nothing for phone codes. New Verify service to be created on the TCSC Twilio account (`TWILIO_VERIFY_SERVICE_SID` env var).
- Email: our `VerificationCode` table, delivered by Resend (`RESEND_API_KEY` env var) from `club@tcsc.ski` once the domain verifies. Subject carries the code ("Your TCSC code: 482913") so it is readable from a spam-folder preview.
- Rate limits enforced in our endpoint layer before any provider call: 3 sends per 10 minutes per target, 10 per hour per IP. Provider errors (including Twilio max-attempts) are caught and translated to friendly copy, never surfaced raw.

## Registration flow

Step 0 (new, ahead of the existing 4-step wizard):

1. Single input: "Your cell number." Submit sends the SMS code; the code entry appears on the same screen. The entered number is echoed back with an Edit link. Resend button with a 30-second countdown. One single code input, `inputmode="numeric"`, `autocomplete="one-time-code"`, tolerant of whitespace, not cleared on a wrong code. No six-box widget.
2. On success, server sets `session['verified_identity']` and looks up `phone_e164`:
   - Exactly one match: "Welcome back, [first name]" with a plainly visible "Not [name]?" link (routes to the email step). Wizard steps 1 to 3 prefill from the record. `phone_verified_at` is stamped.
   - Multiple matches (shared number): skip straight to the email step. Copy: each member identifies individually by email. No chooser UI.
   - No match: success framing, not failure framing. "Your number's verified. We just don't have it on file yet (most alumni don't). Enter the email you've used with the club and we'll link you up." Email field inline, pre-focused.
3. Email step: if a `User` exists at that email, a 6-digit code is emailed. Code entry is labeled with channel and masked destination ("the code we emailed to r•••@gmail.com"). On success: prefill, the verified `phone_e164` is attached to the record, both verified timestamps stamped. On an email miss: "No member found under that address. Try another email, or register as new (heads-up: new registrations go through the lottery)." Multiple tries allowed. An explicit "That email doesn't work for me anymore" link routes to the flagged unverified path.
4. No match on either: new member. Blank form, phone already verified.

Escape hatch: "New to TCSC? Start here" is always available, with the warning "(Skied with us before? Use verification. Registering as new puts you in the new-member lottery.)" If a new registrant's typed email collides with an existing `User`, the response offers two exits: use the email verification path, or "Can't get email there anymore? Continue anyway," which proceeds unverified with `needs_review` set. Email stays unique; no silent merging.

Prefill rules:

- Prefill only ever happens behind a verified match (phone match, or email-code match).
- Emergency contact is shown as read-only text with a forced binary: "Still your emergency contact? [Yes, keep] [Update]." All other fields prefill as editable inputs.

Server trust rules:

- The client-claimed status radio is removed. Returning-vs-new, pricing, and capture method (`automatic` vs `manual`) derive server-side from the session's verified identity only. The payment-intent endpoint reads the session, never the form.
- Above the card field, one unmissable line: "You're registering as a returning member. Your card will be charged $X today" vs "You're registering as a new member. We'll place a hold on your card; you're only charged if you get a spot in the lottery." With a "Does this look wrong? Contact us" link.

Session: Flask signed cookie, identity TTL 2 hours, cleared on completion. Wizard state is kept client-side so an expiry mid-form triggers a quick re-verify (one more code) that returns the member exactly where they were, fields intact. Registration next day means re-verifying; once a year, that is one text.

Degradation (never hard-block during the registration window):

- Twilio down or code undeliverable: clear copy pointing to the email path, which is reachable from the stall, not only after a no-match. A de-emphasized "Can't receive texts?" link is permanently available and routes email-first.
- Both channels failed, or the member is unreachable at any email on file: register unverified. Unverified registrations always get `manual` capture (a hold, never a premature charge) and `needs_review`; an admin confirms membership status before any capture or lottery placement. Copy: "We'll confirm your membership status before anything is charged."
- Degraded-mode copy is written now, not at incident time: "Text messages aren't going through right now. This is on us, not you. Continue with email, or register without verification."

Admin additions:

- A pre-lottery review report: registrations flagged `needs_review`, plus "new" registrations whose name and DOB fuzzy-match an existing member (the returning-member-in-the-lottery trap). Reviewed before the lottery runs.

Payment, the Stripe webhook, and the UserSeason creation race are unchanged. The capture-method table in CLAUDE.md still governs.

## Messaging

Complete v1 send list:

1. Verification codes (Twilio Verify for SMS, Resend for email).
2. Registration confirmation SMS after payment success. Returning: "TCSC: You're registered for the 2026-27 season! Your card was charged $150. See you out there. Reply STOP to opt out." New: "TCSC: You're in the lottery for the {season_name} season! Your card has a hold and is only charged if you get a spot. Reply STOP to opt out"
3. Slack invite heads-up when an accepted new member's invite email goes out: "TCSC: Welcome to the club! Your Slack invite just landed in your email. That's where everything happens, so come say hi. Reply STOP to opt out."

Nothing else in v1. No lottery-result texts (fast follow). The Slack invite mechanism itself is unchanged (inviteBulk email), preserving the email-based SlackUser auto-link.

Mechanics:

- Registration texts send through the existing "Practices - TCSC" Messaging Service (`MG1d94fd27cac61678a41e94914c56cccb`): the club's one number can belong to only one service, and the approved A2P campaign (VERIFIED, LOW_VOLUME) is attached to it. Creating a second service would mean a new campaign approval, which takes weeks. Revisit separation if the club ever buys a second number.
- Texts are plain GSM-7, no emoji, one segment each. Templates live in `config/sms.yaml`.
- Twilio handles STOP/START at the carrier level; a webhook records `sms_opt_out` on the User so we stop trying.
- `app/notifications/sms.py`: `send_sms(user, template, **kwargs)` resolves `phone_e164`, checks opt-out, logs, and never raises into the calling flow. A failed confirmation text logs and moves on; it must not fail a registration.
- Email surface stays exactly two things: Stripe's receipt (`receipt_email`, untouched) and the Resend verification code.

## Account setup (outside the repo)

- Twilio: DONE 2026-08-23. Verify service "Twin Cities Ski Club" created (`VAc3db44e72c904154c4892c8c89afc911`, 6-digit codes). Registration texts reuse the existing Messaging Service (see Messaging).
- Resend: DONE 2026-08-23. Domain `tcsc.ski` verified for sending (id 965f61ec-6742-4d3a-9245-17465965f7b9, us-east-1); DNS records added to the club's Cloudflare by Rob; smoke-test email delivered from `club@tcsc.ski`.
- Warm the Resend domain before September: send a handful of real mails to club-controlled inboxes ahead of launch.
- Env vars (dev `.env` done; Render needs them at deploy): `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_MESSAGING_SERVICE_SID`, `RESEND_API_KEY`.

## Testing

Automated (providers mocked):

- `normalize_phone_e164` against the formats observed in prod (bare 10-digit, leading-1 11-digit, +1, dashed, junk, empty).
- Match logic: single phone hit, multi-hit routes to email step, email hit attaches phone, no hit, collision guard with both exits, needs_review path.
- Server-side status/capture derivation from the session, including the unverified case forcing manual capture.
- Migration backfill against messy fixtures.
- Rate limiter and code-attempt exhaustion.

Live dry run in dev (Stripe CLI, real texts to Rob's cell 612-867-7165):

1. Phone-matched returning member: prefill, payment line, charge, confirmation text.
2. Phone removed from file: email fallback with a real Resend code.
3. New member with a test identity: lottery hold, then the Slack-invite heads-up text on acceptance.
4. Failure drills: wrong codes, resend countdown, rate limiter, degraded copy.

## Rollout

Normal PR; Render auto-deploys on merge; migration and backfill run in the release phase. Prereqs before merge: Cloudflare DNS records added and Resend verified, Twilio Verify and Messaging services created, Render env vars set. The old email-gate endpoint stays in place until the new flow survives its first real week, so reverting is a template switch, not a migration rollback.

## Out of scope (explicitly)

Member accounts/login and persistent sessions; lottery-result texts; RCS (a later Twilio Messaging Service upgrade, no design dependency); trips/events adoption of the verify layer; international numbers; voice-call code delivery.
