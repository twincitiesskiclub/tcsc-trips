# CLAUDE.md

Twin Cities Ski Club (TCSC) — Flask web app for trip/membership registration, practice management, and club operations.

Structure, module inventories, route lists, model fields, and test layout are all derivable from the code — read the repo rather than trusting a list here. This file covers only what the code can't tell you.

## Development Setup

```bash
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
# Copy .env.example → .env (it documents every required variable)
./scripts/dev.sh              # Starts PostgreSQL + Stripe CLI + Flask on port 5001
./scripts/dev.sh 5000         # Custom port
```

`dev.sh` is the only supported dev entrypoint — it pulls the PostgreSQL 18 container (`tcsc-postgres`), runs migrations, and starts Stripe webhook forwarding. Don't hand-run `flask run`; you'll get a server with no database and no webhooks.

- **Docker:** `docker stop/start/rm -f tcsc-postgres`
- **Stripe webhooks, manual:** `stripe listen --forward-to localhost:5000/webhook`
- **Migrations:** `flask db migrate -m "desc"` then `flask db upgrade`

## Status Fields — Two Levels

**CRITICAL:** Status fields are stored as plain strings (e.g. `'ACTIVE'`). `UserStatus` and `UserSeasonStatus` in `app/constants.py` are simple classes, **NOT Python Enums** — do NOT call `.value` on them, they are already strings. Only `MemberType` is a true Enum.

- **`User.status`** (global, *derived* — never set it directly): `PENDING`, `ACTIVE`, `ALUMNI`, `DROPPED`. Computed via `User.derived_status`, persisted via `User.sync_status()`.
- **`UserSeason.status`** (per-season, authoritative): `PENDING_LOTTERY`, `ACTIVE`, `DROPPED_LOTTERY`, `DROPPED_VOLUNTARY`, `DROPPED_CAUSE`.

## Data Conventions

- **Prices are stored in cents** (5000 = $50.00), converted from dollars on form input.
- **Timestamps are UTC in the database**, displayed in US Central (America/Chicago). Use the helpers in `app/utils.py` (`now_central_naive()`, `today_central()`) rather than `datetime.now()`.
- **`User.is_returning` is a derived property, not a stored column** — it checks for past ACTIVE UserSeasons. Member type is always determined server-side; never trust a client-supplied member type.
- Admin dashboard JS follows the `admin_*.js` naming pattern in `app/static/`.

## Payment Flow — capture method is the business rule

Stripe capture method varies by payment type, and getting it wrong charges members prematurely:

| Payment type | Capture | Why |
|---|---|---|
| Season — new member | `manual` | Authorized but not charged; the lottery needs to release losers |
| Season — returning member | `automatic` | Guaranteed a spot, so charge immediately |
| Trips | **Always** `manual` | Hold until an admin confirms the roster |
| Events | `automatic` | No lottery — immediate charge |

Lifecycle: authorize → hold → admin captures or refunds. Payment holds are what make selective acceptance possible; don't "simplify" trip/new-member payments to automatic capture.

## Slack Tier Logic

| `User.status` | `seasons_since_active` | Slack tier |
|---|---|---|
| ACTIVE | 0 | `full_member` |
| ALUMNI | 1 | `multi_channel_guest` |
| ALUMNI | 2+ | `single_channel_guest` |
| PENDING / DROPPED | — | none |

**Coach override:** a HEAD_COACH or ASSISTANT_COACH tag always wins → `full_member`.

Channel sync runs dry-run by default and **preserves manually-joined channels for full members** — it must not "correct" a channel a member joined themselves.

`app/slack/admin_api.py` uses Slack's undocumented cookie-based admin API. It raises `CookieExpiredError` when the session cookie goes stale, which is expected operationally, not a bug.

## Season Management

Returning and new members get separate registration windows. Exactly one `Season.is_current` at a time. The "Activate Season" admin action syncs every user's status — it's a bulk write, not a display toggle.

## Marketing Site Registration Data

The marketing site's registration dates and open/coming_soon/closed state are
**derived from the database**, never authored. `GET /api/season` returns the
registration windows for the soonest-upcoming season per `season_type`; the
Astro build bakes those timestamps plus every state's copy into the HTML, and
`registrationFlip.ts` re-derives the state in the browser so the site flips at
the exact opening minute without a rebuild.

The state rule lives in exactly one place, `site/src/lib/registrationState.ts`.
Do not add a Python twin — the endpoint deliberately returns no computed state,
because a state decided server-side is stale the moment a window boundary
passes.

A build that cannot reach the API **falls back rather than failing**, so it
stamps `data-season-source="fallback"` on `<body>`. If the live site shows
wrong dates, check that attribute first.

## Skipper AI (practice safety evaluation)

Thresholds live in `config/skipper.yaml`; read them there rather than hardcoding.

**Fail-open by design:** a cancellation proposal that no coach acts on within 2 hours expires to *"keep the practice"*, not "cancel". Preserve that default — a silent channel must never cancel practice.

External data adapters (`app/integrations/`) each degrade to `None` on failure so an evaluation still produces a result when a feed is down.

## Practices

- All Slack post updates go through `refresh_practice_posts()` (`app/slack/practices/refresh.py`). Don't update announcement/collab/summary posts individually — the dispatcher keeps them consistent.
- Settings live in `config/practices.yaml`.

## Conditions

`app/conditions/` serves the public marketing-site conditions API. Adapters return `None` on any failure so the endpoint degrades gracefully instead of erroring — keep that contract.

## Background Jobs

`app/scheduler.py` — APScheduler in a thread pool. **Single-worker guard via a file lock (`/tmp/tcsc_scheduler.lock`)** so multi-worker gunicorn doesn't fire every job N times. All schedules are US Central.

## ExpertVoice

Eligibility is ACTIVE members **plus** ALUMNI with `seasons_since_active == 1` — alumni keep pro-deal access for one year after lapsing. Runs daily after the Slack sync.

## Deployment

Gunicorn (120s timeout) on Render. `scripts/release.sh` runs migrations via the Procfile `release` phase. Tailwind CSS builds via `package.json`.

## Tests

pytest with PostgreSQL fixtures. `test_practice_post.py` in the repo root is **not** a pytest file — it's a manual practice-announcement script, so don't expect it to run under the suite.

## Reference

- `CONTRIBUTING.md` — User/UserSeason model details
- `.cursor/rules/tcsc_registration_spec.mdc` — product spec
- `app/constants.py` — status constants, `MemberType` enum
