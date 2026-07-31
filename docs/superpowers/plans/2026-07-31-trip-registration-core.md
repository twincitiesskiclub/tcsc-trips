# Trip Registration Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Native trip registration on tcsc.ski — series/editions data model, atomic form+payment-hold flow, question builder data layer, member form, admin roster.

**Architecture:** Mirrors the events system (`app/events/`) throughout: a `TripRegistration` row is created with the Stripe hold; `custom_questions` JSON on the edition drives both the public form and dynamic roster columns; templates seed questions. New `app/trips/` package parallel to `app/events/`. Slack integration (invites, DMs, unfurls, announcement button) is a **separate plan**: `2026-07-31-trip-registration-slack.md`.

**Tech Stack:** Flask + SQLAlchemy + Alembic, Stripe (manual capture, unchanged), vanilla JS IIFE pattern, Tailwind (public page opts in), pytest against local Postgres.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-31-trip-registration-redesign-design.md`. Payments stay **manual capture** — do not change capture method or add saved-card flows.
- Prices in **cents**; timestamps **UTC naive** in DB (`datetime.utcnow`), compare signup windows in UTC like `app/routes/trips.py` does today.
- Status classes are **plain string classes, not Enums** (match `RegistrationStatus` in `app/events/models.py`).
- Tests run against the real local Postgres (`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`) via `./run-tests.sh`. **Never** `db.create_all()`. Every created row must be cleaned up (slug-scoped autouse fixture, mirroring `tests/events/conftest.py`). Test slugs must be registered in the conftest tuple.
- No pre-fill of member data in the public form (deferred to auth project). Email gate = `User.status == UserStatus.ACTIVE`.
- Server→client data via `<script type="application/json">` islands (CSP); client JS mirrors server rules with a comment saying so.
- All migrations: `flask db migrate` style files under `migrations/versions/` with explicit `revision`/`down_revision`; current head is `539ad532aeb3`.
- Commit after every task; branch `trip-registration-redesign`.

---

### Task 1: Models — TripSeries, Trip edition fields, TripRegistration, TripProfile

**Files:**
- Create: `app/trips/__init__.py` (empty), `app/trips/models.py`
- Modify: `app/models.py` (Trip: add `series_id`; keep everything else — `slack_channel_name` stays until the migration in Task 2 moves its data)
- Test: `tests/trips/__init__.py`, `tests/trips/conftest.py`, `tests/trips/test_models.py`

**Interfaces:**
- Produces: `TripSeries` (`app/trips/models.py`), `TripRegistration`, `TripProfile`, `TripRegistrationStatus` with values `PENDING_PAYMENT="pending_payment"`, `PENDING="pending"`, `CONFIRMED="confirmed"`, `CANCELLED="cancelled"`, `ALL=[...]`. `Trip.series_id`, `Trip.custom_questions`, `Trip.registrations` relationship, `TripSeries.editions` relationship, `TripSeries.current_edition()` method.
- Consumes: `db` from `app/models.py`; `Trip`, `User` models.

- [ ] **Step 1: Write the failing model tests**

`tests/trips/conftest.py` (mirror `tests/events/conftest.py` exactly — `db_session` yields the `db` object, autouse cleanup deletes by slug in FK order):

```python
import pytest

from app import create_app
from app.models import db, Payment, Trip, User
from app.trips.models import TripProfile, TripRegistration, TripSeries

TEST_TRIP_SLUGS = (
    "test-trip-models",
    "test-trip-models-2027",
    "test-trip-service",
    "test-trip-service-2027",
    "test-trip-routes",
    "test-trip-routes-2027",
    "test-trip-admin",
    "test-trip-admin-2027",
    "test-trip-admin-2028",
    "test-trip-admin-2100",
    "test-trip-webhook",
    "test-trip-webhook-2027",
)
TEST_USER_EMAILS = (
    "trip-member@example.com",
    "trip-inactive@example.com",
    "trip-second@example.com",
)


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db
        db.session.rollback()


def _delete_test_trips():
    # Scalar-ID queries only: loading ORM instances (e.g. series.editions)
    # and then bulk-deleting the children makes the later parent delete
    # raise StaleDataError. Mirrors the events fixture pattern.
    series_ids = [
        sid for (sid,) in db.session.query(TripSeries.id).filter(
            TripSeries.slug.in_(TEST_TRIP_SLUGS))
    ]
    edition_filter = Trip.slug.in_(TEST_TRIP_SLUGS)
    if series_ids:
        edition_filter = db.or_(edition_filter, Trip.series_id.in_(series_ids))
    edition_ids = [
        tid for (tid,) in db.session.query(Trip.id).filter(edition_filter)
    ]
    if edition_ids:
        Payment.query.filter(Payment.trip_id.in_(edition_ids)).delete(
            synchronize_session=False
        )
        TripRegistration.query.filter(
            TripRegistration.trip_id.in_(edition_ids)
        ).delete(synchronize_session=False)
        Trip.query.filter(Trip.id.in_(edition_ids)).delete(
            synchronize_session=False
        )
    if series_ids:
        TripSeries.query.filter(TripSeries.id.in_(series_ids)).delete(
            synchronize_session=False
        )
    user_ids = [
        uid for (uid,) in db.session.query(User.id).filter(
            User.email.in_(TEST_USER_EMAILS))
    ]
    if user_ids:
        TripProfile.query.filter(
            TripProfile.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        User.query.filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )
    db.session.commit()
    db.session.expire_all()


@pytest.fixture(autouse=True)
def cleanup_trip_records(db_session):
    _delete_test_trips()
    yield
    db_session.session.rollback()
    _delete_test_trips()
```

`tests/trips/test_models.py`:

```python
from datetime import datetime, timedelta

from app.models import db, Trip, User
from app.constants import UserStatus
from app.trips.models import (
    TripProfile,
    TripRegistration,
    TripRegistrationStatus,
    TripSeries,
)


def _series(slug="test-trip-models"):
    series = TripSeries(
        slug=slug, name="TEST Trip", destination="Testville",
        slack_channel_name="test-trip-channel",
    )
    db.session.add(series)
    db.session.flush()
    return series


def _edition(series, slug="test-trip-models-2027", start=None, status="active"):
    start = start or datetime(2099, 1, 10)
    trip = Trip(
        slug=slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id,
        max_participants_standard=20, max_participants_extra=5,
        start_date=start, end_date=start + timedelta(days=2),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status=status,
        custom_questions=[],
    )
    db.session.add(trip)
    db.session.flush()
    return trip


def test_series_edition_relationship_and_current_edition(db_session):
    series = _series()
    edition = _edition(series)
    db.session.commit()
    assert edition in series.editions
    assert series.current_edition().id == edition.id


def test_current_edition_prefers_upcoming_active_over_past(db_session):
    series = _series()
    past = _edition(series, slug="test-trip-models-2027",
                    start=datetime(2020, 1, 10))
    upcoming = _edition(series, slug="test-trip-routes-2027",
                        start=datetime(2099, 1, 10))
    db.session.commit()
    assert series.current_edition().id == upcoming.id


