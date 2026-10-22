# Trip scholarships: one-time code delivered by Slack DM

Date: 2026-10-22. Ships today. Hayward Training Trip registration closes
Fri 2026-10-23 07:00 Central (`signup_end` 12:00 UTC), and Mitchell told the
team on 10-19 that scholarship recipients would hear how to use it before
then.

## Why

The board funded a Trip Scholarship Program from sponsor money (Twin Cities
Orthopedics, Kwik Trip): members who signed up on Mitchell's Google Form get
up to $100 off one trip this season. 13 people signed up, so each gets the
full $100. Rob and Mitchell agreed (DM, 10-19) on a one-time code of a set
amount, delivered as a DM from the TCSC Slack app in place of a BCC email.

The DM has a "Get my code" button. The code shows only after the click, so a
click is proof the member opened the message. Mitchell sees who has and
hasn't clicked.

## Goals

- Mitchell picks the recipients on an admin page and sends. Nobody else
  handles the list.
- Each recipient gets a DM from the TCSC app with a button. Clicking reveals
  their code in that same message, where it stays.
- The member types the code on any trip registration form and the hold is
  $100 less, on either price tier.
- The code works only for the member it was issued to.
- A lottery loss gives the code back. It is spent only when the trip payment
  is captured.
- Mitchell can see, per recipient: sent, clicked, and where the code is held
  or was used.

## Non-goals

- Replacing Mitchell's Google Form for scholarship signup.
- Automatic reminders for people who haven't clicked.
- Expiry. A code stays good until it is used.
- Scholarships on events or season registration.
- The board's $30-off-every-trip subsidy. Mitchell already set it in trip
  prices.

## Anti-goals

- A member charged the full price after entering a valid code, or charged the
  discounted price twice (two trips) from one scholarship.
- A member losing their scholarship because they lost a lottery.
- The browser deciding the discount. The server computes the amount, like
  every other price in this app.
- Changing capture behavior. Trips stay `capture_method='manual'`.

## Design (decided)

### Data

New table `trip_scholarships`:

- `id`, `user_id` (FK users, not null), `season_id` (FK seasons, the current
  season at send time), `amount_cents` (default 10000), `code` (unique,
  stored uppercase), `sent_at`, `claimed_at` (button clicked),
  `slack_channel_id` + `slack_message_ts` (the DM, for updating it),
  `created_at`.
- Unique on (`user_id`, `season_id`): one scholarship per member per season.

New nullable column `trip_registrations.scholarship_id` (FK
trip_scholarships).

The scholarship's state is derived from registrations that point at it,
never stored:

- used: a linked registration is `confirmed`
- held: a linked registration is `pending`, or `pending_payment` inside the
  existing `PENDING_HOLD_WINDOW`
- available: neither

Because registration status already moves to `cancelled` when a hold is
released (lottery loss, admin release, stale sweep), a lost lottery frees the
code with no new code paths in webhooks or capture.

Migration: one revision. Bump `HEAD_REVISION` in
`tests/practices/test_practice_migration_release.py`.

### Code format

`TCSC-` plus 6 characters from an unambiguous alphabet (no 0/O/1/I/L), for
example `TCSC-7KQ2M9`. Input is matched case-insensitively, ignoring
surrounding whitespace.

### Registration

`create_registration` (app/trips/service.py) accepts an optional
`scholarship_code` in the payload:

- Blank: no discount, and `registration.scholarship_id` is cleared. A reused
  row from an earlier attempt must not keep a stale link.
- Code not found, or found but issued to a different user than the email
  resolves to: field error on `scholarship_code`, "That code doesn't match
  this member." One message for both cases.
- Code held or used by a registration on a different trip: field error,
  "This code is already in use on <trip name>." A held code on the same
  trip's reused row is fine.
