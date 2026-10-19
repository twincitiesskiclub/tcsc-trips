"""Crews backtest: how many of each crew were at this season's practices.

Reads a crew draft and never writes to it. Pairing joins whole crews, so every
hand swap in the draft survives.
"""
from math import ceil

from app.analytics.crew_pairing import MIN_GROUP, best_pairing, share_by_count
from app.analytics.dashboards.base import (
    Chart, Dashboard, Note, Picker, Select, Table, Tile, Tiles, _past_sessions, load_attendance,
)
from app import utils
from app.analytics import charts
from app.analytics.models import PracticeSession
from app.crews import engine
from app.crews.models import CrewDraft
from app.crews.service import PERSON_FIELDS, to_settings
from app.models import Season

NON_CHECKER_LIMIT = 5  # Mitchell: fine as long as no crew has more than 5 non-checkers
ROLES = ("rsvp", "lead", "coach")
MAX_PAIRING_CREWS = 13  # the search grows about 4x per crew; 13 crews take ~2 s


def _drafts():
    season = Season.query.filter_by(is_current=True).first()
    if season is None:
        return None, []
    return season, CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.id).all()


def _int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def pick_draft(drafts, raw):
    chosen = {d.id: d for d in drafts}.get(_int(raw))
    if chosen:
        return chosen
    final = [d for d in drafts if d.status == "final"]
    return final[0] if final else max(drafts, key=lambda d: (d.updated_at, d.id))


def lowest_count(n):
    return ceil(n / 2) if n <= MAX_PAIRING_CREWS else n


def pick_count(raw, n):
    k = _int(raw)
    return k if k is not None and lowest_count(n) <= k <= n else n


def _sessions(label):
    return _past_sessions(("practice",)).filter(
        PracticeSession.season_label == label, PracticeSession.status == "held",
        PracticeSession.reported_count.is_(None),
    ).order_by(PracticeSession.date, PracticeSession.start_time, PracticeSession.id).all()


def _session_labels(sessions):
    labels, seen = [], {}
    for s in sessions:
        seen[s.date] = seen.get(s.date, 0) + 1
        label = f"{s.date:%b} {s.date.day}"
        labels.append(label if seen[s.date] == 1 else f"{label} ({seen[s.date]})")
    return labels


def _apart(rules, crew_of, names):
    """Crew pairs an apart rule forbids joining, and apart pairs already inside one crew."""
    apart, broken = set(), []
    for rule in rules:
        if rule.get("kind") != "apart":
            continue
        a, b = _int(rule.get("a")), _int(rule.get("b"))
        if a not in crew_of or b not in crew_of:
            continue
        if crew_of[a] == crew_of[b]:
            broken.append(f"{names[a]} and {names[b]} are both in crew {crew_of[a]}")
        else:
            apart.add(frozenset({crew_of[a], crew_of[b]}))
    return apart, broken


def _counts(counter):
    return " · ".join(f"{key} {n}" for key, n in counter.items() if n)


def _day(utc_naive):
    local = utils.utc_naive_to_central_naive(utc_naive)
    return f"{local:%b} {local.day}"


def _percent(share):
    return f"{round(share * 100)}%"


