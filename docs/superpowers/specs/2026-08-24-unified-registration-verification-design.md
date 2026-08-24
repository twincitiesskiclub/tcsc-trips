# Unified season registration: everyone verifies by SMS

**Date:** 2026-08-24
**Status:** Approved, ready for planning
**Supersedes parts of:** `2026-08-23-sms-registration-design.md`

## Problem

PR #241 put a phone-verification step in front of season registration, but
left new members an unconditional way around it. The "New to TCSC? Start
here." link (`verify-skip-link`) drops straight into the wizard with no code
sent, so a whole class of registrants arrives unverified by design.

That costs three things:

1. **Two experiences.** Returning members get a verified, prefilled flow. New
   members get a bare form, which is the club's first impression.
2. **Unverifiable data.** Unverified rows land with `needs_review` set and a
   phone number nobody confirmed, so the admin review page carries volume it
   should not have to.
3. **Late failure.** Member type is only resolved at the payment step, so
   someone can fill the whole form and get rejected because their window is
   not open yet.

Consolidating on one phone-first flow fixes all three.

## Decisions

Made during brainstorming, 2026-08-24.

**Phone is the identity proof.** A verified phone that matches exactly one
account is that person. No email code is required to confirm it, and whatever
email they type in the form becomes their email.

**No match on phone means continue, not stop.** A verified phone matching zero
accounts drops into the wizard. Email correlation happens inside the form, not
as a gate in front of it.

**Two strikes and you are new.** Phone matched nothing and the typed email
matched nothing, so they are a new member. No further questions.

**A matched email forces the returning flow.** If the typed email belongs to an
existing account, they verify it with a code and register as that member. There
is no "continue as new anyway" option for someone we have identified.

**Shared numbers still use email.** A phone matching 2+ accounts cannot say
which household member is registering, so the email code stays for that case. No
name chooser.

**Closed windows are told early, with an offer.** Verification resolves member
type before the form renders, so a member type whose window is not open sees the
opening date and can opt into a reminder text.

**Already-registered stops at verification.** No form, no second payment path.

## Approach: one server-side resolver

The branch logic moves out of `app/static/script.js` and into a single Python
function. The client stops deciding and starts rendering verdicts.

The reasoning is about where failures surface. A bug in a client state machine
shows up in a member's browser at noon on opening day, reported as "the site did
something weird," with no stack trace. A bug in a server resolver shows up as a
pytest failure before merge. The repo already tests this way: 13 files in
`tests/registration/`, 8 jsdom tests in total.

It is also the same move already made deliberately for `registrationState.ts`,
where the rule lives in exactly one place with a documented ban on a second
copy.

### Scope discipline

This is one function returning one dict, called by one endpoint. Roughly 120
lines including the docstring. No state-machine library, no versioned API, no
table persisting flow state, no enum hierarchy. If it outgrows one screen, that
is a signal something is wrong, not a signal to add structure.

### Rejected alternatives

**Thicken the client state machine.** Smallest diff, no new endpoint. Rejected
because the rule would spread across `checkPhoneCode`, `checkEmailCode`,
`enterWizard`, and the resume-after-refresh IIFE in a file already at 1042
lines, testable only in jsdom.

**Server-rendered multi-step with POST/redirect per step.** Kills the JS state
machine and makes each step bookmarkable. Rejected as a rewrite of a working
page, and it would lose the sessionStorage answer preservation that keeps people
from retyping a form after a session dies.

## The resolver

```python
def resolve_registration_step(identity, season, now, invite_payload=None):
    """Given a verified-identity session (or None), return (outcome, context)."""
```

Lives in `app/seasons/resolution.py`, alongside `selection.py`, which is already
where a "which thing applies right now" rule lives.

It recomputes the phone match from `User.get_by_phone()` rather than caching a
match count in the session, so it is stateless and a page refresh cannot
disagree with itself.

### Outcomes, in precedence order

| # | Outcome | Condition |
|---|---|---|
| 1 | `verify_phone` | No identity, or the 2-hour TTL expired |
| 2 | `need_email` | Phone verified, matches 2+ accounts, none resolved yet |
| 3 | `already_registered` | Resolved user has ACTIVE or PENDING_LOTTERY for this season |
| 4 | `window_not_yet_open` | The resolved member type's window has not started |
| 5 | `window_ended` | That window has already closed |
| 6 | `wizard_returning` | Resolved, `is_returning`, window open |
| 7 | `wizard_new` | Everything else with an open window |

Order carries meaning:

- **Already-registered beats closed-window.** "You're already in" is more useful
  than "you're too late."
- **A resolved user who is not `is_returning`** (registered last year, lost the
  lottery) lands on `wizard_new` with their prefill intact. This matches what
  `registration.py` already computes today.
- **Not-yet-open and already-ended are separate outcomes** because only one of
  them has a next step. A reminder text makes sense for a window that has not
  started. A window that has ended needs a human, so that screen points at an
  organizer and a late-link invite.

### Late-link invites bypass the window gate

`app/late_link.py` issues signed `(season_id, email)` tokens so an admin can let
someone register after their window closes. `season_register` and
`create_season_payment_intent` both honor them today, so the resolver has to as
well or the resolver would slam a door the rest of the app holds open.

