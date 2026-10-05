"""Build engine Persons for a season's ACTIVE members.

Tenure, counted over seasons that started before this one:
  - Registration records (non-legacy seasons): the member was ACTIVE.
  - Before the first non-legacy season the DB only has a legacy marker, so each
    earlier season label where the member shows up in practice attendance
    (any role but decline) counts as one. A legacy member with no attendance
    counts as one season.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy import text

from app.crews.engine import Person
from app.models import db
from app.utils import today_central

OVERRIDABLE = ("gender", "thot", "board")


@dataclass
class MemberRow:
    user_id: int
    email: str
    person: Person                                # effective values (overrides applied)
    computed: dict                                # values before overrides
    overridden: set = field(default_factory=set)


def gender_from_pronouns(p):
    p = (p or "").lower()
    if "they" in p:
        return "X"
    if "she" in p or "her" in p:
        return "F"
    if re.search(r"\bhe\b|\bhim\b", p):
        return "M"
    return "?"


def age_on(dob, today):
    if not dob:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _tenure(season):
    records_start = db.session.execute(text(
        "SELECT min(start_date) FROM seasons WHERE season_type <> 'legacy'")).scalar()
    rows = db.session.execute(text("""
        SELECT us.user_id, s.name, s.season_type FROM user_seasons us JOIN seasons s ON s.id = us.season_id
        WHERE us.status = 'ACTIVE' AND s.id <> :sid AND s.start_date < :start
          AND us.user_id IN (SELECT user_id FROM user_seasons WHERE season_id = :sid AND status = 'ACTIVE')
    """), {"sid": season.id, "start": season.start_date}).all()
    reg, legacy = {}, set()
    for uid, name, stype in rows:
        if stype == "legacy":
            legacy.add(uid)
        else:
            reg.setdefault(uid, set()).add(name)
    pre = {}
    if records_start:
        for uid, label in db.session.execute(text("""
            SELECT DISTINCT a.user_id, ps.season_label
            FROM practice_attendance a JOIN practice_sessions ps ON ps.id = a.session_id
            WHERE a.role <> 'decline' AND ps.date < :records AND a.user_id IN
                (SELECT user_id FROM user_seasons WHERE season_id = :sid AND status = 'ACTIVE')
        """), {"records": records_start, "sid": season.id}).all():
            pre.setdefault(uid, set()).add(label)
    # Union by label: archive sessions just before a season's start_date can carry its name.
    return {uid: len(reg.get(uid, set()) | pre.get(uid, set())) + (1 if uid in legacy and uid not in pre else 0)
            for uid in set(reg) | legacy | set(pre)}


def load_members(season, config, today=None):
    """MemberRows for everyone ACTIVE in the season, sorted by name."""
    today = today or today_central()
    members = db.session.execute(text("""
        SELECT u.id, u.first_name, u.last_name, u.email, u.pronouns, u.date_of_birth, u.ski_experience,
               EXISTS (SELECT 1 FROM user_tags ut JOIN tags t ON t.id = ut.tag_id
                       WHERE ut.user_id = u.id AND t.name = 'BOARD_MEMBER') AS board
        FROM users u JOIN user_seasons us ON us.user_id = u.id
        WHERE us.season_id = :sid AND us.status = 'ACTIVE'
    """), {"sid": season.id}).all()
    tenure = _tenure(season)
    speedy = set(config.speedy_user_ids or []) if config else set()
    overrides = (config.overrides or {}) if config else {}
    rows = []
    for uid, first, last, email, pronouns, dob, ski, board in members:
        computed = {
            "gender": gender_from_pronouns(pronouns), "age": age_on(dob, today),
            "ski": (ski or "").strip() or "?", "tenure": tenure.get(uid, 0),
            "thot": uid in speedy, "board": bool(board),
        }
        mine = {k: v for k, v in overrides.get(str(uid), {}).items() if k in OVERRIDABLE}
        values = {**computed, **mine}
        person = Person(key=uid, name=f"{first.strip()} {last.strip()}", **values)
        rows.append(MemberRow(uid, email.strip().lower(), person, computed, set(mine)))
    rows.sort(key=lambda r: r.person.name.lower())
    return rows
