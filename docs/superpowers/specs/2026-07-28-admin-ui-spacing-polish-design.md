# Admin UI Spacing & Padding Polish

**Date:** 2026-07-28
**Status:** Approved design, pending implementation plan

## Problem

The admin interface has accumulated spacing drift. Fields sit too close together or
visually overlap across many panes — most noticeably on editable surfaces (drawers,
modals, inline editors). No single pane is broken enough to have been fixed on its
own, but the aggregate reads as sloppy.

The root cause is that there is no spacing scale. `app/static/css/admin_ui.css`
uses ad-hoc pixel values (`padding: 16px 20px`, `gap: 9px`, `margin-bottom: 6px`,
`font-size: 13.5px`), and the ~330KB of `admin_*.js` files each hand-roll their own
markup with their own inline Tailwind spacing utilities. Two files' versions of the
same conceptual component — a form row, a drawer section — disagree by a few pixels.
That disagreement is the bug.

## Goal

Polish, not redesign. Every pane should feel deliberately spaced. A reviewer
comparing before and after on any single element should mostly see a 1–3px shift;
the improvement is in the aggregate consistency.

### Explicit non-goals

- No color changes.
- No type-scale changes.
- No layout restructuring — nothing moves to a different place on the page.
- No new components or features.

If a spacing fix appears to require moving an element, that gets flagged for the
user rather than done.

## Constraints

- **Nothing may be sent outbound.** No Slack messages, no Stripe calls, no email.
  The admin UI has buttons that trigger real member-facing sends.
- **Deploys go through PRs.** Render auto-deploys every commit on `main`, so a
  direct push is an unreviewed deploy.
- **No production credentials.** Verification is local-only.
- **No PII copied to the dev box.** Production may be read for aggregate shape only.

## Architecture

Five phases. Phases 1–3 produce evidence; phases 4–5 act on it.

```
Phase 1  Data shape survey  ──►  synthetic seed matching prod density
Phase 2  Safe capture harness ─►  authenticated, outbound-sealed screenshot runner
Phase 3  Audit               ──►  findings inventory (surface, element, issue, severity)
Phase 4  Fix                 ──►  spacing scale + component pass, per surface group
Phase 5  Verify              ──►  re-capture, diff, test, PR per surface group
```

---

## Phase 1 — Realistic data without PII

### 1a. Survey production, read-only, aggregates only

`PROD_DATABASE_URL` is reachable from the dev container (verified: 266 users). No
IP allowlist change is required.

The survey extracts *shape*, never rows:

- `max(length(...))` and p95 length for every text field surfaced in admin —
  names, emails, Slack handles, trip/event titles, notes, tag labels
- tag-count-per-user distribution
- row counts per table
- enum value distributions (`User.status`, `UserSeason.status`, payment states)

Nothing identifying is read or written to disk. Output is a small JSON stats file.

### 1b. Generate a synthetic fixture

`scripts/seed_ui_fixtures.py` builds a fake club at production's measured density —
~266 users with matching season, payment, practice, and event volume — with p95-
and max-length values deliberately distributed through it.

This density is load-bearing. A field only overlaps its neighbour when someone has
a 34-character name or six role tags; a generic seed of "Jane Smith" rows would
render a clean UI and surface none of the reported problems.

The seed is deterministic (fixed random seed) and re-runnable, so it also serves as
a reusable fixture for future admin UI work.

---

## Phase 2 — Safe capture harness

### Outbound safety: four independent layers

1. **Isolated worktree and env.** Work happens in a `ui-polish` git worktree with
   its own `.env.uiaudit`. The real `.env` is never loaded, so the real
   `SLACK_BOT_TOKEN`, `SLACK_ADMIN_TOKEN`, and `STRIPE_SECRET_KEY` are not present
   in the process at all.
2. **No background workers.** `TCSC_MIGRATION_ONLY=1` skips `init_scheduler()`
   (`app/__init__.py:91`), disabling APScheduler and the Slack Socket Mode listener.
   Nothing can fire on a timer during a capture run.
3. **Import-time outbound guard.** A module monkeypatches
   `slack_sdk.WebClient.api_call`, the Stripe HTTP client, and `smtplib` to raise
   immediately. Any code path attempting outbound traffic fails loudly rather than
   succeeding quietly.
4. **Browser-level interception.** The Playwright context aborts every non-GET
   request at the network layer. A misfired click cannot produce a POST that leaves
   the browser.

Layers 3 and 4 are the real guarantees; 1 and 2 mean an escape would require being
unlucky twice first.

