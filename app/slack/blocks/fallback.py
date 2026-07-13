"""Plain-language cleanup for authored fallback fragments."""

import re

from app.practices.plan_reactions import format_reaction_name_for_fallback


_BROADCAST_TOKEN_RE = re.compile(r"<!(channel|here|everyone)>", re.IGNORECASE)
_SHORTCODE_TOKEN_RE = re.compile(
    r":([a-z0-9_+\-]+(?:::(?:skin-tone-[2-6]))?):",
    re.IGNORECASE,
)


def plainify_fallback_fragment(value) -> str:
    """Render broadcast and emoji controls as inert plain-language text."""
    text = str(value or "")
    text = _BROADCAST_TOKEN_RE.sub(lambda match: match.group(1).lower(), text)
    return _SHORTCODE_TOKEN_RE.sub(
        lambda match: format_reaction_name_for_fallback(match.group(1)),
        text,
    )


def allocate_fallback_component_limits(values, *, budget: int) -> list[int]:
    """Share a budget without allowing early values to starve later ones."""
    lengths = [len(str(value or "")) for value in values]
    if not lengths:
        return []
    remaining_budget = max(0, int(budget))
    if sum(lengths) <= remaining_budget:
        return lengths

    limits = [0] * len(lengths)
    pending = set(range(len(lengths)))
    while pending:
        share, extra = divmod(remaining_budget, len(pending))
        completed = [index for index in pending if lengths[index] <= share]
        if completed:
            for index in completed:
                limits[index] = lengths[index]
                remaining_budget -= lengths[index]
                pending.remove(index)
            continue
        for position, index in enumerate(sorted(pending)):
            limits[index] = share + (1 if position < extra else 0)
        break
    return limits
