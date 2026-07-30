# Registration Dates From the Database — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive the marketing site's registration dates and open/coming_soon/closed state from the app database instead of four hand-maintained content fields.

**Architecture:** A new public Flask endpoint `GET /api/season` returns season registration windows as timestamps. The Astro build fetches it once and bakes both the rendered copy for all three states and the raw window timestamps into the HTML. A small client script re-derives the state from those baked timestamps on page load, so the site flips at the exact opening minute without a rebuild and without a runtime API call.

**Tech Stack:** Flask + SQLAlchemy (Python 3, pytest); Astro 7 + TypeScript (`node --test`, jsdom); Render static hosting.

**Spec:** `docs/superpowers/specs/2026-07-30-registration-dates-from-db-design.md`

## Global Constraints

- Timestamps are stored **naive UTC** in the database and must be serialized with an explicit `Z` suffix.
- All dates displayed to humans render in **US Central (`America/Chicago`)**, never UTC, never the viewer's local zone.
- `UserStatus` / `UserSeasonStatus` are plain strings, **not** Python Enums — never call `.value` on them. (Not used by this plan, but do not "fix" them if encountered.)
- Prices are stored in **cents**.
- A failed build-time fetch **must never fail the build**. It falls back and stamps `data-season-source="fallback"`.
- The state rule exists **exactly once**, in TypeScript. Do not add a Python implementation; the endpoint returns no computed state.
- Python: no `db.create_all()` in app or test code (enforced by `tests/test_no_create_all.py`).
- **Any `.ts` module imported directly by a `node --test` file must have no runtime relative imports.** Node's type stripping erases `import type` but cannot resolve extensionless relative specifiers. `registrationState.ts`, `registrationCopy.ts`, `seasonData.ts`, and `seasonSlug.ts` are all imported by tests, so their cross-imports must stay `import type`. Value imports between them will pass `astro check` and fail `node --test`.
- Astro names a script bundle after the `.astro` file that declares the `<script>`, not after the module it imports. Never locate a bundle in `dist/_astro/` by the module's name — find it by content.
- Run the Python suite with `./run-tests.sh`; run site tests from `site/` with `npm run test:refinement`.
- Never push to `main`. All work lands on the branch `registration-dates-from-db`.

## File Structure

**Python — new**
| File | Responsibility |
|---|---|
| `app/seasons/__init__.py` | package marker |
| `app/seasons/selection.py` | pure selection rule: which season the public site describes |
| `app/seasons/payload.py` | shape the `/api/season` response body |
| `app/routes/marketing_cors.py` | CORS policy shared by the public marketing endpoints |
| `app/routes/season_api.py` | the `/api/season` blueprint |

**Python — modified**
| File | Change |
|---|---|
| `app/routes/conditions.py` | use the shared CORS helper instead of its private copy |
| `app/__init__.py` | import and register `season_api_bp` |

**Site — new**
| File | Responsibility |
|---|---|
| `site/src/lib/registrationState.ts` | pure `deriveRegistrationState(windows, now)` — the only state rule |
| `site/src/lib/seasonData.ts` | build-time fetch, memoized per URL, falls back on failure |
| `site/src/lib/registrationCopy.ts` | Central-time date formatting and copy strings |
| `site/src/components/registrationFlip.ts` | client script: re-derive state, swap the baked variant |

**Site — modified**
| File | Change |
|---|---|
| `site/src/components/registrationCta.ts` | resolve state + windows from the API instead of `home.yaml` |
| `site/src/components/CtaForState.astro` | render all three variants as data attributes |
| `site/src/pages/index.astro` | strip subhead from the DB; mount the flip script |
| `site/src/components/SeasonsGrid.astro` | card note + highlight from the DB, per `season_type` |
| `site/src/layouts/BaseLayout.astro` | stamp `data-season-source` / `data-season-generated-at` on `<body>` |
| `site/src/content.config.ts` | drop `registration_state`; redocument card fields as fallback-only |
| `site/keystatic.config.ts` | drop the `registration_state` selector |
| `site/src/content/pages/home.yaml` | drop `registration_state` |
| `site/package.json` | add new test files to `test:refinement` |
| `render.yaml` | add `PUBLIC_SEASON_API_URL` to `tcsc-team-site` |

---

### Task 1: Season selection rule

**Files:**
- Create: `app/seasons/__init__.py`
- Create: `app/seasons/selection.py`
- Create: `tests/seasons/__init__.py`
- Test: `tests/seasons/test_selection.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `span_start(season) -> datetime | None`, `span_end(season) -> datetime | None`, `select_season(seasons: list, now: datetime) -> season | None`. Accepts any object with `returning_start`, `returning_end`, `new_start`, `new_end`, `id` — tests use a plain dataclass, not the ORM model.

- [ ] **Step 1: Write the failing test**

Create `tests/seasons/__init__.py` as an empty file, then `tests/seasons/test_selection.py`:

```python
"""The selection rule is pure: it takes any object with the four window
columns, so these tests use a stub rather than the ORM model or a database."""
from dataclasses import dataclass
from datetime import datetime

from app.seasons.selection import select_season, span_end, span_start


@dataclass
class StubSeason:
    id: int
    returning_start: datetime | None = None
    returning_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None


NOW = datetime(2026, 7, 30, 12, 0, 0)


def _season(id, r_start=None, r_end=None, n_start=None, n_end=None):
    return StubSeason(id, r_start, r_end, n_start, n_end)


def test_span_start_is_the_earliest_window_open():
    season = _season(
        1,
        r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2),
        n_start=datetime(2026, 9, 3), n_end=datetime(2026, 9, 20),
    )
    assert span_start(season) == datetime(2026, 8, 28)
    assert span_end(season) == datetime(2026, 9, 20)


def test_span_ignores_null_windows():
    season = _season(1, n_start=datetime(2026, 9, 3), n_end=datetime(2026, 9, 20))
    assert span_start(season) == datetime(2026, 9, 3)
    assert span_end(season) == datetime(2026, 9, 20)


def test_span_is_none_when_no_windows_exist():
    assert span_start(_season(1)) is None
    assert span_end(_season(1)) is None


