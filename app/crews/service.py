"""Crew drafts: build, edit, summarize and export. Callers commit."""
import csv
import io

from app.crews import engine
from app.crews.engine import LEVELS, TRAITS, Person, Rule, Settings
from app.crews.models import CrewConfig, CrewDraft
from app.crews.roster import load_members
from app.models import db

DEFAULT_SETTINGS = {"crews": 12, "levels": {t: "normal" for t in TRAITS}, "board_rule": True}
GENDERS = ["F", "M", "X", "?"]
PERSON_FIELDS = ("gender", "age", "ski", "tenure", "thot", "board")
DRAFTS_PER_BATCH = 5
# The first draft of a season uses this seed, so with default settings it is
# the same draw as the 2026-10-05 scratchpad run. Later drafts count up.
FIRST_SEED = 2026


def get_config(season, create=False):
    """The season's config, or an unsaved one with defaults (saved only when create=True)."""
    config = CrewConfig.query.filter_by(season_id=season.id).one_or_none()
    if config is None:
        config = CrewConfig(season_id=season.id, settings=dict(DEFAULT_SETTINGS), overrides={}, rules=[],
                            speedy_user_ids=[])
        if create:
            db.session.add(config)
    return config


def config_settings(config):
    saved = config.settings or {}
    return {**DEFAULT_SETTINGS, **saved, "levels": {**DEFAULT_SETTINGS["levels"], **saved.get("levels", {})}}


def to_settings(settings, rules):
    return Settings(crews=int(settings["crews"]), levels=settings["levels"],
                    board_rule=bool(settings["board_rule"]),
                    rules=[Rule(r["kind"], int(r["a"]), r.get("b") and int(r["b"]), r.get("crew") and int(r["crew"]))
                           for r in rules])


def parse_settings(form):
    """Settings from the settings form; returns (settings, error)."""
    try:
        crews = int(form.get("crews", ""))
    except ValueError:
        return None, "Number of crews must be a whole number."
    if not 2 <= crews <= 40:
        return None, "Number of crews must be between 2 and 40."
    levels = {t: form.get(f"level_{t}", "normal") for t in TRAITS}
    if any(v not in LEVELS for v in levels.values()):
        return None, "Unknown weight."
    return {"crews": crews, "levels": levels, "board_rule": form.get("board_rule") == "on"}, None


def parse_rule(form, member_ids, crews):
    kind = form.get("kind")
    try:
        a = int(form.get("a", ""))
        b = int(form["b"]) if form.get("b") else None
        crew = int(form["crew"]) if form.get("crew") else None
    except ValueError:
        return None, "Pick people from the list."
    if kind not in ("together", "apart", "pin") or a not in member_ids:
        return None, "Pick a rule and a person."
    if kind == "pin":
        if crew is None or not 1 <= crew <= crews:
            return None, f"Pick a crew from 1 to {crews}."
        return {"kind": kind, "a": a, "crew": crew}, None
    if b not in member_ids or b == a:
        return None, "Pick two different people."
    return {"kind": kind, "a": a, "b": b}, None


def set_overrides(config, rows, form):
    """Overrides from the members form: keep only values that differ from computed."""
    overrides = {}
    for r in rows:
        mine = {}
        gender = form.get(f"gender_{r.user_id}")
        if gender in GENDERS and gender != r.computed["gender"]:
            mine["gender"] = gender
        for flag in ("thot", "board"):
            value = form.get(f"{flag}_{r.user_id}") == "on"
            if value != r.computed[flag]:
                mine[flag] = value
        if mine:
            overrides[str(r.user_id)] = mine
    config.overrides = overrides


def make_drafts(season, config):
    settings = config_settings(config)
    rows = load_members(season, config)
    people = [r.person for r in rows]
    last = db.session.query(db.func.max(CrewDraft.seed)).filter_by(season_id=season.id).scalar()
    start = FIRST_SEED if last is None else last + 1
    drafts = []
    for seed in range(start, start + DRAFTS_PER_BATCH):
        result = engine.generate(people, to_settings(settings, config.rules), seed)
        members = [{"user_id": r.user_id, "name": r.person.name, "email": r.email,
                    **{f: getattr(r.person, f) for f in PERSON_FIELDS},
                    "crew": result.assignment[r.user_id] + 1} for r in rows]
        draft = CrewDraft(season_id=season.id, label=f"Draft {seed - FIRST_SEED + 1}", seed=seed,
                          settings=settings, rules=list(config.rules), members=members, crew_names={})
        db.session.add(draft)
        drafts.append(draft)
    db.session.flush()
    return drafts


def summary(draft):
    people = [Person(key=m["user_id"], name=m["name"], **{f: m.get(f) for f in PERSON_FIELDS})
              for m in draft.members]
    assignment = {m["user_id"]: m["crew"] - 1 for m in draft.members}
    settings = to_settings(draft.settings, draft.rules)
    rows = engine.crew_rows(people, assignment, settings.crews)
    return {
        "score": engine.score(people, assignment, settings),
        "rows": rows,
        "spread": engine.spread(people, assignment, settings),
        "no_board": sum(1 for r in rows[:-1] if r["board"] == 0) if settings.board_rule else 0,
        "broken": engine.broken_rules(assignment, settings.rules, {p.key: p.name for p in people}),
        "ski_levels": [s for s in engine.SKI_ORDER if rows[-1]["ski"].get(s)] +
                      sorted(s for s in rows[-1]["ski"] if s not in engine.SKI_ORDER),
    }


def crews_of(draft):
    out = [[] for _ in range(int(draft.settings["crews"]))]
    for m in sorted(draft.members, key=lambda m: (not m.get("board"), m["name"].lower())):
        out[m["crew"] - 1].append(m)
    return out


def save_draft(draft, form):
    """Crew picks, crew names and the draft name from the draft form."""
    k = int(draft.settings["crews"])
    members = [dict(m) for m in draft.members]
    for m in members:
        try:
            crew = int(form.get(f"crew_{m['user_id']}", m["crew"]))
        except ValueError:
            raise ValueError(f"Pick a crew for {m['name']}.")
        if not 1 <= crew <= k:
            raise ValueError(f"Pick a crew from 1 to {k} for {m['name']}.")
        m["crew"] = crew
    draft.members = members
    draft.crew_names = {str(i): name[:80] for i in range(1, k + 1)
                        if (name := form.get(f"name_{i}", "").strip())}
    if label := form.get("label", "").strip():
        draft.label = label[:120]


def mark_final(draft):
    CrewDraft.query.filter(CrewDraft.season_id == draft.season_id, CrewDraft.status == "final",
                           CrewDraft.id != draft.id).update({"status": "draft"})
    db.session.flush()
    draft.status = "final"


def export_csv(draft):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Crew", "Crew name", "Name", "Email", "Board", "Speedy group", "Gender", "Age",
                "Ski experience", "Seasons on team"])
    for i, crew in enumerate(crews_of(draft), start=1):
        for m in crew:
            w.writerow([i, draft.crew_names.get(str(i), ""), m["name"], m["email"], "yes" if m.get("board") else "",
                        "yes" if m.get("thot") else "", m.get("gender") or "", m.get("age") or "",
                        m.get("ski") or "", m.get("tenure") if m.get("tenure") is not None else ""])
    return out.getvalue()