A valid invite for this season suppresses outcomes 4 and 5. The email inside the
token is still checked at POST time exactly as it is now, because the resolver
runs before the email field has been filled in.

### Context payload

Each outcome carries only what its screen renders: `firstName` and the prefill
dict for the wizard outcomes, `member_type` and `opens_at` for
`window_not_yet_open`, `member_type` and `closed_at` for `window_ended`,
`season_name` plus charged-or-held for `already_registered`.

## Flow

```
enter phone -> SMS code -> verified
   |
   +- matches 0 accounts ---------------> wizard_new
   |                                       (email correlation happens IN the form)
   +- matches 1 account ----------------> resolve -> already_registered
   |                                              /  window_not_yet_open
   |                                              /  wizard_returning
   |                                              /  wizard_new
   |      \- "Not [name]?" -------------> need_email
   |
   +- matches 2+ accounts --------------> need_email -> code -> re-resolve
```

The re-resolve after an email link is the payoff. Someone who entered as new and
turned out to be returning can land on `already_registered` or a closed window
with no special-casing, because it is the same function answering again.

## In-wizard email correlation

The email field in section 1 checks on blur. What happens next depends on
whether a phone already resolved them.

**Phone resolved them (`user_id` set).** A free email is simply set on the
account. No code, no friction. That is the phone-is-primary rule.

The one case that still errors: the typed email belongs to a *different*
account. Moving Sam's address onto Jane's row would break Sam, so this keeps
today's rejection.

**Phone matched nothing (`user_id` is None).** A typed email hitting an existing
account forces the link. A panel appears, they request a code, they verify, and
the resolver runs again. No decline.

The blur only detects. It does not auto-send, so a typo does not burn an email.

**Security note.** `/api/verify/email/start` deliberately records a rate-limit
attempt even on a miss, so an unlimited stream of probes against different
addresses still gets capped per IP. The blur-time existence check must carry the
same guard or it reopens an email-enumeration oracle.

## Escape hatches

Verification is mandatory, but registration never hard-blocks. Two links
survive, both routing to unverified + `needs_review` + manual capture:

- **"Can't receive texts?"** on the phone step. Landlines, VOIP, and
  international numbers exist.
- **"Can't reach that inbox?"** on the email step. Read as covering someone who
  genuinely cannot reach an address, not as an opt-out for a known former member
  choosing the new-member lottery.

`verify-skip-link` is deleted. That deletion is the consolidation.

## Data model

### `UserSeason.review_note`

Nullable `String(255)`. `needs_review` tells the admin page that something is
off; this says what. "claims Jane R. (id 412), couldn't verify email" beats a
bare checkbox. Additive migration, backfills to NULL.

### `needs_review` after this change

| Path | Flagged | `review_note` |
|---|---|---|
| Verified phone, no match, new member | no | |
| Verified phone, one match, returning | no | |
| Verified phone, multi-match, email code passed | no | |
| "Not [name]?" then email code passed | no | |
| "Not [name]?" then no email match, continues as new | yes | shared number with `<name>` |
| Email matched an account, mailbox unreachable | yes | claims `<name>` (id N), email unverified |
| "Can't receive texts?" | yes | no verified phone |

Volume should drop sharply. Today every new member can arrive
unflagged-but-unverified through the skip link. After this, the only unflagged
registrations are ones where a real code came back.

Flagging the "Not [name]? then new" case is a judgment call. Shared-number
situations are what the review page exists for, and the flag is advisory rather
than blocking.

## Payment and capture

Both changes in `create_season_payment_intent`, `app/routes/payments.py`.

**Drop the email-mismatch demotion** (lines 675-676). Today a verified returning
member whose typed email differs from the account's is demoted to `manual`
capture. Under the phone-is-primary rule that demotion is wrong, and it is the
direct cause of the stuck `requires_capture` rows noted at launch. They get
`automatic` capture like any other returning member.

**That guard was doing double duty, and the second job needs a replacement.**
Besides catching email edits, the email comparison was the only thing at the
payment layer that noticed a disclaimed identity. "Not [name]?" makes no server
call today, so the session keeps pointing at the account the registrant just
said they are not, and `/create-season-payment-intent` receives only
`season_id`, `email`, `name` and `invite`. It has no disclaim signal of its own.

Without a replacement, this is the failure: B verifies a household number that
resolves to spouse A, a returning member. B clicks "Not A?", takes the
can't-reach-that-inbox hatch, and registers. The intent is built from A's
identity, so B gets `automatic` capture and an immediate full charge, when B is
a new member who belongs on a manual hold until the lottery runs. If the
returning window is open and the new window is not, the intent passes the gate
as returning and the form POST then rejects B, leaving a captured charge with
no registration behind it.

**So disclaiming becomes a server-side act.** `POST /api/verify/disclaim` sets
`user_id` to `None` in the session identity, keeping `phone_e164` because the
phone genuinely was verified. The "Not [name]?" handler calls it before showing
the email step. Every downstream reader, the resolver, the registration POST,
and the payment route, then sees an identity that matches what the registrant
actually claimed. The Task 6 scrub stays as a second line of defense.