def test_prefers_the_season_open_right_now():
    open_now = _season(1, r_start=datetime(2026, 7, 1), r_end=datetime(2026, 8, 1))
    upcoming = _season(2, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([upcoming, open_now], NOW) is open_now


def test_falls_to_the_soonest_upcoming_when_none_are_open():
    soon = _season(1, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    later = _season(2, r_start=datetime(2027, 8, 28), r_end=datetime(2027, 9, 2))
    assert select_season([later, soon], NOW) is soon


def test_falls_to_the_most_recently_ended_when_all_are_past():
    old = _season(1, r_start=datetime(2024, 8, 28), r_end=datetime(2024, 9, 2))
    recent = _season(2, r_start=datetime(2025, 8, 28), r_end=datetime(2025, 9, 2))
    assert select_season([old, recent], NOW) is recent


def test_ignores_seasons_with_no_windows_at_all():
    windowless = _season(1)
    real = _season(2, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([windowless, real], NOW) is real


def test_returns_none_when_nothing_has_a_window():
    assert select_season([_season(1), _season(2)], NOW) is None


def test_returns_none_for_an_empty_list():
    assert select_season([], NOW) is None


def test_ties_break_on_id_so_the_result_is_deterministic():
    a = _season(7, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    b = _season(3, r_start=datetime(2026, 8, 28), r_end=datetime(2026, 9, 2))
    assert select_season([a, b], NOW) is b
    assert select_season([b, a], NOW) is b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./run-tests.sh tests/seasons/test_selection.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.seasons'`

- [ ] **Step 3: Write minimal implementation**

Create `app/seasons/__init__.py` as an empty file, then `app/seasons/selection.py`:

```python
"""Pick the one season the public marketing site should describe.

Deliberately NOT ``Season.is_current``: that flag is set by the "Activate
Season" admin action, which is a bulk write across every user's status.
Nobody is going to run it to correct the website, so the website must not
depend on it.
"""
from __future__ import annotations

from datetime import datetime


def span_start(season) -> datetime | None:
    """Earliest moment any registration window for this season opens."""
    starts = [s for s in (season.returning_start, season.new_start) if s]
    return min(starts) if starts else None


def span_end(season) -> datetime | None:
    """Latest moment any registration window for this season closes."""
    ends = [e for e in (season.returning_end, season.new_end) if e]
    return max(ends) if ends else None


def select_season(seasons, now: datetime):
    """The season taking registrations now, else the soonest one ahead, else
    the most recently ended. ``None`` when no season has a window at all.

    Ties break on ``id`` so a given database state always yields the same
    answer regardless of query ordering.
    """
    candidates = sorted(
        (s for s in seasons if span_start(s) is not None),
        key=lambda s: (span_start(s), s.id or 0),
    )
    if not candidates:
        return None

    for season in candidates:
        end = span_end(season)
        if span_start(season) <= now and (end is None or now <= end):
            return season

    for season in candidates:
        if span_start(season) > now:
            return season

    ended = [s for s in candidates if span_end(s) is not None]
    if ended:
        return max(ended, key=lambda s: (span_end(s), -(s.id or 0)))
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./run-tests.sh tests/seasons/test_selection.py`
Expected: PASS — 10 passed

- [ ] **Step 5: Commit**

```bash
git add app/seasons tests/seasons
git commit -m "feat(seasons): pick the season the public site should describe"
```

---

### Task 2: Season payload builder

**Files:**
- Create: `app/seasons/payload.py`
- Test: `tests/seasons/test_payload.py`

**Interfaces:**
- Consumes: `select_season`, `span_start` from `app/seasons/selection.py`.
- Produces: `serialize_season(season) -> dict`, `build_season_payload(seasons, now: datetime) -> dict` with keys `generated_at`, `primary`, `by_type`.

- [ ] **Step 1: Write the failing test**

Create `tests/seasons/test_payload.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from app.seasons.payload import build_season_payload, serialize_season


@dataclass
class StubSeason:
    id: int
    name: str = '2026 Fall/Winter'
    season_type: str = 'fall/winter'
    year: int = 2026
    price_cents: int | None = 20500
    returning_start: datetime | None = None
    returning_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None


NOW = datetime(2026, 7, 30, 12, 0, 0)

FALL = StubSeason(
    1,
    returning_start=datetime(2026, 8, 28, 17, 0, 0),
    returning_end=datetime(2026, 9, 2, 5, 0, 0),
    new_start=datetime(2026, 9, 3, 17, 0, 0),
    new_end=datetime(2026, 9, 20, 5, 0, 0),
)
SPRING = StubSeason(
    2,
    name='2027 Spring/Summer',
    season_type='spring/summer',
    year=2027,
    returning_start=datetime(2027, 3, 1, 17, 0, 0),
    returning_end=datetime(2027, 3, 20, 5, 0, 0),
)


def test_serializes_timestamps_with_an_explicit_utc_marker():
    body = serialize_season(FALL)
    assert body['returning_start'] == '2026-08-28T17:00:00Z'
    assert body['new_end'] == '2026-09-20T05:00:00Z'


def test_serializes_null_windows_as_null():
    body = serialize_season(SPRING)
    assert body['new_start'] is None
    assert body['new_end'] is None


def test_serializes_the_descriptive_fields():
    body = serialize_season(FALL)
    assert body['name'] == '2026 Fall/Winter'
    assert body['season_type'] == 'fall/winter'
    assert body['year'] == 2026
    assert body['price_cents'] == 20500


def test_payload_keys_one_entry_per_season_type():
    body = build_season_payload([FALL, SPRING], NOW)
    assert sorted(body['by_type']) == ['fall/winter', 'spring/summer']
    assert body['by_type']['fall/winter']['name'] == '2026 Fall/Winter'


def test_primary_is_the_soonest_across_every_type():
    body = build_season_payload([SPRING, FALL], NOW)
    assert body['primary']['season_type'] == 'fall/winter'


def test_primary_is_null_when_no_season_has_a_window():
    body = build_season_payload([StubSeason(9)], NOW)
    assert body['primary'] is None
    assert body['by_type'] == {}


def test_generated_at_marks_the_build_moment():
    body = build_season_payload([FALL], NOW)
    assert body['generated_at'] == '2026-07-30T12:00:00Z'


def test_legacy_season_types_still_appear_and_are_simply_unmatched():
    legacy = StubSeason(
        3,
        name='2019 Winter',
        season_type='legacy',
        returning_start=datetime(2019, 9, 1),
        returning_end=datetime(2019, 9, 30),
    )
    body = build_season_payload([FALL, legacy], NOW)
    assert 'legacy' in body['by_type']
    assert body['primary']['season_type'] == 'fall/winter'


def test_seasons_without_a_type_are_skipped_in_by_type():
    untyped = StubSeason(
        4,
        season_type='',
        returning_start=datetime(2026, 8, 1),
        returning_end=datetime(2026, 8, 5),
    )
    body = build_season_payload([FALL, untyped], NOW)
    assert '' not in body['by_type']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./run-tests.sh tests/seasons/test_payload.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.seasons.payload'`

- [ ] **Step 3: Write minimal implementation**

Create `app/seasons/payload.py`:

```python
"""Shape the public ``/api/season`` body.

Carries timestamps only. There is deliberately no computed open/closed state:
a state decided here is wrong the moment a window boundary passes, and the
marketing site is a static build that would keep serving it. The site derives
state in the browser from these timestamps instead.
"""
from __future__ import annotations

from datetime import datetime

from .selection import select_season


def _iso(value: datetime | None) -> str | None:
    """Naive-UTC column to an explicit Z-suffixed ISO 8601 string."""
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def serialize_season(season) -> dict:
    return {
        'name': season.name,
        'season_type': season.season_type,
        'year': season.year,
        'price_cents': season.price_cents,
        'returning_start': _iso(season.returning_start),
        'returning_end': _iso(season.returning_end),
        'new_start': _iso(season.new_start),
        'new_end': _iso(season.new_end),
    }


def build_season_payload(seasons, now: datetime) -> dict:
    """One rule, applied per type and then across everything."""
    seasons = list(seasons)
    by_type = {}
    for season_type in sorted({s.season_type for s in seasons if s.season_type}):
        chosen = select_season(
            [s for s in seasons if s.season_type == season_type], now
        )
        if chosen is not None:
            by_type[season_type] = serialize_season(chosen)

    primary = select_season(seasons, now)
    return {
        'generated_at': _iso(now),
        'primary': serialize_season(primary) if primary is not None else None,
        'by_type': by_type,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./run-tests.sh tests/seasons/test_payload.py`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add app/seasons/payload.py tests/seasons/test_payload.py
git commit -m "feat(seasons): shape the public season payload"
```

---

### Task 3: Shared marketing CORS policy

**Files:**
- Create: `app/routes/marketing_cors.py`
- Modify: `app/routes/conditions.py` (replace `_ALLOWED_ORIGINS` and `_origin_allowed`)
- Test: `tests/routes/test_marketing_cors.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ALLOWED_ORIGINS: set[str]`, `origin_allowed(origin: str) -> bool`, `apply_marketing_cors(resp, origin: str) -> resp`.

The existing `tests/conditions/test_route.py` must keep passing untouched — that is the regression check for this refactor.

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_marketing_cors.py`:

```python
from app import create_app
from app.routes.marketing_cors import ALLOWED_ORIGINS, origin_allowed


def _ctx(debug=False):
    app = create_app()
    app.debug = debug
    return app


def test_the_marketing_origins_are_allowed():
    app = _ctx()
    with app.app_context():
        assert origin_allowed('https://twincitiesskiclub.org')
        assert origin_allowed('https://www.twincitiesskiclub.org')
        assert origin_allowed('https://tcsc-marketing.onrender.com')


def test_unknown_and_empty_origins_are_rejected():
    app = _ctx()
    with app.app_context():
        assert not origin_allowed('https://evil.com')
        assert not origin_allowed('')


def test_localhost_is_allowed_only_in_debug():
    app = _ctx(debug=True)
    with app.app_context():
        assert origin_allowed('http://localhost:4321')

    app = _ctx(debug=False)
    with app.app_context():
        assert not origin_allowed('http://localhost:4321')


def test_the_allowlist_still_covers_the_conditions_origins():
    # conditions and the season API must not drift apart.
    assert 'https://twincitiesskiclub.org' in ALLOWED_ORIGINS
    assert 'https://www.twincitiesskiclub.org' in ALLOWED_ORIGINS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./run-tests.sh tests/routes/test_marketing_cors.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routes.marketing_cors'`

- [ ] **Step 3: Write minimal implementation**

Create `app/routes/marketing_cors.py`:

```python
"""CORS policy shared by every public endpoint the marketing site consumes.

Lived privately in ``conditions.py`` until the season API needed the same
allowlist. Two copies of an origin allowlist is one copy too many: adding a
staging origin to one and not the other fails silently and only in a browser.
"""
from __future__ import annotations

from flask import current_app

ALLOWED_ORIGINS = {
    'https://twincitiesskiclub.org',
    'https://www.twincitiesskiclub.org',
    # Staging origin (Render Static service for the marketing site).
    'https://tcsc-marketing.onrender.com',
}


def origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    # Astro dev server (e.g. http://localhost:4321), debug/development only.
    if current_app.debug and origin.startswith('http://localhost:'):
        return True
    return False


def apply_marketing_cors(resp, origin: str):
    """Always vary on Origin so shared caches never serve an ACAO-bearing
    response to a different origin."""
    resp.headers['Vary'] = 'Origin'
    if origin_allowed(origin):
        resp.headers['Access-Control-Allow-Origin'] = origin
    return resp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./run-tests.sh tests/routes/test_marketing_cors.py`
Expected: PASS — 4 passed

- [ ] **Step 5: Point conditions at the shared helper**

In `app/routes/conditions.py`, delete the `_ALLOWED_ORIGINS` set and the `_origin_allowed` function, add the import, and replace the header block in `get_conditions`.

Add near the other imports:

```python
from app.routes.marketing_cors import apply_marketing_cors
```

Replace the body of `get_conditions` with:

```python
@bp.route('/conditions', methods=['GET'])
def get_conditions():
    body = _get_response_body()
    resp = jsonify(body)
    apply_marketing_cors(resp, request.headers.get('Origin', ''))
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_TTL_SECONDS}'
    return resp
```

Remove the now-unused `current_app` import from `conditions.py` **only if** nothing else in that file uses it — check with `grep -n current_app app/routes/conditions.py` first.

- [ ] **Step 6: Verify the conditions route is unchanged in behavior**

Run: `./run-tests.sh tests/conditions/ tests/routes/test_marketing_cors.py`
Expected: PASS — the pre-existing conditions route tests still pass untouched.

- [ ] **Step 7: Commit**

```bash
git add app/routes/marketing_cors.py app/routes/conditions.py tests/routes/test_marketing_cors.py
git commit -m "refactor(routes): share one CORS allowlist across the public marketing endpoints"
```

---

### Task 4: The `/api/season` endpoint

**Files:**
- Create: `app/routes/season_api.py`
- Modify: `app/__init__.py` (import beside `conditions_bp`, register beside `conditions_bp`)
- Test: `tests/routes/test_season_api.py`

**Interfaces:**
- Consumes: `build_season_payload` (Task 2), `apply_marketing_cors` (Task 3), `Season` from `app.models`.
- Produces: `bp` — a Flask blueprint named `season_api` with `url_prefix='/api'` serving `GET /api/season`.

- [ ] **Step 1: Write the failing test**

Create `tests/routes/test_season_api.py`:

```python
"""The route is thin: selection and shaping are unit-tested in tests/seasons/.
These tests cover wiring, headers, and the empty-database case, so they stub
the query rather than seeding rows."""
import json

import app.routes.season_api as season_api
from app import create_app


def _client(monkeypatch, seasons, debug=False):
    monkeypatch.setattr(season_api, '_all_seasons', lambda: seasons)
    app = create_app()
    app.debug = debug
    return app.test_client()


class StubSeason:
    id = 1
    name = '2026 Fall/Winter'
    season_type = 'fall/winter'
    year = 2026
    price_cents = 20500
    returning_start = __import__('datetime').datetime(2026, 8, 28, 17, 0, 0)
    returning_end = __import__('datetime').datetime(2026, 9, 2, 5, 0, 0)
    new_start = __import__('datetime').datetime(2026, 9, 3, 17, 0, 0)
    new_end = __import__('datetime').datetime(2026, 9, 20, 5, 0, 0)


def test_returns_json_with_the_expected_shape(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('application/json')
    body = json.loads(resp.data)
    assert set(body) == {'generated_at', 'primary', 'by_type'}
    assert body['primary']['season_type'] == 'fall/winter'
    assert body['by_type']['fall/winter']['returning_start'] == '2026-08-28T17:00:00Z'


def test_returns_a_null_primary_rather_than_erroring_on_an_empty_database(monkeypatch):
    client = _client(monkeypatch, [])
    resp = client.get('/api/season')
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['primary'] is None
    assert body['by_type'] == {}


def test_exposes_no_computed_state(monkeypatch):
    # The browser derives state from the timestamps; a server-computed state
    # would be stale the moment a window boundary passed.
    client = _client(monkeypatch, [StubSeason()])
    body = json.loads(client.get('/api/season').data)
    assert 'state' not in body
    assert 'state' not in body['primary']


def test_always_varies_on_origin(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    assert client.get('/api/season').headers.get('Vary') == 'Origin'
    resp = client.get('/api/season', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Vary') == 'Origin'
    assert 'Access-Control-Allow-Origin' not in resp.headers


def test_sets_cors_for_the_marketing_site(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season', headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://twincitiesskiclub.org'


def test_is_publicly_cacheable(monkeypatch):
    client = _client(monkeypatch, [StubSeason()])
    resp = client.get('/api/season')
    assert resp.headers.get('Cache-Control') == 'public, max-age=300'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./run-tests.sh tests/routes/test_season_api.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routes.season_api'`

- [ ] **Step 3: Write minimal implementation**

Create `app/routes/season_api.py`:

```python
"""Public season API consumed by the marketing site.

Returns registration windows as timestamps and no computed open/closed state.
The marketing site is a static build: a state decided here would be baked into
HTML and keep being served after the window boundary it described had passed.
The site re-derives state in the browser from these timestamps instead.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import Season
from app.routes.marketing_cors import apply_marketing_cors
from app.seasons.payload import build_season_payload

bp = Blueprint('season_api', __name__, url_prefix='/api')

_CACHE_MAX_AGE_SECONDS = 300


def _all_seasons():
    """Seam for tests, which cover shaping without seeding rows."""
    return Season.query.all()


@bp.route('/season', methods=['GET'])
def get_season():
    body = build_season_payload(_all_seasons(), datetime.utcnow())
    resp = jsonify(body)
    apply_marketing_cors(resp, request.headers.get('Origin', ''))
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_MAX_AGE_SECONDS}'
    return resp
```

In `app/__init__.py`, add beside the existing conditions import (line ~32):

```python
from .routes.season_api import bp as season_api_bp
```

and beside the existing conditions registration (line ~78):

```python
    app.register_blueprint(season_api_bp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./run-tests.sh tests/routes/test_season_api.py tests/test_app_startup.py`
Expected: PASS — 6 passed in the new file, app startup unaffected.

- [ ] **Step 5: Verify against a real database**

Run:
```bash
./scripts/dev.sh 5001 &
sleep 25
curl -s localhost:5001/api/season | head -40
```
Expected: JSON with `generated_at`, `primary`, `by_type`. Confirm the timestamps end in `Z`. Stop the dev server afterward.

- [ ] **Step 6: Commit**

```bash
git add app/routes/season_api.py app/__init__.py tests/routes/test_season_api.py
git commit -m "feat(api): serve season registration windows to the marketing site"
```

---

### Task 5: The registration state rule (TypeScript)

**Files:**
- Create: `site/src/lib/registrationState.ts`
- Test: `site/tests/registrationState.test.mjs`
- Modify: `site/package.json` (add the new test file to `test:refinement`)

**Interfaces:**
- Consumes: nothing.
- Produces: `type RegistrationState = 'open' | 'coming_soon' | 'closed'`; `interface RegistrationWindows { returning_start?, returning_end?, new_start?, new_end? }` (all `string | null | undefined`); `deriveRegistrationState(windows: RegistrationWindows, now: number): RegistrationState`.

`now` is a millisecond epoch (`Date.now()`), not a `Date`, so the browser script and the build share one signature.

- [ ] **Step 1: Write the failing test**

Create `site/tests/registrationState.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveRegistrationState } from '../src/lib/registrationState.ts';

const WINDOWS = {
  returning_start: '2026-08-28T17:00:00Z',
  returning_end: '2026-09-02T05:00:00Z',
  new_start: '2026-09-03T17:00:00Z',
  new_end: '2026-09-20T05:00:00Z',
};
const at = (iso) => Date.parse(iso);

test('is coming_soon before anything opens', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-07-30T12:00:00Z')), 'coming_soon');
});

test('is open inside the returning window', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-29T12:00:00Z')), 'open');
});

test('is open inside the new-member window', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-10T12:00:00Z')), 'open');
});

test('is open exactly at a window boundary, both ends', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T17:00:00Z')), 'open');
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-02T05:00:00Z')), 'open');
});

test('is coming_soon one second before opening and open one second after', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T16:59:59Z')), 'coming_soon');
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T17:00:01Z')), 'open');
});

test('is coming_soon in the gap between the two windows', () => {
  // Nobody can actually register here, but a window is still ahead, so
  // saying "open" would be a lie.
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-02T18:00:00Z')), 'coming_soon');
});

test('is closed once every window has passed', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-10-01T12:00:00Z')), 'closed');
});

test('is closed with no windows at all', () => {
  assert.equal(deriveRegistrationState({}, at('2026-07-30T12:00:00Z')), 'closed');
});

test('ignores a half-specified window', () => {
  // Matches Season.is_open_for, which requires both ends to be set.
  const half = { returning_start: '2026-08-28T17:00:00Z', returning_end: null };
  assert.equal(deriveRegistrationState(half, at('2026-08-29T12:00:00Z')), 'closed');
});

test('ignores unparseable timestamps rather than throwing', () => {
  const junk = { returning_start: 'not a date', returning_end: 'nope' };
  assert.equal(deriveRegistrationState(junk, at('2026-08-29T12:00:00Z')), 'closed');
});

test('uses only the new-member window when returning is absent', () => {
  const newOnly = { new_start: '2026-09-03T17:00:00Z', new_end: '2026-09-20T05:00:00Z' };
  assert.equal(deriveRegistrationState(newOnly, at('2026-09-10T12:00:00Z')), 'open');
  assert.equal(deriveRegistrationState(newOnly, at('2026-08-01T12:00:00Z')), 'coming_soon');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `node --test tests/registrationState.test.mjs`
Expected: FAIL — `ERR_MODULE_NOT_FOUND` for `src/lib/registrationState.ts`

- [ ] **Step 3: Write minimal implementation**

Create `site/src/lib/registrationState.ts`:

```typescript
// The registration state rule, in one place.
//
// This module is imported by the Astro build AND shipped to the browser, on
// purpose. The site is a static build, so a state decided at build time is
// wrong the moment a window boundary passes; the browser re-derives it from
// timestamps baked into the HTML. Both callers must agree, so there is
// exactly one implementation and no Python twin.
export type RegistrationState = 'open' | 'coming_soon' | 'closed';

export interface RegistrationWindows {
  returning_start?: string | null;
  returning_end?: string | null;
  new_start?: string | null;
  new_end?: string | null;
}

interface ParsedWindow {
  start: number;
  end: number;
}

// A window counts only when BOTH ends parse, matching Season.is_open_for on
// the Python side, which returns False unless both columns are set.
function parseWindows(w: RegistrationWindows): ParsedWindow[] {
  const pairs: Array<[unknown, unknown]> = [
    [w.returning_start, w.returning_end],
    [w.new_start, w.new_end],
  ];
  const parsed: ParsedWindow[] = [];
  for (const [rawStart, rawEnd] of pairs) {
    if (typeof rawStart !== 'string' || typeof rawEnd !== 'string') continue;
    const start = Date.parse(rawStart);
    const end = Date.parse(rawEnd);
    if (Number.isNaN(start) || Number.isNaN(end)) continue;
    parsed.push({ start, end });
  }
  return parsed;
}

/** `now` is a millisecond epoch (Date.now()), so build and browser share it. */
export function deriveRegistrationState(
  w: RegistrationWindows,
  now: number,
): RegistrationState {
  const windows = parseWindows(w);
  if (windows.length === 0) return 'closed';
  if (windows.some((x) => now >= x.start && now <= x.end)) return 'open';
  // Covers the gap between the returning and new windows: nobody can submit
  // right now, but a window is still ahead, so "open" would be a lie.
  if (windows.some((x) => x.start > now)) return 'coming_soon';
  return 'closed';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `site/`): `node --test tests/registrationState.test.mjs`
Expected: PASS — 11 passed

- [ ] **Step 5: Add the test to the suite and commit**

In `site/package.json`, append ` tests/registrationState.test.mjs` to the end of the `test:refinement` command string.

Run: `npm run test:refinement`
Expected: PASS — all existing tests plus the 11 new ones.

```bash
git add site/src/lib/registrationState.ts site/tests/registrationState.test.mjs site/package.json
git commit -m "feat(site): derive registration state from window timestamps"
```

---

### Task 6: Central-time copy formatting

**Files:**
- Create: `site/src/lib/registrationCopy.ts`
- Test: `site/tests/registrationCopy.test.mjs`
- Modify: `site/package.json`

**Interfaces:**
- Consumes: `RegistrationState`, `RegistrationWindows` (Task 5).
- Produces: `formatDay(iso) -> string | null`, `datesSentence(w) -> string | null`, `stripSubhead(state, w) -> string`, `cardNote(year, w) -> string | null`.

- [ ] **Step 1: Write the failing test**

Create `site/tests/registrationCopy.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cardNote,
  datesSentence,
  formatDay,
  stripSubhead,
} from '../src/lib/registrationCopy.ts';

const WINDOWS = {
  returning_start: '2026-08-28T17:00:00Z',
  returning_end: '2026-09-02T05:00:00Z',
  new_start: '2026-09-03T17:00:00Z',
  new_end: '2026-09-20T05:00:00Z',
};

test('formats a day in US Central, not UTC', () => {
  // 2026-08-28T17:00Z is 12:00 CDT the same day.
  assert.equal(formatDay('2026-08-28T17:00:00Z'), 'Aug 28');
});

test('formats across the UTC date boundary using the Central day', () => {
  // 2026-09-02T05:00Z is 2026-09-01 at midnight CDT -- the Central day is
  // the previous date, which is the one a member reads on the page.
  assert.equal(formatDay('2026-09-02T05:00:00Z'), 'Sep 1');
});

test('formats a winter date in standard time', () => {
  // 2026-12-15T18:00Z is 12:00 CST.
  assert.equal(formatDay('2026-12-15T18:00:00Z'), 'Dec 15');
});

test('returns null for missing or unparseable input', () => {
  assert.equal(formatDay(null), null);
  assert.equal(formatDay(undefined), null);
  assert.equal(formatDay('not a date'), null);
});

test('builds the dates sentence from both windows', () => {
  assert.equal(datesSentence(WINDOWS), 'Returning members Aug 28; new members Sep 3');
});

test('builds a partial dates sentence when only one window exists', () => {
  assert.equal(
    datesSentence({ new_start: '2026-09-03T17:00:00Z' }),
    'New members Sep 3',
  );
});

test('has no dates sentence when no window exists', () => {
  assert.equal(datesSentence({}), null);
});

test('the coming_soon subhead leads with the real dates', () => {
  assert.equal(
    stripSubhead('coming_soon', WINDOWS),
    'Returning members Aug 28; new members Sep 3. Intermediate ability and up, no racing required.',
  );
});

test('the coming_soon subhead omits dates rather than inventing them', () => {
  assert.equal(
    stripSubhead('coming_soon', {}),
    'Registration opens soon. Intermediate ability and up, no racing required.',
  );
});

test('the open and closed subheads do not carry dates', () => {
  assert.equal(
    stripSubhead('open', WINDOWS),
    'Intermediate ability and up, no racing required.',
  );
  assert.equal(
    stripSubhead('closed', WINDOWS),
    'Registration is closed. Intermediate ability and up, no racing required.',
  );
});

test('the card note matches the hand-written format it replaces', () => {
  assert.equal(
    cardNote(2026, WINDOWS),
    '2026 registration: returning members Aug 28 · new members Sep 3',
  );
});

test('there is no card note without dates', () => {
  assert.equal(cardNote(2026, {}), null);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `node --test tests/registrationCopy.test.mjs`
Expected: FAIL — `ERR_MODULE_NOT_FOUND` for `src/lib/registrationCopy.ts`

- [ ] **Step 3: Write minimal implementation**

Create `site/src/lib/registrationCopy.ts`:

```typescript
// Registration copy, formatted in US Central.
//
// Timestamps arrive as UTC from the API; the club is in Minneapolis and every
// date a member reads is a Central date. Formatting in UTC would show the
// wrong DAY for any evening deadline, so the timezone is pinned explicitly
// rather than inherited from the build machine or the visitor.
import type { RegistrationState, RegistrationWindows } from './registrationState';

const CENTRAL = 'America/Chicago';
const ABILITY = 'Intermediate ability and up, no racing required.';

const dayFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: CENTRAL,
  month: 'short',
  day: 'numeric',
});

export function formatDay(iso: string | null | undefined): string | null {
  if (typeof iso !== 'string') return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return dayFormatter.format(new Date(ms));
}

function openingDays(w: RegistrationWindows) {
  return {
    returning: formatDay(w.returning_start),
    fresh: formatDay(w.new_start),
  };
}

/** "Returning members Aug 28; new members Sep 3" — null when no dates. */
export function datesSentence(w: RegistrationWindows): string | null {
  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`Returning members ${returning}`);
  if (fresh) parts.push(returning ? `new members ${fresh}` : `New members ${fresh}`);
  return parts.length ? parts.join('; ') : null;
}

export function stripSubhead(state: RegistrationState, w: RegistrationWindows): string {
  if (state === 'open') return ABILITY;
  if (state === 'closed') return `Registration is closed. ${ABILITY}`;
  const dates = datesSentence(w);
  return dates ? `${dates}. ${ABILITY}` : `Registration opens soon. ${ABILITY}`;
}

/** "2026 registration: returning members Aug 28 · new members Sep 3" */
export function cardNote(year: number, w: RegistrationWindows): string | null {
  const { returning, fresh } = openingDays(w);
  const parts: string[] = [];
  if (returning) parts.push(`returning members ${returning}`);
  if (fresh) parts.push(`new members ${fresh}`);
  return parts.length ? `${year} registration: ${parts.join(' · ')}` : null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `site/`): `node --test tests/registrationCopy.test.mjs`
Expected: PASS — 12 passed

- [ ] **Step 5: Add to the suite and commit**

Append ` tests/registrationCopy.test.mjs` to `test:refinement` in `site/package.json`.

Run: `npm run test:refinement`
Expected: PASS

```bash
git add site/src/lib/registrationCopy.ts site/tests/registrationCopy.test.mjs site/package.json
git commit -m "feat(site): format registration copy in US Central"
```

---

### Task 7: Build-time season fetch with fallback

**Files:**
- Create: `site/src/lib/seasonData.ts`
- Test: `site/tests/seasonData.test.mjs`
- Modify: `site/package.json`
- Modify: `render.yaml` (add `PUBLIC_SEASON_API_URL` to the `tcsc-team-site` service)

**Interfaces:**
- Consumes: `RegistrationWindows` (Task 5).
- Produces: `interface SeasonRecord` (the serialized season from Task 2, plus `name`, `season_type`, `year`, `price_cents`); `interface SeasonData { source: 'api' | 'fallback'; generated_at: string | null; primary: SeasonRecord | null; by_type: Record<string, SeasonRecord> }`; `seasonApiUrl(): string`; `fetchSeasonData(url?: string): Promise<SeasonData>`.

Memoized in a `Map` keyed by URL so one build issues one request while tests stay isolated by using distinct URLs.

- [ ] **Step 1: Write the failing test**

Create `site/tests/seasonData.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';

import { fetchSeasonData } from '../src/lib/seasonData.ts';

const BODY = {
  generated_at: '2026-07-30T12:00:00Z',
  primary: {
    name: '2026 Fall/Winter',
    season_type: 'fall/winter',
    year: 2026,
    price_cents: 20500,
    returning_start: '2026-08-28T17:00:00Z',
    returning_end: '2026-09-02T05:00:00Z',
    new_start: '2026-09-03T17:00:00Z',
    new_end: '2026-09-20T05:00:00Z',
  },
  by_type: { 'fall/winter': { season_type: 'fall/winter', year: 2026 } },
};

async function withServer(handler, run) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/api/season`;
  try {
    return await run(url);
  } finally {
    server.close();
  }
}