def test_registration_unique_per_member_per_edition(db_session):
    series = _series()
    edition = _edition(series)
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    reg = TripRegistration(
        trip_id=edition.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
    )
    db.session.add(reg)
    db.session.commit()
    import sqlalchemy.exc
    import pytest as _pytest
    dupe = TripRegistration(
        trip_id=edition.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
    )
    db.session.add(dupe)
    with _pytest.raises(sqlalchemy.exc.IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_trip_profile_one_row_per_user(db_session):
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    profile = TripProfile(
        user_id=user.id, can_drive=True, seat_capacity=3,
        bike_capacity=2, hitch_size="2", region_code="4",
        dietary_restrictions=["Vegetarian"], dietary_other="",
        has_tent=False,
    )
    db.session.add(profile)
    db.session.commit()
    assert user.trip_profile.seat_capacity == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_models.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'app.trips'` (then, after models exist but before the migration in Task 2, `ProgrammingError: relation "trip_series" does not exist` — that's the expected state at the end of this task; the tests go green in Task 2).

- [ ] **Step 3: Write the models**

`app/trips/models.py`:

```python
from datetime import datetime

from app.models import db


class TripRegistrationStatus:
    PENDING_PAYMENT = "pending_payment"  # row created, card not yet authorized
    PENDING = "pending"                  # hold placed, awaiting roster confirm
    CONFIRMED = "confirmed"              # payment captured
    CANCELLED = "cancelled"              # hold released / registration void
    ALL = [PENDING_PAYMENT, PENDING, CONFIRMED, CANCELLED]


class TripSeries(db.Model):
    __tablename__ = "trip_series"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    slack_channel_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    editions = db.relationship(
        "Trip", backref="series", lazy=True,
        order_by="Trip.start_date.desc()",
    )

    def current_edition(self):
        """The edition the public URL should show.

        Preference order: soonest upcoming non-draft edition, else the most
        recently started non-draft edition, else the newest edition of any
        status (so a fresh draft-only series still resolves for admins).
        """
        now = datetime.utcnow()
        published = [e for e in self.editions if e.status != "draft"]
        upcoming = [e for e in published if e.start_date >= now]
        if upcoming:
            return min(upcoming, key=lambda e: e.start_date)
        if published:
            return max(published, key=lambda e: e.start_date)
        if self.editions:
            return max(self.editions, key=lambda e: e.start_date)
        return None

    def __repr__(self):
        return f"<TripSeries {self.slug}>"


class TripRegistration(db.Model):
    __tablename__ = "trip_registrations"
    __table_args__ = (
        db.UniqueConstraint("trip_id", "user_id", name="uq_trip_registration_member"),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(
        db.Integer, db.ForeignKey("trips.id"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    status = db.Column(
        db.String(50), nullable=False,
        default=TripRegistrationStatus.PENDING_PAYMENT,
    )
    answers = db.Column(db.JSON, nullable=False, default=dict)
    price_tier = db.Column(db.String(10), nullable=False)  # 'low' | 'high'
    amount_cents = db.Column(db.Integer, nullable=False)
    payment_intent_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    trip = db.relationship(
        "Trip", backref=db.backref("registrations", lazy=True)
    )
    user = db.relationship(
        "User", backref=db.backref("trip_registrations", lazy=True)
    )

    def __repr__(self):
        return f"<TripRegistration {self.id} trip={self.trip_id} user={self.user_id}>"


class TripProfile(db.Model):
    """Semi-stable per-member trip facts. Real columns because carpool and
    logistics queries filter on them. Updated (upserted) on every
    registration submit; never pre-filled into forms until the auth project.
    """

    __tablename__ = "trip_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
    can_drive = db.Column(db.Boolean)
    seat_capacity = db.Column(db.Integer)
    bike_capacity = db.Column(db.Integer)
    hitch_size = db.Column(db.String(10))       # '', '1.25', '2'
    region_code = db.Column(db.String(10))
    dietary_restrictions = db.Column(db.JSON, nullable=False, default=list)
    dietary_other = db.Column(db.String(255), nullable=False, default="")
    has_tent = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    user = db.relationship(
        "User", backref=db.backref("trip_profile", uselist=False)
    )

    def __repr__(self):
        return f"<TripProfile user={self.user_id}>"
```

- [ ] **Step 4: Add edition columns to `Trip` in `app/models.py`**

In `class Trip`, directly under the `slug` column, add:

```python
    series_id = db.Column(db.Integer, db.ForeignKey('trip_series.id'), nullable=True)
    custom_questions = db.Column(JSON, nullable=False, default=list)
```

(`JSON` is already imported at the top of `app/models.py`.) `series_id` stays nullable in the model; the Task 2 migration backfills every row and application code treats it as required for new editions.

- [ ] **Step 5: Import trips models at app startup**

In `app/__init__.py`, next to the existing `from .events import models as events_models  # noqa` style import (find the events models import; if events models are imported via `from .events.models import ...` in a blueprint, instead add alongside the model imports), add:

```python
from .trips import models as trips_models  # noqa: F401  (register tables with SQLAlchemy)
```

- [ ] **Step 6: Run the model tests — expect table-missing errors only**

Run: `./run-tests.sh tests/trips/test_models.py -v`
Expected: FAIL with `ProgrammingError` mentioning `relation "trip_series" does not exist` (NOT import errors). That proves the models are wired; tables arrive with Task 2's migration.

- [ ] **Step 7: Commit**

```bash
git add app/trips/__init__.py app/trips/models.py app/models.py app/__init__.py tests/trips/
git commit -m "feat(trips): TripSeries, TripRegistration, TripProfile models"
```

---

### Task 2: Migration — create tables, convert existing trips to series/editions

**Files:**
- Create: `migrations/versions/a7c1e5f2b9d3_trip_series_registrations_profiles.py`
- Test: `tests/trips/test_models.py` (goes green here), plus migration smoke via `flask db upgrade`

**Interfaces:**
- Consumes: Task 1 models. Current alembic head `539ad532aeb3`.
- Produces: tables `trip_series`, `trip_registrations`, `trip_profiles`; `trips.series_id` + `trips.custom_questions` columns; every existing trip re-parented under a series carrying its `slack_channel_name`.

- [ ] **Step 1: Write the migration**

`migrations/versions/a7c1e5f2b9d3_trip_series_registrations_profiles.py`:

```python
"""trip series, registrations, profiles

Revision ID: a7c1e5f2b9d3
Revises: 539ad532aeb3
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7c1e5f2b9d3'
down_revision = '539ad532aeb3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trip_series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('destination', sa.String(length=255), nullable=False),
        sa.Column('slack_channel_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_trip_series_slug'),
    )
    op.create_index('ix_trip_series_slug', 'trip_series', ['slug'])

    op.create_table(
        'trip_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('price_tier', sa.String(length=10), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trip_id', 'user_id',
                            name='uq_trip_registration_member'),
    )

    op.create_table(
        'trip_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('can_drive', sa.Boolean(), nullable=True),
        sa.Column('seat_capacity', sa.Integer(), nullable=True),
        sa.Column('bike_capacity', sa.Integer(), nullable=True),
        sa.Column('hitch_size', sa.String(length=10), nullable=True),
        sa.Column('region_code', sa.String(length=10), nullable=True),
        sa.Column('dietary_restrictions', sa.JSON(), nullable=False),
        sa.Column('dietary_other', sa.String(length=255), nullable=False),
        sa.Column('has_tent', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_trip_profile_user'),
    )

    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('series_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column('custom_questions', sa.JSON(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_trips_series_id', 'trip_series', ['series_id'], ['id']
        )

    # Data migration: each existing trip becomes the first edition of a new
    # series that inherits its slug, name, destination and Slack channel.
    conn = op.get_bind()
    trips = conn.execute(sa.text(
        "SELECT id, slug, name, destination, slack_channel_name FROM trips"
    )).fetchall()
    for trip in trips:
        series_id = conn.execute(
            sa.text(
                "INSERT INTO trip_series "
                "(slug, name, destination, slack_channel_name, created_at, updated_at) "
                "VALUES (:slug, :name, :destination, :channel, NOW(), NOW()) "
                "RETURNING id"
            ),
            {"slug": trip.slug, "name": trip.name,
             "destination": trip.destination,
             "channel": trip.slack_channel_name},
        ).scalar()
        conn.execute(
            sa.text(
                "UPDATE trips SET series_id = :sid, custom_questions = '[]' "
                "WHERE id = :tid"
            ),
            {"sid": series_id, "tid": trip.id},
        )
    conn.execute(sa.text(
        "UPDATE trips SET custom_questions = '[]' WHERE custom_questions IS NULL"
    ))


def downgrade():
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trips_series_id', type_='foreignkey')
        batch_op.drop_column('custom_questions')
        batch_op.drop_column('series_id')
    op.drop_table('trip_profiles')
    op.drop_table('trip_registrations')
    op.drop_index('ix_trip_series_slug', table_name='trip_series')
    op.drop_table('trip_series')
```

- [ ] **Step 2: Run the migration**

Run: `source env/bin/activate 2>/dev/null; flask db upgrade` (with the dev DB running — start via `./scripts/dev.sh` or ensure the `tcsc-postgres` container is up: `docker start tcsc-postgres`).
Expected: `Running upgrade 539ad532aeb3 -> a7c1e5f2b9d3`.

- [ ] **Step 3: Verify the data migration**

Run: `psql postgresql://tcsc:tcsc@localhost:5432/tcsc_trips -c "SELECT t.slug, s.slug AS series_slug, s.slack_channel_name FROM trips t JOIN trip_series s ON t.series_id = s.id;"`
Expected: one row per pre-existing trip, `series_slug` equal to the trip's slug.

- [ ] **Step 4: Run the Task 1 model tests**

Run: `./run-tests.sh tests/trips/test_models.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Run the full suite to catch regressions**

Run: `./run-tests.sh`
Expected: no new failures relative to the pre-task baseline (record baseline first with `git stash && ./run-tests.sh; git stash pop` if unsure).

- [ ] **Step 6: Commit**

```bash
git add migrations/versions/a7c1e5f2b9d3_trip_series_registrations_profiles.py
git commit -m "feat(trips): migration for series/registrations/profiles + data backfill"
```

---

### Task 3: Question schema, validation, and trip templates (seeded from historical forms)

**Files:**
- Create: `app/trips/questions.py`, `config/trip_templates.yaml`
- Test: `tests/trips/test_questions.py`

**Interfaces:**
- Produces:
  - `validate_trip_question(question, index=0) -> None` (raises `ValueError`)
  - `validate_questions(questions) -> None`
  - `load_trip_templates() -> dict[str, dict]`, `get_template(key) -> dict | None`, `apply_template(trip, template_key) -> None` (mutates, no commit), `_reset_cache()`
  - Question dict schema: `key` (str, `[a-z0-9_]+`), `label` (str), `type` ∈ `{"text","choice","multi_choice","yes_no"}`, `options` (list, required for choice/multi_choice), `max_selections` (int ≥ 1, optional, multi_choice only), `required` (bool), `help_text` (str, optional), `visible_if` (optional `{"question": <key of an earlier yes_no question>, "equals": "yes"|"no"}`)
- Consumes: `Trip` model (Task 1).

The **fixed profile section** (driving, region, dietary, tent) is NOT part of `custom_questions` — it is hardcoded in the form (Task 7) and maps to `TripProfile` columns. Templates carry only per-trip questions.

- [ ] **Step 1: Write failing tests**

`tests/trips/test_questions.py`:

```python
import pytest

from app.trips import questions as tq


def _q(**overrides):
    base = {"key": "chore", "label": "Which task do you prefer?",
            "type": "choice", "options": ["Cooking", "Cleaning"],
            "required": True}
    base.update(overrides)
    return base


def test_valid_question_passes():
    tq.validate_trip_question(_q())


def test_missing_field_raises():
    q = _q()
    del q["label"]
    with pytest.raises(ValueError, match="missing 'label'"):
        tq.validate_trip_question(q)


def test_invalid_type_raises():
    with pytest.raises(ValueError, match="invalid type"):
        tq.validate_trip_question(_q(type="dropdown"))


def test_multi_choice_max_selections_must_be_positive_int():
    with pytest.raises(ValueError, match="max_selections"):
        tq.validate_trip_question(
            _q(type="multi_choice", max_selections=0))


def test_visible_if_must_reference_earlier_yes_no():
    qs = [
        _q(key="depart", type="text", options=[]),
        _q(key="follow", visible_if={"question": "depart", "equals": "yes"}),
    ]
    with pytest.raises(ValueError, match="yes_no"):
        tq.validate_questions(qs)


def test_visible_if_forward_reference_rejected():
    qs = [
        _q(key="follow", visible_if={"question": "later", "equals": "yes"}),
        _q(key="later", type="yes_no", options=[]),
    ]
    with pytest.raises(ValueError, match="earlier"):
        tq.validate_questions(qs)


def test_duplicate_key_rejected():
    with pytest.raises(ValueError, match="duplicated"):
        tq.validate_questions([_q(key="a"), _q(key="a")])


def test_templates_load_and_validate():
    tq._reset_cache()
    templates = tq.load_trip_templates()
    for expected in ("race_weekend", "cuyuna_camping", "pre_birkie",
                     "sisu", "birkie", "gbc", "hayward", "blank"):
        assert expected in templates
    for template in templates.values():
        tq.validate_questions(template["custom_questions"])


def test_visible_if_happy_path_validates():
    qs = [
        _q(key="can_stop", type="yes_no", options=[]),
        _q(key="stop_where", type="text", options=[],
           visible_if={"question": "can_stop", "equals": "yes"}),
    ]
    tq.validate_questions(qs)  # must not raise


def test_apply_template_deep_copies():
    tq._reset_cache()
    template = tq.get_template("gbc")
    class FakeTrip:
        custom_questions = None
        template_key = None
    trip = FakeTrip()
    tq.apply_template(trip, "gbc")
    assert trip.template_key == "gbc"
    trip.custom_questions[0]["label"] = "mutated"
    assert tq.get_template("gbc")["custom_questions"][0]["label"] != "mutated"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_questions.py -v`
Expected: FAIL, `No module named 'app.trips.questions'` (or attribute errors).

- [ ] **Step 3: Write `app/trips/questions.py`**

```python
"""Trip custom-question schema: validation + template library.

Parallel to app/events/templates.py, with three additions the trip forms
need: multi_choice (with an optional pick-up-to-N cap), yes_no, and
visible_if conditional display keyed to an earlier yes_no question.
"""
from copy import deepcopy
from pathlib import Path
import re

import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "trip_templates.yaml"
_template_cache = None

QUESTION_TYPES = {"text", "choice", "multi_choice", "yes_no"}
_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _offender(index, question):
    key = question.get("key") if isinstance(question, dict) else None
    return f"Question '{key}'" if key else f"Question {index + 1}"


def validate_trip_question(question, index=0):
    name = _offender(index, question)
    if not isinstance(question, dict):
        raise ValueError(f"{name} must be a mapping")
    for field in ("key", "label", "type", "required"):
        if field not in question:
            raise ValueError(f"{name} is missing '{field}'")
    if not isinstance(question["key"], str) or not _KEY_PATTERN.match(question["key"]):
        raise ValueError(
            f"{name} key must match [a-z0-9_]+ (got {question['key']!r})")
    qtype = question["type"]
    if qtype not in QUESTION_TYPES:
        raise ValueError(f"{name} has invalid type '{qtype}'")
    if not isinstance(question["required"], bool):
        raise ValueError(f"{name} field 'required' must be a bool")
    if qtype in ("choice", "multi_choice"):
        if not isinstance(question.get("options"), list) or not question["options"]:
            raise ValueError(f"{name} must have a non-empty 'options' list")
    if "max_selections" in question and question["max_selections"] is not None:
        if qtype != "multi_choice":
            raise ValueError(f"{name}: max_selections only applies to multi_choice")
        cap = question["max_selections"]
        if type(cap) is not int or cap < 1:
            raise ValueError(f"{name}: max_selections must be a positive int")
    visible_if = question.get("visible_if")
    if visible_if is not None:
        if (not isinstance(visible_if, dict)
                or set(visible_if) != {"question", "equals"}
                or visible_if["equals"] not in ("yes", "no")):
            raise ValueError(
                f"{name}: visible_if must be "
                "{'question': <key>, 'equals': 'yes'|'no'}")


def validate_questions(questions):
    """Validate a full list: per-question rules plus cross-question rules
    (unique keys; visible_if targets an EARLIER yes_no question)."""
    if not isinstance(questions, list):
        raise ValueError("Custom questions must be a list")
    seen = {}
    for index, question in enumerate(questions):
        validate_trip_question(question, index)
        key = question["key"]
        if key in seen:
            raise ValueError(f"Question key '{key}' is duplicated.")
        visible_if = question.get("visible_if")
        if visible_if is not None:
            target = visible_if["question"]
            if target not in seen:
                raise ValueError(
                    f"Question '{key}': visible_if must reference an "
                    f"earlier question (got '{target}').")
            if seen[target]["type"] != "yes_no":
                raise ValueError(
                    f"Question '{key}': visible_if target '{target}' "
                    "must be a yes_no question.")
        seen[key] = question


def load_trip_templates():
    global _template_cache
    if _template_cache is None:
        try:
            with open(_CONFIG_PATH) as handle:
                config = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"trip_templates.yaml is invalid YAML: {exc}")
        templates = (config or {}).get("templates")
        if not isinstance(templates, dict):
            raise ValueError("trip_templates.yaml must have a 'templates' mapping")
        for key, template in templates.items():
            if "name" not in template:
                raise ValueError(f"Template '{key}' is missing 'name'")
            if not isinstance(template.get("custom_questions"), list):
                raise ValueError(
                    f"Template '{key}' field 'custom_questions' must be a list")
            validate_questions(template["custom_questions"])
        _template_cache = templates
    return _template_cache


def get_template(key):
    return load_trip_templates().get(key)


def apply_template(trip, template_key):
    template = get_template(template_key)
    if template is None:
        raise ValueError(f"Unknown trip template '{template_key}'")
    trip.template_key = template_key
    trip.custom_questions = deepcopy(template["custom_questions"])


def _reset_cache():
    global _template_cache
    _template_cache = None
```

Note: `apply_template` sets `trip.template_key`; `Trip` has no such column and doesn't need one persisted — it's harmless instance state used by the admin form. Do NOT add a column.

- [ ] **Step 4: Write `config/trip_templates.yaml`**

Anchors keep the shared race-weekend base DRY. **The departure-time option lists below are provisional reconstructions from screenshots — Step 6 verifies them against the live Slack workflows before launch.**

```yaml
# Trip question templates, seeded from the 2025-26 Slack Workflow Builder
# forms so trip admins start from done. Profile facts (driving, region,
# dietary, tent) are NOT here - the registration form asks them in a fixed
# section that writes to TripProfile.
shared:
  race_departure: &race_departure
    key: departure_time
    label: Approximately what time would you like to leave the Twin Cities?
    type: multi_choice
    max_selections: 8
    required: true
    help_text: Select every window that could work for you.
    options:
      - Wednesday afternoon
      - Wednesday evening
      - Thursday morning
      - Thursday afternoon
      - Thursday evening
      - Friday morning
      - Friday afternoon
      - Friday evening
  chore: &chore
    key: chore_preference
    label: Everyone needs to pitch in for things to run smoothly. Which task do you prefer to help with?
    type: choice
    required: true
    options: [Cooking, Cleaning, "I'm indifferent"]
  bed_share: &bed_share
    key: bed_share
    label: Who are you willing to share a bed with?
    type: text
    required: true
    help_text: Specific names are helpful.
  room_share: &room_share
    key: room_share
    label: Who are you willing to share a room with?
    type: choice
    required: true
    options:
      - Only people with my own gender identity
      - People with any gender identity
  vibe: &vibe
    key: vibe
    label: What is your preferred vibe?
    type: choice
    required: true
    options:
      - Early bird cabin (expect noise in the morning)
      - Night owl cabin (expect noise in the evening)
      - "I'm indifferent"

templates:
  blank:
    name: Blank
    custom_questions: []

  race_weekend:
    name: Race weekend (generic base)
    custom_questions:
      - *race_departure
      - *chore
      - *bed_share
      - *room_share

  gbc:
    name: Great Bear Chase
    custom_questions:
      - <<: *race_departure
        help_text: If you select a Wednesday time, W dinner, Thu breakfast, and Thu lunch are on your own.
      - *chore
      - *bed_share
      - *room_share

  pre_birkie:
    name: Pre-Birkie
    custom_questions:
      - *race_departure
      - *chore
      - *bed_share
      - *room_share
      - key: event_choice
        label: Which event are you participating in?
        type: choice
        required: true
        options:
          - Pre-Birkie 42K (Saturday)
          - Pre-Birkie 26K (Saturday)
          - North End Classic (Sunday)
          - Techno corner baby!

  sisu:
    name: Sisu Ski Fest
    custom_questions:
      - <<: *race_departure
        max_selections: 12
        help_text: If you select a Wednesday time, W dinner, Thu breakfast, and Thu lunch are on your own.
      - *chore
      - *bed_share
      - *room_share
      - *vibe
      - key: event_choice
        label: Which event are you participating in?
        type: choice
        required: true
        options:
          - Sisu 42K Freestyle
          - Sisu 21K Freestyle
          - Sisu 21K Classic
          - Sisu 10K
          - Not racing / cheering

  birkie:
    name: Birkie
    custom_questions:
      - *race_departure
      - *chore
      - *bed_share
      - *room_share
      - key: event_choice
        label: Which of the following events will you participate in?
        type: choice
        required: false
        options:
          - Birkie Skate 50K
          - Birkie Classic 55K
          - Kortelopet 29K
          - Prince Haakon 15K
          - Not racing / cheering

  hayward:
    name: Hayward training weekend
    custom_questions:
      - *race_departure
      - *chore
      - *bed_share
      - *room_share
      - *vibe

  cuyuna_camping:
    name: Cuyuna camping
    custom_questions:
      - key: departure_time
        label: Approximately what time would you like to leave the Twin Cities?
        type: choice
        required: true
        options:
          - Friday morning
          - Friday around noon
          - Friday mid-afternoon
          - Friday evening
          - Saturday morning
      - key: tent_share
        label: Who are you willing to share a tent with (specific names please)?
        type: text
        required: true
      - key: borrow_gear
        label: Do you need to borrow either or both of the following?
        type: multi_choice
        required: false
        options: [Sleeping bag, Sleeping pad]
      - key: activities
        label: Which of the following activities do you hope to partake in during the weekend?
        type: multi_choice
        required: true
        options:
          - Mountain biking
          - Roller skiing
          - Trail running
          - Swimming
          - Canoe / Kayak
          - Sauna
          - Exploring town
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./run-tests.sh tests/trips/test_questions.py -v`
Expected: all PASS.

- [ ] **Step 6: Record the option-list verification TODO where it will be seen**

The provisional option lists (departure times for all race trips; Sisu and Birkie event lists; Cuyuna departure windows) must be checked against the live Slack workflows before any trip goes active. Add one line to the PR description when this branch goes up: "Before first live trip: verify departure-time and event option lists in config/trip_templates.yaml against the retired Slack workflow forms (Rob/Mitchell)." This is an operational gate, not a code task.

- [ ] **Step 7: Commit**

```bash
git add app/trips/questions.py config/trip_templates.yaml tests/trips/test_questions.py
git commit -m "feat(trips): question schema validation + seeded trip templates"
```

---

### Task 4: Registration service — member gate, answer validation, capacity, atomic create

**Files:**
- Create: `app/trips/service.py`
- Test: `tests/trips/test_service.py`

**Interfaces:**
- Produces (all in `app/trips/service.py`):
  - `class TripRegistrationError(Exception)` with `self.errors: dict[str, str]`
  - `lookup_active_member(email) -> User | None` — normalized email, returns the User only when `user.status == UserStatus.ACTIVE`
  - `visible_questions(questions, answers) -> list[dict]` — resolves `visible_if` against submitted answers ("yes"/"no" strings)
  - `validate_answers(questions, submitted) -> tuple[dict, dict]` — `(stored_answers, errors)`; error keys `answers.<key>`
  - `capacity_available(trip) -> bool` — counts `PENDING` + `CONFIRMED` plus `PENDING_PAYMENT` younger than 1 hour, against `max_participants_standard + max_participants_extra`
  - `expire_stale_pending(trip) -> None` — flips `PENDING_PAYMENT` older than 24h to `CANCELLED`, commits
  - `upsert_profile(user, profile_payload) -> TripProfile`
  - `create_registration(trip, payload) -> TripRegistration` — full validation; commits the row with `status=PENDING_PAYMENT`; raises `TripRegistrationError`
- Consumes: Task 1 models, Task 3 `validate_questions` (not needed at runtime here — questions are validated at admin save; the service trusts `trip.custom_questions`).

Payload shape (POST body, defined here, consumed by Tasks 5 & 7):

```json
{
  "email": "member@example.com",
  "price_tier": "low",
  "profile": {
    "can_drive": "yes",
    "seat_capacity": "3",
    "bike_capacity": "2",
    "hitch_size": "2",
    "region_code": "4",
    "dietary_restrictions": ["Vegetarian"],
    "dietary_other": "",
    "has_tent": "no"
  },
  "answers": {"departure_time": ["Friday morning"], "chore_preference": "Cooking"}
}
```

- [ ] **Step 1: Write failing tests**

`tests/trips/test_service.py` (uses `_series`/`_edition` builders — copy them from `tests/trips/test_models.py` with slugs `test-trip-service` / `test-trip-service-2027`):

```python
from datetime import datetime, timedelta

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips import service
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


QUESTIONS = [
    {"key": "departure_time", "label": "Departure?", "type": "multi_choice",
     "options": ["Fri AM", "Fri PM"], "max_selections": 2, "required": True},
    {"key": "can_stop", "label": "Stop for food?", "type": "yes_no",
     "required": True},
    {"key": "stop_where", "label": "Where?", "type": "text", "required": True,
     "visible_if": {"question": "can_stop", "equals": "yes"}},
]

PROFILE = {
    "can_drive": "yes", "seat_capacity": "3", "bike_capacity": "0",
    "hitch_size": "", "region_code": "4",
    "dietary_restrictions": ["Vegetarian"], "dietary_other": "",
    "has_tent": "no",
}


def _series(slug="test-trip-service"):
    series = TripSeries(slug=slug, name="TEST Trip", destination="Testville")
    db.session.add(series)
    db.session.flush()
    return series


def _edition(series, slug="test-trip-service-2027", **overrides):
    fields = dict(
        slug=slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id, max_participants_standard=2,
        max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=QUESTIONS,
    )
    fields.update(overrides)
    trip = Trip(**fields)
    db.session.add(trip)
    db.session.flush()
    return trip


def _member(email="trip-member@example.com", status=UserStatus.ACTIVE):
    user = User(first_name="Test", last_name="Member",
                email=email, status=status)
    db.session.add(user)
    db.session.flush()
    return user


def _payload(**overrides):
    payload = {
        "email": "trip-member@example.com", "price_tier": "low",
        "profile": dict(PROFILE),
        "answers": {"departure_time": ["Fri AM"], "can_stop": "no"},
    }
    payload.update(overrides)
    return payload


def test_lookup_active_member_rejects_inactive(db_session):
    _member("trip-inactive@example.com", status=UserStatus.ALUMNI)
    db.session.commit()
    assert service.lookup_active_member("trip-inactive@example.com") is None
    assert service.lookup_active_member("Trip-Inactive@Example.com ") is None


def test_create_registration_happy_path(db_session):
    series = _series()
    trip = _edition(series)
    user = _member()
    db.session.commit()
    registration = service.create_registration(trip, _payload())
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.amount_cents == 10000
    assert registration.answers == {"departure_time": ["Fri AM"],
                                    "can_stop": "no"}
    assert user.trip_profile.seat_capacity == 3
    assert user.trip_profile.can_drive is True


def test_hidden_conditional_answer_not_required_and_not_stored(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM"],
                                "can_stop": "no",
                                "stop_where": "should be dropped"})
    registration = service.create_registration(trip, payload)
    assert "stop_where" not in registration.answers


def test_visible_conditional_answer_required(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM"],
                                "can_stop": "yes"})
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "answers.stop_where" in excinfo.value.errors


def test_multi_choice_cap_and_invalid_option_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM", "Fri PM", "Sat"],
                                "can_stop": "no"})
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "answers.departure_time" in excinfo.value.errors


