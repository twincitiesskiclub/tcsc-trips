"""
Skipper Agent Module

AI-powered practice monitoring with human approval for cancellations.

Core Components:
- decision_engine: Orchestrates evaluation of practice conditions
- thresholds: Safety threshold checks for weather, trails, leads, daylight
- proposals: CancellationRequest management with fail-open expiration
- brain: Claude API integration for natural language summaries

Routines:
- morning_check: Daily 7am evaluation of today's practices
- pre_practice: 48h and 24h checks for workout/lead confirmation
- weekly_summary: Sunday evening preview of upcoming week
"""

from app.agent.decision_engine import (
    evaluate_practice,
    should_propose_cancellation,
    load_skipper_config
)
from app.agent.thresholds import (
    check_weather_thresholds,
    check_trail_thresholds,
    check_lead_availability,
    check_daylight
)
from app.agent.proposals import (
    create_cancellation_proposal,
    process_cancellation_decision,
    expire_pending_proposals
)
from app.agent.brain import (
    generate_evaluation_summary,
    generate_cancellation_message
)

__all__ = [
    # Decision Engine
    'evaluate_practice',
    'should_propose_cancellation',
    'load_skipper_config',
    # Thresholds
    'check_weather_thresholds',
    'check_trail_thresholds',
    'check_lead_availability',
    'check_daylight',
    # Proposals
    'create_cancellation_proposal',
    'process_cancellation_decision',
    'expire_pending_proposals',
    # Brain
    'generate_evaluation_summary',
    'generate_cancellation_message',
]