test('returns api data when the endpoint responds', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(BODY));
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'api');
      assert.equal(data.primary.season_type, 'fall/winter');
      assert.equal(data.generated_at, '2026-07-30T12:00:00Z');
      assert.equal(data.by_type['fall/winter'].year, 2026);
    },
  );
});

test('issues one request per build no matter how many callers ask', async () => {
  let hits = 0;
  await withServer(
    (req, res) => {
      hits += 1;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(BODY));
    },
    async (url) => {
      await Promise.all([fetchSeasonData(url), fetchSeasonData(url), fetchSeasonData(url)]);
      assert.equal(hits, 1);
    },
  );
});

test('falls back instead of throwing when the endpoint is unreachable', async () => {
  // Port 1 is reserved and nothing listens on it.
  const data = await fetchSeasonData('http://127.0.0.1:1/api/season');
  assert.equal(data.source, 'fallback');
  assert.equal(data.primary, null);
  assert.deepEqual(data.by_type, {});
  assert.equal(data.generated_at, null);
});

test('falls back on a non-200 response', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(503);
      res.end('down');
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'fallback');
      assert.equal(data.primary, null);
    },
  );
});

test('falls back on a malformed body', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{ not json');
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'fallback');
    },
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `node --test tests/seasonData.test.mjs`
Expected: FAIL — `ERR_MODULE_NOT_FOUND` for `src/lib/seasonData.ts`

