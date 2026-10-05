# Interest list

Date: 2026-10-05. Status: approved in brainstorming, awaiting spec review.

## Goal

People who want to join TCSC can leave their contact details while
registration is closed, and the club contacts them when a window opens.
Joining takes one short form. Admins can view and export the list.

People on this list are not members. Their rows never touch `User` or
anything that reads it (Slack sync, ExpertVoice, lottery, recaps).

## Naming

"Waitlist" already means lottery losers in the admin Users page. This
feature is the **interest list** in code and admin. The public page uses
plainer copy ("Get notified when registration opens").

## Decisions

- Fields: name (one field), email (required), phone (optional).
- A phone comes with SMS consent. The consent line sits under the phone
  field ("We'll text you when registration opens. Reply STOP to opt out.")
  and the route stamps `sms_consent_at` when a phone is saved. Texts to
  this list go through the club's Twilio number, and A2P needs opt-in on
  record.
- The app sends nothing to the list. Admins export it and send messages
  themselves.
- Overlap with members is shown, never written: the admin view and the
  CSV match each row against `User` when they load.
- No bulk clear. Delete is per row.

## Data

New model `InterestSignup`, table `interest_signups`:

| column | type | notes |
|---|---|---|
| `id` | int pk | |
| `name` | string(200), not null | trimmed |
| `email` | string(255), not null, unique | `normalize_email()` |
| `phone_e164` | string(20), null | `normalize_phone_e164()` |
| `sms_consent_at` | datetime, null | UTC; set when a phone is saved, cleared when a resubmit drops the phone |
| `created_at` | datetime, not null | UTC, first signup |

One Alembic migration. Per the events scratch DB memory, a new migration
bumps `HEAD_REVISION` in the practices migration test.

## Write path: `POST tcsc.ski/interest`

The only write. Both forms post here.

- `@csrf.exempt`: the marketing site is another origin and cannot carry
  the app's CSRF token. The route does nothing a forged POST could abuse
  beyond adding a row, which a direct POST could do anyway.
- Honeypot: a hidden `leave_blank` field (named so autofill never fills it). If it is filled, render the thanks
  page and save nothing.
- Validation: name and email required, email must contain `@` and a dot
  after it, a non-empty phone must normalize to E.164. On failure,
  re-render the form page (status 400) with a message and the typed values
  kept.
- Upsert by normalized email: an existing row gets its name, phone and
  consent replaced. A resubmit always shows the same thanks page, so the
  form never reveals whether an address is already on the list.
- Success renders a thanks page on tcsc.ski with a link back to
  `https://twincitiesskiclub.org`. No cross-site redirect.

`GET tcsc.ski/interest` renders the standalone form page. The error
re-render uses the same template.

Field names are the contract between the two forms: `name`, `email`,
`phone`, `leave_blank` (honeypot).

## Marketing site

- New page `site/src/pages/join.astro` on `InnerPageLayout`, using the
  site's Tailwind tokens (navy, mint, paper). Heading, then `datesLine()`
  from `registrationCopy.ts` when season data has dates, then the form.
- The form is plain HTML: `method="post"`, `action` from
  `PUBLIC_INTEREST_URL`, default `https://tcsc.ski/interest`. Browser
  validation (`required`, `type="email"`, `type="tel"`) catches most
  errors before submit. No client JS.
- CTA routing: the coming-soon and closed CTAs go to `/join`. Update
  `site/src/content/pages/home.yaml` (`cta_coming_soon_url`,
  `cta_closed_url`) and the fallback defaults in
  `site/src/components/registrationCta.ts`. The homepage strip's
  coming-soon URL in `index.astro` moves from `#registration` to `/join`.
  The closed label changes from "How to register" to "Get notified".
  `registrationFlip.ts` does not change.

## tcsc.ski

- Partial `app/templates/_interest_form.html`, styled with the existing
  `main.css` card and form classes.
- Included on:
  - the season detail page (`season_detail.html`) when
    `is_registration_open` is false
  - the standalone `interest.html` page served by `GET /interest`
- Not on the tcsc.ski home page (removed 2026-10-05 at Rob's request; the
  home page stays registration-only).
- `interest_thanks.html` for success.

## Admin

- `GET /admin/interest-list`, `@admin_required`, linked from the admin
  sidebar. Rendered with `admin_base.html` and the Tailwind admin styles.
- Table columns: name, email, phone, signed up (Central), member.
- Member column: one query matches all rows against `User` by normalized
  email or `phone_e164`. A match shows that user's `status` (ACTIVE,
  PENDING, ALUMNI, DROPPED). No match is blank.
- `GET /admin/interest-list/export.csv`: every row, same columns plus SMS
  consent time, through the existing CSV-injection sanitizer.
- `POST /admin/interest-list/<id>/delete`: deletes one row, normal admin
  CSRF.

## Code layout

- `app/interest/models.py` holds `InterestSignup`.
- `app/interest/service.py` holds `save_signup(form) -> errors | None`
  and `rows_with_member_status() -> list`.
- `app/routes/interest.py` holds the public GET/POST.
- Admin routes go in `app/routes/admin_interest.py`.

## Testing

- Route: create; upsert on the same email with different case; honeypot
  saves nothing; bad phone re-renders with 400 and keeps values; consent
  stamped with a phone, null without; cross-origin POST without a CSRF
  token succeeds.
- Contract: a test reads the `name` attributes from `site/src/pages/join.astro`
  and asserts they equal the field names the route reads.
- Admin: non-admin gets redirected; member match by email and by phone;
  CSV contains every row and sanitizes a leading `=`; delete removes one
  row.
- Site: `astro check` and `astro build` pass. Screenshot `/join` and the
  tcsc.ski closed home page at 375px.

## Out of scope

- Automatic "registration is open" email or SMS.
- Rate limiting beyond the honeypot. Add it if spam shows up.
- Removing list rows when someone registers. The member column covers it.
