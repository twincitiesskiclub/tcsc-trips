"""
Claude API integration for natural language generation.

Uses Anthropic's Claude to generate human-readable summaries
of practice conditions and draft cancellation messages.
"""

import logging
import os
from typing import Optional

from app.practices.interfaces import PracticeEvaluation
from app.practices.models import Practice

logger = logging.getLogger(__name__)

# Import anthropic only if available
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not available - LLM features disabled")


def get_anthropic_client():
    """Get Anthropic client using ANTHROPIC_API_KEY from environment."""
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK not installed")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    return anthropic.Anthropic(api_key=api_key)


def generate_evaluation_summary(evaluation: PracticeEvaluation) -> str:
    """
    Generate human-readable summary of practice conditions.

    Uses Claude to synthesize weather, trail, and safety data into
    a concise natural language summary.

    Args:
        evaluation: Practice evaluation result

    Returns:
        Natural language summary (2-3 sentences)
    """
    if not ANTHROPIC_AVAILABLE:
        logger.warning("Anthropic SDK not available, using fallback summary")
        return _fallback_evaluation_summary(evaluation)

    logger.info(f"Generating evaluation summary for practice {evaluation.practice_id}")

    # Build context for Claude
    context_parts = []

    # Weather context
    if evaluation.weather:
        w = evaluation.weather
        context_parts.append(
            f"Weather: {w.temperature_f:.0f}°F (feels like {w.feels_like_f:.0f}°F), "
            f"{w.conditions_summary}, wind {w.wind_speed_mph:.0f} mph, "
            f"{w.precipitation_chance:.0f}% chance of precipitation"
        )
        if w.has_lightning_threat:
            context_parts.append("Lightning threat detected")

    # Trail context
    if evaluation.trail_conditions:
        t = evaluation.trail_conditions
        context_parts.append(
            f"Trails: {t.ski_quality} quality, {t.trails_open} open, "
            f"{'groomed' if t.groomed else 'not groomed'}"
            + (f" for {t.groomed_for}" if t.groomed_for else "")
        )

    # Violations context
    if evaluation.violations:
        critical = [v for v in evaluation.violations if v.severity == 'critical']
        warnings = [v for v in evaluation.violations if v.severity == 'warning']
        context_parts.append(
            f"Issues: {len(critical)} critical, {len(warnings)} warnings"
        )
        for v in critical[:3]:  # Top 3 critical issues
            context_parts.append(f"- {v.message}")

    # Lead/workout status
    context_parts.append(
        f"Lead confirmed: {evaluation.has_confirmed_lead}, "
        f"Workout posted: {evaluation.has_posted_workout}"
    )

    context = "\n".join(context_parts)

    # Prompt for Claude
    prompt = f"""You are Skipper, an AI assistant for the Twin Cities Ski Club. Your job is to summarize practice conditions for club members.

Given the following practice conditions, write a 2-3 sentence summary that clearly explains whether the practice can proceed safely and why. Be direct and factual.

CONDITIONS:
{context}

OVERALL ASSESSMENT: {"Practice can proceed" if evaluation.is_go else "Practice should be cancelled"}

Write a clear, concise summary for club members:"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        if not response.content:
            logger.error("Empty response from Claude API")
            return _fallback_evaluation_summary(evaluation)

        summary = response.content[0].text.strip()
        logger.info("Generated evaluation summary via Claude")
        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary with Claude: {e}")
        return _fallback_evaluation_summary(evaluation)


def generate_cancellation_message(
    practice: Practice,
    evaluation: PracticeEvaluation
) -> str:
    """
    Draft cancellation announcement message for Slack.

    Uses Claude to generate an empathetic, informative message
    explaining why a practice needs to be cancelled.

    Args:
        practice: Practice being cancelled
        evaluation: Evaluation that triggered cancellation

    Returns:
        Draft message text suitable for Slack posting
    """
    if not ANTHROPIC_AVAILABLE:
        logger.warning("Anthropic SDK not available, using fallback message")
        return _fallback_cancellation_message(practice, evaluation)

    logger.info(f"Generating cancellation message for practice {practice.id}")

    # Build context
    context_parts = []

    # Practice details
    context_parts.append(
        f"Practice: {practice.day_of_week}, {practice.date.strftime('%B %d at %I:%M %p')}"
    )
    if practice.location:
        context_parts.append(f"Location: {practice.location.name}")
    if practice.activities:
        activities = ", ".join(a.name for a in practice.activities)
        context_parts.append(f"Activities: {activities}")

    # Weather
    if evaluation.weather:
        w = evaluation.weather
        context_parts.append(
            f"Weather: {w.temperature_f:.0f}°F (feels like {w.feels_like_f:.0f}°F), "
            f"wind {w.wind_speed_mph:.0f} mph, {w.conditions_summary}"
        )

    # Trail conditions
    if evaluation.trail_conditions:
        t = evaluation.trail_conditions
        context_parts.append(
            f"Trails: {t.ski_quality} quality, {t.trails_open}"
        )

    # Critical issues
    critical = [v for v in evaluation.violations if v.severity == 'critical']
    if critical:
        context_parts.append("\nSafety concerns:")
        for v in critical:
            context_parts.append(f"- {v.message}")

    context = "\n".join(context_parts)

    prompt = f"""You are Skipper, the Twin Cities Ski Club's practice coordinator AI. You need to write a cancellation announcement for a practice.

Write a brief (2-3 sentences) cancellation message that:
1. States the practice is cancelled
2. Explains the main safety reason(s)
3. Is empathetic but factual

PRACTICE DETAILS:
{context}

Write a cancellation message for Slack (use friendly but professional tone):"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        if not response.content:
            logger.error("Empty response from Claude API")
            return _fallback_cancellation_message(practice, evaluation)

        message = response.content[0].text.strip()
        logger.info("Generated cancellation message via Claude")
        return message

    except Exception as e:
        logger.error(f"Failed to generate message with Claude: {e}")
        return _fallback_cancellation_message(practice, evaluation)


def _fallback_evaluation_summary(evaluation: PracticeEvaluation) -> str:
    """
    Fallback summary generation without LLM.

    Args:
        evaluation: Practice evaluation

    Returns:
        Simple text summary
    """
    if evaluation.is_go:
        if evaluation.violations:
            warning_count = len([v for v in evaluation.violations if v.severity == 'warning'])
            return f"Practice can proceed with {warning_count} minor concerns noted."
        else:
            return "All conditions are favorable. Practice can proceed as scheduled."
    else:
        critical = [v for v in evaluation.violations if v.severity == 'critical']
        if len(critical) == 1:
            return f"Practice should be cancelled: {critical[0].message}"
        else:
            return f"Practice should be cancelled due to {len(critical)} safety concerns."


def _fallback_cancellation_message(
    practice: Practice,
    evaluation: PracticeEvaluation
) -> str:
    """
    Fallback cancellation message without LLM.

    Args:
        practice: Practice being cancelled
        evaluation: Evaluation results

    Returns:
        Simple cancellation message
    """
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location_str = f" at {practice.location.name}" if practice.location else ""

    critical = [v for v in evaluation.violations if v.severity == 'critical']
    reasons = [v.message for v in critical[:2]]  # Top 2 reasons
    reason_str = "; ".join(reasons)

    return (
        f"The {practice.day_of_week} practice on {date_str}{location_str} "
        f"has been cancelled due to unsafe conditions: {reason_str}. "
        f"Stay safe and we'll see you at the next practice!"
    )