**The webhook has to read `user_id`.** Adding it to metadata is pointless while
`webhook_received` matches on email alone. On its RETURNING branch it creates
`User(status=ACTIVE)` plus an ACTIVE `UserSeason` outright, which mints a
membership that never went through the lottery. The webhook prefers
`metadata['user_id']` and falls back to email only when it is empty.

**And the email edit has to actually happen.** `user_fields` in
`registration.py` carries no `email` key, so an existing user's row keeps its
old address no matter what was typed. The rule that a resolved member may change
their email was never implemented. It is implemented here: assign the typed
email onto a resolved user's row, still rejecting an address that belongs to a
different account.

**Put `user_id` in the intent metadata.** Fast-follow #1 from the PR #241
launch. The webhook matches on email today, so a verified member typing a new
address can produce a duplicate stub `User`. This change makes email-changing
more common, not less, so the fix belongs here.

**Delete the `status` shim.** Fast-follow #5. Four lines in
`validate_registration_form` (`app/utils.py:253-256`) plus the `validation_form`
copy in `registration.py`. Nothing has submitted a status radio since PR #241.

The capture-method table in CLAUDE.md is unchanged. New members and unverified
registrations still get `manual`; returning members still get `automatic`. Only
the path to being classified returning changes.

## Copy standard

Applies to every member-facing string in this flow.

**Limits.** Headline 6 words or fewer. Body 2 sentences, 25 words. A screen
needing more is doing two jobs.

**Voice.** Second person, active, present tense. "We texted you a code," never
"A code has been sent." Buttons are verbs: "Text me a code," not "Continue."

**Never blame the member.** "That code didn't match," not "You entered an
invalid code." When it breaks on our end, say so.

**Money in plain words, once.** Every screen touching a card says what happens
to it, in the fewest words that are still true.

**No em dashes.** Periods and commas.

### Screens this change creates

| Screen | Copy |
|---|---|
| `wizard_new` | **Number verified.** Let's get you signed up. |
| `window_not_yet_open` | **New member registration opens Thu, Aug 28 at noon.** `[ Text me when it opens ]` |
| `window_ended` | **New member registration closed Sep 4.** Text an organizer and we'll see what we can do. |
| `already_registered` | **You're already registered for 2026 Fall/Winter.** Your card has a hold. We charge it only if you get a lottery spot. |
| `need_email` | **More than one member shares this number.** Enter the email you use with the club. |
| Email collision | **We found your account.** Verify this email and we'll pull your info in. |

### Existing strings tightened

The unverified notice runs 34 words today:

> You're continuing without a verified match, so you'll be registered as a new
> member and entered in the new-member lottery. An organizer will review your
> registration and link any membership history.

Becomes:

> You'll register as a new member and join the lottery. An organizer will check
> for past membership.

Every string in `season_register.html` and the verify-step branch of `script.js`
gets the same pass.

## Phase 2: reminder text

Separable. Phase 1 ships without it, and `window_not_yet_open` renders no button
until this lands.

**`RegistrationReminder`** table: `phone_e164`, `season_id`, `member_type`,
`created_at`, `sent_at`. Unique on `(phone_e164, season_id, member_type)` so a
double-tap cannot double-text. No user row required, which is the point. The
people signing up for these mostly do not have one yet.

**Cron sweep** every 5 minutes in `app/scheduler.py`: find unsent rows whose
window is now open, send, stamp `sent_at`. Cron rather than one-shot timers
because that is the pattern every other job uses and it survives a restart.

**New template** in `config/sms.yaml`, carrying the standard "Reply STOP to opt
out" suffix.

**Admin surfacing:** a waiting count on the season admin page, so the number of
people arriving at open is known in advance.

## Testing

The resolver is the test surface. One pytest per outcome, plus the precedence
pairs that actually bite:

- Already-registered and closed window at once
- Multi-match where one household member has already registered
- A new member who links an email and lands on a closed returning window
- An expired identity mid-wizard

Route tests cover the endpoint's expired-session case. jsdom stays thin, because
the client no longer decides anything.

## Files

**New**
- `app/seasons/resolution.py`
- Migration for `UserSeason.review_note`
- Phase 2: migration for `RegistrationReminder`

**Changed**
- `app/routes/verify.py` (resolve endpoint, blur-time email check)
- `app/routes/registration.py` (POST calls the same resolver; drop the inline
  identity logic and the status shim)
- `app/routes/payments.py` (drop demotion, add `user_id` metadata)
- `app/utils.py` (drop the status validation)
- `app/templates/season_register.html` (delete skip link, add outcome panels)
- `app/static/script.js` (render verdicts, delete branch logic)
- `tests/registration/`

## Sequencing

1. Resolver plus tests, no UI change. Pure addition, nothing breaks.
2. Endpoint, and `script.js` switched to rendering verdicts.
3. Delete `verify-skip-link`, add the new outcome panels, copy pass.
4. Payment and capture changes.
5. Phase 2: reminder table, cron, template, admin count.

Steps 1 through 4 are one shippable change. Step 5 follows.