- [ ] **Step 3: Write minimal implementation**

Create `site/src/lib/seasonData.ts`:

```typescript
// Build-time season fetch.
//
// This runs during `astro build`, once, and its result is baked into static
// HTML. It must NEVER fail the build: a marketing deploy blocked because the
// Flask app happened to be restarting is a worse outcome than a page that
// declines to name a date. The fallback is therefore pessimistic AND
// self-announcing -- see the data-season-source stamp in BaseLayout.
import type { RegistrationWindows } from './registrationState';

export interface SeasonRecord extends RegistrationWindows {
  name?: string;
  season_type?: string;
  year?: number;
  price_cents?: number | null;
}

export interface SeasonData {
  source: 'api' | 'fallback';
  generated_at: string | null;
  primary: SeasonRecord | null;
  by_type: Record<string, SeasonRecord>;
}

const FETCH_TIMEOUT_MS = 10_000;

const FALLBACK: SeasonData = Object.freeze({
  source: 'fallback',
  generated_at: null,
  primary: null,
  by_type: {},
});

export function seasonApiUrl(): string {
  // Optional chaining: this module is also loaded by plain `node --test`,
  // where import.meta.env does not exist.
  return import.meta.env?.PUBLIC_SEASON_API_URL ?? 'https://tcsc.ski/api/season';
}

// Keyed by url so one build issues one request, while tests stay isolated by
// pointing at distinct ephemeral ports.
const inFlight = new Map<string, Promise<SeasonData>>();

async function load(url: string): Promise<SeasonData> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json();
    return {
      source: 'api',
      generated_at: body?.generated_at ?? null,
      primary: body?.primary ?? null,
      by_type: body?.by_type ?? {},
    };
  } catch (error) {
    console.warn(
      `[season] ${url} unreachable (${error}). Falling back to committed copy; ` +
        'the built pages will report data-season-source="fallback".',
    );
    return FALLBACK;
  }
}

export function fetchSeasonData(url: string = seasonApiUrl()): Promise<SeasonData> {
  let pending = inFlight.get(url);
  if (!pending) {
    pending = load(url);
    inFlight.set(url, pending);
  }
  return pending;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `site/`): `node --test tests/seasonData.test.mjs`
Expected: PASS — 5 passed

- [ ] **Step 5: Wire the production URL**

In `render.yaml`, in the `tcsc-team-site` service's `envVars`, add beside `PUBLIC_CONDITIONS_API_URL`:

```yaml
              - key: PUBLIC_SEASON_API_URL
                value: https://tcsc.ski/api/season
