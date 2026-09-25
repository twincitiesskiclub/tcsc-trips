"""Validated history rules and pure venue/title resolution for analytics."""
from dataclasses import dataclass
from datetime import date
from math import isfinite
from pathlib import Path
import re

import yaml

from app.analytics.drafts import LocationRef


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "practice_history.yaml"


class HistoryConfigError(ValueError):
    """The history rules cannot safely be used for a rebuild."""


@dataclass
class HistoryConfig:
    excluded_slack_uids: frozenset
    applause_emoji: frozenset
    coach_emoji: frozenset
    default_lat: float
    default_lon: float
    venues: list[dict]
    activity_rules: list[dict]
    type_rules: list[dict]
    activity_buckets: dict
    workout_buckets: list[tuple[str, list[str]]]
    event_keywords: list[str]
    indoor_locations: list[str]
    capacity_lines: list[dict]


def _mapping(value, key):
    if not isinstance(value, dict):
        raise HistoryConfigError(f"{key}: expected a mapping")


def _list(value, key):
    if not isinstance(value, list):
        raise HistoryConfigError(f"{key}: expected a list")


def _string(value, key):
    if not isinstance(value, str) or not value.strip():
        raise HistoryConfigError(f"{key}: expected a non-empty string")


def _strings(value, key, nonempty=False):
    _list(value, key)
    if nonempty and not value:
        raise HistoryConfigError(f"{key}: expected a non-empty list of strings")
    for index, item in enumerate(value):
        _string(item, f"{key}[{index}]")


def _number(value, key):
    if type(value) not in (int, float) or not isfinite(value):
        raise HistoryConfigError(f"{key}: expected a finite number")


def _date(value, key):
    if type(value) is date:
        return
    if isinstance(value, str):
        try:
            date.fromisoformat(value)
            return
        except ValueError:
            pass
    raise HistoryConfigError(f"{key}: expected an ISO date")


def base_emoji(name: str) -> str:
    return re.sub(r"::skin-tone-\d+$", "", name)


def load_history_config(path: str | Path = DEFAULT_PATH) -> HistoryConfig:
    """Load rules afresh, rejecting malformed content before any rebuild."""
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        raise HistoryConfigError(f"config {path}: {exc}") from exc

    _mapping(data, "config")
    if "corrections" in data:
        raise HistoryConfigError("corrections: per-post corrections belong in the DB")
    if "coach_emoji" in data:
        raise HistoryConfigError('coach_emoji: belongs in AppConfig "analytics_coach_emoji"')
    for key in ("excluded_slack_uids", "applause_emoji", "event_keywords", "indoor_locations"):
        _strings(data.get(key), key)

    default = data.get("default_location")
    _mapping(default, "default_location")
    for key in ("lat", "lon"):
        _number(default.get(key), f"default_location.{key}")

    for key in ("venues", "activity_rules", "type_rules", "capacity_lines"):
        _list(data.get(key), key)
        for index, entry in enumerate(data[key]):
            _mapping(entry, f"{key}[{index}]")

    for index, venue in enumerate(data["venues"]):
        key = f"venues[{index}]"
        _strings(venue.get("match"), f"{key}.match", nonempty=True)
        if ("location" in venue) == ("name" in venue):
            raise HistoryConfigError(f"{key}: expected either location or name")
        if "location" in venue:
            location = venue["location"]
            _mapping(location, f"{key}.location")
            _string(location.get("name"), f"{key}.location.name")
            if "spot" in location:
                _string(location["spot"], f"{key}.location.spot")
        else:
            _string(venue["name"], f"{key}.name")
        for coordinate in ("lat", "lon"):
            if coordinate in venue:
                _number(venue[coordinate], f"{key}.{coordinate}")

    for section, output in (("activity_rules", "activities"), ("type_rules", "types")):
        for index, rule in enumerate(data[section]):
            key = f"{section}[{index}]"
            _strings(rule.get("match"), f"{key}.match", nonempty=True)
            _strings(rule.get(output), f"{key}.{output}")
            if section == "activity_rules" and "default_types" in rule:
                _strings(rule["default_types"], f"{key}.default_types")

    _mapping(data.get("activity_buckets"), "activity_buckets")
    for activity, bucket in data["activity_buckets"].items():
        _string(activity, "activity_buckets key")
        _string(bucket, f"activity_buckets.{activity}")

    _list(data.get("workout_buckets"), "workout_buckets")
    for index, bucket in enumerate(data["workout_buckets"]):
        key = f"workout_buckets[{index}]"
        if not isinstance(bucket, list) or len(bucket) != 2:
            raise HistoryConfigError(f"{key}: expected [name, types]")
        _string(bucket[0], f"{key}[0]")
        _strings(bucket[1], f"{key}[1]")

    for index, line in enumerate(data["capacity_lines"]):
        key = f"capacity_lines[{index}]"
        _number(line.get("value"), f"{key}.value")
        _string(line.get("label"), f"{key}.label")
        _date(line.get("from"), f"{key}.from")
        if "to" in line:
            _date(line["to"], f"{key}.to")

    return HistoryConfig(
        excluded_slack_uids=frozenset(data["excluded_slack_uids"]),
        applause_emoji=frozenset(base_emoji(e) for e in data["applause_emoji"]),
        coach_emoji=frozenset(),
        default_lat=float(default["lat"]), default_lon=float(default["lon"]),
        venues=data["venues"], activity_rules=data["activity_rules"],
        type_rules=data["type_rules"], activity_buckets=data["activity_buckets"],
        workout_buckets=[(name, types) for name, types in data["workout_buckets"]],
        event_keywords=data["event_keywords"], indoor_locations=data["indoor_locations"],
        capacity_lines=data["capacity_lines"],
    )


