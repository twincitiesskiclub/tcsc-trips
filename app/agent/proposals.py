"""
CancellationRequest management for human-in-the-loop workflow.

Handles creation of cancellation proposals, processing human decisions,
and fail-open expiration of proposals that timeout.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.models import db
from app.practices.interfaces import (
    PracticeEvaluation,
    CancellationStatus,
    PracticeStatus
)
from app.practices.models import Practice, CancellationRequest
from app.agent.decision_engine import load_skipper_config

logger = logging.getLogger(__name__)


def create_cancellation_proposal(
    practice: Practice,
    evaluation: PracticeEvaluation
) -> CancellationRequest:
    """
    Create a cancellation proposal requiring human approval.

    Args:
        practice: Practice to potentially cancel
        evaluation: Evaluation results with violations

    Returns:
        CancellationRequest database record
    """
    logger.info(f"Creating cancellation proposal for practice {practice.id}")

    config = load_skipper_config()
    timeout_minutes = config.get('escalation', {}).get('timeout_minutes', 120)

    # Determine primary reason type
    reason_type = _determine_reason_type(evaluation)

    # Generate summary
    reason_summary = _generate_reason_summary(evaluation)

    # Set expiration time
    proposed_at = datetime.utcnow()
    expires_at = proposed_at + timedelta(minutes=timeout_minutes)

    # Serialize evaluation data to JSON
    evaluation_data = _serialize_evaluation(evaluation)

    # Create database record
    request = CancellationRequest(
        practice_id=practice.id,
        status=CancellationStatus.PENDING.value,
        reason_type=reason_type,
        reason_summary=reason_summary,
        evaluation_data=evaluation_data,
        proposed_at=proposed_at,
        expires_at=expires_at
    )

    db.session.add(request)
    db.session.commit()

    logger.info(f"Cancellation request {request.id} created, expires at {expires_at}")
    return request


def process_cancellation_decision(
    request_id: int,
    decision: str,
    decided_by_slack_uid: Optional[str] = None,
    decided_by_user_id: Optional[int] = None,
    notes: Optional[str] = None
) -> CancellationRequest:
    """
    Process a human decision on a cancellation proposal.

    Args:
        request_id: CancellationRequest ID
        decision: 'approved' or 'rejected'
        decided_by_slack_uid: Slack user ID of decision maker
        decided_by_user_id: Database user ID of decision maker
        notes: Optional decision notes

    Returns:
        Updated CancellationRequest
    """
    request = CancellationRequest.query.get(request_id)
    if not request:
        raise ValueError(f"CancellationRequest {request_id} not found")

    if request.status != CancellationStatus.PENDING.value:
        raise ValueError(f"CancellationRequest {request_id} already {request.status}")

    logger.info(f"Processing decision '{decision}' for request {request_id}")

    # Update request status
    if decision.lower() == 'approved':
        request.status = CancellationStatus.APPROVED.value

        # Cancel the practice
        practice = request.practice
        practice.status = PracticeStatus.CANCELLED.value

        # Generate cancellation reason from evaluation
        if not practice.cancellation_reason:
            practice.cancellation_reason = request.reason_summary

        logger.info(f"Practice {practice.id} cancelled per approved request")

    elif decision.lower() == 'rejected':
        request.status = CancellationStatus.REJECTED.value
        logger.info(f"Cancellation request {request_id} rejected - practice continues")

    else:
        raise ValueError(f"Invalid decision: {decision}. Must be 'approved' or 'rejected'")

    # Record decision metadata
    request.decided_at = datetime.utcnow()
    request.decided_by_user_id = decided_by_user_id
    request.decided_by_slack_uid = decided_by_slack_uid
    request.decision_notes = notes

    db.session.commit()

    return request


def expire_pending_proposals() -> list[CancellationRequest]:
    """
    Find and expire proposals past their timeout.

    This implements fail-open behavior: if no human decision is made
    within the timeout window, the practice continues as scheduled.

    Returns:
        List of expired CancellationRequest objects
    """
    now = datetime.utcnow()

    expired_requests = CancellationRequest.query.filter(
        CancellationRequest.status == CancellationStatus.PENDING.value,
        CancellationRequest.expires_at < now
    ).all()

    if expired_requests:
        logger.warning(f"Found {len(expired_requests)} expired cancellation proposals")

        for request in expired_requests:
            request.status = CancellationStatus.EXPIRED.value
            logger.info(f"Request {request.id} expired - practice {request.practice_id} continues (fail-open)")

        db.session.commit()

    return expired_requests


def _determine_reason_type(evaluation: PracticeEvaluation) -> str:
    """
    Determine primary reason category from evaluation violations.

    Returns: 'weather', 'trail_conditions', 'no_lead', or 'multiple_factors'
    """
    if not evaluation.violations:
        return 'multiple_factors'

    # Count violations by category
    categories = {}
    for violation in evaluation.violations:
        # Extract category from threshold name
        if 'temperature' in violation.threshold_name or 'wind' in violation.threshold_name:
            category = 'weather'
        elif 'precipitation' in violation.threshold_name or 'lightning' in violation.threshold_name:
            category = 'weather'
        elif 'trail' in violation.threshold_name or 'groomed' in violation.threshold_name:
            category = 'trail_conditions'
        elif 'lead' in violation.threshold_name:
            category = 'no_lead'
        elif 'daylight' in violation.threshold_name or 'lights' in violation.threshold_name:
            category = 'daylight'
        else:
            category = 'other'

        categories[category] = categories.get(category, 0) + 1

    # Return most common category
    if categories:
        primary_category = max(categories, key=categories.get)
        if categories[primary_category] > len(evaluation.violations) / 2:
            return primary_category

    return 'multiple_factors'


def _generate_reason_summary(evaluation: PracticeEvaluation) -> str:
    """
    Generate human-readable summary of cancellation reasons.

    Args:
        evaluation: Practice evaluation

    Returns:
        Concise summary string
    """
    critical_violations = [v for v in evaluation.violations if v.severity == 'critical']

    if not critical_violations:
        return "Safety concerns detected"

    # Build summary from critical violations
    reasons = []
    for violation in critical_violations[:3]:  # Limit to top 3
        reasons.append(violation.message)

    summary = "; ".join(reasons)

    if len(critical_violations) > 3:
        summary += f" (+{len(critical_violations) - 3} more issues)"

    return summary


def _serialize_evaluation(evaluation: PracticeEvaluation) -> dict:
    """
    Serialize PracticeEvaluation to JSON-compatible dict.

    Args:
        evaluation: Evaluation to serialize

    Returns:
        JSON-compatible dictionary
    """
    return {
        'practice_id': evaluation.practice_id,
        'evaluated_at': evaluation.evaluated_at.isoformat() if evaluation.evaluated_at else None,
        'is_go': evaluation.is_go,
        'confidence': evaluation.confidence,
        'has_confirmed_lead': evaluation.has_confirmed_lead,
        'has_posted_workout': evaluation.has_posted_workout,
        'violations': [
            {
                'threshold_name': v.threshold_name,
                'threshold_value': v.threshold_value,
                'actual_value': v.actual_value,
                'severity': v.severity,
                'message': v.message
            }
            for v in evaluation.violations
        ],
        'weather': {
            'temperature_f': evaluation.weather.temperature_f,
            'feels_like_f': evaluation.weather.feels_like_f,
            'wind_speed_mph': evaluation.weather.wind_speed_mph,
            'precipitation_chance': evaluation.weather.precipitation_chance,
            'conditions_summary': evaluation.weather.conditions_summary,
            'has_lightning_threat': evaluation.weather.has_lightning_threat
        } if evaluation.weather else None,
        'trail_conditions': {
            'location': evaluation.trail_conditions.location,
            'trails_open': evaluation.trail_conditions.trails_open,
            'ski_quality': evaluation.trail_conditions.ski_quality,
            'groomed': evaluation.trail_conditions.groomed,
            'groomed_for': evaluation.trail_conditions.groomed_for
        } if evaluation.trail_conditions else None
    }
