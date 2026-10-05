"""Crew drafts: build, edit, summarize, import and export. Callers commit."""
import csv
import io
from collections import Counter

from app.crews import engine
from app.crews.engine import LEVELS, TRAITS, Person, Rule, Settings
from app.crews.models import CrewConfig, CrewDraft
from app.crews.roster import load_members
from app.crews.slack import DEFAULT_SPEEDY_CHANNEL
from app.models import db

DEFAULT_SETTINGS = {"crews": 12, "levels": {t: "normal" for t in TRAITS}, "board_rule": True,
                    "speedy_channel": DEFAULT_SPEEDY_CHANNEL}
GENDERS = ["F", "M", "X", "?"]
PERSON_FIELDS = ("gender", "age", "ski", "tenure", "thot", "board")


def get_config(season):
    config = CrewConfig.query.filter_by(season_id=season.id).one_or_none()
    if config is None:
        config = CrewConfig(season_id=season.id, settings=dict(DEFAULT_SETTINGS), overrides={}, rules=[],
                            speedy_user_ids=[])
        db.session.add(config)
        db.session.flush()
    return config


def config_settings(config):
    return {**DEFAULT_SETTINGS, **(config.settings or {}),
            "levels": {**DEFAULT_SETTINGS["levels"], **(config.settings or {}).get("levels", {})}}


def to_settings(settings, rules):
    return Settings(crews=int(settings["crews"]), levels=settings["levels"],
                    board_rule=bool(settings["board_rule"]),
                    rules=[Rule(r["kind"], int(r["a"]), r.get("b") and int(r["b"]), r.get("crew") and int(r["crew"]))
                           for r in rules])


def parse_settings(form):
    """Settings from the configure form; returns (settings, error)."""
    try:
        crews = int(form.get("crews", ""))
    except ValueError:
        return None, "Number of crews must be a whole number."
    if not 2 <= crews <= 40:
        return None, "Number of crews must be between 2 and 40."
    levels = {t: form.get(f"level_{t}", "normal") for t in TRAITS}
    if any(v not in LEVELS for v in levels.values()):
        return None, "Unknown weight."
    channel = (form.get("speedy_channel") or "").strip() or DEFAULT_SPEEDY_CHANNEL
    return {"crews": crews, "levels": levels, "board_rule": form.get("board_rule") == "on",
            "speedy_channel": channel}, None


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


def people_snapshot(rows):
    return [{"user_id": r.user_id, "name": r.person.name, "email": r.email,
             **{f: getattr(r.person, f) for f in PERSON_FIELDS}} for r in rows]


def draft_people(draft):
    return [Person(key=m["user_id"], name=m["name"], **{f: m.get(f) for f in PERSON_FIELDS}) for m in draft.members]


def _assignment(draft):
    return {m["user_id"]: m["crew"] - 1 for m in draft.members}


def rescore(draft):
    draft.score = engine.score(draft_people(draft), _assignment(draft), to_settings(draft.settings, draft.rules))


def make_drafts(season, config, count, start_seed, created_by):
    settings = config_settings(config)
    rows = load_members(season, config)
    people = [r.person for r in rows]
    snapshot = people_snapshot(rows)
    drafts = []
    for seed in range(start_seed, start_seed + count):
        result = engine.generate(people, to_settings(settings, config.rules), seed)
        members = [{**m, "crew": result.assignment[m["user_id"]] + 1, "band": result.bands[m["user_id"]]}
                   for m in snapshot]
        draft = CrewDraft(season_id=season.id, label=f"Seed {seed}", seed=seed, settings=settings,
                          rules=list(config.rules), members=members, crew_names={}, score=result.score,
                          created_by=created_by)
        db.session.add(draft)
        drafts.append(draft)
    db.session.flush()
    return drafts


def summary(draft):
    people = draft_people(draft)
    assignment = _assignment(draft)
    settings = to_settings(draft.settings, draft.rules)
    names = {p.key: p.name for p in people}
    rows = engine.crew_rows(people, assignment, settings.crews)
    return {
        "rows": rows,
        "spread": engine.spread(people, assignment, settings),
        "no_board": sum(1 for r in rows[:-1] if r["board"] == 0),
        "broken": engine.broken_rules(assignment, settings.rules, names),
        "ski_levels": [s for s in engine.SKI_ORDER if rows[-1]["ski"].get(s)] +
                      sorted(s for s in rows[-1]["ski"] if s not in engine.SKI_ORDER),
    }