def test_duplicate_registration_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    service.create_registration(trip, _payload())
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert "email" in excinfo.value.errors
    assert "already" in excinfo.value.errors["email"].lower()


def test_capacity_counts_pending_and_confirmed(db_session):
    series = _series()
    trip = _edition(series)  # capacity 2
    user_a = _member()
    user_b = _member("trip-second@example.com")
    db.session.commit()
    reg = service.create_registration(trip, _payload())
    reg.status = TripRegistrationStatus.PENDING
    db.session.commit()
    second = service.create_registration(
        trip, _payload(email="trip-second@example.com"))
    second.status = TripRegistrationStatus.CONFIRMED
    db.session.commit()
    assert service.capacity_available(trip) is False


def test_expire_stale_pending(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    registration = service.create_registration(trip, _payload())
    registration.created_at = datetime.utcnow() - timedelta(hours=25)
    db.session.commit()
    service.expire_stale_pending(trip)
    db.session.expire_all()
    assert registration.status == TripRegistrationStatus.CANCELLED


def test_bool_capacity_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload()
    payload["profile"]["seat_capacity"] = True
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "profile.seat_capacity" in excinfo.value.errors


def test_non_dict_payload_raises_registration_error(db_session):
    series = _series()
    trip = _edition(series)
    db.session.commit()
    with pytest.raises(service.TripRegistrationError):
        service.create_registration(trip, None)


def test_window_closed_rejected(db_session):
    series = _series()
    trip = _edition(series,
                    signup_end=datetime.utcnow() - timedelta(days=1))
    _member()
    db.session.commit()
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert "trip" in excinfo.value.errors
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_service.py -v`
Expected: FAIL, `No module named 'app.trips.service'`.

- [ ] **Step 3: Write `app/trips/service.py`**

```python
"""Trip registration domain logic. Parallel to app/events/service.py.

Key rule inherited from the spec: a registration row is only meaningful
with a payment attached. The row is committed PENDING_PAYMENT before the
Stripe intent exists (same deliberate non-atomicity as events, with the
same two mitigations: capacity ignores stale pendings after 1h, and a 24h
sweep cancels them).
"""
from datetime import datetime, timedelta

from app.constants import UserStatus
from app.models import db, User
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus
from app.utils import normalize_email

PENDING_HOLD_WINDOW = timedelta(hours=1)
STALE_PENDING_AGE = timedelta(hours=24)

HITCH_SIZES = {"", "1.25", "2"}
DIETARY_OPTIONS = [
    "None", "Vegan", "Vegetarian", "Gluten-Free", "Dairy Free / Lactose Intolerant",
    "Nut allergy", "Halal", "Kosher", "Pescatarian", "Other (specify below)",
]


class TripRegistrationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))


def lookup_active_member(email):
    user = User.get_by_email(normalize_email(email))
    if user and user.status == UserStatus.ACTIVE:
        return user
    return None


def visible_questions(questions, answers):
    """Which questions apply given the submitted answers. Mirrored client-side
    in trip_registration.js (applyVisibility) - keep the two in sync."""
    visible = []
    for question in questions or []:
        condition = question.get("visible_if")
        if condition:
            if answers.get(condition["question"]) != condition["equals"]:
                continue
        visible.append(question)
    return visible


def validate_answers(questions, submitted):
    if not isinstance(submitted, dict):
        return {}, {"answers": "Answers must be provided as an object."}
    stored, errors = {}, {}
    for question in visible_questions(questions, submitted):
        key = question["key"]
        label = question.get("label") or key
        answer = submitted.get(key)
        qtype = question["type"]
        if qtype == "multi_choice":
            if answer is None:
                answer = []
            if not isinstance(answer, list):
                errors[f"answers.{key}"] = f"{label} must be a list."
                continue
            answer = [str(a) for a in answer]
            if question.get("required") and not answer:
                errors[f"answers.{key}"] = f"{label} is required."
                continue
            invalid = [a for a in answer if a not in question["options"]]
            if invalid:
                errors[f"answers.{key}"] = f"Select valid options for {label}."
                continue
            cap = question.get("max_selections")
            if cap and len(answer) > cap:
                errors[f"answers.{key}"] = (
                    f"Pick at most {cap} options for {label}.")
                continue
            if answer:
                stored[key] = answer
            continue
        answer = "" if answer is None else str(answer).strip()
        if question.get("required") and not answer:
            errors[f"answers.{key}"] = f"{label} is required."
            continue
        if answer and qtype == "choice" and answer not in question["options"]:
            errors[f"answers.{key}"] = f"Select a valid option for {label}."
            continue
        if answer and qtype == "yes_no" and answer not in ("yes", "no"):
            errors[f"answers.{key}"] = f"Answer yes or no for {label}."
            continue
        if answer:
            stored[key] = answer
    return stored, errors


def _parse_optional_int(value, field, errors, *, maximum=99):
    if value in (None, ""):
        return None
    if isinstance(value, bool):  # bool is an int subclass; True would store 1
        errors[field] = "Enter a whole number."
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = "Enter a whole number."
        return None
    if number < 0 or number > maximum:
        errors[field] = f"Enter a number between 0 and {maximum}."
        return None
    return number


