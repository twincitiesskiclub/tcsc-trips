"""Who comes and who drifts. Names are shown; every /admin user can see them."""
from collections import defaultdict
from datetime import timedelta

from app import utils
from app.analytics import charts
from app.analytics.dashboards.base import (
    Chart, Dashboard, Filters, Note, Table, Tile, Tiles, load_attendance, load_sessions,
)
from app.analytics.models import PracticeAttendance, PracticeSession
from app.models import Season, SlackUser, User, UserSeason, db

KIND_LABELS = {"practice": "Practice", "event": "Event", "trip": "Trip"}
BUCKETS = ("1", "2", "3", "4 to 5", "6 or more")


def season_key(label):
    year, _, kind = label.partition(" ")
    return (int(year), 1 if kind == "Fall/Winter" else 0) if year.isdigit() else (0, 0)


def _shift(label, years):
    year, _, kind = (label or "").partition(" ")
    return f"{int(year) + years} {kind}" if year.isdigit() else None


def attendance_pairs(sessions, attendance):
    by_id = {s.id: s for s in sessions if s.status == "held" and s.reported_count is None}
    pairs = {(row.person_key, row.session_id): by_id[row.session_id] for row in attendance
             if row.role in ("rsvp", "signup") and row.session_id in by_id}
    return sorted(((person, session) for (person, _), session in pairs.items()),
                  key=lambda pair: (pair[1].date, pair[0]))


def _by_season(pairs):
    seasons = defaultdict(lambda: defaultdict(int))
    for person, session in pairs:
        seasons[session.season_label][person] += 1
    return seasons


def _first_season(pairs):
    first = {}
    for person, session in pairs:           # pairs are date-ordered
        first.setdefault(person, session.season_label)
    return first


def retention(pairs):
    seasons, first, rows = _by_season(pairs), _first_season(pairs), []
    for label in sorted(seasons, key=season_key):
        following = _shift(label, 1)
        if following not in seasons:
            continue
        for group in ("First season", "Returning"):
            people = [p for p in seasons[label] if (first[p] == label) == (group == "First season")]
            returned = sum(p in seasons[following] for p in people)
            rows.append({"season_label": label, "next_season": following, "group": group,
                         "people": len(people), "returned": returned,
                         "rate": round(returned / len(people), 2) if people else 0.0})
    return rows


def _bucket(count):
    return str(count) if count <= 3 else "4 to 5" if count <= 5 else "6 or more"


def newcomer_curve(pairs):
    seasons, first, rows = _by_season(pairs), _first_season(pairs), []
    for label in sorted(seasons, key=season_key):
        counts = [n for person, n in seasons[label].items() if first[person] == label]
        rows.extend({"season_label": label, "bucket": bucket,
                     "people": sum(_bucket(n) == bucket for n in counts)} for bucket in BUCKETS)
    return rows


