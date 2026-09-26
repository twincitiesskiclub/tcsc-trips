"""The rebuilt strength lineage must reproduce the hand-verified lift counts.

Uses the real Slack dump, hand-verified counts and proposed corrections in
the gitignored .superpowers folder, so it only runs on the dev box. Nothing
it reads is committed."""
import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.analytics.corrections import TRIP_KEY
from app.analytics.dashboards.splits import _session_rows
from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from app.analytics.parse_trips import is_signup_post
from tests.analytics.conftest import DUMP_DIR


def _corrections():
    path = DUMP_DIR / "corrections.json"   # {key: {"fields": {...}, "note": str}}
    if not path.exists():
        return {}
    return {k: v["fields"] for k, v in json.loads(path.read_text()).items()}


def _messages():
    out = []
    for chan, hist, threads in (("C042G463AQ1", "chan.json", "threads.json"),
                                ("C03FKTTHNHW", "summer.json", "summer_threads.json")):
        replies = json.loads((DUMP_DIR / threads).read_text())
        for raw in json.loads((DUMP_DIR / hist).read_text()):
            out.append(ArchivedMessage(chan, raw["ts"], raw, tuple(replies.get(raw["ts"], []))))
    return out


def _practices():
    rows = json.loads((DUMP_DIR / "app_practices.json").read_text())
    return [AppPractice(**{**r, "date": datetime.fromisoformat(r["date"]),
                           **{k: tuple(r[k]) for k in ("activities", "types", "lead_uids",
                                                       "coach_uids", "plan_emoji", "button_rsvp_uids")}})
            for r in rows]


@pytest.mark.skipif(not (DUMP_DIR / "lift_verified.json").exists(),
                    reason="real Slack dump not present")
def test_strength_lineage_matches_verified_counts():
    locs = [LocationRef(r["id"], r["name"], r["spot"], r["lat"], r["lon"])
            for r in json.loads((DUMP_DIR / "locations.json").read_text())]
    res = build_lineage(_messages(), _practices(), locs, [], load_history_config(), _corrections())
    by_date = {}
    for s in res.sessions:
        if s.activity == "Strength" and s.kind == "practice":
            by_date.setdefault(s.date, []).append(s)
    att = {}
    for a in res.attendance:
        if a.role == "rsvp":
            att.setdefault(a.session_key, []).append(a)
    mismatches = []
    for row in json.loads((DUMP_DIR / "lift_verified.json").read_text())["sessions"]:
        # The correction and verified file disagree on format only; the club leader will decide.
        if row["date"] == "2025-07-24":
            continue
        d = date.fromisoformat(row["date"])
        sessions = by_date.get(d, [])
        rows = [a for s in sessions for a in att.get(s.session_key, [])]
        if row["format"] == "single":
            got = {"one": len({a.slack_uid for a in rows})}
            want = {"one": row["one"]}
        else:
            got = {"early": len({a.slack_uid for a in rows if a.slot == "early"}),
                   "late": len({a.slack_uid for a in rows if a.slot == "late"})}
            want = {"early": row["early"], "late": row["late"]}
        fmt = sorted({s.format for s in sessions})
        if got != want or fmt != [row["format"]]:
            mismatches.append((row["date"], fmt, got, want))
    assert not mismatches, "\n".join(map(str, mismatches))


def _channel_messages(channel_id, filename):
    payload = json.loads((DUMP_DIR / filename).read_text())
    rows = payload["messages"] if isinstance(payload, dict) else payload
    return [ArchivedMessage(channel_id, raw["ts"], raw) for raw in rows]


@pytest.mark.skipif(not (DUMP_DIR / "other" / "tech-trip-signups.json").exists(),
                    reason="real Slack dump not present")
def test_every_trip_signup_post_lands_on_an_edition():
    messages = _channel_messages("C068ECRE0PQ", "other/tech-trip-signups.json")
    assert sum(is_signup_post(message.raw) for message in messages) > 400

    result = build_lineage(messages, [], [], [], load_history_config())
    assert not any(key.startswith("C068ECRE0PQ:") for key in result.possible_misses)
    trips = [session for session in result.sessions if session.kind == "trip"]
    assert all(TRIP_KEY.fullmatch(session.session_key) and session.rsvp_count > 0
               for session in trips)
    people = {}
    for row in result.attendance:
        if row.role == "signup":
            people.setdefault(row.session_key, set()).add(row.person_name or row.slack_uid)
    assert sum(len(people.get(session.session_key, set())) for session in trips) >= 400


@pytest.mark.skipif(any(not (DUMP_DIR / filename).exists() for filename in (
    "general.json", "adventures.json", "other/tech-trip-signups.json")),
    reason="real Slack dump not present")
def test_uncatalogued_event_posts_remain_possible_misses():
    messages = []
    for channel_id, filename in (("C0B2VN1LU11", "general.json"),
                                 ("C02HXN45214", "adventures.json"),
                                 ("C068ECRE0PQ", "other/tech-trip-signups.json")):
        messages.extend(_channel_messages(channel_id, filename))

    result = build_lineage(messages, [], [], [], load_history_config())
    assert len(result.possible_misses) > 0
    assert all(key.startswith(("C0B2VN1LU11:", "C02HXN45214:"))
               for key in result.possible_misses)


@pytest.mark.skipif(any(not (DUMP_DIR / filename).exists() for filename in (
    "lift_verified.json", "chan.json", "threads.json", "summer.json", "summer_threads.json",
    "app_practices.json", "locations.json")), reason="real Slack dump not present")
def test_strength_split_dashboard_matches_verified_counts():
    locs = [LocationRef(r["id"], r["name"], r["spot"], r["lat"], r["lon"])
            for r in json.loads((DUMP_DIR / "locations.json").read_text())]
    result = build_lineage(_messages(), _practices(), locs, [], load_history_config(), _corrections())
    sessions = [s for s in result.sessions if s.activity == "Strength" and s.kind == "practice"]
    ids = {s.session_key: i for i, s in enumerate(sessions)}
    session_rows = [SimpleNamespace(id=ids[s.session_key], date=s.date, format=s.format,
                                    status=s.status, season_label=s.season_label,
                                    day_of_week=s.day_of_week, start_time=s.start_time, slot=s.slot)
                    for s in sessions]
    attendance = [SimpleNamespace(session_id=ids[a.session_key], slack_uid=a.slack_uid,
                                  slot=a.slot, role=a.role)
                  for a in result.attendance if a.role == "rsvp" and a.session_key in ids]
    by_date = {}
    for row in _session_rows(session_rows, attendance):
        by_date.setdefault(row["date"], []).append(row)
    mismatches = []
    for row in json.loads((DUMP_DIR / "lift_verified.json").read_text())["sessions"]:
        # Accepted split-vs-merged mismatch: .superpowers/sdd/2026-09-25-attendance-analytics/progress.md ruling.
        if row["date"] == "2025-07-24":
            continue
        rows = by_date.get(row["date"], [])
        if row["format"] == "single":
            got = {"one": sum(r["single"] for r in rows)}
            want = {"one": row["one"]}
        else:
            got = {"early": sum(r["early"] for r in rows), "late": sum(r["late"] for r in rows)}
            want = {"early": row["early"], "late": row["late"]}
        fmt = sorted({r["format"] for r in rows})
        if got != want or fmt != [row["format"]]:
            mismatches.append((row["date"], fmt, got, want))
    assert not mismatches, "\n".join(map(str, mismatches))
