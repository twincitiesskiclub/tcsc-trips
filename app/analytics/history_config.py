"""History rules and pure venue/title resolution for analytics."""
from dataclasses import dataclass
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
    trip_series: list[dict]


def base_emoji(name: str) -> str:
    return re.sub(r"::skin-tone-\d+$", "", name)


def load_history_config(path: str | Path = DEFAULT_PATH) -> HistoryConfig:
    """Load rules afresh, rejecting the mistakes that would silently misparse."""
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        raise HistoryConfigError(f"config {path}: {exc}") from exc

    for section in ("venues", "activity_rules", "type_rules", "trip_series"):
        for index, rule in enumerate(data[section]):
            # A string would silently match per character.
            if not isinstance(rule["match"], list):
                raise HistoryConfigError(f"{section}[{index}].match: expected a list")
    for index, venue in enumerate(data["venues"]):
        if ("location" in venue) == ("name" in venue):
            raise HistoryConfigError(f"venues[{index}]: expected either location or name")

    return HistoryConfig(
        excluded_slack_uids=frozenset(data["excluded_slack_uids"]),
        applause_emoji=frozenset(base_emoji(e) for e in data["applause_emoji"]),
        coach_emoji=frozenset(),
        default_lat=float(data["default_location"]["lat"]),
        default_lon=float(data["default_location"]["lon"]),
        venues=data["venues"], activity_rules=data["activity_rules"],
        type_rules=data["type_rules"], activity_buckets=data["activity_buckets"],
        workout_buckets=[(name, types) for name, types in data["workout_buckets"]],
        event_keywords=data["event_keywords"], indoor_locations=data["indoor_locations"],
        capacity_lines=data["practice_views"]["capacity_lines"],
        trip_series=data["trip_series"],
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
