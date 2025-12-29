"""Service layer for practice management - model conversions and business logic."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)
from app.practices.models import (
    Practice,
    PracticeLocation,
    SocialLocation,
    PracticeActivity,
    PracticeType,
    PracticeLead,
    PracticeRSVP,
    CancellationRequest
)
from app.practices.interfaces import (
    PracticeInfo,
    PracticeLocationInfo,
    SocialLocationInfo,
    PracticeActivityInfo,
    PracticeTypeInfo,
    PracticeLeadInfo,
    RSVPInfo,
    CancellationProposal,
    PracticeStatus,
    CancellationStatus,
    RSVPStatus,
    LeadRole
)


def convert_social_location_to_info(location: Optional[SocialLocation]) -> Optional[SocialLocationInfo]:
    """Convert SocialLocation model to SocialLocationInfo dataclass."""
    if not location:
        return None

    return SocialLocationInfo(
        id=location.id,
        name=location.name,
        address=location.address,
        google_maps_url=location.google_maps_url
    )


def convert_practice_location_to_info(location: Optional[PracticeLocation]) -> Optional[PracticeLocationInfo]:
    """Convert PracticeLocation model to PracticeLocationInfo dataclass."""
    if not location:
        return None

    return PracticeLocationInfo(
        id=location.id,
        name=location.name,
        spot=location.spot,
        address=location.address,
        google_maps_url=location.google_maps_url,
        latitude=location.latitude,
        longitude=location.longitude,
        parking_notes=location.parking_notes,
        social_location=convert_social_location_to_info(location.social_location),
        airtable_id=location.airtable_id
    )


def convert_activity_to_info(activity: PracticeActivity) -> PracticeActivityInfo:
    """Convert PracticeActivity model to PracticeActivityInfo dataclass."""
    return PracticeActivityInfo(
        id=activity.id,
        name=activity.name,
        gear_required=activity.gear_required or [],
        airtable_id=activity.airtable_id
    )


def convert_type_to_info(practice_type: PracticeType) -> PracticeTypeInfo:
    """Convert PracticeType model to PracticeTypeInfo dataclass."""
    return PracticeTypeInfo(
        id=practice_type.id,
        name=practice_type.name,
        fitness_goals=practice_type.fitness_goals or [],
        has_intervals=practice_type.has_intervals,
        airtable_id=practice_type.airtable_id
    )


def convert_lead_to_info(lead: Optional[PracticeLead]) -> Optional[PracticeLeadInfo]:
    """Convert PracticeLead model to PracticeLeadInfo dataclass."""
    if not lead or not lead.user:
        return None

    # Safe enum conversion with fallback
    try:
        role = LeadRole(lead.role) if lead.role else LeadRole.LEAD
    except (ValueError, KeyError):
        role = LeadRole.LEAD

    user = lead.user
    slack_uid = user.slack_user.slack_uid if user.slack_user else None

    return PracticeLeadInfo(
        id=lead.id,
        practice_id=lead.practice_id,
        user_id=user.id,
        display_name=f"{user.first_name} {user.last_name}",
        slack_user_id=slack_uid,
        email=user.email,
        role=role,
        confirmed=lead.confirmed,
        confirmed_at=lead.confirmed_at
    )


def convert_rsvp_to_info(rsvp: Optional[PracticeRSVP]) -> Optional[RSVPInfo]:
    """Convert PracticeRSVP model to RSVPInfo dataclass."""
    if not rsvp:
        return None

    # Safe enum conversion with fallback
    try:
        status = RSVPStatus(rsvp.status) if rsvp.status else RSVPStatus.MAYBE
    except (ValueError, KeyError):
        status = RSVPStatus.MAYBE

    return RSVPInfo(
        id=rsvp.id,
        practice_id=rsvp.practice_id,
        user_id=rsvp.user_id,
        status=status,
        responded_at=rsvp.responded_at,
        slack_user_id=rsvp.slack_user_id,
        notes=rsvp.notes
    )


def convert_practice_to_info(practice: Practice) -> PracticeInfo:
    """Convert Practice model to PracticeInfo dataclass."""
    # Convert leads with logging for any that fail conversion
    converted_leads = []
    for lead in practice.leads:
        lead_info = convert_lead_to_info(lead)
        if lead_info is not None:
            converted_leads.append(lead_info)
        else:
            logger.warning(
                f"PracticeLead id={lead.id} for practice id={practice.id} "
                f"could not be converted (user_id={lead.user_id})"
            )

    # Safe enum conversion with fallback
    try:
        practice_status = PracticeStatus(practice.status) if practice.status else PracticeStatus.SCHEDULED
    except (ValueError, KeyError):
        logger.warning(f"Invalid practice status '{practice.status}' for practice id={practice.id}, defaulting to SCHEDULED")
        practice_status = PracticeStatus.SCHEDULED

    return PracticeInfo(
        id=practice.id,
        date=practice.date,
        day_of_week=practice.day_of_week,
        status=practice_status,
        location=convert_practice_location_to_info(practice.location),
        activities=[convert_activity_to_info(a) for a in practice.activities],
        practice_types=[convert_type_to_info(t) for t in practice.practice_types],
        warmup_description=practice.warmup_description,
        workout_description=practice.workout_description,
        cooldown_description=practice.cooldown_description,
        has_social=practice.has_social,
        is_dark_practice=practice.is_dark_practice,
        leads=converted_leads,
        slack_message_ts=practice.slack_message_ts,
        slack_channel_id=practice.slack_channel_id,
        cancellation_reason=practice.cancellation_reason,
        airtable_id=practice.airtable_id,
        created_at=practice.created_at,
        updated_at=practice.updated_at
    )


def convert_cancellation_to_proposal(request: CancellationRequest) -> CancellationProposal:
    """Convert CancellationRequest model to CancellationProposal dataclass."""
    # Parse evaluation_data if present
    evaluation = None
    if request.evaluation_data:
        # TODO: Deserialize JSON to PracticeEvaluation dataclass
        # For now, leave as None
        pass

    # Safe enum conversion with fallback
    try:
        cancellation_status = CancellationStatus(request.status) if request.status else CancellationStatus.PENDING
    except (ValueError, KeyError):
        logger.warning(f"Invalid cancellation status '{request.status}' for request id={request.id}, defaulting to PENDING")
        cancellation_status = CancellationStatus.PENDING

    return CancellationProposal(
        id=request.id,
        practice_id=request.practice_id,
        proposed_at=request.proposed_at,
        status=cancellation_status,
        reason_type=request.reason_type,
        reason_summary=request.reason_summary,
        evaluation=evaluation,
        slack_message_ts=request.slack_message_ts,
        slack_channel_id=request.slack_channel_id,
        decided_at=request.decided_at,
        decided_by_user_id=request.decided_by_user_id,
        decided_by_slack_uid=request.decided_by_slack_uid,
        decision_notes=request.decision_notes,
        expires_at=request.expires_at
    )
