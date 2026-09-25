"""The rebuilt strength lineage must reproduce the hand-verified lift counts.

Uses the real Slack dump, hand-verified counts and proposed corrections in
the gitignored .superpowers folder, so it only runs on the dev box. Nothing
it reads is committed."""
import json
from datetime import date, datetime

import pytest

from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from tests.analytics.conftest import DUMP_DIR

pytestmark = pytest.mark.skipif(not (DUMP_DIR / "lift_verified.json").exists(),
                                reason="real Slack dump not present")


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
