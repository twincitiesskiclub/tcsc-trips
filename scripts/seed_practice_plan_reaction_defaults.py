#!/usr/bin/env python3
"""Digest-approved seeding of reviewed practice reaction defaults."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, time
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    update,
)
from sqlalchemy.orm import Session


MANIFEST_PATH = (
    Path(__file__).parent
    / "data/2026-07-15-practice-plan-reaction-history.json"
)
APPROVED_ACTIVITY_NAMES = (
    "Run",
    "Bike",
    "Mountain Bike",
    "Classic Rollerski",
    "Skate Rollerski",
    "Skate/Classic Rollerski",
)

MAX_PLAN_REACTIONS = 4
MAX_PLAN_REACTION_LABEL = 80
MAX_PLAN_REACTION_NAME = 80
_BASE_EMOJI_PATTERN = r"[a-z0-9_+\-]+"
_SKIN_TONE_PATTERN = r"skin-tone-[2-6]"
_EMOJI_RE = re.compile(
    rf"^(?P<base>{_BASE_EMOJI_PATTERN})"
    rf"(?:::(?P<modifier>{_SKIN_TONE_PATTERN}))?$"
)
_LINE_BREAK_RE = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
_RESERVED_ATTENDANCE_EMOJIS = frozenset({
    "white_check_mark",
    "ballot_box_with_check",
    "heavy_check_mark",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "keycap_ten",
})

_EXACT_EXTRACTION = {
    "channel_id": "C042G463AQ1",
    "channel_name": "announcements-practices",
    "extracted_at_utc": "2026-07-15T17:05:15Z",
    "history_pages": 6,
    "returned_messages": 1097,
    "raw_extract_sha256": (
        "cec3462bc1a7cb4aa2e09b66a26b0c6ec5aaa5448f5f3498a1f42ee22d19674e"
    ),
}
_EXACT_REVIEW = {
    "state": "approved",
    "reviewed_on": "2026-07-15",
    "reviewer": "announcement-format design review",
    "note": (
        "Approved normalization follows the current 2026 reaction grammar; "
        "observations are never promoted at runtime."
    ),
}
_MANIFEST_KEYS = {
    "schema_version",
    "extraction",
    "review",
    "evidence",
    "approved_targets",
}
_VALID_ENVIRONMENTS = frozenset({"local", "production", "test"})


metadata = MetaData()

practice_types = Table(
    "practice_types",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("has_intervals", Boolean, nullable=False),
    Column("default_plan_reactions", JSON, nullable=False),
)
practice_activities = Table(
    "practice_activities",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("default_plan_reactions", JSON, nullable=False),
)
practices = Table(
    "practices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("date", DateTime, nullable=False),
    Column("status", String(50), nullable=False),
    Column("plan_reactions", JSON, nullable=False),
)
practice_activities_junction = Table(
    "practice_activities_junction",
    metadata,
    Column("practice_id", Integer, primary_key=True),
    Column("activity_id", Integer, primary_key=True),
)
practice_types_junction = Table(
    "practice_types_junction",
    metadata,
    Column("practice_id", Integer, primary_key=True),
    Column("type_id", Integer, primary_key=True),
)


class SeedPlanError(RuntimeError):
    """Raised before a seed operation can make an unsafe change."""


@dataclass(frozen=True)
class SeedChange:
    kind: str
    record_id: int
    name: str
    current: tuple[dict[str, str], ...]
    desired: tuple[dict[str, str], ...]
    status: str


@dataclass(frozen=True)
class SeedPlan:
    changes: tuple[SeedChange, ...]
    upcoming_snapshot_mismatches: tuple[dict, ...]
    extraction_sha256: str = _EXACT_EXTRACTION["raw_extract_sha256"]

    @property
    def has_conflicts(self) -> bool:
        return any(item.status == "conflict" for item in self.changes)

    def change_for(self, name: str) -> SeedChange | None:
        return next((item for item in self.changes if item.name == name), None)

    def to_dict(self) -> dict:
        return {
            "changes": [asdict(item) for item in self.changes],
            "upcoming_snapshot_mismatches": list(
                self.upcoming_snapshot_mismatches
            ),
        }


@dataclass(frozen=True)
class RenderedSeedPlan:
    canonical_json: str
    digest: str


@dataclass(frozen=True)
class SeedCommitResult:
    verified: bool
    plan: SeedPlan


def _normalize_emoji(value: object, source: str) -> str:
    emoji = str(value or "").strip().lower()
    if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
        emoji = emoji[1:-1]
    if len(emoji) > MAX_PLAN_REACTION_NAME:
        raise SeedPlanError(
            f"{source}: emoji name must be {MAX_PLAN_REACTION_NAME} characters or fewer"
        )
    match = _EMOJI_RE.fullmatch(emoji)
    if not match:
        raise SeedPlanError(f"{source}: enter a Slack emoji shortcode")
    if match.group("base") in _RESERVED_ATTENDANCE_EMOJIS:
        raise SeedPlanError(f"{source}: :{emoji}: is reserved for attendance")
    return emoji


def normalize_plan_reactions(
    value: object,
    *,
    source: str = "Plan reactions",
) -> list[dict[str, str]]:
    """Normalize reaction pairs using the current reviewed grammar."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise SeedPlanError(f"{source}: expected a list")
    if len(value) > MAX_PLAN_REACTIONS:
        raise SeedPlanError(
            f"{source}: use at most {MAX_PLAN_REACTIONS} reactions"
        )

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        item_source = f"{source} row {index}"
        if not isinstance(item, Mapping):
            raise SeedPlanError(f"{item_source}: expected emoji and label")
        emoji = _normalize_emoji(item.get("emoji"), item_source)
        raw_label = str(item.get("label") or "")
        if _LINE_BREAK_RE.search(raw_label):
            raise SeedPlanError(f"{item_source}: label must be a single line")
        label = raw_label.strip()
        if not label:
            raise SeedPlanError(f"{item_source}: label is required")
        if not re.sub(r"[.?!]+$", "", label.rstrip()).rstrip():
            raise SeedPlanError(f"{item_source}: label is required")
        if len(label) > MAX_PLAN_REACTION_LABEL:
            raise SeedPlanError(
                f"{item_source}: label must be "
                f"{MAX_PLAN_REACTION_LABEL} characters or fewer"
            )
        if emoji in seen:
            raise SeedPlanError(f"{source}: :{emoji}: appears more than once")
        seen.add(emoji)
        normalized.append({"emoji": emoji, "label": label})
    return normalized