def _parse_yes_no(value):
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def validate_profile(payload):
    """Returns (clean_profile_dict, errors). All fields live in a fixed form
    section (never custom questions) and map 1:1 to TripProfile columns."""
    if not isinstance(payload, dict):
        return {}, {"profile": "Profile must be provided as an object."}
    errors = {}
    clean = {
        "can_drive": _parse_yes_no(payload.get("can_drive")),
        "has_tent": _parse_yes_no(payload.get("has_tent")),
        "seat_capacity": _parse_optional_int(
            payload.get("seat_capacity"), "profile.seat_capacity", errors),
        "bike_capacity": _parse_optional_int(
            payload.get("bike_capacity"), "profile.bike_capacity", errors),
    }
    if payload.get("can_drive") not in ("yes", "no"):
        errors["profile.can_drive"] = "Tell us whether you can drive."
    hitch = str(payload.get("hitch_size") or "")
    if hitch not in HITCH_SIZES:
        errors["profile.hitch_size"] = "Choose a valid hitch size."
    clean["hitch_size"] = hitch
    region = str(payload.get("region_code") or "").strip()
    if not region:
        errors["profile.region_code"] = "Your region code is required."
    elif len(region) > 10:
        errors["profile.region_code"] = "Region code is too long."
    clean["region_code"] = region
    dietary = payload.get("dietary_restrictions") or []
    if not isinstance(dietary, list):
        errors["profile.dietary_restrictions"] = "Dietary picks must be a list."
        dietary = []
    invalid = [d for d in dietary if d not in DIETARY_OPTIONS]
    if invalid:
        errors["profile.dietary_restrictions"] = "Choose valid dietary options."
    clean["dietary_restrictions"] = [str(d) for d in dietary]
    clean["dietary_other"] = str(payload.get("dietary_other") or "").strip()[:255]
    if payload.get("has_tent") not in ("yes", "no", None, ""):
        errors["profile.has_tent"] = "Answer yes or no for the tent question."
    return clean, errors


def upsert_profile(user, clean_profile):
    profile = TripProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        profile = TripProfile(user_id=user.id)
        db.session.add(profile)
    for field, value in clean_profile.items():
        setattr(profile, field, value)
    return profile


def _active_count(trip):
    recent_cutoff = datetime.utcnow() - PENDING_HOLD_WINDOW
    count = 0
    for registration in trip.registrations:
        if registration.status in (TripRegistrationStatus.PENDING,
                                   TripRegistrationStatus.CONFIRMED):
            count += 1
        elif (registration.status == TripRegistrationStatus.PENDING_PAYMENT
              and registration.created_at >= recent_cutoff):
            count += 1
    return count


def capacity_available(trip):
    capacity = (trip.max_participants_standard or 0) + (
        trip.max_participants_extra or 0)
    if capacity <= 0:
        return True
    return _active_count(trip) < capacity


def expire_stale_pending(trip):
    cutoff = datetime.utcnow() - STALE_PENDING_AGE
    stale = TripRegistration.query.filter(
        TripRegistration.trip_id == trip.id,
        TripRegistration.status == TripRegistrationStatus.PENDING_PAYMENT,
        TripRegistration.created_at < cutoff,
    ).all()
    if not stale:
        return
    for registration in stale:
        registration.status = TripRegistrationStatus.CANCELLED
    db.session.commit()


def create_registration(trip, payload):
    if not isinstance(payload, dict):
        raise TripRegistrationError(
            {"payload": "Registration data must be an object."})
    errors = {}
    now = datetime.utcnow()
    if trip.status != "active" or not (
            trip.signup_start <= now <= trip.signup_end):
        raise TripRegistrationError(
            {"trip": "Trip registration is not currently open."})

    user = lookup_active_member(payload.get("email") or "")
    if user is None:
        raise TripRegistrationError({
            "email": "We couldn't find a current member with that email. "
                     "Trips are open to registered members only."})

    existing = TripRegistration.query.filter(
        TripRegistration.trip_id == trip.id,
        TripRegistration.user_id == user.id,
        TripRegistration.status != TripRegistrationStatus.CANCELLED,
    ).first()
    if existing:
        raise TripRegistrationError(
            {"email": "You're already signed up for this trip."})

    price_tier = payload.get("price_tier")
    if price_tier == "low":
        amount_cents = trip.price_low
    elif price_tier == "high":
        amount_cents = trip.price_high
    else:
        errors["price_tier"] = "Choose a valid price option."

    clean_profile, profile_errors = validate_profile(payload.get("profile"))
    errors.update(profile_errors)
    stored_answers, answer_errors = validate_answers(
        trip.custom_questions or [], payload.get("answers") or {})
    errors.update(answer_errors)
    if errors:
        raise TripRegistrationError(errors)

    if not capacity_available(trip):
        raise TripRegistrationError(
            {"trip": "This trip is full."})

    upsert_profile(user, clean_profile)
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers=stored_answers, price_tier=price_tier,
        amount_cents=amount_cents,
    )
    db.session.add(registration)
    db.session.commit()
    return registration
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./run-tests.sh tests/trips/test_service.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/trips/service.py tests/trips/test_service.py
git commit -m "feat(trips): registration service - gate, answers, capacity, profile upsert"
```

---

### Task 5: Public routes — series resolution, register page, member check, registration + intent

**Files:**
- Modify: `app/routes/trips.py` (rewrite), `app/routes/payments.py` (add `registration_id` to trip intent metadata — see Step 6)
- Test: `tests/trips/test_routes.py`

**Interfaces:**
- Produces routes:
  - `GET /<slug>` — series-resolved trip page (existing bespoke template, now passed `series` + `edition`)
  - `GET /<slug>/register` — registration form page, template `trips/register.html` (Task 7 builds it; this task ships a minimal version so routes are testable)
  - `POST /api/trips/member-check` — JSON `{"email": ...}` → `{"eligible": true|false}`
  - `POST /<slug>/register` — JSON payload (Task 4 shape) → `{"clientSecret", "registrationId", "amountCents"}` or `{"error": {...}}` 400
- Consumes: `service.create_registration`, `service.expire_stale_pending`, `TripSeries.current_edition()`, `build_statement_descriptor` / `stripe_idempotency_options` from `app/routes/payments.py`.

- [ ] **Step 1: Write failing route tests**

`tests/trips/test_routes.py` (builders as in Task 4, slugs `test-trip-routes` / `test-trip-routes-2027`; Stripe mocked exactly like `tests/events/test_routes.py`):

```python
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


QUESTIONS = [
    {"key": "chore_preference", "label": "Which task?", "type": "choice",
     "options": ["Cooking", "Cleaning"], "required": True},
]


@pytest.fixture
def public_trip(db_session):
    series = TripSeries(slug="test-trip-routes", name="TEST Trip",
                        destination="Testville")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-routes-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=5,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=QUESTIONS,
    )
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add_all([trip, user])
    db.session.commit()
    return series, trip, user


def _intent(intent_id="pi_trip_test", amount=10000):
    return SimpleNamespace(id=intent_id, client_secret=f"cs_{intent_id}",
                           amount=amount, status="requires_payment_method")


def _payload():
    return {
        "email": "trip-member@example.com", "price_tier": "low",
        "profile": {"can_drive": "no", "seat_capacity": "",
                    "bike_capacity": "", "hitch_size": "",
                    "region_code": "4", "dietary_restrictions": [],
                    "dietary_other": "", "has_tent": ""},
        "answers": {"chore_preference": "Cooking"},
    }


def test_series_slug_resolves_to_current_edition(client, public_trip):
    series, trip, _ = public_trip
    response = client.get("/test-trip-routes/register")
    assert response.status_code == 200
    assert b"TEST Trip 2027" in response.data


def test_member_check_eligible_and_not(client, public_trip):
    ok = client.post("/api/trips/member-check",
                     json={"email": "Trip-Member@Example.com "})
    assert ok.get_json() == {"eligible": True}
    miss = client.post("/api/trips/member-check",
                       json={"email": "nobody@example.com"})
    assert miss.get_json() == {"eligible": False}


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_register_creates_pending_row_and_manual_capture_intent(
        create_intent, client, db_session, public_trip):
    series, trip, user = public_trip
    create_intent.return_value = _intent()
    response = client.post("/test-trip-routes/register", json=_payload(),
                           headers={"Idempotency-Key": "trip-attempt-1"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["clientSecret"] == "cs_pi_trip_test"
    kwargs = create_intent.call_args.kwargs
    assert kwargs["capture_method"] == "manual"
    assert kwargs["metadata"]["payment_type"] == "trip"
    assert kwargs["metadata"]["registration_id"] == str(body["registrationId"])
    assert kwargs["metadata"]["trip_id"] == str(trip.id)
    registration = db_session.session.get(
        TripRegistration, body["registrationId"])
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id == "pi_trip_test"


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_stripe_failure_leaves_registration_pending(
        create_intent, client, db_session, public_trip):
    create_intent.side_effect = RuntimeError("Stripe is unavailable")
    response = client.post("/test-trip-routes/register", json=_payload())
    assert response.status_code == 500
    registration = TripRegistration.query.order_by(
        TripRegistration.id.desc()).first()
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id is None


def test_register_validation_error_returns_field_errors(
        client, public_trip):
    payload = _payload()
    payload["answers"] = {}
    response = client.post("/test-trip-routes/register", json=payload)
    assert response.status_code == 400
    assert "answers.chore_preference" in response.get_json()["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_routes.py -v`
Expected: FAIL (404s and missing attributes — old `trips.py` has none of these routes).

- [ ] **Step 3: Rewrite `app/routes/trips.py`**

```python
from datetime import datetime

import stripe
from flask import Blueprint, render_template, request

from ..constants import PaymentType
from ..errors import json_error
from ..models import Trip
from ..trips import service
from ..trips.models import TripSeries
from ..utils import format_datetime_central, normalize_email
from .payments import build_statement_descriptor, stripe_idempotency_options

trips = Blueprint('trips', __name__)


def _resolve_series(slug):
    """Public trip URLs are SERIES slugs; legacy edition slugs still resolve
    via their parent series so old links keep working."""
    series = TripSeries.query.filter_by(slug=slug).first()
    if series is None:
        edition = Trip.query.filter_by(slug=slug).first()
        series = edition.series if edition else None
    return series


def _registration_state(trip):
    now = datetime.utcnow()
    if trip.status == 'active' and trip.signup_start <= now <= trip.signup_end:
        return True, None
    if trip.status != 'active':
        return False, 'Trip registration is not currently open.'
    if now < trip.signup_start:
        opens_at = format_datetime_central(trip.signup_start)
        return False, f'Trip registration opens {opens_at}.'
    return False, 'Trip registration has closed.'


@trips.route('/<slug>')
def get_trip_page(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        from flask import abort
        abort(404)
    registration_open, registration_message = _registration_state(trip)
    return render_template(
        f'trips/{series.slug}.html',
        trip=trip,
        series=series,
        registration_open=registration_open,
        registration_message=registration_message,
    )


@trips.route('/<slug>/register')
def get_trip_register_page(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        from flask import abort
        abort(404)
    service.expire_stale_pending(trip)
    registration_open, registration_message = _registration_state(trip)
    registration_data = {
        'slug': series.slug,
        'priceLow': trip.price_low,
        'priceHigh': trip.price_high,
        'customQuestions': trip.custom_questions or [],
    }
    return render_template(
        'trips/register.html',
        trip=trip,
        series=series,
        registration_open=registration_open,
        registration_message=registration_message,
        registration_data=registration_data,
    )


@trips.route('/api/trips/member-check', methods=['POST'])
def member_check():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get('email', ''))
    return {'eligible': service.lookup_active_member(email) is not None}


@trips.route('/<slug>/register', methods=['POST'])
def register_for_trip(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        return json_error('Trip not found', 404)
    payload = request.get_json(silent=True) or {}
    try:
        registration = service.create_registration(trip, payload)
    except service.TripRegistrationError as exc:
        return json_error(exc.errors)

    try:
        intent = stripe.PaymentIntent.create(
            amount=registration.amount_cents,
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=registration.user.email,
            statement_descriptor=build_statement_descriptor('TRIP', trip.name),
            description=f"TCSC Trip - {trip.name}",
            metadata={
                'payment_type': PaymentType.TRIP,
                'trip_id': str(trip.id),
                'trip_slug': series.slug,
                'registration_id': str(registration.id),
                'price_tier': registration.price_tier,
                'email': registration.user.email,
                'name': registration.user.full_name,
            },
            **stripe_idempotency_options(),
        )
    except Exception as exc:
        # Row stays PENDING_PAYMENT; the 1h capacity window and 24h sweep
        # (service.py) handle abandonment - mirrors events.
        return json_error(str(exc), 500)

    from ..models import db
    registration.payment_intent_id = intent.id
    db.session.commit()
    return {
        'clientSecret': intent.client_secret,
        'registrationId': registration.id,
        'amountCents': registration.amount_cents,
    }
```

Note on route order: `/api/trips/member-check` must be declared and will match before the `/<slug>` catch-alls because Flask routes on specificity, but `'api'` would otherwise match `/<slug>` — the explicit route wins since it's a longer static rule. Verify with the member-check test.

- [ ] **Step 4: Minimal `app/templates/trips/register.html` so routes render**

Create a minimal page now (Task 7 replaces it with the real form — keep the same template name and the `trip-registration-data` island contract):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ trip.name }} — Registration — Twin Cities Ski Club</title>
  {{ csrf_meta_tag() }}
  <script id="trip-registration-data" type="application/json">{{ registration_data|tojson }}</script>
</head>
<body>
  <h1>{{ trip.name }}</h1>
  {% if not registration_open %}<p>{{ registration_message }}</p>{% endif %}
</body>
</html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./run-tests.sh tests/trips/test_routes.py -v`
Expected: all PASS.

- [ ] **Step 6: Confirm nothing else breaks — legacy `create-payment-intent` stays**

The old `POST /create-payment-intent` trip flow in `app/routes/payments.py` stays untouched during the transition (old trip pages still use it until Task 10 cuts them over). Run the full suite:

Run: `./run-tests.sh`
Expected: no new failures. (`tests/routes/test_payments.py` still passes — we didn't touch that path.)

- [ ] **Step 7: Commit**

```bash
git add app/routes/trips.py app/templates/trips/register.html tests/trips/test_routes.py
git commit -m "feat(trips): public routes - series resolution, member check, register + manual-capture intent"
```

---

### Task 6: Webhook — trip registration status transitions

**Files:**
- Modify: `app/routes/payments.py`
- Test: `tests/trips/test_webhook.py`

**Interfaces:**
- Consumes: `registration_id` metadata key set in Task 5; `TripRegistration`, `TripRegistrationStatus`.
- Produces: webhook side-effects — `PAYMENT_CAPTURABLE` → registration `PENDING`; `PAYMENT_SUCCEEDED` → `CONFIRMED`; `PAYMENT_CANCELED` → `CANCELLED`. Existing Payment-row behavior for trips is unchanged (Payment is still created on `PAYMENT_CAPTURABLE` with `trip_id`).

- [ ] **Step 1: Write failing webhook tests**

`tests/trips/test_webhook.py` (dev-mode webhook bypass, exactly like `tests/events/test_webhook.py`):

```python
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


@pytest.fixture
def pending_registration(db_session):
    series = TripSeries(slug="test-trip-webhook", name="TEST Trip",
                        destination="Testville")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-webhook-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[],
    )
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add_all([trip, user])
    db.session.flush()
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_webhook",
    )
    db.session.add(registration)
    db.session.commit()
    return registration


