# scripts/ui_audit/seed_fixtures.py
"""Populate the local database so every admin pane renders with real content.

The bar is "no pane is empty and no table is one row" -- the spacing problems
this seed exists to expose show up under ordinary data, so plausible content at
roughly production volume is enough. Deterministic, so before/after screenshots
are comparable across runs.

`seed_core()` builds the "core" tables (users/seasons/trips/tags + the
payments and user_seasons that hang off them). `seed_domain()` layers
practices, events, and newsletter records on top of `seed_core()`'s return
value. `seed_all()` runs both.
"""

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random

from app.constants import UserSeasonStatus, UserStatus
from app.events.models import (
    Audience,
    Event,
    EventParticipant,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.models import Payment, Season, StatusChange, Tag, Trip, User, UserSeason, UserTag, db
from app.newsletter.interfaces import NewsletterStatus, SubmissionStatus, SubmissionType
from app.newsletter.models import Newsletter, NewsletterPrompt, NewsletterSubmission
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.interfaces import CancellationStatus, LeadRole, PracticeStatus, RSVPStatus
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
from app.utils import now_central_naive, today_central

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

# Matches the <select> options in app/templates/admin/trip_form.html
# (draft/active/completed/canceled). admin_trips.js's list-page filter pills
# additionally recognize a "closed" status value, but the edit form has no
# matching <option> for it -- seeding a trip with status="closed" would make
# its own edit form silently pre-select "Draft" for a record that isn't one,
# an impossible admin state we'd rather not hand the spacing screenshot pass.
# Prod itself never wrote "closed" either (its trips.status enum was only
# active/completed), so using the edit form's real four values loses nothing.
TRIP_STATUSES = ["draft", "active", "completed", "canceled"]

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


TAG_SATURATION = 0.36  # fraction of members carrying at least one tag


def _tag_users(users, tags, rng):
    """Tag roughly production's ~36% of members, some with 2-3 roles.

    Production tags 95/266 (~36%) of members. The brief's every-6th-user
    version (~17%) would leave the roles column and every tag-badge cell
    looking sparse, so this samples closer to prod's real saturation.

    Scaled off len(users), not a fixed modulo -- `index % 100 < 36` only
    approximates 36% when there are many more than 100 users; at 40 users
    (this project's own small-volume test fixture) every index in 0-35
    satisfies `< 36`, tagging 90% of them instead of 36%.
    """
    tagged_count = round(TAG_SATURATION * len(users))
    for index, user in enumerate(users):
        if index >= tagged_count:
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


# =============================================================================
# Domain seed (Task 5): practices, events, newsletter
# =============================================================================
#
# Enum vocabulary for every status/enum value below was verified against the
# template that actually renders it -- not the model, not app/constants.py --
# per the lesson from Task 4's seeded-but-unrenderable "closed" trip status:
#
#   - Practice.status: app/templates/admin/practices/list.html's filter and
#     detail.html's <select> both offer all five PracticeStatus values
#     (scheduled/confirmed/in_progress/cancelled/completed) -- all five used.
#   - Event.status: event_form.html's <select> and events.html's filter both
#     offer only draft/active/closed. EventStatus has no "published" value
#     (the brief asked for one) -- "active" is the live-and-accepting state,
#     used here for the second event so draft/active/closed are all covered.
#   - EventRegistration.status: event_registrations.html's filter offers
#     exactly RegistrationStatus.ALL (pending_payment/confirmed/cancelled/
#     refunded) -- all four used.
#   - PracticeLead.role: admin_practices.js's _detail_context.js maps
#     lead/coach to display labels (assist is a retired, still-readable
#     value per admin_practices.py's own comment) -- lead/coach used.
#   - LeadAvailabilityPoll.status: admin_practices.js's POLL_STATUS_LABEL
#     covers draft/open/closed -- all three used across the three polls.

REGISTRATION_STATUSES = [
    RegistrationStatus.PENDING_PAYMENT,
    RegistrationStatus.CONFIRMED,
    RegistrationStatus.CANCELLED,
    RegistrationStatus.REFUNDED,
]

PRACTICE_LOCATION_SPECS = [
    # name, spot, address, lat, lon, parking_notes
    (
        "Theodore Wirth Park", "Trailhead Chalet parking lot",
        "1301 Theodore Wirth Pkwy, Golden Valley, MN", 45.0057, -93.3226,
        "Lot fills by 5:30pm on weeknights; overflow parking along Wirth Pkwy.",
    ),
    (
        "Hyland Hills", "Richardson Nature Center lot",
        "10145 Bush Lake Rd, Bloomington, MN", 44.8398, -93.3654,
        "Enter from Bush Lake Rd; trail access is behind the nature center.",
    ),
    (
        "Elm Creek Park Reserve", "Chalet parking lot",
        "14105 Elm Creek Rd, Maple Grove, MN", 45.1462, -93.4635,
        "Chalet lot; groomed trail starts at the chalet's rear door.",
    ),
    (
        "Battle Creek Regional Park", "Upper lot off Winthrop St",
        "1000 Winthrop St S, St Paul, MN", 44.9336, -93.0102,
        "Small lot -- carpool when possible.",
    ),
]

SOCIAL_LOCATION_SPECS = [
    ("Grumpy's NE", "2200 NE University Ave, Minneapolis, MN"),
    ("Sisu Coffee Bar", "1223 Marshall St NE, Minneapolis, MN"),
]

PRACTICE_ACTIVITY_SPECS = [
    ("Classic Skiing", ["classic skis", "poles", "kick wax"]),
    ("Skate Skiing", ["skate skis", "poles"]),
    ("Trail Running", ["trail shoes", "headlamp"]),
    ("Roller Skiing", ["roller skis", "poles", "helmet"]),
    ("Strength & Mobility", ["mat", "resistance band"]),
]

PRACTICE_TYPE_SPECS = [
    # name, fitness_goals, has_intervals
    ("Skate Technique", ["Technique", "Balance"], False),
    ("Classic Distance", ["Aerobic Base", "Endurance"], False),
    ("Strength & Balance", ["Strength", "Core"], False),
    ("Trail Run", ["Aerobic Base"], False),
    ("Interval Session", ["VO2 Max", "Threshold"], True),
]

# Weekday (Mon=0) -> (hour, minute). Tue/Thu evenings, Sat morning, matching
# a realistic nordic-club practice cadence.
PRACTICE_WEEKDAYS = {1: (17, 30), 3: (17, 30), 5: (9, 0)}

WORKOUT_TEXTS = [
    "6x3min @ threshold, 2min recovery between.",
    "60min continuous distance at conversational pace.",
    "4x8min @ tempo with active recovery.",
    "Technique focus: diagonal stride drills, then 30min easy distance.",
]

CANCELLATION_REASON_TYPES = ["weather", "trail_conditions", "no_lead", "event_conflict"]
CANCELLATION_SUMMARIES = {
    "weather": "Wind chill forecast below -20F at practice time.",
    "trail_conditions": "Trails not yet groomed after recent snowfall.",
    "no_lead": "No confirmed lead within 24 hours of practice.",
    "event_conflict": "Location closed for a permitted race.",
}

EVENT_SPECS = [
    dict(
        slug="frosty-5k-fun-run",
        name="Frosty 5K Fun Run",
        description=(
            "A casual 5K out-and-back on groomed trail, open to the public. "
            "Costumes encouraged."
        ),
        location="Theodore Wirth Park",
        status=EventStatus.DRAFT,
        audience=Audience.EXTERNAL,
        days_from_today=45,
        capacity=150,
    ),
    dict(
        slug="tcsc-season-kickoff",
        name="TCSC Season Kickoff Party",
        description=(
            "Kick off the season with the team: gear swap, wax demo, and potluck."
        ),
        location="Elm Creek Park Reserve Chalet",
        status=EventStatus.ACTIVE,
        audience=Audience.INTERNAL,
        days_from_today=20,
        capacity=80,
    ),
    dict(
        slug="wax-clinic-gear-swap",
        name="Wax Clinic & Gear Swap",
        description="Hands-on wax clinic followed by a member gear swap.",
        location="Hyland Hills",
        status=EventStatus.CLOSED,
        audience=Audience.BOTH,
        days_from_today=-25,
        capacity=60,
    ),
]

NEWSLETTER_PROMPT_SPECS = [
    (
        "main",
        "Primary generation prompt for weekly newsletters with full content.",
        "You are drafting the TCSC Monthly Dispatch. Use a warm, upbeat club "
        "voice and lead with the most exciting practice or trip news.",
    ),
    (
        "quiet",
        "Shorter prompt for weeks with minimal activity.",
        "Activity was light this period -- keep the dispatch brief and focus "
        "on upcoming practices and any open registrations.",
    ),
    (
        "final",
        "Prompt for generating the final polished version before publishing.",
        "Polish the draft below for publishing: tighten language, keep the "
        "section order, and preserve every link.",
    ),
]

NEWSLETTER_STATUSES = [
    NewsletterStatus.PUBLISHED,
    NewsletterStatus.PUBLISHED,
    NewsletterStatus.BUILDING,
]

SUBMISSION_SPECS = [
    (
        SubmissionType.CONTENT,
        "Loved seeing everyone at Saturday's practice -- can't wait for the next one!",
    ),
    (
        SubmissionType.SPOTLIGHT,
        "Shoutout to our newest skate skiers who braved their first lesson this week.",
    ),
    (SubmissionType.EVENT, "Reminder: sign-ups for the Frosty 5K close next week."),
    (
        SubmissionType.ANNOUNCEMENT,
        "Board meeting minutes from this month are posted in #announcements.",
    ),
]
SUBMISSION_STATUSES = [
    SubmissionStatus.INCLUDED,
    SubmissionStatus.PENDING,
    SubmissionStatus.PENDING,
    SubmissionStatus.REJECTED,
]

DROP_REASONS = [
    "Requested to be removed after moving out of state.",
    "Dropped after non-payment following lottery placement.",
    "Voluntary withdrawal -- schedule conflict with practices.",
]


def _make_practice_locations():
    locations = []
    for name, spot, address, lat, lon, notes in PRACTICE_LOCATION_SPECS:
        location = PracticeLocation(
            name=name, spot=spot, address=address,
            google_maps_url=f"https://maps.google.com/?q={lat},{lon}",
            latitude=lat, longitude=lon, parking_notes=notes,
        )
        db.session.add(location)
        locations.append(location)
    db.session.flush()
    return locations


def _make_social_locations():
    socials = []
    for name, address in SOCIAL_LOCATION_SPECS:
        social = SocialLocation(
            name=name, address=address,
            google_maps_url=f"https://maps.google.com/?q={address.replace(' ', '+')}",
        )
        db.session.add(social)
        socials.append(social)
    db.session.flush()
    return socials


def _make_practice_activities():
    activities = []
    for name, gear in PRACTICE_ACTIVITY_SPECS:
        activity = PracticeActivity(name=name, gear_required=gear)
        db.session.add(activity)
        activities.append(activity)
    db.session.flush()
    return activities


def _make_practice_types():
    types = []
    for name, goals, has_intervals in PRACTICE_TYPE_SPECS:
        practice_type = PracticeType(
            name=name, fitness_goals=goals, has_intervals=has_intervals,
        )
        db.session.add(practice_type)
        types.append(practice_type)
    db.session.flush()
    return types


def _practice_dates():
    """~36 Tue/Thu/Sat sessions spanning 6 weeks before through 6 weeks after
    today -- both the practices list and the calendar need populated ranges
    on either side of "now", not just a pile of future rows."""
    anchor = today_central()
    dates = []
    for offset in range(-42, 42):
        day = anchor + timedelta(days=offset)
        time_of_day = PRACTICE_WEEKDAYS.get(day.weekday())
        if time_of_day is None:
            continue
        hour, minute = time_of_day
        dates.append(datetime(day.year, day.month, day.day, hour, minute))

    # Guarantee one session lands exactly on "today", regardless of which
    # weekday that is. _make_practices only ever assigns IN_PROGRESS to a
    # practice whose date == today (a future-dated row can't be "in
    # progress"), so without this, IN_PROGRESS coverage -- and the admin
    # filter pill it backs -- would silently disappear on the 4 of 7 days
    # that aren't Tue/Thu/Sat.
    if not any(d.date() == anchor for d in dates):
        dates.append(datetime(anchor.year, anchor.month, anchor.day, 17, 30))
        dates.sort()

    return dates


def _make_practices(locations, socials, activities, types, rng):
    dates = _practice_dates()
    today = today_central()
    practices = []
    past_count = future_count = 0

    for index, practice_date in enumerate(dates):
        is_future = practice_date.date() >= today
        if practice_date.date() == today:
            # IN_PROGRESS means "happening today" -- a date days in the
            # future rendered next to that status is an impossible state in
            # the exact admin row (admin_practices.js renders date and
            # status badge together) this project's audit exists to catch.
            # _practice_dates() guarantees a session lands on `today`, so
            # this branch is always reachable regardless of weekday.
            status = PracticeStatus.IN_PROGRESS.value
        elif is_future:
            # First real future session covers a confirmed-but-not-yet-
            # started lead, so that filter pill has a row without waiting on
            # random luck. A sparse cancellation further out shows the pill
            # can occur even before the block.
            if future_count == 0:
                status = PracticeStatus.CONFIRMED.value
            elif future_count % 7 == 0:
                status = PracticeStatus.CANCELLED.value
            else:
                status = PracticeStatus.SCHEDULED.value
            future_count += 1
        else:
            status = (
                PracticeStatus.CANCELLED.value if past_count % 6 == 0
                else PracticeStatus.COMPLETED.value
            )
            past_count += 1

        location = locations[index % len(locations)]
        is_dark = practice_date.hour >= 17
        practice = Practice(
            date=practice_date,
            day_of_week=practice_date.strftime("%A"),
            status=status,
            location_id=location.id,
            social_location_id=(
                socials[index % len(socials)].id if index % 4 == 0 else None
            ),
            warmup_description="15min easy striding, dynamic stretching, drills.",
            workout_description=WORKOUT_TEXTS[index % len(WORKOUT_TEXTS)],
            cooldown_description="10min easy ski + static stretching.",
            logistics_notes=(
                "Bring lights -- low visibility after sunset." if is_dark else None
            ),
            is_dark_practice=is_dark,
            leads_needed=rng.choice([1, 2, 2, 3]),
            cancellation_reason=(
                CANCELLATION_SUMMARIES[
                    CANCELLATION_REASON_TYPES[index % len(CANCELLATION_REASON_TYPES)]
                ] if status == PracticeStatus.CANCELLED.value else None
            ),
        )
        practice.activities.append(activities[index % len(activities)])
        if index % 3 == 0:
            practice.activities.append(activities[(index + 1) % len(activities)])
        practice.practice_types.append(types[index % len(types)])
        db.session.add(practice)
        practices.append(practice)

    # The farthest-out block hasn't been published yet -- gives the
    # availability-poll widget both a draft block to collect against and
    # already-published sessions to compare it to. is_draft is deliberately
    # independent of status (see the model's own comment), so these get
    # bumped back to "scheduled" rather than staying whatever the modulo
    # above assigned.
    future_practices = [p for p in practices if p.date.date() >= today]
    for practice in future_practices[-6:]:
        practice.is_draft = True
        practice.status = PracticeStatus.SCHEDULED.value

    db.session.flush()
    return practices


def _make_practice_leads(practices, users, rng):
    lead_candidates = users[: max(10, len(users) // 3)] or users
    for index, practice in enumerate(practices):
        if practice.status == PracticeStatus.CANCELLED.value and rng.random() < 0.5:
            continue  # some cancelled practices never got a lead assigned
        lead_user = lead_candidates[index % len(lead_candidates)]
        confirmed = index % 3 != 0
        db.session.add(
            PracticeLead(
                practice_id=practice.id, user_id=lead_user.id,
                role=LeadRole.LEAD.value, confirmed=confirmed,
                confirmed_at=now_central_naive() if confirmed else None,
            )
        )
        if index % 4 == 0:
            coach_user = lead_candidates[(index + 3) % len(lead_candidates)]
            coach_confirmed = index % 5 != 0
            db.session.add(
                PracticeLead(
                    practice_id=practice.id, user_id=coach_user.id,
                    role=LeadRole.COACH.value, confirmed=coach_confirmed,
                    confirmed_at=now_central_naive() if coach_confirmed else None,
                )
            )


def _make_practice_rsvps(practices, users, rng):
    """RSVPs on past practices only -- nobody RSVPs to a session that already happened."""
    today = today_central()
    past_practices = [p for p in practices if p.date.date() < today]
    for practice in past_practices:
        attendee_count = min(len(users), rng.randint(4, 10))
        for user in rng.sample(users, k=attendee_count):
            db.session.add(
                PracticeRSVP(
                    practice_id=practice.id, user_id=user.id,
                    status=rng.choices(
                        [RSVPStatus.GOING.value, RSVPStatus.MAYBE.value, RSVPStatus.NOT_GOING.value],
                        weights=[0.7, 0.2, 0.1], k=1,
                    )[0],
                    responded_at=now_central_naive() - timedelta(days=rng.randint(1, 30)),
                )
            )


def _make_cancellation_requests(practices, users, rng):
    """One approved proposal per actually-cancelled practice, plus a rejected
    and a still-pending/expired proposal against practices that were NOT
    cancelled -- only an *approved* proposal cancels a practice, so seeding
    'rejected' against a cancelled row would be an impossible state, exactly
    the kind of brief-vs-template mismatch this file's header warns about."""
    decider_pool = users[:10] or users
    cancelled = [p for p in practices if p.status == PracticeStatus.CANCELLED.value]
    non_cancelled = [p for p in practices if p.status != PracticeStatus.CANCELLED.value]

    for index, practice in enumerate(cancelled):
        reason_type = CANCELLATION_REASON_TYPES[index % len(CANCELLATION_REASON_TYPES)]
        proposed_at = practice.date - timedelta(hours=20)
        decider = decider_pool[index % len(decider_pool)]
        db.session.add(
            CancellationRequest(
                practice_id=practice.id,
                status=CancellationStatus.APPROVED.value,
                reason_type=reason_type,
                reason_summary=CANCELLATION_SUMMARIES[reason_type],
                proposed_at=proposed_at,
                expires_at=proposed_at + timedelta(hours=2),
                decided_at=proposed_at + timedelta(hours=1),
                decided_by_user_id=decider.id,
                decision_notes="Approved -- conditions confirmed unsafe.",
            )
        )

    now = now_central_naive()
    extra_specs = [
        (CancellationStatus.REJECTED.value, "Coaches judged conditions marginal but safe; practice proceeded."),
        (CancellationStatus.PENDING.value, None),
        (CancellationStatus.EXPIRED.value, None),
    ]
    for index, (cr_status, notes) in enumerate(extra_specs):
        if index >= len(non_cancelled):
            break
        practice = non_cancelled[index]
        reason_type = CANCELLATION_REASON_TYPES[index % len(CANCELLATION_REASON_TYPES)]
        proposed_at = practice.date - timedelta(hours=20) if practice.date > now else now - timedelta(hours=1)
        is_decided = cr_status in (CancellationStatus.REJECTED.value, CancellationStatus.EXPIRED.value)
        db.session.add(
            CancellationRequest(
                practice_id=practice.id,
                status=cr_status,
                reason_type=reason_type,
                reason_summary=CANCELLATION_SUMMARIES[reason_type],
                proposed_at=proposed_at,
                expires_at=proposed_at + timedelta(hours=2),
                decided_at=proposed_at + timedelta(hours=2) if is_decided else None,
                decided_by_user_id=(
                    decider_pool[index % len(decider_pool)].id
                    if cr_status == CancellationStatus.REJECTED.value else None
                ),
                decision_notes=notes,
            )
        )


def _make_availability_polls(practices, users, rng):
    """Prod has zero rows here, but /admin/availability/ backs a live widget
    on the practices list page (admin_practices.js's pl-poll cards) -- an
    empty response renders as an empty section, never screenshotted for
    spacing. Seed one poll per PollStatus (draft/open/closed) so all three
    status pills and the publish/unpublished-count layout get exercised."""
    today = today_central()
    participants_pool = users[:12] or users
    future_drafts = [p for p in practices if p.is_draft]
    published_future = [
        p for p in practices if p.date.date() >= today and not p.is_draft
    ]
    recently_past = [p for p in practices if p.date.date() < today][-6:]

    if not recently_past:
        return  # degenerate practice list (shouldn't happen at real volume)

    polls = []

    closed_poll = LeadAvailabilityPoll(
        starts_on=recently_past[0].date.date(), ends_on=recently_past[-1].date.date(),
        status=PollStatus.CLOSED, is_shadow=True, channel_id="C0SEEDSHADOW1",
        done_emoji="white_check_mark",
        opened_at=now_central_naive() - timedelta(days=14),
        closed_at=now_central_naive() - timedelta(days=7),
    )
    db.session.add(closed_poll)
    polls.append((closed_poll, recently_past))

    if published_future:
        open_block = published_future[:6]
        open_poll = LeadAvailabilityPoll(
            starts_on=open_block[0].date.date(), ends_on=open_block[-1].date.date(),
            status=PollStatus.OPEN, is_shadow=True, channel_id="C0SEEDSHADOW1",
            done_emoji="white_check_mark",
            opened_at=now_central_naive() - timedelta(days=2),
        )
        db.session.add(open_poll)
        polls.append((open_poll, open_block))

    if future_drafts:
        draft_poll = LeadAvailabilityPoll(
            starts_on=future_drafts[0].date.date(), ends_on=future_drafts[-1].date.date(),
            status=PollStatus.DRAFT, is_shadow=True, channel_id="C0SEEDSHADOW1",
        )
        db.session.add(draft_poll)
        polls.append((draft_poll, future_drafts))

    db.session.flush()

    letters = "abcdefghijklmnopqrstuvwxyz"
    for poll, block in polls:
        for position, practice in enumerate(block):
            db.session.add(
                LeadAvailabilityPollPractice(
                    poll_id=poll.id, practice_id=practice.id,
                    emoji=f"letter_{letters[position % len(letters)]}", position=position,
                )
            )

        poll_participants = participants_pool[: min(len(participants_pool), 6)]
        for index, user in enumerate(poll_participants):
            status = (
                ParticipantStatus.DONE if poll.status == PollStatus.CLOSED
                else (ParticipantStatus.RESPONDED if index % 3 else ParticipantStatus.PENDING)
            )
            db.session.add(
                LeadAvailabilityParticipant(
                    poll_id=poll.id, user_id=user.id, status=status,
                    nudge_count=0 if status == ParticipantStatus.PENDING else rng.randint(0, 2),
                )
            )

        if poll.status == PollStatus.DRAFT:
            continue  # a draft poll hasn't been posted, so it has no responses
        for user in poll_participants:
            for practice in block[: max(1, len(block) // 2)]:
                if rng.random() < 0.6:
                    db.session.add(
                        LeadAvailabilityResponse(
                            poll_id=poll.id, practice_id=practice.id, user_id=user.id,
                            answered_for_date=practice.date,
                            answered_for_location_id=practice.location_id,
                        )
                    )


def _make_events():
    events = []
    for spec in EVENT_SPECS:
        event_date = now_central_naive() + timedelta(days=spec["days_from_today"])
        event = Event(
            slug=spec["slug"], name=spec["name"], description=spec["description"],
            location=spec["location"], event_date=event_date,
            signup_start=event_date - timedelta(days=60),
            signup_end=event_date - timedelta(days=7),
            capacity=spec["capacity"], status=spec["status"], audience=spec["audience"],
        )
        db.session.add(event)
        events.append(event)
    db.session.flush()
    return events


def _make_event_price_options(events):
    """Every event gets 2 price options: an individual and a family bundle,
    so the participant-roles editor and the registration table's
    participant_N columns both render with more than one shape."""
    price_options = []
    for event in events:
        individual = EventPriceOption(
            event_id=event.id, name="Individual", description="One registrant.",
            price_cents=2500, member_price_cents=1500,
            participant_roles=["Participant"], sort_order=0,
        )
        family = EventPriceOption(
            event_id=event.id, name="Family (up to 4)", description="Up to four participants.",
            price_cents=6000, member_price_cents=4000,
            participant_roles=["Participant", "Participant", "Participant", "Participant"],
            sort_order=1,
        )
        db.session.add_all([individual, family])
        price_options.append((event, [individual, family]))
    db.session.flush()
    return price_options


def _make_event_registrations(price_options, users, rng):
    counter = 0
    for event, options in price_options:
        for offset in range(3):
            option = options[offset % len(options)]
            user = users[(counter * 3 + offset) % len(users)]
            status = REGISTRATION_STATUSES[counter % len(REGISTRATION_STATUSES)]
            registration = EventRegistration(
                event_id=event.id, price_option_id=option.id,
                contact_email=user.email, contact_phone=user.phone or "612-555-0100",
                team_name=f"Team {user.last_name}" if len(option.participant_roles) > 1 else None,
                amount_cents=option.member_price_cents or option.price_cents,
                discount_applied=counter % 5 == 0,
                status=status,
                payment_intent_id=(
                    f"pi_seed_event_{counter:04d}"
                    if status != RegistrationStatus.PENDING_PAYMENT else None
                ),
                created_at=now_central_naive() - timedelta(days=counter),
            )
            db.session.add(registration)
            db.session.flush()
            for position, role_label in enumerate(option.participant_roles, start=1):
                participant_user = users[(counter * 3 + offset + position) % len(users)]
                db.session.add(
                    EventParticipant(
                        registration_id=registration.id, position=position, role_label=role_label,
                        name=participant_user.full_name,
                        date_of_birth=participant_user.date_of_birth or date(1990, 1, 1),
                        email=participant_user.email,
                        phone=participant_user.phone or "612-555-0100",
                        emergency_contact_name=(
                            participant_user.emergency_contact_name
                            or f"{participant_user.first_name} Contact"
                        ),
                        emergency_contact_phone=(
                            participant_user.emergency_contact_phone
                            or "612-555-0199"
                        ),
                    )
                )
            counter += 1


def _make_newsletter_prompts():
    for name, description, content in NEWSLETTER_PROMPT_SPECS:
        db.session.add(
            NewsletterPrompt(
                name=name, description=description, content=content,
                version=1, is_active=True,
                created_by_email="admin@tcsc.org", updated_by_email="admin@tcsc.org",
            )
        )
    db.session.flush()


def _make_newsletters():
    newsletters = []
    anchor = today_central().replace(day=1)
    for index in range(3):
        # Walk back 2, 1, 0 months from the current month.
        months_back = 2 - index
        year = anchor.year
        month = anchor.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        period_start = datetime(year, month, 1)
        _, last_day = monthrange(year, month)
        period_end = datetime(year, month, last_day, 23, 59, 59)
        status = NEWSLETTER_STATUSES[index]
        newsletter = Newsletter(
            week_start=period_start, week_end=period_end,
            month_year=f"{year}-{month:02d}",
            period_start=period_start, period_end=period_end,
            publish_target_date=datetime(year, month, 15, 12, 0, 0),
            qotm_question="What's one ski goal you're chasing this season?",
            status=status.value,
            current_version=2 if status != NewsletterStatus.BUILDING else 0,
            published_at=period_end if status == NewsletterStatus.PUBLISHED else None,
        )
        db.session.add(newsletter)
        newsletters.append(newsletter)
    db.session.flush()
    return newsletters


def _make_newsletter_submissions(newsletters, users):
    for index, (submission_type, content) in enumerate(SUBMISSION_SPECS):
        user = users[index % len(users)]
        status = SUBMISSION_STATUSES[index]
        # The last submission predates any newsletter existing -- a real
        # state per the model's own nullable=True comment ("may be
        # submitted before newsletter exists").
        newsletter = newsletters[index % len(newsletters)] if index < len(SUBMISSION_SPECS) - 1 else None
        db.session.add(
            NewsletterSubmission(
                newsletter_id=newsletter.id if newsletter else None,
                slack_user_id=f"U0SEED{index:03d}",
                display_name=user.full_name,
                submission_type=submission_type.value,
                content=content,
                permission_to_name=index % 2 == 0,
                status=status.value,
                included_in_version=2 if status == SubmissionStatus.INCLUDED else None,
                submitted_at=now_central_naive() - timedelta(days=index * 3),
            )
        )


def _make_status_changes(users, rng):
    """Prod has zero status_changes rows. There's no admin surface reading
    this table yet (grepped app/templates and app/routes -- only the
    User.status_changes relationship exists), but the brief calls it out
    explicitly as a table to populate ahead of that surface being built, so
    seed it for DROPPED users regardless."""
    for user in users:
        if user.status != UserStatus.DROPPED:
            continue
        db.session.add(
            StatusChange(
                user_id=user.id, previous_status=UserStatus.ACTIVE, new_status=UserStatus.DROPPED,
                reason=rng.choice(DROP_REASONS),
                changed_at=now_central_naive() - timedelta(days=rng.randint(10, 200)),
            )
        )


def seed_domain(core: dict) -> None:
    """Populate practices, events, and newsletter tables on top of seed_core's output."""
    rng = Random(SEED)
    users = core["users"]

    locations = _make_practice_locations()
    socials = _make_social_locations()
    activities = _make_practice_activities()
    types = _make_practice_types()
    practices = _make_practices(locations, socials, activities, types, rng)

    _make_practice_leads(practices, users, rng)
    _make_practice_rsvps(practices, users, rng)
    _make_cancellation_requests(practices, users, rng)
    _make_availability_polls(practices, users, rng)

    events = _make_events()
    price_options = _make_event_price_options(events)
    _make_event_registrations(price_options, users, rng)

    _make_newsletter_prompts()
    newsletters = _make_newsletters()
    _make_newsletter_submissions(newsletters, users)

    _make_status_changes(users, rng)

    db.session.commit()


def seed_all(volumes: dict | None = None) -> None:
    """Full seed. Safe to re-run against an empty database: seed_core and
    seed_domain both only ever insert."""
    core = seed_core(volumes or default_volumes())
    seed_domain(core)