def validate_manifest(manifest: object) -> None:
    """Validate the immutable review envelope and approved target schema."""
    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_KEYS:
        raise SeedPlanError("Manifest schema must match the reviewed format exactly")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise SeedPlanError("Manifest schema version must be 1")
    extraction = manifest.get("extraction")
    if (
        not isinstance(extraction, Mapping)
        or set(extraction) != set(_EXACT_EXTRACTION)
        or any(
            type(extraction.get(key)) is not type(expected)
            or extraction.get(key) != expected
            for key, expected in _EXACT_EXTRACTION.items()
        )
    ):
        raise SeedPlanError("Manifest extraction scope does not match the review")
    review = manifest.get("review")
    if (
        not isinstance(review, Mapping)
        or set(review) != set(_EXACT_REVIEW)
        or any(
            type(review.get(key)) is not type(expected)
            or review.get(key) != expected
            for key, expected in _EXACT_REVIEW.items()
        )
    ):
        raise SeedPlanError("Manifest review approval does not match the review")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list):
        raise SeedPlanError("Manifest evidence must be a list")
    evidence_ids: list[str] = []
    for item in evidence:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("id"), str)
            or not item["id"]
        ):
            raise SeedPlanError("Every evidence record must have a string id")
        evidence_ids.append(item["id"])
    if len(evidence_ids) != len(set(evidence_ids)):
        raise SeedPlanError("Manifest must contain unique evidence ids")

    targets = manifest.get("approved_targets")
    if not isinstance(targets, list) or len(targets) != 7:
        raise SeedPlanError("Manifest must contain exactly seven approved targets")
    for target in targets:
        if not isinstance(target, Mapping):
            raise SeedPlanError("Every approved target must be an object")
        target_keys = set(target)
        if target.get("kind") == "workout_type_selector":
            expected_keys = {"kind", "selector", "defaults", "evidence_ids"}
            if target_keys != expected_keys:
                raise SeedPlanError(
                    "Workout Type selector has unexpected target fields"
                )
        elif target.get("kind") == "activity":
            required_keys = {"kind", "name", "defaults", "evidence_ids"}
            allowed_keys = required_keys | {"normalization_note"}
            if not required_keys <= target_keys or not target_keys <= allowed_keys:
                raise SeedPlanError("Activity has unexpected target fields")
            if "normalization_note" in target and not isinstance(
                target["normalization_note"], str
            ):
                raise SeedPlanError("Activity normalization note must be text")
        else:
            raise SeedPlanError("Approved target has an unsupported kind")
    selector_targets = [
        item
        for item in targets
        if isinstance(item, Mapping)
        and item.get("kind") == "workout_type_selector"
    ]
    if len(selector_targets) != 1:
        raise SeedPlanError("Manifest must contain one exact interval selector")
    selector = selector_targets[0].get("selector")
    if (
        not isinstance(selector, Mapping)
        or set(selector) != {"has_intervals"}
        or type(selector.get("has_intervals")) is not bool
        or selector["has_intervals"] is not True
    ):
        raise SeedPlanError("Manifest requires the exact boolean interval selector")

    activity_targets = [
        item
        for item in targets
        if isinstance(item, Mapping) and item.get("kind") == "activity"
    ]
    activity_names = [item.get("name") for item in activity_targets]
    if (
        len(activity_targets) != len(APPROVED_ACTIVITY_NAMES)
        or not all(isinstance(name, str) for name in activity_names)
        or len(set(activity_names)) != len(APPROVED_ACTIVITY_NAMES)
        or set(activity_names) != set(APPROVED_ACTIVITY_NAMES)
    ):
        raise SeedPlanError("Manifest must contain the six exact Activity names")

    known_evidence = set(evidence_ids)
    for target in targets:
        references = target.get("evidence_ids")
        if not isinstance(references, list) or not references:
            raise SeedPlanError("Every approved target needs evidence references")
        if any(not isinstance(reference, str) for reference in references):
            raise SeedPlanError("Approved target has an invalid evidence reference")
        if len(references) != len(set(references)):
            raise SeedPlanError(
                "Every approved target needs unique evidence references"
            )
        if any(
            reference not in known_evidence
            for reference in references
        ):
            raise SeedPlanError("Approved target has an unknown evidence reference")
        defaults = target.get("defaults")
        normalized = normalize_plan_reactions(
            defaults,
            source="Approved target defaults",
        )
        if normalized != defaults:
            raise SeedPlanError("Approved target defaults must already be normalized")