def _webhook_payload(event_type, registration_id, trip_id,
                     intent_id="pi_trip_webhook"):
    return {"type": event_type, "data": {"object": {
        "id": intent_id, "amount": 10000,
        "metadata": {"payment_type": "trip",
                     "trip_id": str(trip_id),
                     "registration_id": str(registration_id),
                     "email": "trip-member@example.com",
                     "name": "Test Member",
                     "member_type": "returning"}}}}


def _post_development_webhook(client, payload):
    with patch.dict("os.environ", {"FLASK_ENV": "development",
                                   "STRIPE_WEBHOOK_SECRET": ""}):
        return client.post("/webhook", json=payload)


def test_capturable_marks_registration_pending(client, db_session,
                                               pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.PENDING


@patch("app.routes.payments.send_payment_notification")
def test_succeeded_confirms_registration(notify, client, db_session,
                                         pending_registration):
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.CONFIRMED


def test_canceled_cancels_registration(client, db_session,
                                       pending_registration):
    payload = _webhook_payload("payment_intent.canceled",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.CANCELLED


def test_missing_registration_id_does_not_error(client, db_session,
                                                pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    del payload["data"]["object"]["metadata"]["registration_id"]
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200  # legacy trip intents lack the key
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/trips/test_webhook.py -v`
Expected: the three transition tests FAIL (status unchanged); the legacy test may already pass.

- [ ] **Step 3: Add the trip transition helper to `app/routes/payments.py`**

Below `_cancel_event_registration` (after line ~113), add:

```python
def _trip_registration_from_metadata(metadata):
    from app.trips.models import TripRegistration
    registration_id = metadata.get('registration_id')
    payment_type = metadata.get('payment_type')
    if payment_type != PaymentType.TRIP or not registration_id:
        return None
    try:
        return db.session.get(TripRegistration, int(registration_id))
    except (TypeError, ValueError):
        return None


def _transition_trip_registration(payment_intent, new_status):
    """Move a TripRegistration along hold->capture/cancel. Legacy trip
    intents (no registration_id in metadata) are silently skipped."""
    from app.trips.models import TripRegistrationStatus
    metadata = _stripe_object_value(payment_intent, 'metadata', {}) or {}
    registration = _trip_registration_from_metadata(metadata)
    if registration is None:
        return
    if (new_status == TripRegistrationStatus.CANCELLED
            and registration.status == TripRegistrationStatus.CONFIRMED):
        return  # never un-confirm from a stray cancel event
    registration.status = new_status
    db.session.commit()
```

(`db` and `PaymentType` are already imported in `payments.py`.)

- [ ] **Step 4: Call it from the three webhook branches**

In `webhook_received()`:

1. In the `StripeEvent.PAYMENT_CAPTURABLE` branch, after the existing Payment create/update logic commits (end of the branch, before its return/fallthrough), add:

```python
            if payment_type == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    payment_intent, TripRegistrationStatus.PENDING)
```

2. In the `StripeEvent.PAYMENT_SUCCEEDED` branch, after the Payment update/notification logic (same placement pattern), add:

```python
            if payment_type == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    payment_intent, TripRegistrationStatus.CONFIRMED)
```

3. In the `StripeEvent.PAYMENT_CANCELED` branch, after `payment.status = 'canceled'` handling, add:

```python
            if metadata.get('payment_type') == PaymentType.TRIP:
                from app.trips.models import TripRegistrationStatus
                _transition_trip_registration(
                    data_object, TripRegistrationStatus.CANCELLED)
```

Match each branch's local variable names when inserting (the capturable/succeeded branches call the intent `payment_intent`; the canceled branch uses `data_object` — read the surrounding code before editing).

- [ ] **Step 5: Run tests to verify they pass**

Run: `./run-tests.sh tests/trips/test_webhook.py tests/events/test_webhook.py tests/routes/test_payments.py -v`
Expected: all PASS (events + legacy payment tests prove no regression).

- [ ] **Step 6: Commit**

```bash
git add app/routes/payments.py tests/trips/test_webhook.py
git commit -m "feat(trips): webhook transitions for trip registrations"
```

---

### Task 7: Member registration form — real template + JS

**Files:**
- Modify: `app/templates/trips/register.html` (replace Task 5's minimal version)
- Create: `app/static/trip_registration.js`
- Modify: `app/security.py` (add `trips.get_trip_register_page` to `_PAYMENT_PAGE_ENDPOINTS` so the Stripe-permitting CSP applies — find the tuple/set of endpoint names and append it)
- Test: `tests/trips/test_routes.py` (extend), manual browser pass

**Interfaces:**
- Consumes: `registration_data` island (Task 5): `{slug, priceLow, priceHigh, customQuestions}`; endpoints `/api/trips/member-check`, `POST /<slug>/register`, `GET /get-stripe-key`.
- Produces: the POST payload shape from Task 4 (email, price_tier, profile, answers).

UX requirements (from the spec — these are acceptance criteria, not suggestions):
mobile-first single page; topic-grouped sections with a visible step count; email gate reveals the form; conditional questions expand inline; price tier hidden when `priceLow == priceHigh`; payment on the same page; clear inline field errors mapped from server keys.

- [ ] **Step 1: Replace `app/templates/trips/register.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ trip.name }} — Registration — Twin Cities Ski Club</title>
  {{ csrf_meta_tag() }}
  <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/tailwind-output.css') }}">
  <script src="{{ url_for('static', filename='csrf.js') }}"></script>
  <script src="https://js.stripe.com/v3/"></script>
  <script id="trip-registration-data" type="application/json">{{ registration_data|tojson }}</script>
  <script src="{{ url_for('static', filename='trip_registration.js') }}" defer></script>
</head>
<body class="bg-tcsc-gray-50 text-tcsc-navy">
<div class="mx-auto max-w-form-lg px-4 py-8">
  <header class="mb-6">
    <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="Twin Cities Ski Club" class="h-10 mb-4">
    <h1 class="text-2xl font-bold">{{ trip.name }}</h1>
    <p class="text-tcsc-gray-600">{{ trip.destination }} · {{ trip.formatted_date_range }}</p>
  </header>

  {% if not registration_open %}
    <div class="rounded-tcsc bg-tcsc-gray-100 p-4">{{ registration_message }}</div>
  {% else %}
  <form id="trip-registration-form" class="payment-view space-y-8" novalidate
        data-trip-slug="{{ series.slug }}">

    <section class="rounded-tcsc bg-white p-5 shadow-sm" id="gate-section">
      <h2 class="font-semibold mb-1">Member check</h2>
      <p class="text-sm text-tcsc-gray-600 mb-3">Trips are for current members. Enter the email you registered with.</p>
      <label class="block text-sm font-medium" for="member-email">Email</label>
      <input id="member-email" type="email" required autocomplete="email"
             class="mt-1 w-full rounded-tcsc border-tcsc-gray-400">
      <p id="gate-message" class="mt-2 text-sm hidden"></p>
      <button type="button" id="gate-check"
              class="mt-3 rounded-tcsc bg-tcsc-navy px-4 py-2 text-tcsc-white">Continue</button>
    </section>

    <div id="form-body" class="hidden space-y-8">

      <section class="rounded-tcsc bg-white p-5 shadow-sm">
        <h2 class="font-semibold mb-3">Getting there</h2>
        <fieldset>
          <legend class="text-sm font-medium">Can you drive a carpool? *</legend>
          <div class="mt-1 flex gap-4">
            <label><input type="radio" name="profile-can-drive" value="yes"> Yes</label>
            <label><input type="radio" name="profile-can-drive" value="no"> No</label>
          </div>
        </fieldset>
        <div id="driver-details" class="hidden mt-3 space-y-3 border-l-2 border-tcsc-mint pl-4">
          <div><label class="block text-sm font-medium" for="profile-seats">How many people can you accommodate (besides yourself)?</label>
            <input id="profile-seats" type="number" min="0" max="99" class="mt-1 w-24 rounded-tcsc border-tcsc-gray-400"></div>
          <div><label class="block text-sm font-medium" for="profile-bikes">How many bikes can you accommodate?</label>
            <input id="profile-bikes" type="number" min="0" max="99" class="mt-1 w-24 rounded-tcsc border-tcsc-gray-400"></div>
          <fieldset><legend class="text-sm font-medium">Do you have a trailer hitch?</legend>
            <div class="mt-1 flex gap-4">
              <label><input type="radio" name="profile-hitch" value="" checked> No</label>
              <label><input type="radio" name="profile-hitch" value="1.25"> 1.25&Prime;</label>
              <label><input type="radio" name="profile-hitch" value="2"> 2&Prime;</label>
            </div></fieldset>
        </div>
        <div class="mt-3"><label class="block text-sm font-medium" for="profile-region">What is your region code? *</label>
          <input id="profile-region" type="text" maxlength="10" class="mt-1 w-24 rounded-tcsc border-tcsc-gray-400">
          <p class="text-sm text-tcsc-gray-600 mt-1">See the map: <a class="underline" href="https://bit.ly/TCSCmap" target="_blank" rel="noopener">bit.ly/TCSCmap</a></p></div>
      </section>

      <section class="rounded-tcsc bg-white p-5 shadow-sm">
        <h2 class="font-semibold mb-3">Food &amp; sleeping</h2>
        <fieldset><legend class="text-sm font-medium">Dietary restrictions</legend>
          <div id="dietary-options" class="mt-1 grid grid-cols-2 gap-1 text-sm"></div></fieldset>
        <div class="mt-3"><label class="block text-sm font-medium" for="profile-dietary-other">Other dietary restriction(s)?</label>
          <input id="profile-dietary-other" type="text" maxlength="255" class="mt-1 w-full rounded-tcsc border-tcsc-gray-400"></div>
        <fieldset class="mt-3"><legend class="text-sm font-medium">Do you have a 2+ person tent?</legend>
          <div class="mt-1 flex gap-4">
            <label><input type="radio" name="profile-tent" value="yes"> Yes</label>
            <label><input type="radio" name="profile-tent" value="no"> No</label>
          </div></fieldset>
      </section>

      <section class="rounded-tcsc bg-white p-5 shadow-sm" id="trip-questions">
        <h2 class="font-semibold mb-3">This trip</h2>
        {% for question in trip.custom_questions %}
        <div class="form-field mt-3" data-question-field="{{ loop.index0 }}"
             {% if question.visible_if %}data-visible-if='{{ question.visible_if|tojson }}'{% endif %}>
          <label class="block text-sm font-medium" for="question-{{ loop.index0 }}">
            {{ question.label }}{% if question.required %} *{% endif %}</label>
          {% if question.type == 'choice' %}
            <select id="question-{{ loop.index0 }}" class="mt-1 w-full rounded-tcsc border-tcsc-gray-400"
                    data-question-key="{{ question.key }}" data-question-type="choice"
                    {% if question.required %}required{% endif %}>
              <option value="">Select an option</option>
              {% for option in question.options %}<option value="{{ option }}">{{ option }}</option>{% endfor %}
            </select>
          {% elif question.type == 'multi_choice' %}
            <div class="mt-1 space-y-1" data-question-key="{{ question.key }}" data-question-type="multi_choice"
                 {% if question.max_selections %}data-max-selections="{{ question.max_selections }}"{% endif %}
                 {% if question.required %}data-required="true"{% endif %}>
              {% for option in question.options %}
              <label class="block text-sm"><input type="checkbox" value="{{ option }}"> {{ option }}</label>
              {% endfor %}
            </div>
          {% elif question.type == 'yes_no' %}
            <div class="mt-1 flex gap-4" data-question-key="{{ question.key }}" data-question-type="yes_no"
                 {% if question.required %}data-required="true"{% endif %}>
              <label><input type="radio" name="question-{{ loop.index0 }}-yn" value="yes"> Yes</label>
              <label><input type="radio" name="question-{{ loop.index0 }}-yn" value="no"> No</label>
            </div>
          {% else %}
            <input id="question-{{ loop.index0 }}" type="text" class="mt-1 w-full rounded-tcsc border-tcsc-gray-400"
                   data-question-key="{{ question.key }}" data-question-type="text"
                   {% if question.required %}required{% endif %}>
          {% endif %}
          {% if question.help_text %}<p class="text-sm text-tcsc-gray-600 mt-1">{{ question.help_text }}</p>{% endif %}
        </div>
        {% endfor %}
      </section>

      <section class="rounded-tcsc bg-white p-5 shadow-sm">
        <h2 class="font-semibold mb-3">Payment</h2>
        <div id="price-tiers" class="space-y-2 {% if trip.price_low == trip.price_high %}hidden{% endif %}">
          <label class="flex items-center gap-2"><input type="radio" name="price-tier" value="low" checked>
            Standard — <span>{{ trip.price_low|format_price }}</span></label>
          <label class="flex items-center gap-2"><input type="radio" name="price-tier" value="high">
            Supporter — <span>{{ trip.price_high|format_price }}</span></label>
        </div>
        <p class="text-sm text-tcsc-gray-600 my-3">Your card is <strong>authorized now and only charged when the roster is confirmed</strong>.</p>
        <div id="card-element" class="rounded-tcsc border border-tcsc-gray-400 p-3 bg-white"></div>
        <p id="form-errors" class="mt-3 text-sm text-red-700"></p>
        <button type="submit" id="submit"
                class="mt-4 w-full rounded-tcsc bg-tcsc-navy px-4 py-3 font-semibold text-tcsc-white">
          <span id="button-text">Register &amp; place hold</span></button>
      </section>
    </div>
  </form>

  <div class="completed-view hidden rounded-tcsc bg-tcsc-mint p-6">
    <h2 class="font-bold text-lg">You're signed up! 🎿</h2>
    <p id="confirmation-message" class="mt-2"></p>
  </div>
  {% endif %}