def overlap(pairs):
    kinds = defaultdict(set)
    for person, session in pairs:
        kinds[person].add(KIND_LABELS[session.kind])
    counts = defaultdict(int)
    for labels in kinds.values():
        counts[" + ".join(sorted(labels))] += 1
    return [{"combo": combo, "people": n} for combo, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def current_label(pairs, today):
    past = [session for _, session in pairs if session.date <= today]
    return max(past, key=lambda s: s.date).season_label if past else None


def lapsed_regulars(pairs, today):
    current = current_label(pairs, today)
    previous = _shift(current, -1)
    practices = [(p, s) for p, s in pairs if s.kind == "practice" and s.date <= today]
    if current is None or not any(s.date >= today - timedelta(days=14) for _, s in practices):
        return []
    last_count, this_count, last_seen = defaultdict(int), defaultdict(int), {}
    for person, session in practices:
        last_count[person] += session.season_label == previous
        this_count[person] += session.season_label == current
        last_seen[person] = max(last_seen.get(person, session.date), session.date)
    cutoff = today - timedelta(days=28)
    rows = [{"person_key": p, "last_rsvp": last_seen[p].isoformat(), "last_season_count": n,
             "this_season_count": this_count[p]}
            for p, n in last_count.items() if n >= 6 and last_seen[p] < cutoff]
    return sorted(rows, key=lambda r: r["last_rsvp"])


def everyone(pairs, current):
    previous, rows = _shift(current, -1), {}
    for person, session in pairs:
        row = rows.setdefault(person, {"person_key": person, "first_seen": session.date,
                                       "last_seen": session.date, "practice_this": 0, "event_this": 0,
                                       "trip_this": 0, "practice_last": 0, "all_time": 0})
        row["last_seen"] = max(row["last_seen"], session.date)
        row["all_time"] += 1
        if session.season_label == current:
            row[f"{session.kind}_this"] += 1
        if session.season_label == previous and session.kind == "practice":
            row["practice_last"] += 1
    return [{**row, "first_seen": row["first_seen"].isoformat(), "last_seen": row["last_seen"].isoformat()}
            for row in sorted(rows.values(), key=lambda r: r["last_seen"], reverse=True)]


def display_names(keys):
    keys = list(dict.fromkeys(keys))
    uids = [key[6:] for key in keys if key.startswith("slack:")]
    ids = [int(key[5:]) for key in keys if key.startswith("user:")]
    names = {}
    if uids:
        for uid, first, last in db.session.query(SlackUser.slack_uid, User.first_name, User.last_name).join(
                User, User.slack_user_id == SlackUser.id).filter(SlackUser.slack_uid.in_(uids)):
            names[f"slack:{uid}"] = f"{first} {last}"
        for uid, full in db.session.query(SlackUser.slack_uid, SlackUser.full_name).filter(
                SlackUser.slack_uid.in_(uids)):
            names.setdefault(f"slack:{uid}", full or uid)
    if ids:
        for user_id, first, last in db.session.query(User.id, User.first_name, User.last_name).filter(
                User.id.in_(ids)):
            names[f"user:{user_id}"] = f"{first} {last}"
    for key in keys:
        names.setdefault(key, key[5:].title() if key.startswith("name:") else key)
    return names


def never_rsvpd():
    season = Season.get_current()
    if season is None:
        return []
    came = db.session.query(PracticeAttendance.user_id).join(PracticeSession).filter(
        PracticeSession.date >= season.start_date, PracticeAttendance.user_id.isnot(None),
        PracticeAttendance.role.in_(("rsvp", "signup")))
    rows = db.session.query(User.first_name, User.last_name).join(
        UserSeason, UserSeason.user_id == User.id).filter(
        UserSeason.season_id == season.id, UserSeason.status == "ACTIVE",
        ~User.id.in_(came)).order_by(User.last_name, User.first_name).all()
    return [{"name": f"{first} {last}"} for first, last in rows]


def build(filters):
    everything = load_sessions(Filters(kinds=filters.kinds))
    pairs = attendance_pairs(everything, load_attendance([s.id for s in everything], role=("rsvp", "signup")))
    today = utils.today_central()
    current = current_label(pairs, today)
    lapsed = lapsed_regulars(pairs, today)
    names = display_names([p for p, _ in pairs])
    selected = [(p, s) for p, s in pairs if not filters.seasons or s.season_label in filters.seasons]

    this_season = _by_season(pairs).get(current, {})
    first = _first_season(pairs)
    practice_counts = defaultdict(int)
    for person, session in pairs:
        if session.season_label == current and session.kind == "practice":
            practice_counts[person] += 1
    tiles = Tiles([
        Tile("People this season", len(this_season), current or ""),
        Tile("Regulars", sum(n >= 6 for n in practice_counts.values()), "6 or more practices this season"),
        Tile("First-timers", sum(first[p] == current for p in this_season), "first time ever this season"),
        Tile("Lapsed regulars", len(lapsed), "regular last season, gone 4 weeks"),
    ])
    retained = retention(selected)
    retention_description = "Share of each season's people who came back the next season of the same type."
    newcomers = newcomer_curve(selected)
    newcomer_description = "People in their first season, by how many sessions they came to that season."
    return [
        tiles,
        Chart("Coming back next season", retention_description,
              charts.spec(retention_description, charts.grouped_bars(
                  retained, x="season_label", y="rate", color="group",
                  color_domain=["First season", "Returning"],
                  color_range=[charts.PALETTE["early"], charts.PALETTE["violet"]],
                  x_title="Season", y_title="Came back", tooltip=["season_label", "group", "people", "returned", "rate"])),
              retained, [("season_label", "Season"), ("group", "Group"), ("people", "People"),
                         ("returned", "Came back"), ("rate", "Rate")]),
        Chart("How far newcomers get", newcomer_description,
              charts.spec(newcomer_description, charts.stacked_columns(
                  newcomers, x="season_label", y="people", color="bucket", color_domain=list(BUCKETS),
                  color_range=["#c7d2fe", "#a5b4fc", "#818cf8", "#6366f1", "#4a3aa7"],
                  x_title="Season", y_title="People", tooltip=["season_label", "bucket", "people"])),
              newcomers, [("season_label", "Season"), ("bucket", "Sessions"), ("people", "People")]),
        Table("Who comes to what", overlap(selected), [("combo", "Comes to"), ("people", "People")]),
        Table("Lapsed regulars", [{**row, "name": names[row["person_key"]]} for row in lapsed],
              [("name", "Name"), ("last_rsvp", "Last RSVP"), ("last_season_count", "Last season"),
               ("this_season_count", "This season")]),
        Table("Registered, never RSVP'd", never_rsvpd(), [("name", "Name")]),
        Table("Everyone", [{**row, "name": names[row["person_key"]]} for row in everyone(pairs, current)],
              [("name", "Name"), ("first_seen", "First seen"), ("last_seen", "Last seen"),
               ("practice_this", "Practices this season"), ("event_this", "Events this season"),
               ("trip_this", "Trips this season"), ("practice_last", "Practices last season"),
               ("all_time", "All time")]),
        Note("A person counts as coming when they RSVP'd or signed up. Count-only sessions from the "
             "old general channel have no names, so they are left out here."),
    ]


DASHBOARD = Dashboard(
    slug="people", title="Who comes and who drifts",
    question="Who keeps coming, who stops, and who never started?",
    filters=["season", "kind"], build=build,
)