def load_manifest(path: Path | str = MANIFEST_PATH) -> dict:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeedPlanError(f"Could not load reviewed manifest: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def _source_field(source: object, field: str) -> object:
    if isinstance(source, Mapping):
        return source.get(field)
    return getattr(source, field, None)


def _distinct_sources(items: Iterable, kind: str) -> list[tuple[str, object]]:
    by_key: dict[str, object] = {}
    for item in items or ():
        source_id = _source_field(item, "id")
        name = str(_source_field(item, "name") or "").strip()
        if isinstance(source_id, bool) or not isinstance(source_id, int) or not name:
            raise SeedPlanError(f"Invalid {kind} reaction source")
        by_key.setdefault(f"{kind}:{source_id}", item)
    return sorted(
        by_key.items(),
        key=lambda pair: str(_source_field(pair[1], "name")).casefold(),
    )


def resolve_default_plan_reactions(
    practice_type_sources: Iterable,
    activity_sources: Iterable,
) -> tuple[dict[str, str], ...]:
    """Resolve type defaults and multisport-only Activity defaults locally."""
    type_items = _distinct_sources(practice_type_sources, "type")
    activity_items = _distinct_sources(activity_sources, "activity")
    applicable = type_items + (
        activity_items if len(activity_items) >= 2 else []
    )
    rows: list[dict[str, str]] = []
    by_emoji: dict[str, tuple[str, str]] = {}
    for source_key, item in applicable:
        source_name = (
            f"Workout Type {_source_field(item, 'name')}"
            if source_key.startswith("type:")
            else f"Activity {_source_field(item, 'name')}"
        )
        defaults = normalize_plan_reactions(
            _source_field(item, "default_plan_reactions") or [],
            source=source_name,
        )
        for option in defaults:
            prior = by_emoji.get(option["emoji"])
            if prior and prior[0] != option["label"]:
                raise SeedPlanError(
                    f":{option['emoji']}: has conflicting labels in "
                    f"{prior[1]} and {source_name}"
                )
            if prior:
                continue
            by_emoji[option["emoji"]] = (option["label"], source_name)
            rows.append(dict(option))
    if len(rows) > MAX_PLAN_REACTIONS:
        raise SeedPlanError(
            "Selected Activities and Workout Types produce more than "
            f"{MAX_PLAN_REACTIONS} reactions"
        )
    return tuple(rows)


def _approved_defaults(
    manifest: Mapping,
) -> tuple[tuple[dict[str, str], ...], dict[str, tuple[dict[str, str], ...]]]:
    interval_defaults: tuple[dict[str, str], ...] | None = None
    activity_defaults: dict[str, tuple[dict[str, str], ...]] = {}
    for target in manifest["approved_targets"]:
        desired = tuple(dict(item) for item in target["defaults"])
        if target["kind"] == "workout_type_selector":
            interval_defaults = desired
        elif target["kind"] == "activity":
            activity_defaults[target["name"]] = desired
    if interval_defaults is None:
        raise SeedPlanError("Manifest has no approved interval defaults")
    return interval_defaults, activity_defaults


def _target_selects(manifest: Mapping, *, lock: bool) -> tuple:
    """Return the two explicit target selects, optionally row-locking each."""
    validate_manifest(manifest)
    statements = (
        select(
            practice_types.c.id,
            practice_types.c.name,
            practice_types.c.has_intervals,
            practice_types.c.default_plan_reactions,
        )
        .where(practice_types.c.has_intervals.is_(True))
        .order_by(practice_types.c.name, practice_types.c.id),
        select(
            practice_activities.c.id,
            practice_activities.c.name,
            practice_activities.c.default_plan_reactions,
        )
        .where(practice_activities.c.name.in_(APPROVED_ACTIVITY_NAMES))
        .order_by(practice_activities.c.name, practice_activities.c.id),
    )
    if lock:
        return tuple(statement.with_for_update() for statement in statements)
    return statements


def _classify_change(
    *,
    kind: str,
    row: Mapping,
    desired: tuple[dict[str, str], ...],
) -> SeedChange:
    current = tuple(
        normalize_plan_reactions(
            row["default_plan_reactions"] or [],
            source=f"{kind.replace('_', ' ').title()} {row['name']}",
        )
    )
    if current == desired:
        status = "exact"
    elif not current:
        status = "fill"
    else:
        status = "conflict"
    return SeedChange(
        kind=kind,
        record_id=row["id"],
        name=row["name"],
        current=current,
        desired=desired,
        status=status,
    )


def _load_upcoming_snapshot_mismatches(
    session: Session,
    *,
    interval_defaults: tuple[dict[str, str], ...],
    activity_defaults: Mapping[str, tuple[dict[str, str], ...]],
) -> tuple[dict, ...]:
    central_today = datetime.now(ZoneInfo("America/Chicago")).date()
    cutoff = datetime.combine(central_today, time.min)
    upcoming = list(
        session.execute(
            select(
                practices.c.id,
                practices.c.date,
                practices.c.plan_reactions,
            )
            .where(practices.c.date >= cutoff)
            .where(practices.c.status != "cancelled")
            .order_by(practices.c.date, practices.c.id)
        ).mappings()
    )
    if not upcoming:
        return ()

    practice_ids = [row["id"] for row in upcoming]
    activity_links: dict[int, set[int]] = {
        practice_id: set() for practice_id in practice_ids
    }
    for link in session.execute(
        select(
            practice_activities_junction.c.practice_id,
            practice_activities_junction.c.activity_id,
        ).where(practice_activities_junction.c.practice_id.in_(practice_ids))
    ).mappings():
        activity_links[link["practice_id"]].add(link["activity_id"])

    eligible_ids = {
        practice_id
        for practice_id, activity_ids in activity_links.items()
        if len(activity_ids) >= 2
    }
    if not eligible_ids:
        return ()

    type_links: dict[int, set[int]] = {
        practice_id: set() for practice_id in eligible_ids
    }
    for link in session.execute(
        select(
            practice_types_junction.c.practice_id,
            practice_types_junction.c.type_id,
        ).where(practice_types_junction.c.practice_id.in_(eligible_ids))
    ).mappings():
        type_links[link["practice_id"]].add(link["type_id"])

    activity_ids = set().union(
        *(activity_links[practice_id] for practice_id in eligible_ids)
    )
    type_ids = set().union(
        *(type_links[practice_id] for practice_id in eligible_ids)
    )
    activity_rows = {
        row["id"]: dict(row)
        for row in session.execute(
            select(
                practice_activities.c.id,
                practice_activities.c.name,
                practice_activities.c.default_plan_reactions,
            ).where(practice_activities.c.id.in_(activity_ids))
        ).mappings()
    }
    type_rows = (
        {
            row["id"]: dict(row)
            for row in session.execute(
                select(
                    practice_types.c.id,
                    practice_types.c.name,
                    practice_types.c.has_intervals,
                    practice_types.c.default_plan_reactions,
                ).where(practice_types.c.id.in_(type_ids))
            ).mappings()
        }
        if type_ids
        else {}
    )
    if set(activity_rows) != activity_ids or set(type_rows) != type_ids:
        raise SeedPlanError(
            "An upcoming practice references a missing reaction source"
        )

    mismatches: list[dict] = []
    for practice in upcoming:
        practice_id = practice["id"]
        if practice_id not in eligible_ids:
            continue
        activities_for_practice = []
        for activity_id in activity_links[practice_id]:
            row = activity_rows[activity_id]
            activities_for_practice.append({
                "id": row["id"],
                "name": row["name"],
                "default_plan_reactions": [
                    dict(item)
                    for item in activity_defaults.get(
                        row["name"],
                        tuple(
                            normalize_plan_reactions(
                                row["default_plan_reactions"] or [],
                                source=f"Activity {row['name']}",
                            )
                        ),
                    )
                ],
            })
        types_for_practice = []
        for type_id in type_links[practice_id]:
            row = type_rows[type_id]
            current_or_desired = (
                interval_defaults
                if row["has_intervals"] is True
                else tuple(
                    normalize_plan_reactions(
                        row["default_plan_reactions"] or [],
                        source=f"Workout Type {row['name']}",
                    )
                )
            )
            types_for_practice.append({
                "id": row["id"],
                "name": row["name"],
                "default_plan_reactions": [
                    dict(item) for item in current_or_desired
                ],
            })
        resolved = resolve_default_plan_reactions(
            types_for_practice,
            activities_for_practice,
        )
        current = normalize_plan_reactions(
            practice["plan_reactions"] or [],
            source=f"Practice {practice_id} snapshot",
        )
        resolved_list = [dict(item) for item in resolved]
        if current != resolved_list:
            practice_date = practice["date"]
            mismatches.append({
                "practice_id": practice_id,
                "date": practice_date.isoformat(),
                "current": current,
                "resolved": resolved_list,
            })
    return tuple(mismatches)


def build_seed_plan(
    session: Session,
    manifest: Mapping,
    *,
    lock: bool = False,
) -> SeedPlan:
    """Build a deterministic read-only plan from the approved targets."""
    validate_manifest(manifest)
    interval_defaults, activity_defaults = _approved_defaults(manifest)
    type_select, activity_select = _target_selects(manifest, lock=lock)
    type_rows = [dict(row) for row in session.execute(type_select).mappings()]
    activity_rows = [
        dict(row) for row in session.execute(activity_select).mappings()
    ]

    if not type_rows:
        raise SeedPlanError(
            "expected at least one has_intervals Workout Type target"
        )
    selected_activity_names = [row["name"] for row in activity_rows]
    if (
        len(activity_rows) != len(APPROVED_ACTIVITY_NAMES)
        or len(set(selected_activity_names)) != len(APPROVED_ACTIVITY_NAMES)
        or set(selected_activity_names) != set(APPROVED_ACTIVITY_NAMES)
    ):
        raise SeedPlanError(
            "expected 6 exact Activity targets; target names or count drifted"
        )

    changes = [
        _classify_change(
            kind="workout_type",
            row=row,
            desired=interval_defaults,
        )
        for row in type_rows
    ]
    changes.extend(
        _classify_change(
            kind="activity",
            row=row,
            desired=activity_defaults[row["name"]],
        )
        for row in activity_rows
    )
    upcoming_mismatches = _load_upcoming_snapshot_mismatches(
        session,
        interval_defaults=interval_defaults,
        activity_defaults=activity_defaults,
    )
    return SeedPlan(
        changes=tuple(changes),
        upcoming_snapshot_mismatches=upcoming_mismatches,
        extraction_sha256=manifest["extraction"]["raw_extract_sha256"],
    )


def render_seed_plan(
    plan: SeedPlan,
    *,
    environment: str,
) -> RenderedSeedPlan:
    """Bind a canonical representation and digest to one environment."""
    if environment not in _VALID_ENVIRONMENTS:
        raise SeedPlanError(
            "Environment must be one of local, production, or test"
        )
    changes = [asdict(item) for item in plan.changes]
    payload = {
        "environment": environment,
        "extraction_sha256": plan.extraction_sha256,
        "changes": changes,
        "conflicts": [
            item for item in changes if item["status"] == "conflict"
        ],
        "upcoming_snapshot_mismatches": list(
            plan.upcoming_snapshot_mismatches
        ),
    }
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return RenderedSeedPlan(
        canonical_json=canonical_json,
        digest=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    )


def commit_seed_plan(
    engine,
    manifest: Mapping,
    *,
    approved_digest: str,
    environment: str,
) -> SeedCommitResult:
    """Lock, recheck, fill, commit atomically, and independently read back."""
    if not approved_digest:
        raise SeedPlanError("--commit requires an approval digest")
    if environment not in _VALID_ENVIRONMENTS:
        raise SeedPlanError(
            "Environment must be one of local, production, or test"
        )

    with Session(engine) as session, session.begin():
        locked = build_seed_plan(session, manifest, lock=True)
        rendered = render_seed_plan(locked, environment=environment)
        if rendered.digest != approved_digest:
            raise SeedPlanError(
                "The locked plan no longer matches the approval digest; "
                "run a new dry run"
            )
        if locked.has_conflicts:
            raise SeedPlanError(
                "A target has a different non-empty value; nothing was changed"
            )
        for change in locked.changes:
            if change.status != "fill":
                continue
            table = (
                practice_types
                if change.kind == "workout_type"
                else practice_activities
            )
            result = session.execute(
                update(table)
                .where(table.c.id == change.record_id)
                .values(
                    default_plan_reactions=[
                        dict(item) for item in change.desired
                    ]
                )
            )
            if result.rowcount != 1:
                raise SeedPlanError(
                    "A locked target disappeared; nothing was changed"
                )
        session.flush()

    with Session(engine) as verification:
        verified_plan = build_seed_plan(
            verification,
            manifest,
            lock=False,
        )
        if any(item.status != "exact" for item in verified_plan.changes):
            raise SeedPlanError("Committed values failed read-back verification")
    return SeedCommitResult(verified=True, plan=verified_plan)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed reviewed practice-plan reaction defaults with digest approval."
        )
    )
    parser.add_argument(
        "--environment",
        choices=("local", "production"),
        required=True,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--approve")
    return parser


def _print_plan(rendered: RenderedSeedPlan) -> None:
    print(
        json.dumps(
            json.loads(rendered.canonical_json),
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.commit and not args.approve:
        parser.error("--commit requires --approve <dry-run-digest>")
    if args.dry_run and args.approve:
        parser.error("--approve may only be used with --commit")

    from dotenv import load_dotenv

    load_dotenv(".env")
    url_name = (
        "PROD_DATABASE_URL"
        if args.environment == "production"
        else "DATABASE_URL"
    )
    database_url = os.environ.get(url_name)
    if not database_url:
        print(f"{url_name} is required", file=sys.stderr)
        return 1

    engine = create_engine(database_url)
    try:
        manifest = load_manifest()
        if args.dry_run:
            with Session(engine) as session:
                plan = build_seed_plan(session, manifest, lock=False)
            rendered = render_seed_plan(
                plan,
                environment=args.environment,
            )
            _print_plan(rendered)
            if plan.has_conflicts:
                raise SeedPlanError(
                    "A target has a different non-empty value; no digest approved"
                )
            print(f"Approval digest: {rendered.digest}")
            return 0

        result = commit_seed_plan(
            engine,
            manifest,
            approved_digest=args.approve,
            environment=args.environment,
        )
        for change in result.plan.changes:
            print(
                f"{change.kind} {change.record_id} {change.name}: "
                f"{change.status}"
            )
        print(f"Verified {len(result.plan.changes)} targets.")
        return 0
    except SeedPlanError as exc:
        print(f"Seed aborted: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
