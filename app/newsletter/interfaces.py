"""
Interface contracts for the Weekly Dispatch newsletter system.

Defines enums and dataclasses used across newsletter modules for
type-safe communication between collection, generation, and publishing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# =============================================================================
# Status Enums
# =============================================================================

class NewsletterStatus(str, Enum):
    """Newsletter lifecycle status."""
    BUILDING = 'building'              # Daily regenerations in progress
    READY_FOR_REVIEW = 'ready_for_review'  # Sunday finalization complete
    APPROVED = 'approved'              # Admin approved
    PUBLISHED = 'published'            # Posted to announcement channel


class SubmissionStatus(str, Enum):
    """Member submission processing status."""
    PENDING = 'pending'    # Awaiting inclusion in next generation
    INCLUDED = 'included'  # Used in a newsletter version
    REJECTED = 'rejected'  # Declined by admin


class SubmissionType(str, Enum):
    """Types of member submissions."""
    SPOTLIGHT = 'spotlight'      # Member highlight/shoutout
    CONTENT = 'content'          # General content/story
    EVENT = 'event'              # Event announcement
    ANNOUNCEMENT = 'announcement'  # Official club announcement


class VersionTrigger(str, Enum):
    """What triggered a newsletter version."""
    SCHEDULED = 'scheduled'  # Daily 8am job
    MANUAL = 'manual'        # Admin triggered regeneration
    SUBMISSION = 'submission'  # New submission added
    FEEDBACK = 'feedback'    # Admin feedback incorporated


class MessageVisibility(str, Enum):
    """Visibility level for collected messages."""
    PUBLIC = 'public'    # From public channel - can link/quote/name
    PRIVATE = 'private'  # From private channel - summarize only


class NewsSource(str, Enum):
    """External news sources for scraping."""
    SKINNYSKI = 'skinnyski'
    LOPPET = 'loppet'
    THREE_RIVERS = 'three_rivers'


class SectionType(str, Enum):
    """Newsletter section types."""
    OPENER = 'opener'
    QOTM = 'qotm'
    COACHES_CORNER = 'coaches_corner'
    MEMBER_HEADS_UP = 'member_heads_up'
    UPCOMING_EVENTS = 'upcoming_events'
    MEMBER_HIGHLIGHT = 'member_highlight'
    MONTH_IN_REVIEW = 'month_in_review'
    FROM_THE_BOARD = 'from_the_board'
    CLOSER = 'closer'
    PHOTO_GALLERY = 'photo_gallery'


class SectionStatus(str, Enum):
    """Newsletter section status state machine."""
    AWAITING_CONTENT = 'awaiting_content'  # Waiting for human input
    HAS_AI_DRAFT = 'has_ai_draft'          # AI generated, needs edit
    HUMAN_EDITED = 'human_edited'          # Human has modified
    FINAL = 'final'                        # No more edits expected


class HostStatus(str, Enum):
    """Newsletter host submission status."""
    ASSIGNED = 'assigned'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'


class CoachStatus(str, Enum):
    """Coach rotation submission status."""
    ASSIGNED = 'assigned'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'


class HighlightStatus(str, Enum):
    """Member highlight submission status."""
    NOMINATED = 'nominated'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'


# =============================================================================
# Collection Dataclasses
# =============================================================================

@dataclass
class SlackMessage:
    """Collected Slack message for newsletter inclusion."""
    channel_id: str
    channel_name: str
    message_ts: str
    user_id: str
    user_name: str
    text: str
    permalink: Optional[str] = None  # None for private channels
    reaction_count: int = 0
    reply_count: int = 0
    visibility: MessageVisibility = MessageVisibility.PUBLIC
    posted_at: Optional[datetime] = None
    thread_ts: Optional[str] = None  # Parent message ts if this is a reply


@dataclass
class NewsItem:
    """Scraped news article from external source."""
    source: NewsSource
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None


@dataclass
class MemberSubmission:
    """Member-submitted content via /dispatch."""
    id: int
    slack_user_id: str
    display_name: str
    submission_type: SubmissionType
    content: str
    permission_to_name: bool = False
    submitted_at: Optional[datetime] = None


@dataclass
class TrailConditionSummary:
    """Summarized trail conditions for newsletter."""
    location: str
    trails_open: str  # 'all', 'most', 'partial', 'closed'
    ski_quality: str  # 'excellent', 'good', 'fair', 'poor'
    groomed: bool = False
    groomed_for: Optional[str] = None  # 'classic', 'skate', 'both'
    report_date: Optional[datetime] = None
    notes: Optional[str] = None


# =============================================================================
# Generation Dataclasses
# =============================================================================

@dataclass
class NewsletterContext:
    """All collected data for newsletter generation."""
    week_start: datetime
    week_end: datetime
    slack_messages: list[SlackMessage] = field(default_factory=list)
    submissions: list[MemberSubmission] = field(default_factory=list)
    news_items: list[NewsItem] = field(default_factory=list)
    trail_conditions: list[TrailConditionSummary] = field(default_factory=list)
    prior_newsletter_content: Optional[str] = None
    admin_feedback: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of newsletter generation."""
    success: bool
    content: Optional[str] = None  # Raw content (JSON string or markdown)
    structured_content: Optional[dict] = None  # Parsed JSON dict (if JSON format)
    version_number: int = 0
    model_used: str = ""
    tokens_used: int = 0
    error: Optional[str] = None


# =============================================================================
# Publishing Dataclasses
# =============================================================================

@dataclass
class SlackPostReference:
    """Reference to a Slack message for updates."""
    channel_id: str
    message_ts: str
    thread_ts: Optional[str] = None


@dataclass
class PublishResult:
    """Result of publishing to Slack."""
    success: bool
    main_post: Optional[SlackPostReference] = None
    thread_post: Optional[SlackPostReference] = None
    error: Optional[str] = None