### Authentication

`admin_required` (`app/auth.py:34`) is Google OAuth gated on email domain — it
checks only that `session['user']['email']` ends with `@twincitiesskiclub.org`.
There is no admin user record to seed and no password.

Flask sessions are `itsdangerous`-signed with `SECRET_KEY`, which is controlled
locally via `.env.uiaudit`. The harness therefore **mints a valid session cookie
offline** containing `{'user': {'email': 'ui-audit@twincitiesskiclub.org'}}` and
injects it with Playwright's `addCookies()`.

This deliberately avoids adding a dev-login route to the application. A backdoor
route, however well guarded by an environment check, is app code that can ship to
production. An offline-signed cookie cannot.

### Capture

A Node Playwright runner (Playwright 1.62 and Chromium are already installed)
drives a **declarative manifest**: each entry is a route plus a list of states to
reveal, where a state is a selector to click or a snippet to evaluate.

The manifest is deliberate rather than crawled, so it is auditable — the exact set
of interactions is reviewable as a list. Openers only; nothing matching
submit/save/delete/run/send is ever clicked, and layer 4 backstops that rule.

Output goes to a git-ignored `.ui-audit/<date>/` directory.

**Coverage:** ~22 admin page routes × 3 viewports (1440 / 1024 / 390), plus every
drawer, modal, inline editor, expanded row, filter panel, and tab. Roughly 250–300
captures.

`tailwind-output.css` is currently 0 bytes in the working tree (build output is not
committed), so `npm run tailwind:build` is a prerequisite for the admin UI to render
at all locally.

---

## Phase 3 — Audit

Every capture is reviewed and reduced to a findings inventory: surface, element,
issue, severity.

Codex (`gpt-5.6-sol` at `model_reasoning_effort=max`) assists via
`codex exec -i <screenshots>` with the relevant markup attached, used for the dense
surfaces where the correct fix is not evident from the diff alone, and for proposing
the spacing scale itself. All Codex output is reviewed before it lands; it does not
run unattended.

---

## Phase 4 — Fix

### Layer A: spacing scale

Define CSS custom properties in `admin_ui.css` — `--admin-space-1` through `-6`
(4/8/12/16/24/32) plus semantic aliases (`--admin-field-gap`,
`--admin-section-gap`, `--admin-drawer-pad`) — and snap every existing value to the
nearest step.

Individually invisible; in aggregate this is what stops the interface reading as
sloppy, and it prevents the drift from recurring.

### Layer B: component pass

The four patterns the JS files repeatedly hand-roll — form row, drawer section,
field group, button row — become shared classes. This is where actual overlaps get
resolved, since an overlap is typically one file's field-group having a smaller
bottom margin than another's.

### Surface groups

These are also the PR boundaries:

| Group | Surfaces |
|---|---|
| Shared primitives | `admin_ui.css`, `admin_base.html`, sidebar, header, toasts |
| Members | users list, user detail, user edit, roles/tags |
| Payments | payments dashboard, event registrations |
| Slack ops | slack sync, channel sync, scheduled tasks, skipper |
| Practices | list, detail, calendar, config, availability poll, lead picker |
| Catalog | trips, seasons, events, newsletter prompts |

Shared primitives lands first; the rest build on it.

---

## Phase 5 — Verification

Per surface group, before opening the PR:

- Re-capture all affected surfaces at all three viewports
- Side-by-side before/after diff; confirm each flagged issue is resolved and no new
  issue appeared
- `npm run test:practice-reactions`
- `npm run test:events`
- pytest suite (markup changes can break JS tests that assert on structure)

Each PR ships with its before/after gallery so the change is reviewable visually
rather than only as a diff.

Verification is performed locally against the seeded instance. Because the change
is entirely CSS and markup, and the seed reproduces production's field lengths and
row counts, local before/after is a faithful proxy for production appearance.

---

## Delivery

One branch, commits stacked by surface group, one PR per group so each is
reviewable independently. Shared primitives merges first.

## Risks

| Risk | Mitigation |
|---|---|
| A capture click triggers a member-facing send | Four independent outbound layers; non-GET requests aborted in-browser |
| Synthetic seed misses a real data shape | Seed generated from measured prod distributions, including p95/max lengths |
| Snapping values regresses a deliberate spacing choice | Before/after diff per surface at three viewports; visual review per PR |
| Markup changes break JS tests | Full JS + pytest suite run per surface group before PR |
| Component pass changes more than intended | Non-goals are explicit; anything requiring an element to move is flagged, not done |
