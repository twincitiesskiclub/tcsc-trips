"""Block Kit builders for daily practice recap."""

from datetime import datetime
from typing import Optional


def build_daily_practice_recap_blocks(
    evaluations: list[dict],
    has_proposals: bool = False
) -> list[dict]:
    """Build Block Kit blocks for daily practice recap.

    Posted to #practices-core at 7am daily when there are practices scheduled.
    Shows weather, trail conditions, lead status, and any warnings for each practice.

    Args:
        evaluations: List of dicts with keys:
            - practice: PracticeInfo
            - evaluation: PracticeEvaluation (or None)
            - summary: str (generated summary)
            - is_go: bool
            - proposal_id: int (if cancellation proposed)
        has_proposals: Whether any cancellation proposals were created

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Header
    today_str = datetime.now().strftime('%A, %B %-d')
    header_emoji = ":warning:" if has_proposals else ":clipboard:"
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{header_emoji} Practice Conditions - {today_str}",
            "emoji": True
        }
    })

    if not evaluations:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No practices scheduled for today._"
            }
        })
        return blocks

    # Summary line
    total = len(evaluations)
    safe = sum(1 for e in evaluations if e.get('is_go', True))
    proposed = sum(1 for e in evaluations if e.get('proposal_id'))

    summary_parts = [f"*{total} practice{'s' if total != 1 else ''}* scheduled today"]
    if proposed > 0:
        summary_parts.append(f":warning: {proposed} cancellation proposal{'s' if proposed != 1 else ''}")
    elif safe == total:
        summary_parts.append(":white_check_mark: All conditions look good")

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": " | ".join(summary_parts)}]
    })

    blocks.append({"type": "divider"})

    # Each practice
    for eval_data in evaluations:
        practice = eval_data.get('practice')
        evaluation = eval_data.get('evaluation')
        summary = eval_data.get('summary', '')
        is_go = eval_data.get('is_go', True)
        proposal_id = eval_data.get('proposal_id')

        if not practice:
            continue

        # Practice header line
        time_str = practice.date.strftime('%I:%M %p').lstrip('0')
        location = practice.location.name if practice.location else "TBD"
        status_emoji = ":warning:" if not is_go else ":white_check_mark:"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_emoji} *{time_str}* at *{location}*"
            }
        })

        # Weather and conditions
        conditions_parts = []

        if evaluation and evaluation.weather:
            w = evaluation.weather
            temp_text = f":thermometer: {w.temperature_f:.0f}°F"
            if w.feels_like_f and abs(w.feels_like_f - w.temperature_f) > 3:
                temp_text += f" (feels {w.feels_like_f:.0f}°)"
            conditions_parts.append(temp_text)

            if w.wind_speed_mph:
                wind_text = f":dash: {w.wind_speed_mph:.0f} mph"
                if w.wind_gust_mph and w.wind_gust_mph > w.wind_speed_mph:
                    wind_text += f" (gusts {w.wind_gust_mph:.0f})"
                conditions_parts.append(wind_text)

            if w.precipitation_chance and w.precipitation_chance > 20:
                conditions_parts.append(f":cloud_with_rain: {w.precipitation_chance:.0f}%")

        if evaluation and evaluation.trail_conditions:
            t = evaluation.trail_conditions
            trail_text = f":ski: {t.ski_quality.replace('_', ' ').title()}"
            if t.groomed:
                trail_text += " (groomed)"
            conditions_parts.append(trail_text)

        if conditions_parts:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " | ".join(conditions_parts)}]
            })

        # Lead status
        if evaluation:
            lead_status = []
            if evaluation.has_confirmed_lead:
                lead_status.append(":white_check_mark: Lead confirmed")
            else:
                lead_status.append(":grey_question: Lead not confirmed")

            if evaluation.has_posted_workout:
                lead_status.append(":memo: Workout posted")

            if lead_status:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": " | ".join(lead_status)}]
                })

        # Violations (if any)
        if evaluation and evaluation.violations:
            violation_text = ""
            for v in evaluation.violations:
                icon = ":warning:" if v.severity == "warning" else ":x:"
                violation_text += f"{icon} {v.message}\n"

            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": violation_text.strip()}]
            })

        # Summary / recommendation
        if summary:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"_{summary}_"}]
            })

        # If there's a proposal, add action buttons
        if proposal_id and proposal_id != 'DRY_RUN':
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve Cancellation"},
                        "style": "danger",
                        "action_id": "cancellation_approve",
                        "value": str(proposal_id)
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Keep Practice"},
                        "style": "primary",
                        "action_id": "cancellation_reject",
                        "value": str(proposal_id)
                    }
                ]
            })

        blocks.append({"type": "divider"})

    return blocks