```

- [ ] **Step 6: Add to the suite and commit**

Append ` tests/seasonData.test.mjs` to `test:refinement` in `site/package.json`.

Run: `npm run test:refinement`
Expected: PASS

```bash
git add site/src/lib/seasonData.ts site/tests/seasonData.test.mjs site/package.json render.yaml
git commit -m "feat(site): fetch season windows at build time, falling back loudly"
```

---

### Task 8: Resolve the CTA from the database

**Files:**
- Modify: `site/src/components/registrationCta.ts`
- Modify: `site/src/components/CtaForState.astro`
- Modify: `site/src/layouts/BaseLayout.astro:95`
- Modify: `site/src/pages/index.astro`
- Modify: `site/src/content/pages/home.yaml` (delete `registration_state`)
- Modify: `site/src/content.config.ts:208` (delete `registration_state`)
- Modify: `site/keystatic.config.ts:69` (delete the `registration_state` selector)
- Test: `site/tests/seasonBuild.test.mjs`
- Modify: `site/package.json`

**Interfaces:**
- Consumes: `fetchSeasonData` (Task 7), `deriveRegistrationState` (Task 5), `stripSubhead` (Task 6), `isSamePageAnchor` (already on the branch).
- Produces: `getRegistrationCta()` now returns `RegistrationCta` extended with `state` (derived), `windows: RegistrationWindows`, `source: 'api' | 'fallback'`, `generated_at: string | null`.

- [ ] **Step 1: Write the failing test**

Create `site/tests/seasonBuild.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
const { document } = new JSDOM(html).window;