def build(filters):
    season, drafts = _drafts()
    if not drafts:
        return [Note("No crew drafts for the current season yet.")]
    draft = pick_draft(drafts, filters.params.get("draft"))
    members = [m for m in draft.members if m.get("user_id") is not None]
    n = int(draft.settings.get("crews") or max((m["crew"] for m in members), default=1))
    k = pick_count(filters.params.get("crews"), n)
    crew_of = {m["user_id"]: m["crew"] for m in members}
    names = {m["user_id"]: m["name"] for m in members}

    sessions = _sessions(season.name)
    present = {(row.session_id, row.user_id)
               for row in load_attendance([s.id for s in sessions], role=ROLES) if row.user_id in crew_of}
    turnout = {c: [0] * len(sessions) for c in range(1, n + 1)}
    for i, s in enumerate(sessions):
        for uid, c in crew_of.items():
            turnout[c][i] += (s.id, uid) in present
    checked = {uid for _, uid in present}
    apart, already_broken = _apart(draft.rules or [], crew_of, names)

    people = [engine.Person(key=m["user_id"], name=m["name"], **{f: m.get(f) for f in PERSON_FIELDS})
              for m in members]
    base_settings = to_settings({**draft.settings, "crews": n}, [])
    settings = engine.Settings(crews=k, levels=base_settings.levels, board_rule=base_settings.board_rule)

    def assignment(groups):
        group_of = {c: i for i, g in enumerate(groups) for c in g}
        return {uid: group_of[c] for uid, c in crew_of.items()}

    pick = best_pairing(turnout, k, apart,
                        balance=lambda groups: engine.score(people, assignment(groups), settings))
    crew_names = draft.crew_names or {}
    labels = [" + ".join(crew_names.get(str(c)) or str(c) for c in g) for g in pick.groups]
    columns = _session_labels(sessions)
    balance_rows = engine.crew_rows(people, assignment(pick.groups), k)

    grid, rows = [], []
    for label, group, balance in zip(labels, pick.groups, balance_rows):
        counts = [sum(turnout[c][i] for c in group) for i in range(len(sessions))]
        grid.extend({"crew": label, "practice": p, "people": n_} for p, n_ in zip(columns, counts))
        non_checkers = sum(1 for uid, c in crew_of.items() if c in group and uid not in checked)
        rows.append({
            "label": label, "size": balance["size"], "non_checkers": non_checkers,
            "over_limit": "Yes" if non_checkers > NON_CHECKER_LIMIT * len(group) else "",
            "average": round(sum(counts) / len(counts), 1) if counts else 0,
            "share_4plus": _percent(sum(x >= MIN_GROUP for x in counts) / len(counts) if counts else 0),
            "zero_practices": sum(x == 0 for x in counts),
            "board": balance["board"], "speedy": balance["thot"], "gender": _counts(balance["gender"]),
            "ski": _counts({s: balance["ski"][s] for s in
                            engine.SKI_ORDER + sorted(set(balance["ski"]) - set(engine.SKI_ORDER))}),
            "age": (f"{balance['age_min']} to {balance['age_max']}" if balance["age_min"] is not None else ""),
            "tenure": _counts(balance["tenure"]),
        })

    sizes = sorted(r["size"] for r in rows)
    slots = k * len(sessions)
    counts_by_k = (share_by_count(turnout, apart) if n <= MAX_PAIRING_CREWS
                   else [{"crews": n, "share": pick.share}])
    count_rows = [{"crews": r["crews"], "share": round(r["share"] * 100)} for r in counts_by_k]
    blocks = [
        Picker([
            Select("draft", "Draft", [(str(d.id), f"{d.label} (updated {_day(d.updated_at)})")
                                      for d in drafts], str(draft.id)),
            Select("crews", "Crews", [(str(c), str(c)) for c in range(lowest_count(n), n + 1)], str(k)),
        ]),
        Tiles([
            Tile("Crews", k, f"from {n} in {draft.label}" if k < n else draft.label),
            Tile("People per crew", str(sizes[0]) if sizes[0] == sizes[-1] else f"{sizes[0]} to {sizes[-1]}"),
            Tile("Practices", len(sessions)),
            Tile("Average per crew", f"{(sum(sum(c) for c in turnout.values()) / slots) if slots else 0:.1f}",
                 "people at a practice"),
            Tile("Crew-practices with 4+", _percent(pick.share)),
            Tile("Crews over 5 non-checkers", sum(r["over_limit"] == "Yes" for r in rows),
                 "5 per original crew when paired"),
        ]),
        Chart("Crew count",
              f"Share of crew-practices with {MIN_GROUP} or more people at each crew count. "
              "Each count uses the pairing that fits these practices best.",
              {"data": {"values": count_rows}, "width": "container", "height": 240, "mark": "bar",
               "encoding": {"x": {"field": "crews", "type": "ordinal", "title": "Crews"},
                            "y": {"field": "share", "type": "quantitative", "title": "% with 4 or more",
                                  "scale": {"domain": [0, 100]}},
                            "color": {"value": charts.PALETTE["early"]},
                            "tooltip": [{"field": "crews", "type": "ordinal"},
                                        {"field": "share", "type": "quantitative", "title": "%"}]}},
              rows=count_rows, columns=[("crews", "Crews"), ("share", "% with 4 or more")]),
        Chart("Crew by practice",
              f"People from each crew at each practice. Filled cells have {MIN_GROUP} or more.",
              charts.heatmap(grid, x="practice", y="crew", value="people", threshold=MIN_GROUP,
                             x_title="Practice", y_title="Crew", tooltip=["crew", "practice", "people"],
                             x_sort=columns, y_sort=labels),
              rows=grid, columns=[("crew", "Crew"), ("practice", "Practice"), ("people", "People")]),
        Table("Crews", rows, [
            ("label", "Crew"), ("size", "Size"), ("non_checkers", "Non-checkers"), ("over_limit", "Over limit"),
            ("average", "Average"), ("share_4plus", "4 or more"), ("zero_practices", "Nobody there"),
            ("board", "Board"), ("speedy", "Speedy"), ("gender", "Gender"), ("ski", "Ski experience"),
            ("age", "Age"),
            ("tenure", "Seasons on team"),
        ]),
    ]
    span = f", {columns[0]} to {columns[-1]}" if sessions else ""
    notes = [f"RSVPs, not headcounts. {draft.label}, {season.name}, {len(sessions)} practices{span}. "
             "Pairings are the best fit for these practices. Fall turnout may not predict winter."]
    if n > MAX_PAIRING_CREWS:
        notes.append(f"With {n} crews, pairing is off: it is only worked out for {MAX_PAIRING_CREWS} crews or fewer.")
    if pick.broken:
        notes.append(f"This pairing puts {pick.broken} keep-apart pair(s) in one crew; no pairing avoids it.")
    notes.extend(f"Already in the draft: {line}." for line in already_broken)
    return blocks + [Note(text) for text in notes]


DASHBOARD = Dashboard(slug="crews", title="Crews",
                      question="How many of each crew would have been at practice this season?",
                      filters=[], params=("draft", "crews"), build=build)
