"""Seed script tests.

These run against a dedicated `tcsc_trips_uiaudit_test` database, created and
dropped per session. The suite's usual `app` fixture points at the real local
dev database and the convention is not to write to it -- this seed writes
hundreds of rows, so it needs its own.
"""

import os
import subprocess

import pytest
from sqlalchemy import create_engine

from app import create_app
from app.models import Payment, Season, Tag, Trip, User, UserSeason, db

TEST_DB = "tcsc_trips_uiaudit_test"
TEST_URL = f"postgresql://tcsc:tcsc@localhost:5432/{TEST_DB}"


def _psql(sql, database="postgres"):
    subprocess.run(
        ["docker", "exec", "tcsc-postgres", "psql", "-U", "tcsc", "-d", database, "-c", sql],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def app():
    _psql(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
    _psql(f'CREATE DATABASE "{TEST_DB}"')

    # Flask-SQLAlchemy 3.x builds its engine *synchronously inside
    # db.init_app()* (called from create_app()), keyed off whatever
    # SQLALCHEMY_DATABASE_URI is in app.config at that exact moment -- see
    # flask_sqlalchemy.extension.SQLAlchemy.init_app's own docstring:
    # "Changes to application config after this call will not be reflected."
    # So overriding application.config *after* create_app() returns (as an
    # earlier version of this fixture did) is silently a no-op: the engine is
    # already bound to whatever DATABASE_URL was in the environment when
    # create_app() ran, which tests/conftest.py's pytest_configure defaults to
    # the real dev database. That earlier version of this fixture in fact
    # wrote hundreds of rows to the dev DB before this was caught -- see
    # task-4-report.md's pollution-incident section. The fix is to point
    # DATABASE_URL at the throwaway DB *before* create_app() runs.
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_URL
    try:
        application = create_app()
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    assert application.config["SQLALCHEMY_DATABASE_URI"] == TEST_URL, (
        "engine bound to the wrong database -- refusing to run seed tests"
    )

    with application.app_context():
        # `flask db upgrade` cannot bootstrap a genuinely empty database in
        # this repo: the oldest tracked migration (d3309936c477) only ALTERs
        # `seasons` -- the base schema predates this repo's Alembic history
        # entirely (it was created out-of-band before migrations were
        # introduced, and the dev DB's `seasons` table already existed before
        # that revision). A brand-new sibling database has none of that, so
        # `flask db upgrade` dies with "relation seasons does not exist".
        # Build the throwaway schema from the current models instead, via a
        # bare engine + `db.metadata` rather than the shared `db` object --
        # this is the escape hatch the `test_no_create_all` guard's own
        # docstring names as sanctioned (see
        # tests/practices/test_practice_migration_release.py's
        # release_schema fixture and
        # tests/scripts/test_seed_practice_plan_reaction_defaults.py).
        engine = create_engine(TEST_URL)
        db.metadata.create_all(engine)
        engine.dispose()
        yield application
        # Postgres refuses DROP DATABASE while connections are still open;
        # Flask-SQLAlchemy's pool holds several from the app-context db
        # access above, so release them before the teardown drop below.
        db.engine.dispose()

    _psql(f'DROP DATABASE IF EXISTS "{TEST_DB}"')


@pytest.fixture
def db_session(app):
    """Empty every table before each test so counts are exact."""
    with app.app_context():
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()


@pytest.fixture
def seeded(db_session):
    from scripts.ui_audit.seed_fixtures import seed_core

    return seed_core({"users": 40, "seasons": 3, "trips": 4, "tags": 8})


def test_every_core_table_is_populated(seeded, db_session):
    assert User.query.count() == 40
    assert Season.query.count() == 3
    assert Trip.query.count() == 4
    assert Tag.query.count() == 8
    assert Payment.query.count() > 0
    assert UserSeason.query.count() > 0


def test_exactly_one_season_is_current(seeded, db_session):
    assert Season.query.filter_by(is_current=True).count() == 1


def test_every_user_status_is_represented(seeded, db_session):
    """Admin filters by status; each filter must have rows behind it."""
    from app.constants import UserStatus

    present = {row.status for row in User.query.all()}
    assert {
        UserStatus.ACTIVE,
        UserStatus.PENDING,
        UserStatus.ALUMNI,
        UserStatus.DROPPED,
    } <= present


def test_some_users_carry_multiple_tags(seeded, db_session):
    """Tag badges wrapping in a table cell is a spacing surface worth capturing."""
    assert any(len(u.tags) >= 2 for u in User.query.all())


def _seed_fingerprint():
    """Every rng-driven field, not just email (which is derived purely from
    index + fixed name lists and would stay identical even if `rng` went
    nondeterministic). Determinism matters here specifically because the
    whole point of the seed is that before/after screenshots differ only
    because of CSS changes -- if the data varies between runs, every capture
    diff is noise.

    Identifies each UserSeason's season by *name* rather than the raw
    `season_id` FK: row deletion between the two seed_core() calls in
    test_seed_is_deterministic doesn't reset the id sequence, so the same
    logical (first, deterministic) season would otherwise compare unequal
    across runs purely because of a monotonic counter, not real
    nondeterminism.
    """
    season_names = {s.id: s.name for s in Season.query.all()}
    users = User.query.order_by(User.id).all()
    return [
        (
            u.email,
            u.status,
            u.seasons_since_active,
            u.preferred_technique,
            u.tshirt_size,
            u.ski_experience,
            tuple(sorted(t.name for t in u.tags)),
            tuple(
                (season_names[us.season_id], us.status, us.registration_type, us.registration_date)
                for us in sorted(u.user_seasons, key=lambda us: season_names[us.season_id])
            ),
            tuple(sorted(p.status for p in u.payments)),
        )
        for u in users
    ]


def test_seed_is_deterministic(db_session):
    from scripts.ui_audit.seed_fixtures import seed_core

    volumes = {"users": 10, "seasons": 1, "trips": 1, "tags": 4}
    seed_core(volumes)
    first = _seed_fingerprint()

    for table in reversed(db.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    seed_core(volumes)
    second = _seed_fingerprint()

    assert first == second


def test_user_seasons_have_required_fields(seeded, db_session):
    """registration_type and registration_date are NOT NULL columns -- a
    naive UserSeason(...) call that omits them raises IntegrityError. Assert
    they're actually populated, not just that the insert didn't blow up."""
    for user_season in UserSeason.query.all():
        assert user_season.registration_type in ("new", "returning")
        assert user_season.registration_date is not None


def test_tag_specs_have_twenty_unique_entries():
    """Production carries 20 tags; the brief's reference list only had 8."""
    from scripts.ui_audit.seed_fixtures import TAG_SPECS

    assert len(TAG_SPECS) == 20
    names = [spec[0] for spec in TAG_SPECS]
    assert len(names) == len(set(names))


def test_default_volumes_uses_prod_shape():
    """.ui-audit/prod-shape.json on disk should drive the real volumes."""
    from scripts.ui_audit.seed_fixtures import default_volumes

    volumes = default_volumes()
    assert volumes["users"] == 266
    assert volumes["seasons"] == 5
    assert volumes["trips"] == 8
    assert volumes["tags"] == 20


def _tag_saturation(volumes):
    from scripts.ui_audit.seed_fixtures import seed_core

    users = seed_core(volumes)["users"]
    tagged = sum(1 for u in users if len(u.tags) > 0)
    return tagged / len(users)


def test_tag_saturation_is_near_production(db_session):
    """Production tags ~36% of members; the brief's every-6th-user version
    (~17%) would leave the roles column looking sparse. Seed at full volume
    and check the fraction lands in a plausible band around 36%."""
    from scripts.ui_audit.seed_fixtures import default_volumes

    fraction = _tag_saturation(default_volumes())
    assert 0.28 <= fraction <= 0.45, f"tag saturation {fraction:.2%} not near prod's 36%"


def test_tag_saturation_is_near_production_at_small_volume(db_session):
    """Regression test: an earlier version tagged with `index % 100 < 36`,
    which only approximates 36% when there are many more than 100 users. At
    exactly the 40-user volume this file's own `seeded` fixture uses, every
    index in 0-35 satisfied that condition, tagging 90% of users instead of
    36% -- masked because this test originally only exercised the 266-user
    default volume, where the modulo wraparound happened to land near 40%."""
    for table in reversed(db.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    fraction = _tag_saturation({"users": 40, "seasons": 2, "trips": 2, "tags": 8})
    assert 0.28 <= fraction <= 0.45, f"tag saturation {fraction:.2%} not near prod's 36%"


def test_every_trip_status_is_represented(db_session):
    """Trip status drives the edit form's <select> (draft/active/completed/
    canceled, per app/templates/admin/trip_form.html) -- an empty option
    teaches us nothing about its spacing, so seed all of them at real trip
    volume. Deliberately excludes admin_trips.js's "closed" filter-pill value,
    which has no matching <option> in the edit form: seeding it would make
    that trip's own edit page silently pre-select "Draft" for a record that
    isn't one."""
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_core

    core = seed_core(default_volumes())
    present = {t.status for t in core["trips"]}
    assert {"draft", "active", "completed", "canceled"} <= present
    assert "closed" not in present


def test_domain_tables_are_populated(db_session):
    from app.events.models import Event, EventParticipant, EventPriceOption, EventRegistration
    from app.newsletter.models import Newsletter, NewsletterPrompt, NewsletterSubmission
    from app.practices.availability_models import LeadAvailabilityPoll, LeadAvailabilityResponse
    from app.practices.models import (
        CancellationRequest,
        Practice,
        PracticeActivity,
        PracticeLead,
        PracticeLocation,
        PracticeRSVP,
        PracticeType,
        SocialLocation,
    )
    from scripts.ui_audit.seed_fixtures import seed_core, seed_domain

    core = seed_core({"users": 30, "seasons": 2, "trips": 3, "tags": 8})
    seed_domain(core)

    assert PracticeLocation.query.count() >= 3
    assert SocialLocation.query.count() >= 2
    assert PracticeType.query.count() >= 3
    assert PracticeActivity.query.count() >= 5
    assert Practice.query.count() >= 12
    assert PracticeLead.query.count() > 0
    assert PracticeRSVP.query.count() > 0
    assert CancellationRequest.query.count() > 0
    assert LeadAvailabilityPoll.query.count() > 0
    assert LeadAvailabilityResponse.query.count() > 0
    assert Event.query.count() >= 2
    assert EventPriceOption.query.count() >= 3
    assert EventRegistration.query.count() >= 5
    assert EventParticipant.query.count() > 0
    assert NewsletterPrompt.query.count() >= 1
    assert Newsletter.query.count() > 0
    assert NewsletterSubmission.query.count() > 0


def test_practices_span_past_and_future(db_session):
    """The practices list and calendar both need populated ranges."""
    from datetime import date

    from app.practices.models import Practice
    from scripts.ui_audit.seed_fixtures import seed_core, seed_domain

    core = seed_core({"users": 10, "seasons": 1, "trips": 1, "tags": 8})
    seed_domain(core)

    dates = [p.date.date() for p in Practice.query.all()]
    today = date.today()
    assert any(d < today for d in dates)
    assert any(d > today for d in dates)


def test_in_progress_practice_is_always_dated_today(db_session, monkeypatch):
    """Regression test for a bug the review caught: the original assignment
    gave IN_PROGRESS to whichever practice was chronologically nearest in
    the future, unconditionally -- on the 4 of 7 weekdays that aren't
    Tue/Thu/Sat, that's a session 1-4 days out, not one happening today.
    admin_practices.js renders date and status badge in the same row, so a
    future-dated "In Progress" practice is a concrete impossible state in
    the exact pane this project audits.

    Forces "today" to a Wednesday via monkeypatch rather than asserting
    against the real `date.today()` -- the bug is invisible on Tue/Thu/Sat
    (the earliest future practice legitimately IS today on those days,
    which is exactly why it shipped unnoticed the first time, on a Tuesday).
    Asserting against the real wall-clock day would only catch this on 3 of
    7 days; forcing a non-practice weekday catches it every time regardless
    of which day the suite actually runs on."""
    from datetime import date

    from app.practices.interfaces import PracticeStatus
    from app.practices.models import Practice
    from scripts.ui_audit import seed_fixtures
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_all

    forced_today = date(2026, 7, 29)  # a Wednesday -- not in PRACTICE_WEEKDAYS
    assert forced_today.strftime("%A") == "Wednesday"
    monkeypatch.setattr(seed_fixtures, "today_central", lambda: forced_today)

    seed_all(default_volumes())

    in_progress = Practice.query.filter_by(status=PracticeStatus.IN_PROGRESS.value).all()
    assert in_progress, "no practice was assigned IN_PROGRESS at all"
    assert all(p.date.date() == forced_today for p in in_progress), (
        f"IN_PROGRESS practice(s) not dated today: "
        f"{[p.date.date() for p in in_progress if p.date.date() != forced_today]}"
    )

    # Also guarantee the schedule itself always includes today, regardless
    # of weekday -- otherwise IN_PROGRESS coverage would silently vanish
    # rather than fail loudly.
    assert any(p.date.date() == forced_today for p in Practice.query.all())


def test_every_practice_status_is_represented(db_session):
    """practices/list.html's filter and detail.html's edit <select> both offer
    all five PracticeStatus values -- seed every one so none of those pills
    or the edit form's dropdown renders against a status nobody has."""
    from app.practices.models import Practice
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_all

    seed_all(default_volumes())
    present = {p.status for p in Practice.query.all()}
    assert {"scheduled", "confirmed", "in_progress", "cancelled", "completed"} <= present


def test_every_event_status_is_represented_by_the_edit_forms_vocabulary(db_session):
    """event_form.html's <select> and events.html's filter both offer
    draft/active/closed -- there is no 'published' EventStatus, despite the
    brief asking for one -- so assert the real vocabulary is what's seeded."""
    from app.events.models import Event
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_all

    seed_all(default_volumes())
    present = {e.status for e in Event.query.all()}
    assert {"draft", "active", "closed"} <= present


def test_every_registration_status_is_represented(db_session):
    from app.events.models import EventRegistration
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_all

    seed_all(default_volumes())
    present = {r.status for r in EventRegistration.query.all()}
    assert {"pending_payment", "confirmed", "cancelled", "refunded"} <= present


def test_status_changes_populated_for_dropped_users(db_session):
    """Prod has zero status_changes rows; seed them for DROPPED users so the
    table isn't empty ahead of any admin surface reading it."""
    from app.models import StatusChange
    from scripts.ui_audit.seed_fixtures import default_volumes, seed_all

    seed_all(default_volumes())
    assert StatusChange.query.count() > 0


def test_seed_all_runs_end_to_end(db_session):
    from app.models import User
    from scripts.ui_audit.seed_fixtures import seed_all

    seed_all({"users": 20, "seasons": 2, "trips": 2, "tags": 8})
    assert User.query.count() == 20