</div>
</body>
</html>
```

- [ ] **Step 2: Write `app/static/trip_registration.js`**

```javascript
(function tripRegistrationPage() {
  const dataNode = document.getElementById('trip-registration-data');
  const form = document.getElementById('trip-registration-form');
  if (!dataNode || !form) return;
  const tripData = JSON.parse(dataNode.textContent);

  const DIETARY_OPTIONS = [
    'None', 'Vegan', 'Vegetarian', 'Gluten-Free',
    'Dairy Free / Lactose Intolerant', 'Nut allergy', 'Halal', 'Kosher',
    'Pescatarian', 'Other (specify below)',
  ]; // Mirrors DIETARY_OPTIONS in app/trips/service.py - keep in sync.

  const dietaryBox = document.getElementById('dietary-options');
  DIETARY_OPTIONS.forEach(function (option) {
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.value = option;
    box.dataset.dietary = 'true';
    label.appendChild(box);
    label.appendChild(document.createTextNode(' ' + option));
    dietaryBox.appendChild(label);
  });

  // --- email gate -------------------------------------------------------
  const gateButton = document.getElementById('gate-check');
  const gateMessage = document.getElementById('gate-message');
  const emailInput = document.getElementById('member-email');
  const formBody = document.getElementById('form-body');
  gateButton.addEventListener('click', async function () {
    gateMessage.classList.add('hidden');
    const response = await fetch('/api/trips/member-check', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailInput.value }),
    });
    const result = await response.json();
    if (result.eligible) {
      formBody.classList.remove('hidden');
      document.getElementById('gate-section').classList.add('opacity-60');
      emailInput.readOnly = true;
      gateButton.classList.add('hidden');
    } else {
      gateMessage.textContent = "We couldn't find a current member with that "
        + 'email. Trips are open to registered members - see tcsc.ski to join.';
      gateMessage.classList.remove('hidden');
    }
  });

  // --- conditional visibility ------------------------------------------
  // Mirrors visible_questions() in app/trips/service.py - keep in sync.
  function currentAnswers() {
    const answers = {};
    form.querySelectorAll('[data-question-key]').forEach(function (node) {
      const key = node.dataset.questionKey;
      const type = node.dataset.questionType;
      if (type === 'multi_choice') {
        answers[key] = Array.from(
          node.querySelectorAll('input:checked')).map(function (i) { return i.value; });
      } else if (type === 'yes_no') {
        const checked = node.querySelector('input:checked');
        answers[key] = checked ? checked.value : '';
      } else {
        answers[key] = node.value;
      }
    });
    return answers;
  }

  function applyVisibility() {
    const answers = currentAnswers();
    form.querySelectorAll('[data-question-field]').forEach(function (wrapper) {
      const raw = wrapper.dataset.visibleIf;
      if (!raw) return;
      const condition = JSON.parse(raw);
      const applies = answers[condition.question] === condition.equals;
      wrapper.classList.toggle('hidden', !applies);
      wrapper.querySelectorAll('input, select').forEach(function (input) {
        input.disabled = !applies;
      });
    });
    const driver = form.querySelector('input[name="profile-can-drive"]:checked');
    document.getElementById('driver-details')
      .classList.toggle('hidden', !driver || driver.value !== 'yes');
  }
  form.addEventListener('change', applyVisibility);
  applyVisibility();

  // multi-choice caps
  form.addEventListener('change', function (event) {
    const group = event.target.closest('[data-max-selections]');
    if (!group) return;
    const cap = Number(group.dataset.maxSelections);
    const checked = group.querySelectorAll('input:checked');
    if (checked.length > cap) {
      event.target.checked = false;
      showError('Pick at most ' + cap + ' options.');
    }
  });

  // --- Stripe -----------------------------------------------------------
  let stripe = null;
  let card = null;
  async function ensureStripe() {
    if (card) return;
    const keyResponse = await fetch('/get-stripe-key');
    const { publicKey } = await keyResponse.json();
    stripe = window.Stripe(publicKey);
    card = stripe.elements().create('card');
    card.mount('#card-element');
    card.on('change', function (event) {
      showError(event.error ? event.error.message : '');
    });
  }
  ensureStripe();

  // --- submit -----------------------------------------------------------
  function collectPayload() {
    const drive = form.querySelector('input[name="profile-can-drive"]:checked');
    const tent = form.querySelector('input[name="profile-tent"]:checked');
    const hitch = form.querySelector('input[name="profile-hitch"]:checked');
    const tier = form.querySelector('input[name="price-tier"]:checked');
    const answers = {};
    form.querySelectorAll('[data-question-key]').forEach(function (node) {
      const wrapper = node.closest('[data-question-field]');
      if (wrapper && wrapper.classList.contains('hidden')) return;
      const key = node.dataset.questionKey;
      const type = node.dataset.questionType;
      if (type === 'multi_choice') {
        answers[key] = Array.from(
          node.querySelectorAll('input:checked')).map(function (i) { return i.value; });
      } else if (type === 'yes_no') {
        const checked = node.querySelector('input:checked');
        if (checked) answers[key] = checked.value;
      } else if (node.value) {
        answers[key] = node.value;
      }
    });
    return {
      email: emailInput.value,
      price_tier: tier ? tier.value : 'low',
      profile: {
        can_drive: drive ? drive.value : '',
        seat_capacity: document.getElementById('profile-seats').value,
        bike_capacity: document.getElementById('profile-bikes').value,
        hitch_size: hitch ? hitch.value : '',
        region_code: document.getElementById('profile-region').value,
        dietary_restrictions: Array.from(
          form.querySelectorAll('[data-dietary]:checked')).map(function (i) { return i.value; }),
        dietary_other: document.getElementById('profile-dietary-other').value,
        has_tent: tent ? tent.value : '',
      },
      answers: answers,
    };
  }

  function showError(message) {
    document.getElementById('form-errors').textContent = message || '';
  }

  function showServerErrors(errors) {
    if (typeof errors === 'string') { showError(errors); return; }
    showError(Object.values(errors).join(' '));
  }

  let isSubmitting = false;
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (isSubmitting) return;
    if (!form.checkValidity()) { form.reportValidity(); return; }
    isSubmitting = true;
    const button = document.getElementById('submit');
    button.disabled = true;
    try {
      await ensureStripe();
      const response = await fetch(
        '/' + encodeURIComponent(tripData.slug) + '/register', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': (crypto.randomUUID
              ? crypto.randomUUID()
              : Date.now() + '-' + Math.random().toString(36).slice(2)),
          },
          body: JSON.stringify(collectPayload()),
        });
      const result = await response.json();
      if (!response.ok) { showServerErrors(result.error); return; }
      const confirmation = await stripe.confirmCardPayment(result.clientSecret, {
        payment_method: {
          card: card,
          billing_details: { email: emailInput.value },
        },
      });
      if (confirmation.error) { showError(confirmation.error.message); return; }
      form.classList.add('hidden');
      const completed = document.querySelector('.completed-view');
      document.getElementById('confirmation-message').textContent =
        'Your card hold of $' + (result.amountCents / 100).toFixed(2)
        + ' is placed. You will be charged when the roster is confirmed.';
      completed.classList.remove('hidden');
    } finally {
      isSubmitting = false;
      button.disabled = false;
    }
  });
})();
```

**Amendments (post-review, authoritative over the code blocks above):**

1. Stylesheet path is `css/tailwind-output.css` (the build writes `app/static/css/tailwind-output.css`; the admin base template confirms the convention).
2. **Step indicator:** number the section headings with a Jinja counter so conditional sections stay correctly numbered. At the top of the form add `{% set steps = namespace(n=0) %}`; each section `<h2>` becomes:

```html
{% set steps.n = steps.n + 1 %}
<h2 class="font-semibold mb-3"><span class="text-tcsc-gray-400 mr-1">{{ steps.n }}.</span> Getting there</h2>
```

(same pattern for Member check, Food &amp; sleeping, This trip, Payment). Wrap the "This trip" section in `{% if trip.custom_questions %}` so empty trips skip it and the numbering stays contiguous.

3. **Per-field server errors** in `trip_registration.js` — replace `showServerErrors` with:

```javascript
  var PROFILE_ERROR_FIELDS = {
    'profile.seat_capacity': 'profile-seats',
    'profile.bike_capacity': 'profile-bikes',
    'profile.region_code': 'profile-region',
    'profile.dietary_restrictions': 'dietary-options',
    'email': 'member-email',
  };

  function findErrorField(key) {
    if (key.indexOf('answers.') === 0) {
      return form.querySelector(
        '[data-question-key="' + key.slice(8) + '"]');
    }
    var id = PROFILE_ERROR_FIELDS[key];
    return id ? document.getElementById(id) : null;
  }

  function showServerErrors(errors) {
    form.querySelectorAll('.field-error').forEach(function (node) {
      node.classList.remove('field-error', 'ring-2', 'ring-red-500');
    });
    if (typeof errors === 'string') { showError(errors); return; }
    var firstField = null;
    Object.keys(errors).forEach(function (key) {
      var field = findErrorField(key);
      if (field) {
        field.classList.add('field-error', 'ring-2', 'ring-red-500');
        if (!firstField) firstField = field;
      }
    });
    showError(Object.values(errors).join(' '));
    if (firstField) {
      firstField.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
```

**Amendments round 2 (post-review):**

4. Give the three profile radio fieldsets ids — `profile-can-drive-group`, `profile-hitch-group`, `profile-tent-group` — and extend `PROFILE_ERROR_FIELDS` with `'profile.can_drive': 'profile-can-drive-group'`, `'profile.hitch_size': 'profile-hitch-group'`, `'profile.has_tent': 'profile-tent-group'` so every server profile error key highlights a field.
5. Stripe failure feedback: the load-time call becomes `ensureStripe().catch(function () { showError('The payment form failed to load. Refresh the page to try again.'); });` and the submit handler's `try { ... } finally { ... }` gains a `catch (err) { showError('Something went wrong placing the hold — you have not been charged. Please try again.'); }` before the `finally`.
6. Driver-details parity with the custom-question pattern: `applyVisibility` disables all inputs inside `#driver-details` whenever it is hidden, and `collectPayload` sends `''` for `seat_capacity`/`bike_capacity`/`hitch_size` when their inputs are disabled — so flipping "can you drive" back to No cannot submit stale driver data.

- [ ] **Step 3: Add the register endpoint to the payment CSP list**

In `app/security.py`, find `_PAYMENT_PAGE_ENDPOINTS` and add `'trips.get_trip_register_page'` to it (existing entries show the exact format — match them).

- [ ] **Step 4: Extend route tests with a rendered-form assertion**

Append to `tests/trips/test_routes.py`:

```python
def test_register_page_renders_questions_and_gate(client, public_trip):
    response = client.get("/test-trip-routes/register")
    html = response.get_data(as_text=True)
    assert "member-email" in html
    assert "Which task?" in html
    assert "trip-registration-data" in html
```

Run: `./run-tests.sh tests/trips/test_routes.py -v` → all PASS.

- [ ] **Step 5: Build Tailwind and verify in a browser**

Run: `npm run tailwind:build`
Then with `./scripts/dev.sh` running, open `http://localhost:5001/<a-real-series-slug>/register` at 375px width. Check: gate flow, driver-details expansion, multi-select cap toast, Stripe element mounts, mobile layout has no horizontal scroll.

- [ ] **Step 6: Commit**

```bash
git add app/templates/trips/register.html app/static/trip_registration.js app/security.py tests/trips/test_routes.py
git commit -m "feat(trips): member registration form - grouped, conditional, Stripe on-page"
```

---

### Task 8: Admin — series management, editions, question builder

**Files:**
- Modify: `app/routes/admin.py` (trip routes section), `app/templates/admin/trip_form.html`, `app/templates/admin/trips.html`, `app/static/admin_trips.js`
- Create: `app/static/admin_trip_questions.js`
- Test: `tests/trips/test_admin.py`

**Interfaces:**
- Consumes: `validate_questions`, `load_trip_templates`, `get_template`, `apply_template` (Task 3); `TripSeries`, `Trip.custom_questions`.
- Produces routes:
  - `GET /admin/trips` — grid grouped by series (extend existing `trips_data` JSON with `series_slug`, `series_id`, `registration_count`)
  - `POST /admin/trips/<int:trip_id>/new-edition` — clone: questions (deepcopy), prices, capacities, `slack_channel_name` untouched (lives on series); dates shifted +364 days; slug `<series-slug>-<year>`; status `draft`. Returns `{"success": true, "id": <new id>}`
  - Trip form (`new_trip` / `edit_trip`) gains: series select (or new-series fields), hidden `custom_questions_json` textarea, `template_key` select — same round-trip contract as `admin_events.py` (`_render_form` preserves the submitted JSON on validation errors)

- [ ] **Step 1: Write failing admin tests**

`tests/trips/test_admin.py`:

```python
import json
from datetime import datetime, timedelta

import pytest

from app.models import db, Trip
from app.trips.models import TripSeries


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}
    return client


def _series_with_edition(db_session, slug="test-trip-admin",
                         edition_slug="test-trip-admin-2027"):
    series = TripSeries(slug=slug, name="TEST Trip", destination="Testville",
                        slack_channel_name="test-channel")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug=edition_slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id, max_participants_standard=20,
        max_participants_extra=5,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime(2098, 11, 1), signup_end=datetime(2098, 12, 31),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[{"key": "chore_preference", "label": "Which task?",
                           "type": "choice",
                           "options": ["Cooking", "Cleaning"],
                           "required": True}],
    )
    db.session.add(trip)
    db.session.commit()
    return series, trip


def test_new_edition_clones_questions_and_prices(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    response = admin_client.post(f"/admin/trips/{trip.id}/new-edition")
    assert response.status_code == 200
    new_id = response.get_json()["id"]
    clone = db_session.session.get(Trip, new_id)
    assert clone.series_id == series.id
    assert clone.status == "draft"
    assert clone.custom_questions == trip.custom_questions
    assert clone.custom_questions is not trip.custom_questions
    assert clone.price_low == trip.price_low
    assert clone.slug == "test-trip-admin-2100"  # 2099-01-10 + 364d -> 2100
    assert clone.start_date == trip.start_date + timedelta(days=364)


def test_edit_saves_custom_questions_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    questions = [{"key": "vibe", "label": "Vibe?", "type": "choice",
                  "options": ["Early bird", "Night owl"], "required": True}]
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps(questions),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code in (200, 302)
    db_session.session.expire_all()
    assert trip.custom_questions == questions


def test_edit_rejects_invalid_question_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps([{"key": "bad"}]),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code == 400
    db_session.session.expire_all()
    assert trip.custom_questions[0]["key"] == "chore_preference"
```

Run: `./run-tests.sh tests/trips/test_admin.py -v` → FAIL (404 on new-edition; edit ignores questions JSON).

- [ ] **Step 2: Extend the admin trip routes in `app/routes/admin.py`**

Modify `parse_trip_form(form)`: **remove** `slug` handling from edit (already popped) and stop parsing `slack_channel_name` if present (it lives on the series now — if `parse_trip_form` includes it, delete that line).

Add to `new_trip()` and `edit_trip()` (mirroring `admin_events.py`'s `_render_form` contract):

```python
from ..trips.questions import (
    apply_template, get_template, load_trip_templates, validate_questions,
)

def _parse_trip_questions(raw_value):
    if raw_value is None:
        return None
    import json as _json
    try:
        rows = _json.loads(raw_value)
    except ValueError:
        raise ValueError("Custom questions must contain valid JSON.")
    validate_questions(rows)
    return rows
```

In `edit_trip` POST handling, after the existing field updates and before commit:

```python
        submitted_questions = request.form.get('custom_questions_json')
        try:
            parsed = _parse_trip_questions(submitted_questions)
        except ValueError as exc:
            db.session.rollback()
            return render_template('admin/trip_form.html', trip=trip,
                                   error=str(exc),
                                   templates=load_trip_templates(),
                                   questions_json=submitted_questions or '[]',
                                   ), 400
        if parsed is not None:
            trip.custom_questions = parsed
```

In `new_trip` POST handling, after `Trip(**fields)` is built: apply the chosen template first, then the submitted JSON overwrites (same order as events):

```python
        template_key = request.form.get('template_key', 'blank')
        apply_template(trip, template_key)
        parsed = _parse_trip_questions(request.form.get('custom_questions_json'))
        if parsed is not None:
            trip.custom_questions = parsed
```

Both GET renders pass `templates=load_trip_templates()`, `questions_json=json.dumps(trip.custom_questions if trip else [])`, and a JSON island of template data (same shape as `_editor_template_data` in `admin_events.py`: `{key: {"custom_questions": deepcopy(...)}}`).

Add the clone route next to `delete_trip_json`:

```python
@admin.route('/admin/trips/<int:trip_id>/new-edition', methods=['POST'])
@admin_required
def new_trip_edition(trip_id):
    from copy import deepcopy
    from datetime import timedelta
    trip = db.session.get(Trip, trip_id)
    if trip is None or trip.series_id is None:
        return {'success': False, 'error': 'Trip not found'}, 404
    new_start = trip.start_date + timedelta(days=364)
    slug = f"{trip.series.slug}-{new_start.year}"
    suffix = 2
    while Trip.query.filter_by(slug=slug).first():
        slug = f"{trip.series.slug}-{new_start.year}-{suffix}"
        suffix += 1
    clone = Trip(
        slug=slug, name=trip.name, destination=trip.destination,
        series_id=trip.series_id,
        max_participants_standard=trip.max_participants_standard,
        max_participants_extra=trip.max_participants_extra,
        start_date=new_start,
        end_date=trip.end_date + timedelta(days=364),
        signup_start=trip.signup_start + timedelta(days=364),
        signup_end=trip.signup_end + timedelta(days=364),
        price_low=trip.price_low, price_high=trip.price_high,
        description=trip.description, status='draft',
        custom_questions=deepcopy(trip.custom_questions or []),
    )
    db.session.add(clone)
    db.session.commit()
    return {'success': True, 'id': clone.id}
```

Extend `trips_data()` rows with `"series_slug": trip.series.slug if trip.series else None, "series_id": trip.series_id, "registration_count": len([r for r in trip.registrations if r.status in ('pending', 'confirmed')])`.

- [ ] **Step 3: Question builder UI**

`app/templates/admin/trip_form.html`: add (inside the form, before the submit button) — a template select on new only, the hidden textarea, the builder mount point, and the data islands:

```html
{% if not trip %}
<div class="form-field"><label for="template_key">Start from template</label>
  <select id="template_key" name="template_key">
    {% for key, template in templates.items() %}
    <option value="{{ key }}">{{ template.name }}</option>
    {% endfor %}
  </select></div>
{% endif %}
<h3>Trip questions</h3>
<div id="trip-question-rows"></div>
<button type="button" id="add-trip-question" class="aef-add">Add question</button>
<textarea name="custom_questions_json" id="custom_questions_json" hidden>{{ questions_json }}</textarea>
<script type="application/json" id="trip-template-data">{{ template_editor_data|tojson }}</script>
<script src="{{ url_for('static', filename='admin_trip_questions.js') }}" defer></script>
```

`app/static/admin_trip_questions.js` — adapt the row builder from `admin_events.js` `initEventForm()` (read that file first; reuse its `el()` helper pattern). Differences from events, in full:

```javascript
(function tripQuestionBuilder() {
  var hidden = document.getElementById('custom_questions_json');
  var container = document.getElementById('trip-question-rows');
  var addButton = document.getElementById('add-trip-question');
  var templateSelect = document.getElementById('template_key');
  var templateNode = document.getElementById('trip-template-data');
  if (!hidden || !container) return;
  var templates = templateNode ? JSON.parse(templateNode.textContent) : {};

  var rows;
  try { rows = JSON.parse(hidden.value) || []; } catch (e) { rows = []; }

  var TYPES = [
    ['text', 'Text'], ['choice', 'Single choice'],
    ['multi_choice', 'Multi choice'], ['yes_no', 'Yes / No'],
  ];

  function field(labelText, control) {
    var wrap = document.createElement('div');
    wrap.className = 'aef-field';
    var label = document.createElement('label');
    label.textContent = labelText;
    if (control.id) label.htmlFor = control.id;
    wrap.appendChild(label);
    wrap.appendChild(control);
    return wrap;
  }

  function input(id, value, type) {
    var node = document.createElement('input');
    node.type = type || 'text';
    node.id = id;
    node.value = value == null ? '' : value;
    return node;
  }

  function yesNoKeys(uptoIndex) {
    return rows.slice(0, uptoIndex)
      .filter(function (r) { return r.type === 'yes_no' && r.key; })
      .map(function (r) { return r.key; });
  }

  function render() {
    container.textContent = '';
    rows.forEach(function (item, index) {
      var row = document.createElement('div');
      row.className = 'aef-editor-row';
      var grid = document.createElement('div');
      grid.className = 'aef-editor-grid';

      var key = input('tq-key-' + index, item.key);
      key.dataset.field = 'key';
      key.pattern = '[a-z0-9_]+';
      key.required = true;
      grid.appendChild(field('Key', key));

      var label = input('tq-label-' + index, item.label);
      label.dataset.field = 'label';
      label.required = true;
      grid.appendChild(field('Label', label));

      var type = document.createElement('select');
      type.id = 'tq-type-' + index;
      type.dataset.field = 'type';
      TYPES.forEach(function (pair) {
        var option = document.createElement('option');
        option.value = pair[0];
        option.textContent = pair[1];
        if (item.type === pair[0]) option.selected = true;
        type.appendChild(option);
      });
      grid.appendChild(field('Type', type));

      var options = document.createElement('textarea');
      options.id = 'tq-options-' + index;
      options.dataset.field = 'options';
      options.rows = 4;
      options.value = (item.options || []).join('\n');
      grid.appendChild(field('Options (one per line)', options));

      var cap = input('tq-cap-' + index, item.max_selections, 'number');
      cap.dataset.field = 'max-selections';
      cap.min = '1';
      grid.appendChild(field('Pick up to (multi choice only)', cap));

      var help = input('tq-help-' + index, item.help_text);
      help.dataset.field = 'help-text';
      grid.appendChild(field('Help text', help));

      var required = input('tq-required-' + index, null, 'checkbox');
      required.dataset.field = 'required';
      required.checked = Boolean(item.required);
      grid.appendChild(field('Required', required));

      var visSelect = document.createElement('select');
      visSelect.id = 'tq-visible-' + index;
      visSelect.dataset.field = 'visible-if';
      var none = document.createElement('option');
      none.value = '';
      none.textContent = 'Always shown';
      visSelect.appendChild(none);
      yesNoKeys(index).forEach(function (parentKey) {
        ['yes', 'no'].forEach(function (answer) {
          var option = document.createElement('option');
          option.value = parentKey + '=' + answer;
          option.textContent = 'Only if "' + parentKey + '" = ' + answer;
          if (item.visible_if
              && item.visible_if.question === parentKey
              && item.visible_if.equals === answer) option.selected = true;
          visSelect.appendChild(option);
        });
      });
      grid.appendChild(field('Show when', visSelect));

      var remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'aef-remove';
      remove.textContent = 'Remove question';
      remove.addEventListener('click', function () {
        rows.splice(index, 1);
        render();
      });

      row.appendChild(grid);
      row.appendChild(remove);
      row.addEventListener('input', sync);
      row.addEventListener('change', sync);
      container.appendChild(row);
    });
    sync();
  }

  function sync() {
    rows = Array.from(container.querySelectorAll('.aef-editor-row'))
      .map(function (row) {
        var visible = row.querySelector('[data-field="visible-if"]').value;
        var capValue = row.querySelector('[data-field="max-selections"]').value;
        var item = {
          key: row.querySelector('[data-field="key"]').value.trim(),
          label: row.querySelector('[data-field="label"]').value.trim(),
          type: row.querySelector('[data-field="type"]').value,
          options: row.querySelector('[data-field="options"]').value
            .split('\n').map(function (o) { return o.trim(); }).filter(Boolean),
          required: row.querySelector('[data-field="required"]').checked,
          help_text: row.querySelector('[data-field="help-text"]').value.trim(),
        };
        if (capValue) item.max_selections = Number(capValue);
        if (visible) {
          var parts = visible.split('=');
          item.visible_if = { question: parts[0], equals: parts[1] };
        }
        return item;
      });
    hidden.value = JSON.stringify(rows);
  }

  addButton.addEventListener('click', function () {
    rows.push({ key: '', label: '', type: 'text', options: [],
                required: false, help_text: '' });
    render();
  });

  if (templateSelect) {
    templateSelect.addEventListener('change', function () {
      var template = templates[templateSelect.value];
      if (!template) return;
      if (rows.length
          && !window.confirm('Replace the current questions with this template?')) return;
      rows = JSON.parse(JSON.stringify(template.custom_questions || []));
      render();
    });
  }

  var form = hidden.closest('form');
  if (form) form.addEventListener('submit', sync);
  render();
})();
```

Also add a **"New edition"** button per trip card in `admin_trips.js` (next to the existing edit/delete actions in `tripsRenderCard` / `tripsOpenDrawer`): POST to `'/admin/trips/' + trip.id + '/new-edition'` via the existing `AdminUI.mutate` helper, then reload the grid.

- [ ] **Step 4: Run tests**

Run: `./run-tests.sh tests/trips/test_admin.py tests/routes/ -v`
Expected: new tests PASS, existing admin route tests PASS.

- [ ] **Step 5: Manual builder pass**

With dev server up: `/admin/trips/new` → pick "Great Bear Chase" template → rows appear seeded → tweak, save, reopen, rows round-trip. Verify a validation error (blank a key) re-renders the form **with your rows intact**.

- [ ] **Step 6: Commit**

```bash
git add app/routes/admin.py app/templates/admin/trip_form.html app/templates/admin/trips.html app/static/admin_trips.js app/static/admin_trip_questions.js tests/trips/test_admin.py
git commit -m "feat(trips): admin editions + seeded question builder"
```

---

### Task 9: Admin roster — dynamic columns, capture/cancel, filters, CSV

**Files:**
- Modify: `app/routes/admin.py`, `app/templates/admin/trips.html` (link), `app/static/admin_trips.js` (link)
- Create: `app/templates/admin/trip_registrations.html`, `app/static/admin_trip_registrations.js`
- Test: `tests/trips/test_admin.py` (extend)

**Interfaces:**
- Consumes: `TripRegistration` + `TripProfile`; existing payment mutation endpoints `POST /admin/payments/<id>/capture`, `/refund`, `/admin/payments/bulk-capture`, `/bulk-refund` (unchanged — the roster resolves each registration's Payment via `Payment.get_by_payment_intent(registration.payment_intent_id)`).
- Produces routes:
  - `GET /admin/trips/<int:trip_id>/registrations` → `admin/trip_registrations.html`
  - `GET /admin/trips/<int:trip_id>/registrations/data` → `{"columns": [{"key","label"}], "registrations": rows}`
  - `GET /admin/trips/<int:trip_id>/registrations/export.csv`

Column layout (fixed → profile → dynamic questions → trailing), mirroring `_registration_columns` in `admin_events.py`:

```python
_TRIP_REG_BASE_COLUMNS = [
    ("id", "ID"), ("member", "Member"), ("email", "Email"),
    ("status", "Status"), ("price_tier", "Tier"),
]
_TRIP_REG_PROFILE_COLUMNS = [
    ("can_drive", "Can drive"), ("seat_capacity", "Seats"),
    ("bike_capacity", "Bikes"), ("hitch_size", "Hitch"),
    ("region_code", "Region"), ("dietary", "Dietary"),
    ("has_tent", "Tent"),
]
_TRIP_REG_TRAILING_COLUMNS = [
    ("amount_cents", "Amount"), ("payment_status", "Payment"),
    ("payment_id", "PaymentId"), ("created_at", "Created at"),
]
```

- [ ] **Step 1: Write failing tests**

Append to `tests/trips/test_admin.py`:

```python
import csv
from io import StringIO

from app.constants import UserStatus
from app.models import Payment, User
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus


def _registered_member(db_session, trip, email="trip-member@example.com"):
    user = User(first_name="Test", last_name="Member", email=email,
                status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    db.session.add(TripProfile(user_id=user.id, can_drive=True,
                               seat_capacity=3, region_code="4",
                               dietary_restrictions=["Vegetarian"],
                               dietary_other="", has_tent=None))
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING,
        answers={"chore_preference": "Cooking"},
        price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_admin",
    )
    db.session.add(registration)
    db.session.add(Payment(payment_intent_id="pi_trip_admin",
                           email=email, name="Test Member", amount=10000,
                           status="requires_capture", payment_type="trip",
                           trip_id=trip.id, user_id=user.id))
    db.session.commit()
    return user, registration


def test_roster_data_has_profile_and_question_columns(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(f"/admin/trips/{trip.id}/registrations/data")
    body = response.get_json()
    keys = [c["key"] for c in body["columns"]]
    assert "region_code" in keys
    assert "chore_preference" in keys
    row = body["registrations"][0]
    assert row["member"] == "Test Member"
    assert row["chore_preference"] == "Cooking"
    assert row["region_code"] == "4"
    assert row["payment_status"] == "requires_capture"
    assert row["payment_id"] is not None


def test_roster_csv_export(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(
        f"/admin/trips/{trip.id}/registrations/export.csv")
    reader = csv.DictReader(StringIO(response.get_data(as_text=True)))
    rows = list(reader)
    assert rows[0]["Member"] == "Test Member"
    assert rows[0]["Region"] == "4"
```

Run: `./run-tests.sh tests/trips/test_admin.py -v` → new tests FAIL with 404.

- [ ] **Step 2: Implement the roster routes in `app/routes/admin.py`**

```python
def _trip_registration_columns(trip):
    question_columns = []
    seen = set()
    for question in trip.custom_questions or []:
        key = question["key"]
        if key in seen:
            continue
        seen.add(key)
        question_columns.append((key, question.get("label") or key))
    return (_TRIP_REG_BASE_COLUMNS + _TRIP_REG_PROFILE_COLUMNS
            + question_columns + _TRIP_REG_TRAILING_COLUMNS)


def _display_trip_answer(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value


def _trip_registration_rows(trip):
    columns = _trip_registration_columns(trip)
    column_keys = [key for key, _ in columns]
    rows = []
    registrations = sorted(trip.registrations,
                           key=lambda r: r.created_at, reverse=True)
    for registration in registrations:
        profile = registration.user.trip_profile
        payment = (Payment.get_by_payment_intent(registration.payment_intent_id)
                   if registration.payment_intent_id else None)
        row = {
            "id": registration.id,
            "member": registration.user.full_name,
            "email": registration.user.email,
            "status": registration.status,
            "price_tier": registration.price_tier,
            "amount_cents": registration.amount_cents,
            "payment_status": payment.status if payment else "",
            "payment_id": payment.id if payment else None,
            "created_at": registration.created_at.isoformat(),
        }
        if profile:
            dietary = list(profile.dietary_restrictions or [])
            if profile.dietary_other:
                dietary.append(profile.dietary_other)
            row.update({
                "can_drive": {True: "yes", False: "no"}.get(profile.can_drive, ""),
                "seat_capacity": profile.seat_capacity,
                "bike_capacity": profile.bike_capacity,
                "hitch_size": profile.hitch_size or "",
                "region_code": profile.region_code or "",
                "dietary": ", ".join(dietary),
                "has_tent": {True: "yes", False: "no"}.get(profile.has_tent, ""),
            })
        for key, value in (registration.answers or {}).items():
            row[key] = _display_trip_answer(value)
        rows.append({key: row.get(key, "") for key in column_keys})
    return columns, rows


@admin.route('/admin/trips/<int:trip_id>/registrations')
@admin_required
def trip_registrations_page(trip_id):
    trip = db.session.get(Trip, trip_id)
    if trip is None:
        from flask import abort
        abort(404)
    return render_template('admin/trip_registrations.html', trip=trip)


@admin.route('/admin/trips/<int:trip_id>/registrations/data')
@admin_required
def trip_registrations_data(trip_id):
    trip = db.session.get(Trip, trip_id)
    if trip is None:
        return {'error': 'Trip not found'}, 404
    columns, rows = _trip_registration_rows(trip)
    return {'columns': [{'key': k, 'label': l} for k, l in columns],
            'registrations': rows}


@admin.route('/admin/trips/<int:trip_id>/registrations/export.csv')
@admin_required
def export_trip_registrations(trip_id):
    import csv as _csv
    from io import StringIO
    from flask import Response
    trip = db.session.get(Trip, trip_id)
    if trip is None:
        from flask import abort
        abort(404)
    columns, rows = _trip_registration_rows(trip)
    buffer = StringIO()
    writer = _csv.DictWriter(
        buffer, fieldnames=[label for _, label in columns])
    writer.writeheader()
    key_to_label = dict(columns)
    for row in rows:
        writer.writerow({key_to_label[k]: _sanitize_trip_csv(v)
                         for k, v in row.items()})
    return Response(
        buffer.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename="registrations-{trip.slug}.csv"'})


def _sanitize_trip_csv(value):
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value
```

(Import `Payment` at the top of `admin.py` if not present.)

- [ ] **Step 3: Roster page + JS**

`app/templates/admin/trip_registrations.html`: extend `admin/admin_base.html`; root `<div id="trip-reg-root" data-trip-id="{{ trip.id }}" data-page="trip-registrations">`; toolbar with a text filter input `#trip-reg-filter`, status select `#trip-reg-status`, an "Export CSV" link to the export route, bulk bar with `#trip-reg-bulk-capture` / `#trip-reg-bulk-refund`; a plain `<table id="trip-reg-table">`. Load `admin_trip_registrations.js` cache-busted like other admin pages.

`app/static/admin_trip_registrations.js` — column-driven grid, modeled on `initRegistrationsGrid()` in `admin_events.js` (read it first) with three additions:

1. Row checkboxes (only when `payment_status === 'requires_capture'` for capture; `requires_capture` or `succeeded` for refund) feeding the bulk bar.
2. Per-row Capture / Release buttons calling the **existing** endpoints: `fetch('/admin/payments/' + row.payment_id + '/capture', {method: 'POST'})` and `/refund`; bulk via `fetch('/admin/payments/bulk-capture', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({payment_ids: ids})})`. Reload data after each mutation.
3. Client-side filter: text match across all columns + status select filtering the `status` column.

- [ ] **Step 4: Link from the trips grid**

In `admin_trips.js` (`tripsOpenDrawer` or card actions), add a "Roster" link to `'/admin/trips/' + trip.id + '/registrations'` showing `registration_count` from the extended `trips_data`.

- [ ] **Step 5: Run tests + manual pass**

Run: `./run-tests.sh tests/trips/test_admin.py -v` → all PASS.
Manual: roster renders, filter works, capture button flips payment status (Stripe CLI running), CSV downloads with question columns.

- [ ] **Step 6: Commit**

```bash
git add app/routes/admin.py app/templates/admin/trip_registrations.html app/static/admin_trip_registrations.js app/static/admin_trips.js app/templates/admin/trips.html tests/trips/test_admin.py
git commit -m "feat(trips): admin roster with dynamic columns, capture actions, CSV"
```

---

### Task 10: Cut public trip pages over to the new flow

**Files:**
- Modify: `app/templates/trips/base_trip.html`
- Test: `tests/trips/test_routes.py` (extend), manual pass

**Interfaces:**
- Consumes: `GET /<slug>/register` (Task 5), `registration_open` / `series` template variables.

- [ ] **Step 1: Replace the embedded payment form with a CTA**

In `app/templates/trips/base_trip.html`, delete the `.sr-payment-form` payment section (the name/email/card block and its `.completed-view` sibling) and the `https://js.stripe.com/v3/` script tag. In its place:

```html
{% if registration_open %}
  <a class="cta-button" href="/{{ series.slug }}/register">Sign up for {{ trip.name }}</a>
{% else %}
  <p class="registration-status-message">{{ registration_message }}</p>
{% endif %}
```

(Use the page's existing CTA/button class — inspect `base_trip.html` for the class used by other buttons and match it.)

- [ ] **Step 2: Add a regression test**

Append to `tests/trips/test_routes.py`:

```python
def test_trip_page_links_to_register_flow(client, public_trip):
    response = client.get("/test-trip-routes")
    html = response.get_data(as_text=True)
    assert "/test-trip-routes/register" in html
    assert "sr-payment-form" not in html
```

Note: this hits `trips/test-trip-routes.html` which doesn't exist — the series fixture slug must match a real template. Instead, temporarily point the test at an existing bespoke template by creating the series with slug `test-trip-routes` and adding a 3-line `app/templates/trips/test-trip-routes.html` extending `base_trip.html` **in the test-support commit**, mirroring how `cuyuna.html` extends it. Keep that template; it doubles as the template for future test/manual QA trips.

- [ ] **Step 3: Run tests, full suite, manual pass**

Run: `./run-tests.sh` → no new failures.
Manual: every existing trip page (`/birkie`, `/cuyuna`, …) renders with the CTA; `/create-payment-intent` is now unreferenced by any template (verify: `grep -rn "create-payment-intent" app/templates app/static` → only `script.js` season code paths remain; the trip branch of `script.js` is dead but harmless — leave it for the auth-project cleanup).

- [ ] **Step 4: Commit**

```bash
git add app/templates/trips/base_trip.html app/templates/trips/test-trip-routes.html tests/trips/test_routes.py
git commit -m "feat(trips): trip pages link to the native registration flow"
```

---

## Final verification (whole plan)

- [ ] `./run-tests.sh` — zero new failures vs. baseline.
- [ ] `flask db upgrade` idempotent on a fresh pull (head `a7c1e5f2b9d3`).
- [ ] Manual end-to-end with Stripe CLI: register on a draft trip's register page (set it active), watch the webhook flip the registration to `pending`, capture from the roster, watch it flip to `confirmed`.
- [ ] Mobile pass at 375px on the register page.
- [ ] The old Slack Workflow form is NOT retired in this plan — that happens after the Slack plan ships and a real trip runs on the new flow.