test('the page records where its season data came from', () => {
  const source = document.body.getAttribute('data-season-source');
  assert.ok(
    source === 'api' || source === 'fallback',
    `expected an api/fallback stamp, got ${source}`,
  );
});

test('every registration CTA carries all three baked variants', () => {
  const ctas = document.querySelectorAll('[data-registration]');
  assert.ok(ctas.length > 0, 'expected at least one registration CTA');

  for (const cta of ctas) {
    for (const attr of [
      'data-open-label', 'data-open-url',
      'data-soon-label', 'data-soon-url',
      'data-closed-label', 'data-closed-url',
    ]) {
      assert.ok(cta.getAttribute(attr), `missing ${attr}`);
    }
  }
});

test('a CTA renders the variant matching the baked state', () => {
  const cta = document.querySelector('[data-registration]');
  const state = cta.getAttribute('data-state');
  assert.ok(['open', 'coming_soon', 'closed'].includes(state), `bad state: ${state}`);

  const expected = {
    open: 'data-open-label',
    coming_soon: 'data-soon-label',
    closed: 'data-closed-label',
  }[state];
  assert.equal(cta.textContent.trim(), cta.getAttribute(expected));
});

test('the registration strip still never links to its own section', () => {
  // Guards the fix from earlier on this branch against the rewrite.
  const strip = document.querySelector('#registration');
  const button = strip.querySelector('a[href]');
  const href = new URL(button.getAttribute('href'), 'https://twincitiesskiclub.org/');
  assert.notEqual(href.hash, '#registration');
});

