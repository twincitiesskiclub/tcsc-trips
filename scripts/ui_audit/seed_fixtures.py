# scripts/ui_audit/seed_fixtures.py
"""Populate the local database so every admin pane renders with real content.

The bar is "no pane is empty and no table is one row" -- the spacing problems
this seed exists to expose show up under ordinary data, so plausible content at
roughly production volume is enough. Deterministic, so before/after screenshots
are comparable across runs.

Only builds the "core" tables (users/seasons/trips/tags + the payments and
user_seasons that hang off them). Practices, events, and newsletter records
are Task 5's job, layered on top of this function's return value.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random

from app.constants import UserSeasonStatus, UserStatus
from app.models import Payment, Season, Tag, Trip, User, UserSeason, UserTag, db

REPO = Path(__file__).resolve().parents[2]
SEED = 20260728  # fixed so runs are reproducible

FIRST_NAMES = [
    "Anna", "Bjorn", "Clara", "Devin", "Elin", "Finn", "Greta", "Hans", "Ingrid",
    "Jonas", "Kari", "Lars", "Maja", "Nils", "Oskar", "Petra", "Quinn", "Rune",
    "Sigrid", "Tobias", "Ulla", "Viktor", "Wren", "Yara", "Zach", "Marguerite",
    "Christopher", "Alexandra",
]
LAST_NAMES = [
    "Andersen", "Berg", "Christensen", "Dahl", "Eriksson", "Fjeld", "Gundersen",
    "Haugen", "Iversen", "Johansen", "Kristiansen", "Lindqvist", "Moen", "Nygaard",
    "Olsen", "Pedersen", "Rasmussen", "Solberg", "Thorsen", "Vasquez-Lindstrom",
]

# Production carries 20 tags; the brief's reference list only had 8 plausible
# roles. Extended to 20 so the roles admin page and every tag-badge column
# render at real volume instead of looking sparse.
TAG_SPECS = [
    ("HEAD_COACH", "Head Coach", "🎿", "linear-gradient(135deg,#1c2c44,#3b5578)"),
    ("ASSISTANT_COACH", "Assistant Coach", "⛷️", "linear-gradient(135deg,#2d6a4f,#52b788)"),
    ("BOARD_MEMBER", "Board Member", "🏛️", "linear-gradient(135deg,#6a4c93,#9d78c9)"),
    ("PRACTICE_LEAD", "Practice Lead", "📋", "linear-gradient(135deg,#bc4749,#e07a5f)"),
    ("TRIP_ORGANIZER", "Trip Organizer", "🗺️", "linear-gradient(135deg,#0077b6,#48cae4)"),
    ("WAX_TECH", "Wax Technician", "🧪", "linear-gradient(135deg,#7f5539,#b08968)"),
    ("VOLUNTEER", "Volunteer", "🤝", "linear-gradient(135deg,#606c38,#a3b18a)"),
    ("ALUMNI_MENTOR", "Alumni Mentor", "🎓", "linear-gradient(135deg,#495057,#adb5bd)"),
    ("TREASURER", "Treasurer", "💰", "linear-gradient(135deg,#264653,#2a9d8f)"),
    ("SECRETARY", "Secretary", "📝", "linear-gradient(135deg,#5f0f40,#9a031e)"),
    ("MEMBERSHIP_CHAIR", "Membership Chair", "📇", "linear-gradient(135deg,#3a5a40,#588157)"),
    ("SOCIAL_CHAIR", "Social Chair", "🎉", "linear-gradient(135deg,#d62828,#f77f00)"),
    ("NEWSLETTER_EDITOR", "Newsletter Editor", "📰", "linear-gradient(135deg,#023047,#219ebc)"),
    ("EQUIPMENT_MANAGER", "Equipment Manager", "🎒", "linear-gradient(135deg,#6d6875,#b5838d)"),
    ("SAFETY_OFFICER", "Safety Officer", "🚑", "linear-gradient(135deg,#9d0208,#dc2f02)"),
    ("RACE_CAPTAIN", "Race Captain", "🏁", "linear-gradient(135deg,#03071e,#6a040f)"),
    ("JUNIOR_COACH", "Junior Coach", "🧒", "linear-gradient(135deg,#ffb703,#fb8500)"),
    ("FUNDRAISING_CHAIR", "Fundraising Chair", "💵", "linear-gradient(135deg,#283618,#606c38)"),
    ("PHOTOGRAPHER", "Club Photographer", "📷", "linear-gradient(135deg,#22223b,#4a4e69)"),
    ("WEBMASTER", "Webmaster", "🖥️", "linear-gradient(135deg,#14213d,#457b9d)"),
]

STATUSES = [UserStatus.ACTIVE, UserStatus.PENDING, UserStatus.ALUMNI, UserStatus.DROPPED]
# Approximates prod (126 ACTIVE / 140 ALUMNI out of 266, plus a PENDING/DROPPED
# minority the club has never actually had -- see task brief for why we seed
# them anyway: every admin status filter needs at least one row behind it).
STATUS_WEIGHTS = [0.42, 0.10, 0.40, 0.08]

# Rotated across DROPPED users so all three drop reasons populate their own
# admin filter, not just whichever one falls out of `rng.choice`.
DROPPED_SEASON_STATUSES = [
    UserSeasonStatus.DROPPED_LOTTERY,
    UserSeasonStatus.DROPPED_VOLUNTARY,
    UserSeasonStatus.DROPPED_CAUSE,
]

# Matches the <select> options in app/templates/admin/trip_form.html plus the
# "closed" filter pill in admin_trips.js (a raw status value the form itself
# never writes, but the JS still filters on).
TRIP_STATUSES = ["draft", "active", "closed", "completed"]

# Values the admin edit form's <select>s actually offer (see
# app/templates/admin/user_edit.html) -- not app/constants.py's
# VALID_TECHNIQUES/VALID_TSHIRT_SIZES, which govern the *public* registration
# form and use a different vocabulary ('no_preference' vs 'None', '2XL' vs
# 'XXL'). Using the admin form's own values means the edit page's dropdowns
# show a real selection instead of falling through to a blank option.
TECHNIQUES = ["Classic", "Skate", "None"]
TSHIRT_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
SKI_EXPERIENCE_LEVELS = ["1-3", "3-7", "7+"]

# Raw Payment.status values. Includes one value (COMPLETED_UNMAPPED) with no
# entry in admin_payments.js's STATUS_BADGE_MAP, matching a real quirk in
# production data (9 rows of payments.status='completed') so the "Unknown"
# badge variant has something to render too.
PAYMENT_STATUSES = ["succeeded", "requires_capture", "canceled", "processing", "refunded"]
COMPLETED_UNMAPPED = "completed"


def default_volumes() -> dict:
    """Volumes from the prod survey when available, otherwise sane defaults."""
    shape_file = REPO / ".ui-audit" / "prod-shape.json"
    fallback = {"users": 266, "seasons": 5, "trips": 8, "tags": len(TAG_SPECS)}
    if not shape_file.exists():
        return fallback
    counts = json.loads(shape_file.read_text()).get("row_counts", {})
    return {
        "users": counts.get("users") or fallback["users"],
        "seasons": counts.get("seasons") or fallback["seasons"],
        "trips": counts.get("trips") or fallback["trips"],
        "tags": max(counts.get("tags") or 0, len(TAG_SPECS)),
    }


def _make_tags(volumes):
    tags = []
    for name, display, emoji, gradient in TAG_SPECS[: volumes["tags"]]:
        tag = Tag(
            name=name,
            display_name=display,
            emoji=emoji,
            gradient=gradient,
            description=f"Members designated as {display.lower()} for the current season.",
        )
        db.session.add(tag)
        tags.append(tag)
    db.session.flush()
    return tags


def _make_seasons(volumes):
    seasons = []
    base_year = 2026 - volumes["seasons"] + 1
    for index in range(volumes["seasons"]):
        year = base_year + index
        season = Season(
            name=f"{year}-{str(year + 1)[2:]} Season",
            season_type="winter",
            year=year,
            start_date=date(year, 11, 1),
            end_date=date(year + 1, 3, 31),
            price_cents=32500,
            returning_start=datetime(year, 8, 1, 12, 0),
            returning_end=datetime(year, 8, 21, 12, 0),
            new_start=datetime(year, 9, 1, 12, 0),
            new_end=datetime(year, 9, 21, 12, 0),
            registration_limit=280,
            description=(
                f"Registration for the {year}-{str(year + 1)[2:]} nordic season, "
                "including coached practices, waxing support, and club trips."
            ),
            is_current=(index == volumes["seasons"] - 1),
        )
        db.session.add(season)
        seasons.append(season)
    db.session.flush()
    return seasons


def _make_trips(volumes):
    trips = []
    names = ["Sisu Ski Fest", "Birkie Week", "Mora Vasaloppet", "Noquemanon Weekend",
             "Korteloppet Camp", "Boulder Lake Training Camp", "Elk River Classic",
             "Cable Union Camp"]
    destinations = ["Ironwood, MI", "Hayward, WI", "Mora, MN", "Marquette, MI",
                     "Cable, WI", "Duluth, MN", "Elk River, MN", "Cable, WI"]
    for index in range(volumes["trips"]):
        # Spread trips around "today" (2026-07-28) so both the upcoming and
        # past groupings in the admin trip list have rows in them.
        start = datetime(2026, 1, 15) + timedelta(days=45 * index)
        trips.append(
            Trip(
                slug=f"seed-trip-{index + 1}",
                name=names[index % len(names)],
                destination=destinations[index % len(destinations)],
                slack_channel_name=f"trip-seed-{index + 1}",
                max_participants_standard=40,
                max_participants_extra=10,
                start_date=start,
                end_date=start + timedelta(days=3),
                signup_start=start - timedelta(days=60),
                signup_end=start - timedelta(days=14),
                price_low=18500,
                price_high=27500,
                description=(
                    "Club trip with shared lodging, wax room access, and coached "
                    "sessions on Saturday morning."
                ),
                status=TRIP_STATUSES[index % len(TRIP_STATUSES)],
            )
        )
    db.session.add_all(trips)
    db.session.flush()
    return trips


def _make_users(volumes, rng):
    users = []
    for index in range(volumes["users"]):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
        # Force the first four users to cover all four statuses so
        # test_every_user_status_is_represented (and the admin status
        # filters it stands in for) never depend on random luck -- the
        # remaining users are weighted to match prod's rough shape.
        if index < len(STATUSES):
            status = STATUSES[index]
        else:
            status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        user = User(
            first_name=first,
            last_name=last,
            email=f"{first.lower()}.{last.lower().replace('-', '')}{index}@example.com",
            status=status,
            seasons_since_active=0 if status == UserStatus.ACTIVE else rng.randint(1, 3),
            phone=f"612-555-{1000 + index:04d}",
            date_of_birth=date(1975 + (index % 35), 1 + (index % 12), 1 + (index % 28)),
            pronouns=rng.choice(["she/her", "he/him", "they/them", None]),
            preferred_technique=rng.choice(TECHNIQUES),
            tshirt_size=rng.choice(TSHIRT_SIZES),
            ski_experience=rng.choice(SKI_EXPERIENCE_LEVELS),
            emergency_contact_name=f"{rng.choice(FIRST_NAMES)} {last}",
            emergency_contact_relation=rng.choice(["spouse", "parent", "sibling", "friend"]),
            emergency_contact_phone=f"612-555-{5000 + index:04d}",
            emergency_contact_email=f"ec{index}@example.com",
            notes=(
                "Requested classic-only groups; prefers Thursday sessions."
                if index % 9 == 0 else None
            ),
        )
        db.session.add(user)
        users.append(user)
    db.session.flush()
    return users


def _tag_users(users, tags, rng):
    """Tag roughly production's ~36% of members, some with 2-3 roles.

    Production tags 95/266 (~36%) of members. The brief's every-6th-user
    version (~17%) would leave the roles column and every tag-badge cell
    looking sparse, so this samples closer to prod's real saturation.
    """
    for index, user in enumerate(users):
        if index % 100 >= 36:
            continue
        for tag in rng.sample(tags, k=min(len(tags), rng.choice([1, 2, 2, 3]))):
            db.session.add(UserTag(user_id=user.id, tag_id=tag.id))


def _make_user_seasons_and_payments(users, seasons, rng):
    current_season = seasons[-1]
    past_season = seasons[0] if len(seasons) > 1 else seasons[-1]
    dropped_index = 0
    base_registration = date(2026, 6, 1)

    for index, user in enumerate(users):
        # ALUMNI members were active in a past season, not the current one --
        # tie their UserSeason to an older season so the roster/CSV export
        # for non-current seasons has rows too, not just the current one.
        if user.status == UserStatus.ALUMNI:
            season = past_season
            season_status = UserSeasonStatus.ACTIVE
        elif user.status == UserStatus.DROPPED:
            season = current_season
            season_status = DROPPED_SEASON_STATUSES[dropped_index % len(DROPPED_SEASON_STATUSES)]
            dropped_index += 1
        elif user.status == UserStatus.PENDING:
            season = current_season
            season_status = UserSeasonStatus.PENDING_LOTTERY
        else:  # ACTIVE
            season = current_season
            season_status = UserSeasonStatus.ACTIVE

        registration_date = base_registration + timedelta(days=index % 45)
        registration_type = "returning" if rng.random() < 0.6 else "new"
        payment_status = rng.choice(PAYMENT_STATUSES)
        db.session.add(
            UserSeason(
                user_id=user.id,
                season_id=season.id,
                registration_type=registration_type,
                registration_date=registration_date,
                payment_date=(
                    registration_date + timedelta(days=2)
                    if payment_status == "succeeded" else None
                ),
                status=season_status,
            )
        )

        db.session.add(
            Payment(
                payment_intent_id=f"pi_seed_{index:05d}",
                email=user.email,
                name=user.full_name,
                amount=season.price_cents,
                status=payment_status,
                payment_type="season",
                season_id=season.id,
                user_id=user.id,
            )
        )

    # A handful of stray payments carrying a raw status with no display_status
    # mapping (see admin.py's display_status dict), so the "Unknown" badge
    # variant -- which real prod data actually triggers -- has rows too.
    for offset, user in enumerate(users[:5]):
        db.session.add(
            Payment(
                payment_intent_id=f"pi_seed_unmapped_{offset:03d}",
                email=user.email,
                name=user.full_name,
                amount=current_season.price_cents,
                status=COMPLETED_UNMAPPED,
                payment_type="season",
                season_id=current_season.id,
                user_id=user.id,
            )
        )


def _make_trip_payments(users, trips, rng):
    """Trip payments so the payments dashboard has more than one payment_type."""
    for index, trip in enumerate(trips):
        window = users[index * 5: index * 5 + 12]
        for offset, user in enumerate(window):
            db.session.add(
                Payment(
                    payment_intent_id=f"pi_seed_trip_{index}_{offset:03d}",
                    email=user.email,
                    name=user.full_name,
                    amount=trip.price_low,
                    status=rng.choice(PAYMENT_STATUSES),
                    payment_type="trip",
                    trip_id=trip.id,
                    user_id=user.id,
                )
            )


def seed_core(volumes: dict) -> dict:
    rng = Random(SEED)

    tags = _make_tags(volumes)
    seasons = _make_seasons(volumes)
    trips = _make_trips(volumes)
    users = _make_users(volumes, rng)

    _tag_users(users, tags, rng)
    _make_user_seasons_and_payments(users, seasons, rng)
    _make_trip_payments(users, trips, rng)

    db.session.commit()
    return {"users": users, "seasons": seasons, "trips": trips, "tags": tags}
