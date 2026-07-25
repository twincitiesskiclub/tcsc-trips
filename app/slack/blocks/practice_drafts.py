"""Block Kit for the monthly draft readiness digest."""

# Each incomplete draft gets its own section so it can carry an edit button.
# Budget: header + summary + MAX_LISTED rows + 2 context blocks, well under 50.
MAX_LISTED = 12


def _row_text(practice, missing: list[str]) -> str:
    when = practice.date.strftime("%a %-m/%-d · %-I:%M%p").replace("PM", "p").replace("AM", "a")
    return f":red_circle: *{when}* — _no {', no '.join(missing)}_"


def build_readiness_digest_blocks(summary: dict, start_label: str, end_label: str) -> list[dict]:
    """Digest posted to the coaches/directors channel after drafting a block.

    Each incomplete row carries a button wired to the existing
    ``edit_practice_full`` action, which reads the practice id from
    ``action["value"]`` — so no new interaction handler is needed.
    """
    total = summary["total"]
    ready = summary["ready"]
    incomplete = summary["incomplete"]

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"{total} practices drafted · {start_label} – {end_label}", "emoji": True}},
    ]

    if not incomplete:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{ready} of {total} ready* — the availability poll is *ready to send*."}})
        return blocks

    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": f"*{ready} of {total} ready* · {len(incomplete)} still need details. "
                "The availability poll unlocks once all of them are set."}})

    for practice, missing in incomplete[:MAX_LISTED]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": _row_text(practice, missing)},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Fill in", "emoji": True},
                "action_id": "edit_practice_full",
                "value": str(practice.id),
            },
        })

    if len(incomplete) > MAX_LISTED:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"_+{len(incomplete) - MAX_LISTED} more not shown._"}]})

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": ":bulb: Leads pick availability from location, type and time — "
                "these are what's blocking the poll."}]})
    return blocks