test('registration_state is gone from the content schema', () => {
  const home = readFileSync(
    new URL('../src/content/pages/home.yaml', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(home, /registration_state/);

  const config = readFileSync(
    new URL('../src/content.config.ts', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(config, /registration_state/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `npm run build && node --test tests/seasonBuild.test.mjs`
Expected: FAIL — no `data-season-source` attribute, no `[data-registration]` elements.

- [ ] **Step 3: Extend the CTA resolver**

Replace `site/src/components/registrationCta.ts` entirely:

```typescript
import { getEntry } from 'astro:content';

import { fetchSeasonData } from '@/lib/seasonData';
import {
  deriveRegistrationState,
  type RegistrationState,
  type RegistrationWindows,
} from '@/lib/registrationState';

export interface RegistrationCta {
  /** Derived from the database windows, never authored. */
  state: RegistrationState;
  windows: RegistrationWindows;
  source: 'api' | 'fallback';
  generated_at: string | null;
  label_open: string;
  url_open?: string;
  label_coming_soon: string;
  url_coming_soon?: string;
  label_closed: string;
  url_closed?: string;
}

// Resolves the registration CTA for every consumer (nav, mobile menu, hero,
// strip). Labels and urls stay editorial in Keystatic; the STATE and the dates
// come from the app database, because a human toggle is exactly what used to
// drift out of sync with reality.
//
// With no season data the state is `closed`, which is the safe direction: its
// destination is tcsc.ski, which reads the database live and shows the real
// opening date regardless of what this static build believes. Falling back to
// `open` would send members at a form that may refuse them.
export async function getRegistrationCta(): Promise<RegistrationCta> {
  const home = await getEntry('home', 'home');
  const d = home?.data;
  const season = await fetchSeasonData();
  const windows: RegistrationWindows = season.primary ?? {};

  return {
    state: deriveRegistrationState(windows, Date.now()),
    windows,
    source: season.source,
    generated_at: season.generated_at,
    label_open: d?.cta_open_label ?? 'Register for the season',
    url_open: d?.cta_open_url ?? 'https://tcsc.ski/',
    label_coming_soon: d?.cta_coming_soon_label ?? 'Get on the list',
    url_coming_soon: d?.cta_coming_soon_url,
    label_closed: d?.cta_closed_label ?? 'Register',
    url_closed: d?.cta_closed_url ?? 'https://tcsc.ski/',
  };
}
```

- [ ] **Step 4: Bake all three variants into the CTA element**

Replace `site/src/components/CtaForState.astro` entirely:

```astro
---
import type { RegistrationState, RegistrationWindows } from '@/lib/registrationState';

interface Props {
  state: RegistrationState;
  windows?: RegistrationWindows;
  label_open: string; url_open?: string;
  label_coming_soon: string; url_coming_soon?: string;
  label_closed: string; url_closed?: string;
  variant?: 'on-navy' | 'on-paper';
  // Accepted and ignored. Nav and MobileNavPanel render this component as
  // `<CtaForState {...cta} />`, so every field getRegistrationCta returns has
  // to be nameable here or astro check fails on the spread.
  source?: 'api' | 'fallback';
  generated_at?: string | null;
}
const {
  state, windows = {},
  label_open, url_open,
  label_coming_soon, url_coming_soon,
  label_closed, url_closed,
  variant = 'on-navy',
} = Astro.props;

const label = state === 'open' ? label_open : state === 'coming_soon' ? label_coming_soon : label_closed;
const url = state === 'open' ? url_open : state === 'coming_soon' ? url_coming_soon : url_closed;
const disabled = !url;
const cls = variant === 'on-navy'
  ? 'inline-flex items-center px-5 py-3 rounded-md bg-mint text-navy font-semibold text-sm transition-colors duration-150 hover:bg-paper active:bg-mint/90'
  : 'inline-flex items-center px-5 py-3 rounded-md bg-navy text-mint font-semibold text-sm transition-colors duration-150 hover:bg-navy-deep active:bg-navy/90';

// Every state's rendered strings ship in the markup so the browser only
// CHOOSES a variant -- it holds no copy and does no date formatting. The
// timestamps ride along so it can re-derive the state as time passes.
const baked = {
  'data-registration': '',
  'data-state': state,
  'data-returning-start': windows.returning_start ?? '',
  'data-returning-end': windows.returning_end ?? '',
  'data-new-start': windows.new_start ?? '',
  'data-new-end': windows.new_end ?? '',
  'data-open-label': label_open,
  'data-open-url': url_open ?? '',
  'data-soon-label': label_coming_soon,
  'data-soon-url': url_coming_soon ?? '',
  'data-closed-label': label_closed,
  'data-closed-url': url_closed ?? '',
};
---
{disabled ? (
  <span class={cls + ' opacity-70 cursor-default'} {...baked}>{label}</span>
) : (
  <a href={url} class={cls} {...baked}>{label}</a>
)}
```

- [ ] **Step 5: Stamp the data source on the page**

In `site/src/layouts/BaseLayout.astro`, add to the frontmatter (after the existing imports):

```typescript
import { fetchSeasonData } from '@/lib/seasonData';

// Stamped on every page so a fallback build is one curl away from being
// detected. Deploys are deliberately never blocked by an unreachable API, so
// this is what stops a stale build from shipping invisibly.
const season = await fetchSeasonData();
```

Then change line 95's `<body>` tag to carry the stamp:

```astro
  <body
    class={`site-shell flex flex-col ${isHome ? 'bg-navy text-mint' : 'bg-paper text-ink'}`}
    data-season-source={season.source}
    data-season-generated-at={season.generated_at ?? ''}
  >
```

- [ ] **Step 6: Drive the strip subhead from the database**

In `site/src/pages/index.astro`, add to the imports:

```typescript
import { stripSubhead } from '@/lib/registrationCopy';
```

Replace the hardcoded `ctaStripSubhead` block with:

```typescript
const ctaStripSubhead = stripSubhead(cta.state, cta.windows);
```

In the same file, change the `<HeroHome ... />` invocation's state line from `state={h.registration_state}` (the field being deleted) to:

```astro
    state={cta.state}
    windows={cta.windows}
```

In `site/src/components/HeroHome.astro`, add the type import to the frontmatter:

```typescript
import type { RegistrationWindows } from '@/lib/registrationState';
```

add one line to `Props` after `state`:

```typescript
  windows?: RegistrationWindows;
```

and pass it down by adding one attribute to the `<CtaForState ... />` invocation:

```astro
          windows={props.windows}
```

- [ ] **Step 7: Retire the hardcoded-subhead assertions**

`site/tests/contentRefinements.test.mjs` pins the literal subhead this task is deleting. It will fail otherwise — this is expected, not a regression.

Delete line 37:

```javascript
const REGISTRATION_SUBHEAD = 'Returning members Aug 28; new members Sep 3.';
```

Replace it with the part of the copy that is still static:

```javascript
// The dates now come from the database, so only the ability line is a
// fixed string worth pinning here.
const ABILITY_LINE = 'Intermediate ability and up, no racing required.';
```

Then change the two assertions that used it. Line ~113 becomes:

```javascript
  assert.match(source.homePage, /stripSubhead\(cta\.state, cta\.windows\)/);
```

and line ~117 becomes:

```javascript
  assert.ok(registrationText.includes(ABILITY_LINE));
```

- [ ] **Step 8: Remove the manual toggle**

- Delete the `registration_state: coming_soon` line from `site/src/content/pages/home.yaml`.
- Delete the `registration_state:` line from `site/src/content.config.ts` (line ~208).
- Delete the `registration_state: fields.select({...})` block from `site/keystatic.config.ts` (starting line ~69, through its closing `}),`).

- [ ] **Step 9: Run the tests**

Run (from `site/`): `npm run build && node --test tests/seasonBuild.test.mjs && npm run check`
Expected: PASS — 5 passed, and `astro check` reports 0 errors.

- [ ] **Step 10: Add to the suite and commit**

Append ` tests/seasonBuild.test.mjs` to `test:refinement` in `site/package.json`.

Run: `npm run test:refinement`
Expected: PASS — including the pre-existing `contentRefinements` and `registrationCta` tests.

```bash
git add site render.yaml
git commit -m "feat(site): derive the registration CTA state from the database"
```

---

### Task 9: Flip the state in the browser

**Files:**
- Create: `site/src/components/registrationFlip.ts`
- Modify: `site/src/layouts/BaseLayout.astro` (mount the script once per page)
- Test: `site/tests/registrationFlip.test.mjs`
- Modify: `site/package.json`

**Interfaces:**
- Consumes: `deriveRegistrationState` (Task 5).
- Produces: a side-effecting module with no exports; runs on load and updates every `[data-registration]` element whose baked state no longer matches the current time.

- [ ] **Step 1: Write the failing test**

Create `site/tests/registrationFlip.test.mjs`. It drives the **real built bundle** against the **real built page**, the harness that caught the mobile-menu defect earlier on this branch:

```javascript
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// Astro names the bundle after the .astro file that declares the <script>
// (BaseLayout), not after registrationFlip.ts -- so find it by content.
const distDir = new URL('../dist/_astro/', import.meta.url);
const bundleName = readdirSync(distDir).find(
  (f) =>
    f.endsWith('.js') &&
    readFileSync(new URL(f, distDir), 'utf8').includes('data-registration'),
);
assert.ok(bundleName, 'a bundle containing the flip script should be built');
const bundlePath = new URL(bundleName, distDir);

const PAGE = `<!doctype html><html><body>
  <a data-registration
     data-state="coming_soon"
     data-returning-start="2026-08-28T17:00:00Z"
     data-returning-end="2026-09-02T05:00:00Z"
     data-new-start="2026-09-03T17:00:00Z"
     data-new-end="2026-09-20T05:00:00Z"
     data-open-label="Register for the season" data-open-url="https://tcsc.ski/"
     data-soon-label="Fall registration dates" data-soon-url="https://twincitiesskiclub.org/#registration"
     data-closed-label="How to register" data-closed-url="https://tcsc.ski/"
     href="https://twincitiesskiclub.org/#registration">Fall registration dates</a>
</body></html>`;

async function runFlipAt(isoNow) {
  const dom = new JSDOM(PAGE, { url: 'https://twincitiesskiclub.org/' });
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.Element = dom.window.Element;

  const realNow = Date.now;
  Date.now = () => Date.parse(isoNow);
  try {
    // Cache-bust so each run re-executes the side-effecting module.
    await import(`${bundlePath.href}?t=${encodeURIComponent(isoNow)}`);
  } finally {
    Date.now = realNow;
  }
  return dom.window.document.querySelector('[data-registration]');
}

test('leaves the DOM alone while the baked state is still correct', async () => {
  const cta = await runFlipAt('2026-07-30T12:00:00Z');
  assert.equal(cta.textContent, 'Fall registration dates');
  assert.equal(cta.getAttribute('href'), 'https://twincitiesskiclub.org/#registration');
});

test('flips to the open variant once registration has opened', async () => {
  const cta = await runFlipAt('2026-08-29T12:00:00Z');
  assert.equal(cta.textContent, 'Register for the season');
  assert.equal(cta.getAttribute('href'), 'https://tcsc.ski/');
  assert.equal(cta.getAttribute('data-state'), 'open');
});

test('flips to the closed variant once every window has passed', async () => {
  const cta = await runFlipAt('2026-10-01T12:00:00Z');
  assert.equal(cta.textContent, 'How to register');
  assert.equal(cta.getAttribute('href'), 'https://tcsc.ski/');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `npm run build && node --test tests/registrationFlip.test.mjs`
Expected: FAIL — assertion that the `registrationFlip` bundle should be built.

- [ ] **Step 3: Write minimal implementation**

Create `site/src/components/registrationFlip.ts`:

```typescript
// Re-derive the registration state in the browser.
//
// The site is a static build, so the state baked into the HTML is only true
// as of the last deploy. Rather than rebuild on a schedule or call an API on
// every page load, the CTA carries the real window timestamps and every
// state's copy; this picks the right variant for the CURRENT time. That makes
// the site correct at the exact minute registration opens, with no network.
//
// It holds no copy and formats no dates -- it only chooses among variants the
// build already rendered.
import { deriveRegistrationState } from '@/lib/registrationState';

type Variant = 'open' | 'coming_soon' | 'closed';

const ATTR: Record<Variant, { label: string; url: string }> = {
  open: { label: 'data-open-label', url: 'data-open-url' },
  coming_soon: { label: 'data-soon-label', url: 'data-soon-url' },
  closed: { label: 'data-closed-label', url: 'data-closed-url' },
};

function orNull(value: string | null): string | null {
  return value ? value : null;
}

for (const element of document.querySelectorAll<HTMLElement>('[data-registration]')) {
  const actual = deriveRegistrationState(
    {
      returning_start: orNull(element.getAttribute('data-returning-start')),
      returning_end: orNull(element.getAttribute('data-returning-end')),
      new_start: orNull(element.getAttribute('data-new-start')),
      new_end: orNull(element.getAttribute('data-new-end')),
    },
    Date.now(),
  );

  if (actual === element.getAttribute('data-state')) continue;

  const { label, url } = ATTR[actual];
  const nextLabel = element.getAttribute(label);
  const nextUrl = element.getAttribute(url);
  if (nextLabel) element.textContent = nextLabel;
  // hasAttribute rather than `instanceof HTMLAnchorElement`: the disabled
  // variant renders a <span> with no href, and an instanceof check would also
  // drag a DOM global into the jsdom test harness for no benefit.
  if (nextUrl && element.hasAttribute('href')) element.setAttribute('href', nextUrl);
  element.setAttribute('data-state', actual);
}
```

- [ ] **Step 4: Mount it once per page**

In `site/src/layouts/BaseLayout.astro`, immediately before the closing `</body>` tag (line ~104), add:

```astro
    <script>
      import '@/components/registrationFlip';
    </script>
```

- [ ] **Step 5: Run test to verify it passes**

Run (from `site/`): `npm run build && node --test tests/registrationFlip.test.mjs`
Expected: PASS — 3 passed

- [ ] **Step 6: Add to the suite and commit**

Append ` tests/registrationFlip.test.mjs` to `test:refinement` in `site/package.json`.

Run: `npm run test:refinement && npm run check`
Expected: PASS, 0 type errors.

```bash
git add site
git commit -m "feat(site): flip the registration CTA when the window opens"
```

---

### Task 10: Season cards from the database

**Files:**
- Create: `site/src/lib/seasonSlug.ts`
- Modify: `site/src/components/SeasonsGrid.astro:59-61`
- Modify: `site/src/content.config.ts:124-126` (redocument the card fields as fallback-only)
- Modify: `site/keystatic.config.ts:313-314` (relabel the two card fields)
- Test: `site/tests/seasonCards.test.mjs`
- Modify: `site/package.json`

**Interfaces:**
- Consumes: `fetchSeasonData` (Task 7), `deriveRegistrationState` (Task 5), `cardNote` (Task 6).
- Produces: nothing consumed by later tasks.

The content file slug maps to `season_type` by replacing `/` with `-`: `'fall/winter'` → `fall-winter`, `'spring/summer'` → `spring-summer`.

- [ ] **Step 1: Write the failing test**

Create `site/tests/seasonCards.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { seasonTypeToSlug } from '../src/lib/seasonSlug.ts';

test('maps a database season_type to its content file slug', () => {
  assert.equal(seasonTypeToSlug('fall/winter'), 'fall-winter');
  assert.equal(seasonTypeToSlug('spring/summer'), 'spring-summer');
  assert.equal(seasonTypeToSlug('legacy'), 'legacy');
  assert.equal(seasonTypeToSlug(''), '');
  assert.equal(seasonTypeToSlug(undefined), '');
});

test('the season cards render a registration line', () => {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document } = new JSDOM(html).window;
  const notes = document.querySelectorAll('[data-season-card-note]');
  assert.ok(notes.length > 0, 'expected at least one season card note');
  for (const note of notes) {
    assert.ok(note.textContent.trim().length > 0, 'card note should not be empty');
  }
});

test('the card fields are documented as fallback-only', () => {
  const config = readFileSync(
    new URL('../src/content.config.ts', import.meta.url),
    'utf8',
  );
  assert.match(config, /fallback/i, 'card schema should say these are fallbacks');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `npm run build && node --test tests/seasonCards.test.mjs`
Expected: FAIL — `ERR_MODULE_NOT_FOUND` for `src/lib/seasonSlug.ts`

- [ ] **Step 3: Write the slug mapper**

Create `site/src/lib/seasonSlug.ts`:

```typescript
// The database stores season_type as 'fall/winter'; the content collection
// keys the same season as the file `fall-winter.yaml`. One character apart,
// and worth naming rather than inlining a .replace() at the call site.
export function seasonTypeToSlug(seasonType: string | null | undefined): string {
  if (!seasonType) return '';
  return seasonType.replace(/\//g, '-');
}
```

- [ ] **Step 4: Drive the cards from the database**

In `site/src/components/SeasonsGrid.astro`, add to the frontmatter imports:

```typescript
import { fetchSeasonData } from '@/lib/seasonData';
import { deriveRegistrationState } from '@/lib/registrationState';
import { cardNote } from '@/lib/registrationCopy';
import { seasonTypeToSlug } from '@/lib/seasonSlug';
```

After the existing `seasons.sort(...)` line, add:

```typescript
// Registration lines come from the app database, keyed by season_type. A card
// with no matching database season keeps its committed copy -- the failure
// shows up as slightly stale prose, never as a wrong claim about whether
// registration is open.
const seasonData = await fetchSeasonData();
const dbBySlug = new Map(
  Object.entries(seasonData.by_type).map(([type, record]) => [
    seasonTypeToSlug(type),
    record,
  ]),
);

const now = Date.now();
function registrationLine(entry) {
  const record = dbBySlug.get(entry.id);
  if (!record) {
    return { note: entry.data.registration_note, open: entry.data.registration_open };
  }
  const note = cardNote(record.year ?? new Date().getFullYear(), record);
  return {
    note: note ?? entry.data.registration_note,
    open: deriveRegistrationState(record, now) === 'open',
  };
}

// Resolved once per card, not once per attribute that reads it.
const cardLines = new Map(seasons.map((s) => [s.id, registrationLine(s)]));
```

Then replace exactly this block (`site/src/components/SeasonsGrid.astro:59-61`):

```astro
            <p class:list={['text-[13px]', s.data.registration_open ? `font-semibold ${accent}` : muted]}>
              {s.data.registration_note}
            </p>
```

with this, which keeps the identical class logic and only changes where the two values come from:

```astro
            <p
              data-season-card-note
              class:list={['text-[13px]', cardLines.get(s.id).open ? `font-semibold ${accent}` : muted]}
            >
              {cardLines.get(s.id).note}
            </p>
```

- [ ] **Step 5: Redocument the fallback fields**

In `site/src/content.config.ts`, replace the comment above `registration_note` (line ~124) with:

```typescript
      // FALLBACK ONLY. The live registration line comes from the app database
      // (see src/components/SeasonsGrid.astro). These two fields are used when
      // the season API is unreachable at build time, or when no database
      // season carries a matching season_type.
```

In `site/keystatic.config.ts` (lines ~313-314), relabel both fields so an editor knows they are not the live values:

```typescript
        registration_note: fields.text({ label: 'Registration status line (fallback only — live text comes from the app)', validation: { isRequired: true } }),
        registration_open: fields.checkbox({ label: 'Highlight registration line (fallback only)', defaultValue: false }),
```

- [ ] **Step 6: Run test to verify it passes**

Run (from `site/`): `npm run build && node --test tests/seasonCards.test.mjs && npm run check`
Expected: PASS — 3 passed, 0 type errors.

- [ ] **Step 7: Add to the suite and commit**

Append ` tests/seasonCards.test.mjs` to `test:refinement` in `site/package.json`.

Run: `npm run test:refinement`
Expected: PASS

```bash
git add site
git commit -m "feat(site): drive the season cards from the database"
```

---

### Task 11: Prove the fallback path and finish

**Files:**
- Test: `site/tests/seasonFallback.test.mjs`
- Modify: `site/package.json`
- Modify: `CLAUDE.md` (document the new data flow)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

This task exists because the chosen failure policy — never block a deploy — is only safe if the fallback is actually exercised and actually detectable. Asserting it is the mitigation.

- [ ] **Step 1: Write the failing test**

Create `site/tests/seasonFallback.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// Builds the whole site against a dead endpoint. Slow by nature: this is the
// only way to prove the accepted tradeoff (a deploy is never blocked) does not
// silently ship a page that claims registration is open.
test('a build against a dead API still succeeds and announces itself', () => {
  const root = new URL('..', import.meta.url).pathname;

  execFileSync('npm', ['run', 'build'], {
    cwd: root,
    env: { ...process.env, PUBLIC_SEASON_API_URL: 'http://127.0.0.1:1/api/season' },
    stdio: 'pipe',
  });

  const html = readFileSync(`${root}/dist/index.html`, 'utf8');
  const { document } = new JSDOM(html).window;

  assert.equal(document.body.getAttribute('data-season-source'), 'fallback');

  // Never claims open registration without data to back it.
  for (const cta of document.querySelectorAll('[data-registration]')) {
    assert.equal(cta.getAttribute('data-state'), 'closed');
  }

  // And the destination is the app, which reads the database live.
  const strip = document.querySelector('#registration a[href]');
  assert.equal(strip.getAttribute('href'), 'https://tcsc.ski/');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `site/`): `node --test tests/seasonFallback.test.mjs`
Expected: FAIL if any part of the fallback chain is wrong. If Tasks 7–10 are correct it may pass immediately — that is acceptable for this task only, because it is a characterization test of an already-implemented policy. Confirm it genuinely exercises the path by checking the build output contains the `[season]` warning.

- [ ] **Step 3: Restore a normal build**

Run (from `site/`): `npm run build`
Expected: `data-season-source="api"` when the Flask app is reachable, `fallback` otherwise. Either is a valid local result; note which you got.

- [ ] **Step 4: Document the data flow**

In `CLAUDE.md`, add a section after the "Season Management" section:

```markdown
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
```

- [ ] **Step 5: Full verification**

Run from the repo root:
```bash
./run-tests.sh
cd site && npm run test:refinement && npm run test:sponsors && npm run check
```
Expected: the Python suite passes, all site suites pass, 0 type errors.

- [ ] **Step 6: Commit**

Append ` tests/seasonFallback.test.mjs` to `test:refinement` in `site/package.json`.

```bash
git add site CLAUDE.md
git commit -m "test(site): prove the season fallback ships detectable, not silent"
```

---

## Verification Checklist

Before opening the PR:

- [ ] `./run-tests.sh` passes from the repo root.
- [ ] `npm run test:refinement`, `npm run test:sponsors`, and `npm run check` pass from `site/`.
- [ ] `curl -s localhost:5001/api/season` returns Z-suffixed timestamps against a real database.
- [ ] `dist/index.html` carries `data-season-source="api"` when the app is reachable.
- [ ] `grep -rn registration_state site/src site/keystatic.config.ts` returns nothing.
- [ ] The bottom CTA strip button does not link to `#registration`.
- [ ] The mobile menu closes when its CTA is tapped.