def _normalize(text: str) -> str:
    return text.lower().replace("’", "'")


def _matches(text: str, keywords: list[str]) -> bool:
    return any(_normalize(keyword) in text for keyword in keywords)


def resolve_venue(raw: str | None, cfg: HistoryConfig, locations: list[LocationRef]) -> dict:
    """Resolve the first matching rule, preserving a missing DB row as a match."""
    result = {
        "location_id": None, "location_name": None,
        "lat": cfg.default_lat, "lon": cfg.default_lon,
        "is_indoor": False, "matched": False, "rule_kind": None,
    }
    text = _normalize(raw or "")
    for rule in cfg.venues:
        if not _matches(text, rule["match"]):
            continue
        result["matched"] = True
        spot = None
        if "location" in rule:
            result["rule_kind"] = "location"
            target = rule["location"]
            result["location_name"] = target["name"]
            spot = target.get("spot")
            location = next((loc for loc in locations if loc.name == target["name"]
                             and ("spot" not in target or loc.spot == spot)), None)
            if location is not None:
                result["location_id"] = location.id
                spot = location.spot
                if location.lat is not None:
                    result["lat"] = location.lat
                if location.lon is not None:
                    result["lon"] = location.lon
        else:
            result["rule_kind"] = "name"
            result["location_name"] = rule["name"]
            result["lat"] = rule.get("lat", cfg.default_lat)
            result["lon"] = rule.get("lon", cfg.default_lon)
        indoor = {_normalize(name) for name in cfg.indoor_locations}
        result["is_indoor"] = any(
            _normalize(value) in indoor for value in (result["location_name"], spot)
            if value is not None
        )
        return result
    return result


def classify_title(title: str, cfg: HistoryConfig) -> dict:
    text = _normalize(title)
    activity = next((rule for rule in cfg.activity_rules if _matches(text, rule["match"])), None)
    type_rules = [rule for rule in cfg.type_rules if _matches(text, rule["match"])]
    types = list(dict.fromkeys(value for rule in type_rules for value in rule["types"]))
    if not type_rules and activity is not None:
        types = list(activity.get("default_types", []))
    return {
        "activities": list(activity["activities"]) if activity is not None else [],
        "workout_types": types,
        "kind": "event" if _matches(text, cfg.event_keywords) else "practice",
        "matched": activity is not None,
    }


def activity_bucket(activities: list, cfg: HistoryConfig) -> str:
    buckets = {cfg.activity_buckets.get(activity, "Other") for activity in activities}
    if len(buckets) > 1:
        return "Multisport"
    return next(iter(buckets), "Other")


def workout_bucket(types: list, cfg: HistoryConfig) -> str:
    for name, members in cfg.workout_buckets:
        if any(value in members for value in types):
            return name
    return "Other"
