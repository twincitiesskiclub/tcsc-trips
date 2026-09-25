import textwrap

import pytest

from app.analytics.drafts import LocationRef
from app.analytics.history_config import (
    HistoryConfigError, activity_bucket, base_emoji, classify_title,
    load_history_config, resolve_venue, workout_bucket)

LOCS = [
    LocationRef(34, "Theodore Wirth", "Xerxes Field", 44.98, -93.31),
    LocationRef(36, "Theodore Wirth", "Trailhead Bridge", 44.99, -93.32),
    LocationRef(38, "Balance Fitness Studio", None, 44.95, -93.28),
    LocationRef(32, "Hyland", "Jan's Place", 44.82, -93.36),
]


@pytest.fixture(scope="module")
def cfg():
    return load_history_config()


def test_real_config_loads(cfg):
    assert "U06FYPUNQCU" in cfg.excluded_slack_uids
    assert cfg.coach_emoji == frozenset()
    assert cfg.capacity_lines[0]["value"] == 27


def test_venue_by_name_and_spot(cfg):
    v = resolve_venue("The Trailhead @ Wirth", cfg, LOCS)
    assert (v["location_id"], v["matched"]) == (36, True)
    assert v["rule_kind"] == "location"
    v = resolve_venue("Theodore Wirth Trails", cfg, LOCS)
    assert v["location_id"] == 34


def test_indoor_and_unknown_venue(cfg):
    assert resolve_venue("Balance Fitness Studio", cfg, LOCS)["is_indoor"] is True
    v = resolve_venue("Somewhere New", cfg, LOCS)
    assert v["matched"] is False and v["location_id"] is None
    assert v["rule_kind"] is None
    assert (v["lat"], v["lon"]) == (44.9778, -93.2650)


def test_config_only_venue_has_own_coordinates(cfg):
    v = resolve_venue("Beards Plaisance", cfg, LOCS)
    assert v["location_id"] is None and v["location_name"] == "Beards Plaisance"
    assert v["rule_kind"] == "name"
    assert v["lat"] == pytest.approx(44.9215) and v["matched"] is True


def test_private_home_never_keeps_raw_text(cfg):
    v = resolve_venue("Somebody's House", cfg, LOCS)
    assert v["location_name"] == "Member's home"


@pytest.mark.parametrize("title,acts,types", [
    ("Strength Circuit", ["Strength"], ["Circuit"]),
    ("Strength", ["Strength"], ["Circuit"]),
    ("Skate or Classic Intervals", ["Skate/Classic Ski"], ["Intervals"]),
    ("Run w/ Poles - Intervals", ["Pole Run"], ["Intervals"]),
    ("Classic Ski - Technique", ["Classic Ski"], ["Technique"]),
    ("Multi-Sport (Rollerski, Run, Bike)", ["Run", "Skate/Classic Rollerski", "Bike"], []),
])
def test_classify_title(cfg, title, acts, types):
    r = classify_title(title, cfg)
    assert r["activities"] == acts and r["workout_types"] == types and r["matched"]


def test_event_titles_and_unmatched(cfg):
    assert classify_title("Season Kickoff + Potluck", cfg)["kind"] == "event"
    r = classify_title("Super Secret Surprise", cfg)
    assert r["matched"] is False and r["activities"] == []


def test_buckets(cfg):
    assert activity_bucket(["Pole Run"], cfg) == "Run"
    assert activity_bucket(["Run", "Bike"], cfg) == "Multisport"
    assert activity_bucket([], cfg) == "Other"
    assert workout_bucket(["Technique", "Intervals"], cfg) == "Intervals"
    assert workout_bucket([], cfg) == "Other"


def test_base_emoji():
    assert base_emoji("older_adult::skin-tone-4") == "older_adult"
    assert base_emoji("six") == "six"


def test_invalid_config_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(textwrap.dedent("""
        excluded_slack_uids: not-a-list
    """))
    with pytest.raises(HistoryConfigError):
        load_history_config(p)


@pytest.mark.parametrize("raw", [None, "", "Somewhere New"])
def test_unmatched_venue_returns_complete_shape(cfg, raw):
    assert resolve_venue(raw, cfg, LOCS) == {
        "location_id": None, "location_name": None,
        "lat": cfg.default_lat, "lon": cfg.default_lon,
        "is_indoor": False, "matched": False, "rule_kind": None,
    }


def test_missing_location_row_retains_rule_name_and_indoor_spot(cfg):
    assert resolve_venue("ROYALS ATHLETIC CENTER", cfg, LOCS) == {
        "location_id": None, "location_name": "Hopkins Highschool",
        "lat": cfg.default_lat, "lon": cfg.default_lon,
        "is_indoor": True, "matched": True, "rule_kind": "location",
    }


def test_indoor_spot_and_nullable_coordinates(cfg):
    locations = [LocationRef(99, "Hopkins Highschool", "Royals Athletic Center", None, None)]
    venue = resolve_venue("Royals Athletic", cfg, locations)
    assert venue["location_id"] == 99
    assert venue["is_indoor"] is True
    assert (venue["lat"], venue["lon"]) == (cfg.default_lat, cfg.default_lon)


def test_location_spot_must_match(cfg):
    venue = resolve_venue("The Trailhead", cfg, LOCS[:1])
    assert venue["matched"] is True
    assert venue["location_id"] is None
    assert venue["location_name"] == "Theodore Wirth"
    assert venue["rule_kind"] == "location"


def test_venue_normalizes_apostrophes_on_both_sides(cfg):
    from dataclasses import replace

    custom = replace(cfg, venues=[{
        "match": ["FAKE’S FIELD"], "name": "Synthetic Field",
    }])
    assert resolve_venue("fake's field", custom, [])["matched"] is True
    custom.venues[0]["match"] = ["fake's field"]
    assert resolve_venue("FAKE’S FIELD", custom, [])["matched"] is True