def crews_of(draft):
    k = int(draft.settings["crews"])
    out = [[] for _ in range(k)]
    for m in sorted(draft.members, key=lambda m: (not m.get("board"), m["name"].lower())):
        out[m["crew"] - 1].append(m)
    return out


def move(draft, user_id, crew):
    k = int(draft.settings["crews"])
    if not 1 <= crew <= k:
        raise ValueError(f"Pick a crew from 1 to {k}.")
    members = [dict(m) for m in draft.members]
    for m in members:
        if m["user_id"] == user_id:
            m["crew"] = crew
            break
    else:
        raise ValueError("That person is not in this draft.")
    draft.members = members
    rescore(draft)


def swap(draft, a, b):
    members = [dict(m) for m in draft.members]
    by_id = {m["user_id"]: m for m in members}
    if a not in by_id or b not in by_id or a == b:
        raise ValueError("Pick two different people from this draft.")
    by_id[a]["crew"], by_id[b]["crew"] = by_id[b]["crew"], by_id[a]["crew"]
    draft.members = members
    rescore(draft)


def mark_final(draft):
    CrewDraft.query.filter(CrewDraft.season_id == draft.season_id, CrewDraft.status == "final",
                           CrewDraft.id != draft.id).update({"status": "draft"})
    db.session.flush()
    draft.status = "final"


def _read_csv(file_storage):
    text = file_storage.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower(): f for f in reader.fieldnames or []}
    if "email" not in fields:
        raise ValueError("The CSV needs an Email column.")
    return [{k: (row.get(orig) or "").strip() for k, orig in fields.items()} for row in reader]


def _truthy(v):
    return v.strip().lower() in ("1", "1.0", "y", "yes", "true", "x")


def _gender(v):
    v = v.strip().lower()
    return {"f": "F", "female": "F", "woman": "F", "w": "F", "m": "M", "male": "M", "man": "M",
            "x": "X", "nb": "X", "nonbinary": "X", "non-binary": "X"}.get(v)


def import_overrides(config, rows, file_storage):
    """Overrides from a CSV with Email plus any of gender, thot, board."""
    data = _read_csv(file_storage)
    by_email = {r.email: r for r in rows}
    overrides = {k: dict(v) for k, v in (config.overrides or {}).items()}
    updated, unknown = 0, []
    for line in data:
        row = by_email.get(line["email"].lower())
        if row is None:
            if line["email"]:
                unknown.append(line["email"])
            continue
        values = {}
        if line.get("gender") and _gender(line["gender"]):
            values["gender"] = _gender(line["gender"])
        for flag in ("thot", "board"):
            if flag in line:  # a blank cell in a present column means no
                values[flag] = _truthy(line[flag])
        mine = overrides.setdefault(str(row.user_id), {})
        for key, value in values.items():
            if value == row.computed[key]:
                mine.pop(key, None)
            else:
                mine[key] = value
        updated += 1
    config.overrides = {k: v for k, v in overrides.items() if v}
    return updated, unknown


def set_overrides(config, rows, form):
    """Overrides from the members table form: keep only values that differ from computed."""
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


def import_draft(season, config, rows, file_storage, created_by):
    """A draft from a CSV with Email and Crew columns (e.g. the 10/5 scratchpad draw)."""
    data = _read_csv(file_storage)
    by_email = {r.email: r for r in rows}
    crews = {}
    for line in data:
        row = by_email.get(line["email"].lower())
        if row is None:
            continue
        try:
            crews[row.user_id] = int(line.get("crew", ""))
        except ValueError:
            continue
    if not crews:
        raise ValueError("No rows matched a member with a crew number.")
    k = max(crews.values())
    missing = [r for r in rows if r.user_id not in crews]
    sizes = Counter(crews.values())
    for r in missing:  # members who joined after the CSV go to the smallest crew
        crews[r.user_id] = min(range(1, k + 1), key=lambda c: (sizes[c], c))
        sizes[crews[r.user_id]] += 1
    settings = {**config_settings(config), "crews": k}
    members = [{**m, "crew": crews[m["user_id"]], "band": -1} for m in people_snapshot(rows)]
    draft = CrewDraft(season_id=season.id, label=f"Imported {file_storage.filename or 'CSV'}"[:120],
                      settings=settings, rules=list(config.rules), members=members, crew_names={},
                      created_by=created_by)
    rescore(draft)
    db.session.add(draft)
    db.session.flush()
    return draft, missing


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
