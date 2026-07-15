"""Database loading for Plan-reaction source selections."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.practices.models import PracticeActivity, PracticeType
from app.practices.plan_reactions import PlanReactionValidationError


@dataclass(frozen=True)
class SelectedPlanReactionSources:
    practice_types: tuple[PracticeType, ...]
    activities: tuple[PracticeActivity, ...]


class PlanReactionSourceSelectionError(PlanReactionValidationError):
    def __init__(self, message: str, *, field: str):
        super().__init__(message)
        self.field = field


def _coerce_ids(values, *, label, field):
    if values is None:
        values = ()
    elif (
        isinstance(values, (str, bytes, Mapping))
        or not isinstance(values, Iterable)
    ):
        raise PlanReactionSourceSelectionError(
            f"{label}: invalid ID",
            field=field,
        )
    result = []
    seen = set()
    for value in values:
        if isinstance(value, bool):
            raise PlanReactionSourceSelectionError(
                f"{label}: invalid ID",
                field=field,
            )
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise PlanReactionSourceSelectionError(
                f"{label}: invalid ID",
                field=field,
            )
        if str(value).strip() != str(normalized) or normalized <= 0:
            raise PlanReactionSourceSelectionError(
                f"{label}: invalid ID",
                field=field,
            )
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def _load_exact(session, model, ids, *, label, field):
    if not ids:
        return ()
    records = session.query(model).filter(model.id.in_(ids)).all()
    by_id = {record.id: record for record in records}
    missing = [value for value in ids if value not in by_id]
    if missing:
        noun = "ID" if len(missing) == 1 else "IDs"
        singular_label = (
            f"{label[:-3]}y" if label.endswith("ies") else label[:-1]
        )
        raise PlanReactionSourceSelectionError(
            f"Unknown {singular_label} {noun}: {', '.join(map(str, missing))}",
            field=field,
        )
    return tuple(by_id[value] for value in ids)


def load_selected_plan_reaction_sources(
    session,
    *,
    activity_ids,
    type_ids,
) -> SelectedPlanReactionSources:
    activity_ids = _coerce_ids(
        activity_ids,
        label="Activity IDs",
        field="activities",
    )
    type_ids = _coerce_ids(
        type_ids,
        label="Workout Type IDs",
        field="types",
    )
    return SelectedPlanReactionSources(
        practice_types=_load_exact(
            session,
            PracticeType,
            type_ids,
            label="Workout Types",
            field="types",
        ),
        activities=_load_exact(
            session,
            PracticeActivity,
            activity_ids,
            label="Activities",
            field="activities",
        ),
    )


def load_all_plan_reaction_sources(session) -> SelectedPlanReactionSources:
    return SelectedPlanReactionSources(
        practice_types=tuple(
            session.query(PracticeType).order_by(PracticeType.name).all()
        ),
        activities=tuple(
            session.query(PracticeActivity).order_by(PracticeActivity.name).all()
        ),
    )