def test_all_type_rules_contribute_in_rule_order(cfg):
    result = classify_title("Skate technique threshold intervals VO2 repeats tempo", cfg)
    assert result["workout_types"] == [
        "Intervals (VO2 Max)", "Intervals (Threshold)",
        "Intervals (Tempo)", "Intervals", "Technique",
    ]
    assert result["kind"] == "practice"
    assert classify_title("Strength Technique", cfg)["workout_types"] == ["Technique"]


def test_type_deduplication_and_title_normalization(cfg):
    from dataclasses import replace

    custom = replace(cfg, activity_rules=[{
        "match": ["FAKE’S WORKOUT"], "activities": ["Run"],
    }], type_rules=[
        {"match": ["workout"], "types": ["Technique", "Technique"]},
        {"match": ["fake's"], "types": ["Technique", "Endurance"]},
    ], event_keywords=["fake’s"])
    assert classify_title("fake's workout", custom) == {
        "activities": ["Run"], "workout_types": ["Technique", "Endurance"],
        "kind": "event", "matched": True,
    }


def test_event_and_type_matches_do_not_imply_activity_match(cfg):
    assert classify_title("Board Meeting", cfg) == {
        "activities": [], "workout_types": [], "kind": "event", "matched": False,
    }
    assert classify_title("VO2", cfg)["matched"] is False


def test_bucket_distinctness_and_unknown_values(cfg):
    assert activity_bucket(["Pole Run", "Hike", "Run"], cfg) == "Run"
    assert activity_bucket(["Unlisted"], cfg) == "Other"
    assert activity_bucket(["Unlisted", "Run"], cfg) == "Multisport"
    assert workout_bucket(["Unlisted"], cfg) == "Other"
    assert workout_bucket(["Endurance", "Technique", "Benchmark"], cfg) == "Time Trial"


def test_config_public_types(cfg):
    assert isinstance(cfg.excluded_slack_uids, frozenset)
    assert isinstance(cfg.coach_emoji, frozenset)
    assert isinstance(cfg.default_lat, float)
    assert isinstance(cfg.default_lon, float)
    assert all(isinstance(bucket, tuple) for bucket in cfg.workout_buckets)


@pytest.mark.parametrize("key,value", [
    ("corrections", []),
    ("excluded_slack_uids", "not-a-list"),
    ("excluded_slack_uids", [123]),
    ("coach_emoji", [False]),
    ("default_location", []),
    ("default_location", {"lat": "north", "lon": -93}),
    ("default_location", {"lat": 45, "lon": True}),
    ("default_location", {"lat": float("nan"), "lon": -93}),
    ("venues", {}),
    ("venues", [None]),
    ("venues", [{"match": [], "name": "Synthetic"}]),
    ("venues", [{"match": [1], "name": "Synthetic"}]),
    ("venues", [{"match": ["synthetic"]}]),
    ("venues", [{"match": ["synthetic"], "location": {}}]),
    ("venues", [{"match": ["synthetic"], "location": {"name": "Synthetic", "spot": 3}}]),
    ("venues", [{"match": ["synthetic"], "name": "Synthetic", "location": {"name": "Synthetic"}}]),
    ("venues", [{"match": ["synthetic"], "name": "Synthetic", "lat": "north"}]),
    ("activity_rules", {}),
    ("activity_rules", [{"match": ["run"], "activities": "Run"}]),
    ("activity_rules", [{"match": ["run"], "activities": ["Run"], "default_types": [3]}]),
    ("type_rules", [{"match": "run", "types": ["Endurance"]}]),
    ("type_rules", [{"match": ["run"], "types": [3]}]),
    ("activity_buckets", []),
    ("activity_buckets", {"Run": ["Run"]}),
    ("workout_buckets", {}),
    ("workout_buckets", [["Intervals"]]),
    ("workout_buckets", [["Intervals", "Intervals"]]),
    ("event_keywords", "kickoff"),
    ("indoor_locations", [None]),
    ("capacity_lines", {}),
    ("capacity_lines", [None]),
    ("capacity_lines", [{"value": "27", "label": "Synthetic", "from": "2025-05-01"}]),
    ("capacity_lines", [{"value": 27, "label": 3, "from": "2025-05-01"}]),
    ("capacity_lines", [{"value": 27, "label": "Synthetic", "from": "not-a-date"}]),
])
def test_invalid_fields_name_the_key(tmp_path, key, value):
    import yaml
    from app.analytics.history_config import DEFAULT_PATH

    data = yaml.safe_load(DEFAULT_PATH.read_text())
    data[key] = value
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(HistoryConfigError, match=key):
        load_history_config(path)


@pytest.mark.parametrize("content", ["", "[]", "venues: [", "!!python/object:builtins.object {}"])
def test_invalid_yaml_documents_raise_config_error(tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content)
    with pytest.raises(HistoryConfigError):
        load_history_config(str(path))


def test_missing_config_raises_config_error(tmp_path):
    with pytest.raises(HistoryConfigError):
        load_history_config(tmp_path / "missing.yaml")


@pytest.mark.parametrize("value", [["coachface"], [], None])
def test_coach_emoji_belongs_in_app_config(tmp_path, value):
    import yaml
    from app.analytics.history_config import DEFAULT_PATH

    data = yaml.safe_load(DEFAULT_PATH.read_text())
    data["coach_emoji"] = value
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(HistoryConfigError, match='coach_emoji.*AppConfig "analytics_coach_emoji"'):
        load_history_config(path)