- Otherwise: `amount_cents = max(tier_price - scholarship.amount_cents, 50)`
  (Stripe's minimum) and `registration.scholarship_id` is set.

`register_for_trip` (app/routes/trips.py, where the PaymentIntent is
created) adds `scholarship_id` to the intent metadata. The intent amount
already comes from `registration.amount_cents`. Webhooks and capture don't
change for new registrations.

Form (`templates/trips/register.html`, `static/trip_registration.js`): one
optional text field "Scholarship code" near the price tiers. The field is on
every trip's form, not gated per member. The client sends it as
`scholarship_code` and renders server field errors like the other fields. The
hold summary after submit already uses the server's `amountCents`.

### Sending (admin)

New admin page `/admin/trips/scholarships`, linked from the admin trips list.
Admin-only like the rest of `/admin/trips`.

- A member search (active members only, by name or email, since trip
  registration accepts only active members) to build the list, plus an
  amount field defaulting to $100.
- "Send" creates a scholarship per member (skipping anyone who already has
  one this season) and posts the DM. A member with no linked Slack account
  gets the row but is reported "not sent: no Slack account" so Mitchell can
  give them the code himself.
- A table of every scholarship this season: member, code, sent, clicked
  (time), state (available / held on Trip / used on Trip).
- A "Resend DM" action per row for a failed or missing send. It posts a new
  DM and stores the new message reference.

The code is visible to admins on this page. That is the fallback for members
without Slack and for "I deleted the DM" questions.

### The DM

Sent with the app's bot token (`get_slack_client()`), same as trip
confirmation DMs. Blocks live with the other trip blocks in
`app/slack/blocks/trips.py`.

Before the click:

> Hi {first_name}, you're getting a TCSC trip scholarship: ${amount} off one
> trip this season, thanks to our sponsors Twin Cities Orthopedics and Kwik
> Trip. Tap the button to get your code. Questions? Ask @Mitchell.
>
> [Get my code]

After the click, the same message is updated in place (button removed):

> Your code: *TCSC-7KQ2M9*
> Enter it in the Scholarship code box when you register for a trip at
> tcsc.ski. It takes ${amount} off either price and only works for you. If
> you aren't picked in a trip lottery, the code comes back for another trip.
>
> Open now: <Hayward Training Trip> (registration closes Fri Oct 23, 7:00am)

The "open now" line lists trips whose registration is open at click time
(active status, inside the signup window), with each trip's register link and
close time in Central. If none are open it is omitted.

The Mitchell mention is a constant Slack user ID (`U045LF8PCSW`) in the
scholarship module.

### The button handler

A Bolt action `trip_scholarship_reveal` registered in `app/slack/bolt_app.py`,
value = scholarship id. It acks, checks that the clicking Slack user is the
scholarship's member (otherwise it does nothing and logs), sets `claimed_at`
if it is empty, and `chat_update`s the message to the revealed form. A second
click re-renders the same thing.

## Recipients already registered (Mira Tomten, Katherine Koehler)

Two recipients already hold Hayward registrations (prod, 10-22): Mira Tomten
($110 hold) and Katherine Koehler. The form refuses a second registration on
the same trip, so they can't enter the code themselves.

- After send, a one-off script takes a list of registration ids and links
  each to its member's scholarship (`scholarship_id`), so the code shows as
  held/used and can't be spent on a second trip. It leaves `amount_cents`
  alone so the record matches the Stripe intent. It refuses a registration whose member has no
  scholarship or whose scholarship is already held elsewhere. Prod one-offs
  follow the existing rule: `TCSC_MIGRATION_ONLY=1`, no `SLACK_APP_TOKEN`.
- The reveal message checks for a held registration first. If there is one,
  it says "Already applied to <trip>: we'll take ${amount} off when your spot
  is confirmed." in place of the "enter it on the form" line.
- Money: Rob refunds $100 to each in the Stripe dashboard after the Hayward
  roster is captured (Rob's decision, 10-22). No capture code changes. Trips
  have two capture paths (single `/admin/payments/<id>/capture` and
  `/admin/payments/bulk-capture`), and neither is touched.

## Left to the builder

- Admin page layout and styling (follow the existing `admin_*.js` pattern and
  the admin trips pages).
- Member search implementation (an existing admin user search can be reused).
- Hold-summary wording on the form when a code is typed, as long as the
  client never computes the final amount.
- Test layout. Cover: code match/mismatch, wrong user, already in use on
  another trip, freed after cancel, reused row clears a stale link, the
  Stripe amount, the reveal handler's user check and idempotence, and the
  admin send skipping existing recipients.

## Rollout today

1. PR, review, merge. Render deploys main.
2. Migration runs in the release phase.
3. Mitchell opens `/admin/trips/scholarships`, adds the 13 names and sends.
   Prod names differ for three: Bradley Waldorf, JOSHUA KLINE, Katherine
   Koehler. Erin Arntson is the ACTIVE account erin.arntson@gmail.com (an
   ALUMNI duplicate exists). All 13 are ACTIVE with linked Slack accounts.
4. Claude runs the already-registered one-off for Mira and Katherine.
5. After Mitchell captures the Hayward roster, Rob refunds $100 each to Mira
   and Katherine in Stripe.
6. Watch the clicked column tonight and tell Mitchell who hasn't opened it.
