# Monthly Dispatch Newsletter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the Weekly Dispatch into a Monthly Dispatch with hybrid human/AI editorial workflow, publishing mid-month with human-first content and AI-assisted drafts.

**Architecture:** Thread-based Slack living post (one reply per section to avoid 50-block limit), channel post for QOTM collection (not mass DM), template-based Member Highlight with AI composition, and single daily orchestrator job that checks what day of the month it is.

**Tech Stack:** Flask/SQLAlchemy, Slack Bolt, APScheduler, Claude Opus 4.5

---

## Task 1: Add Section Type and Status Enums

**Files:**
- Modify: `app/newsletter/interfaces.py`

**Step 1: Add SectionType enum**

Add after `NewsSource` enum:

```python
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
```

**Step 2: Add SectionStatus enum**

Add after `SectionType`:

```python
class SectionStatus(str, Enum):
    """Newsletter section status state machine."""
    AWAITING_CONTENT = 'awaiting_content'  # Waiting for human input
    HAS_AI_DRAFT = 'has_ai_draft'          # AI generated, needs edit
    HUMAN_EDITED = 'human_edited'          # Human has modified
    FINAL = 'final'                        # No more edits expected
```

**Step 3: Add HostStatus enum**

```python
class HostStatus(str, Enum):
    """Newsletter host submission status."""
    ASSIGNED = 'assigned'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'
```

**Step 4: Add CoachStatus enum**

```python
class CoachStatus(str, Enum):
    """Coach rotation submission status."""
    ASSIGNED = 'assigned'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'
```

**Step 5: Add HighlightStatus enum**

```python
class HighlightStatus(str, Enum):
    """Member highlight submission status."""
    NOMINATED = 'nominated'
    SUBMITTED = 'submitted'
    DECLINED = 'declined'
```

**Step 6: Run tests**

Run: `pytest tests/ -k "interface" -v --tb=short`
Expected: Tests pass (or no interface tests exist yet)

**Step 7: Commit**

```bash
git add app/newsletter/interfaces.py
git commit -m "feat(newsletter): add section and status enums for monthly dispatch"
```

---

## Task 2: Update Newsletter Model with Monthly Fields

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add monthly fields to Newsletter model**

Add these columns to the `Newsletter` class after `week_end`:

```python
    # Monthly dispatch fields (nullable for migration)
    month_year = db.Column(db.String(7))  # e.g., "2026-01"
    period_start = db.Column(db.DateTime)  # Generic, works for weekly or monthly
    period_end = db.Column(db.DateTime)
    publish_target_date = db.Column(db.DateTime)  # 15th of month
    qotm_question = db.Column(db.Text)  # Question of the Month
```

**Step 2: Add get_or_create_current_month class method**

Add to Newsletter class:

```python
    @classmethod
    def get_or_create_current_month(cls, month_year: str = None) -> 'Newsletter':
        """Get or create newsletter for the specified or current month.

        Args:
            month_year: Month in YYYY-MM format, or None for current month

        Returns:
            Newsletter instance for the month
        """
        from datetime import datetime
        from calendar import monthrange

        if month_year is None:
            now = datetime.utcnow()
            month_year = now.strftime('%Y-%m')

        # Parse month_year
        year, month = map(int, month_year.split('-'))

        # Check for existing
        newsletter = cls.query.filter_by(month_year=month_year).first()
        if newsletter:
            return newsletter

        # Create new
        period_start = datetime(year, month, 1)
        _, last_day = monthrange(year, month)
        period_end = datetime(year, month, last_day, 23, 59, 59)
        publish_target = datetime(year, month, 15, 12, 0, 0)  # 15th at noon

        newsletter = cls(
            month_year=month_year,
            period_start=period_start,
            period_end=period_end,
            publish_target_date=publish_target,
            # Keep week_start/week_end as None for monthly newsletters
            week_start=period_start,
            week_end=period_end,
            status=NewsletterStatus.BUILDING.value
        )
        db.session.add(newsletter)
        db.session.flush()

        return newsletter
```

**Step 3: Add has_highlight_nomination property**

```python
    @property
    def has_highlight_nomination(self) -> bool:
        """Check if newsletter has a member highlight nomination."""
        return hasattr(self, 'highlight') and self.highlight is not None
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/ -v --tb=short`
Expected: Existing tests pass

**Step 5: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add monthly fields to Newsletter model"
```

---

## Task 3: Create NewsletterSection Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add import for new enums**

Update imports at top of file:

```python
from app.newsletter.interfaces import (
    NewsletterStatus,
    SubmissionStatus,
    SubmissionType,
    VersionTrigger,
    MessageVisibility,
    NewsSource,
    SectionType,
    SectionStatus,
)
```

**Step 2: Add NewsletterSection model**

Add after NewsletterPrompt class:

```python
class NewsletterSection(db.Model):
    """Per-section content with status and Slack thread reference.

    Each section of the newsletter has its own status and can be
    edited independently via Slack modals.
    """
    __tablename__ = 'newsletter_sections'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Section identification
    section_type = db.Column(db.String(50), nullable=False)
    section_order = db.Column(db.Integer, default=0)

    # Content
    content = db.Column(db.Text)
    ai_draft = db.Column(db.Text)  # Original AI draft (for AI-assisted sections)

    # Status state machine
    status = db.Column(
        db.String(20),
        nullable=False,
        default=SectionStatus.AWAITING_CONTENT.value
    )

    # Slack thread reference (each section is a thread reply)
    slack_thread_ts = db.Column(db.String(50))

    # Edit tracking
    edited_by = db.Column(db.String(100))
    edited_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationship
    newsletter = db.relationship('Newsletter', backref=db.backref('sections', lazy='dynamic'))

    def __repr__(self):
        return f'<NewsletterSection {self.section_type} newsletter={self.newsletter_id}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'section_type',
            name='uq_newsletter_section_type'
        ),
    )
```

**Step 3: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import NewsletterSection; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add NewsletterSection model"
```

---

## Task 4: Create QOTMResponse Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add QOTMResponse model**

Add after NewsletterSection:

```python
class QOTMResponse(db.Model):
    """Question of the Month response from a member.

    Stores member responses to the monthly question. Each user can
    only submit one response per newsletter (upsert on resubmit).
    """
    __tablename__ = 'qotm_responses'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Submitter info (Slack user)
    user_id = db.Column(db.String(20), nullable=False)  # Slack user ID
    user_name = db.Column(db.String(100))

    # Response content
    response = db.Column(db.Text, nullable=False)

    # Admin curation
    selected = db.Column(db.Boolean, default=False)

    # Timestamps
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    newsletter = db.relationship('Newsletter', backref=db.backref('qotm_responses', lazy='dynamic'))

    def __repr__(self):
        return f'<QOTMResponse user={self.user_id} newsletter={self.newsletter_id}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'user_id',
            name='uq_qotm_response'
        ),
    )
```

**Step 2: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import QOTMResponse; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add QOTMResponse model"
```

---

## Task 5: Create CoachRotation Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add CoachRotation model**

Add after QOTMResponse:

```python
class CoachRotation(db.Model):
    """Coach assignment and content for Coaches Corner section.

    Tracks which coach is assigned each month and their submitted content.
    Used to implement fair rotation through coaches.
    """
    __tablename__ = 'coach_rotations'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False,
        unique=True  # One coach per newsletter
    )

    # Coach info (links to User model)
    coach_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    # Content
    content = db.Column(db.Text)

    # Status
    status = db.Column(db.String(20), default='assigned')  # assigned, submitted, declined

    # Timestamps
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    # Relationships
    newsletter = db.relationship('Newsletter', backref=db.backref('coach_rotation', uselist=False))
    coach = db.relationship('User', backref=db.backref('coach_rotations', lazy='dynamic'))

    def __repr__(self):
        return f'<CoachRotation coach={self.coach_user_id} newsletter={self.newsletter_id}>'
```

**Step 2: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import CoachRotation; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add CoachRotation model"
```

---

## Task 6: Create MemberHighlight Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add MemberHighlight model**

Add after CoachRotation:

```python
class MemberHighlight(db.Model):
    """Member spotlight with template-based questions and AI composition.

    Admin nominates a member, member answers structured questions,
    AI composes into polished prose, editor reviews/edits.
    """
    __tablename__ = 'member_highlights'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False,
        unique=True  # One highlight per newsletter
    )

    # Member info (links to User model)
    member_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    # Who nominated them
    nominated_by = db.Column(db.String(100))  # Admin email

    # Raw answers from member (structured JSON)
    raw_answers = db.Column(db.JSON)

    # AI-composed version from raw_answers
    ai_composed_content = db.Column(db.Text)

    # Final edited version (what appears in newsletter)
    content = db.Column(db.Text)

    # Status
    status = db.Column(db.String(20), default='nominated')  # nominated, submitted, declined

    # Timestamps
    nominated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    # Relationships
    newsletter = db.relationship('Newsletter', backref=db.backref('highlight', uselist=False))
    member = db.relationship('User', backref=db.backref('highlights', lazy='dynamic'))

    def __repr__(self):
        return f'<MemberHighlight member={self.member_user_id} newsletter={self.newsletter_id}>'
```

**Step 2: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import MemberHighlight; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add MemberHighlight model"
```

---

## Task 7: Create NewsletterHost Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add NewsletterHost model**

Add after MemberHighlight:

```python
class NewsletterHost(db.Model):
    """Newsletter host assignment for opener and closer content.

    The host is manually assigned by admin and writes both the opener
    and closer sections. Can be a Slack member or external guest.
    """
    __tablename__ = 'newsletter_hosts'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False,
        unique=True  # One host per newsletter
    )

    # Host info (could be member or external)
    slack_user_id = db.Column(db.String(20))  # If Slack member
    external_name = db.Column(db.String(100))  # If external guest
    external_email = db.Column(db.String(200))  # For external contact

    # Content
    opener_content = db.Column(db.Text)
    closer_content = db.Column(db.Text)

    # Status
    status = db.Column(db.String(20), default='assigned')  # assigned, submitted, declined

    # Timestamps
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    # Relationship
    newsletter = db.relationship('Newsletter', backref=db.backref('host', uselist=False))

    def __repr__(self):
        host_id = self.slack_user_id or self.external_name or 'unknown'
        return f'<NewsletterHost {host_id} newsletter={self.newsletter_id}>'

    @property
    def display_name(self) -> str:
        """Get display name for the host."""
        if self.external_name:
            return self.external_name
        # For Slack members, would need to look up - return user_id for now
        return self.slack_user_id or 'Unknown Host'

    @property
    def is_external(self) -> bool:
        """Check if host is external (not a Slack member)."""
        return bool(self.external_name or self.external_email) and not self.slack_user_id
```

**Step 2: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import NewsletterHost; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add NewsletterHost model"
```

---

## Task 8: Create PhotoSubmission Model

**Files:**
- Modify: `app/newsletter/models.py`

**Step 1: Add PhotoSubmission model**

Add after NewsletterHost:

```python
class PhotoSubmission(db.Model):
    """Curated photo from #photos channel for Photo Gallery.

    Photos are collected from the channel and ranked by reactions.
    Admin selects which photos to include in the newsletter.
    """
    __tablename__ = 'photo_submissions'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Slack file info
    slack_file_id = db.Column(db.String(20), nullable=False)
    slack_permalink = db.Column(db.String(500))

    # Fallback if permalink expires
    fallback_description = db.Column(db.Text)

    # Who posted the photo
    submitted_by_user_id = db.Column(db.String(20))

    # Photo metadata
    caption = db.Column(db.Text)
    reaction_count = db.Column(db.Integer, default=0)

    # Admin curation
    selected = db.Column(db.Boolean, default=False)

    # Timestamps
    posted_at = db.Column(db.DateTime)  # When originally posted to Slack
    collected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    newsletter = db.relationship('Newsletter', backref=db.backref('photo_submissions', lazy='dynamic'))

    def __repr__(self):
        return f'<PhotoSubmission {self.slack_file_id} newsletter={self.newsletter_id}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'slack_file_id',
            name='uq_photo_submission_file'
        ),
    )
```

**Step 2: Run test to verify model loads**

Run: `python -c "from app.newsletter.models import PhotoSubmission; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/newsletter/models.py
git commit -m "feat(newsletter): add PhotoSubmission model"
```

---

## Task 9: Create Database Migration

**Files:**
- Create: `migrations/versions/xxx_monthly_dispatch_models.py`

**Step 1: Generate migration**

Run: `flask db migrate -m "Monthly dispatch newsletter models"`

**Step 2: Review the generated migration file**

Open the generated migration in `migrations/versions/` and verify it includes:
- `newsletter_sections` table
- `qotm_responses` table
- `coach_rotations` table
- `member_highlights` table
- `newsletter_hosts` table
- `photo_submissions` table
- New columns on `newsletters` table (month_year, period_start, period_end, publish_target_date, qotm_question)

**Step 3: Apply migration**

Run: `flask db upgrade`
Expected: Migration applies successfully

**Step 4: Verify tables exist**

Run: `python -c "from app.newsletter.models import *; print('All models OK')"`
Expected: All models OK

**Step 5: Commit**

```bash
git add migrations/versions/
git commit -m "feat(newsletter): add migration for monthly dispatch models"
```

---

## Task 10: Create QOTM Module

**Files:**
- Create: `app/newsletter/qotm.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_qotm.py`:

```python
"""Tests for Question of the Month system."""
import pytest
from app.newsletter.qotm import (
    post_qotm_to_channel,
    handle_qotm_submission,
    get_qotm_responses,
    select_qotm_responses,
    get_selected_qotm_for_newsletter,
)


def test_handle_qotm_submission_creates_response(app, db_session, newsletter):
    """Test that submitting a QOTM response creates a record."""
    result = handle_qotm_submission(
        newsletter_id=newsletter.id,
        user_id='U123456',
        user_name='Test User',
        response='This is my answer!'
    )

    assert result['success'] is True
    assert result['response_id'] is not None


def test_handle_qotm_submission_upserts(app, db_session, newsletter):
    """Test that resubmitting updates the existing response."""
    # First submission
    result1 = handle_qotm_submission(
        newsletter_id=newsletter.id,
        user_id='U123456',
        user_name='Test User',
        response='First answer'
    )

    # Second submission (same user)
    result2 = handle_qotm_submission(
        newsletter_id=newsletter.id,
        user_id='U123456',
        user_name='Test User',
        response='Updated answer'
    )

    assert result2['response_id'] == result1['response_id']

    responses = get_qotm_responses(newsletter.id)
    assert len(responses) == 1
    assert responses[0].response == 'Updated answer'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_qotm.py -v`
Expected: FAIL - module not found

**Step 3: Implement qotm.py**

Create `app/newsletter/qotm.py`:

```python
"""Question of the Month system for Monthly Dispatch.

Handles:
- Posting QOTM to #chat channel with "Share Your Answer" button
- Processing member submissions via modal
- Admin curation of responses
"""
import logging
from datetime import datetime
from typing import Any, Optional

from app.models import db
from app.newsletter.models import Newsletter, QOTMResponse
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)


def post_qotm_to_channel(
    newsletter_id: int,
    question: str,
    channel: str = 'chat'
) -> dict[str, Any]:
    """Post Question of the Month to channel with response button.

    Args:
        newsletter_id: Newsletter this QOTM belongs to
        question: The question text
        channel: Channel name to post to (default: chat)

    Returns:
        Dict with success status and message_ts
    """
    client = get_slack_client()
    if not client:
        logger.error("Slack client not available")
        return {'success': False, 'error': 'Slack client not available'}

    try:
        # Store question on newsletter
        newsletter = Newsletter.query.get(newsletter_id)
        if newsletter:
            newsletter.qotm_question = question
            db.session.commit()

        # Build Block Kit message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Question of the Month",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{question}*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Your response may be featured in the Monthly Dispatch newsletter!"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Share Your Answer",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "qotm_response_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        # Get channel ID
        from app.slack.client import get_channel_id_by_name
        channel_id = get_channel_id_by_name(channel)
        if not channel_id:
            return {'success': False, 'error': f'Channel #{channel} not found'}

        # Post message
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"Question of the Month: {question}",
            blocks=blocks
        )

        return {
            'success': True,
            'message_ts': response['ts'],
            'channel_id': channel_id
        }

    except Exception as e:
        logger.error(f"Failed to post QOTM: {e}")
        return {'success': False, 'error': str(e)}


def handle_qotm_submission(
    newsletter_id: int,
    user_id: str,
    user_name: str,
    response: str
) -> dict[str, Any]:
    """Handle a QOTM submission from a member.

    Creates or updates the response (upsert based on user_id).

    Args:
        newsletter_id: Newsletter this response belongs to
        user_id: Slack user ID
        user_name: Display name
        response: The response text

    Returns:
        Dict with success status and response_id
    """
    try:
        # Check for existing response (upsert)
        existing = QOTMResponse.query.filter_by(
            newsletter_id=newsletter_id,
            user_id=user_id
        ).first()

        if existing:
            existing.response = response
            existing.user_name = user_name
            existing.submitted_at = datetime.utcnow()
            db.session.commit()
            return {'success': True, 'response_id': existing.id, 'updated': True}

        # Create new response
        qotm_response = QOTMResponse(
            newsletter_id=newsletter_id,
            user_id=user_id,
            user_name=user_name,
            response=response
        )
        db.session.add(qotm_response)
        db.session.commit()

        return {'success': True, 'response_id': qotm_response.id, 'updated': False}

    except Exception as e:
        logger.error(f"Failed to save QOTM response: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def get_qotm_responses(newsletter_id: int) -> list[QOTMResponse]:
    """Get all QOTM responses for a newsletter.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of QOTMResponse objects
    """
    return QOTMResponse.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(QOTMResponse.submitted_at).all()


def select_qotm_responses(response_ids: list[int], newsletter_id: int) -> dict[str, Any]:
    """Mark selected QOTM responses for inclusion in newsletter.

    Args:
        response_ids: List of response IDs to select
        newsletter_id: Newsletter ID (for security check)

    Returns:
        Dict with success status
    """
    try:
        # Deselect all first
        QOTMResponse.query.filter_by(newsletter_id=newsletter_id).update(
            {'selected': False}
        )

        # Select the specified ones
        if response_ids:
            QOTMResponse.query.filter(
                QOTMResponse.id.in_(response_ids),
                QOTMResponse.newsletter_id == newsletter_id
            ).update({'selected': True}, synchronize_session=False)

        db.session.commit()
        return {'success': True, 'selected_count': len(response_ids)}

    except Exception as e:
        logger.error(f"Failed to select QOTM responses: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def get_selected_qotm_for_newsletter(newsletter_id: int) -> list[QOTMResponse]:
    """Get selected QOTM responses for rendering in newsletter.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of selected QOTMResponse objects
    """
    return QOTMResponse.query.filter_by(
        newsletter_id=newsletter_id,
        selected=True
    ).order_by(QOTMResponse.submitted_at).all()
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_qotm.py -v`
Expected: Tests pass (may need fixtures)

**Step 5: Commit**

```bash
git add app/newsletter/qotm.py tests/newsletter/test_qotm.py
git commit -m "feat(newsletter): add QOTM system"
```

---

## Task 11: Create Newsletter Host Module

**Files:**
- Create: `app/newsletter/host.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_host.py`:

```python
"""Tests for Newsletter Host system."""
import pytest
from app.newsletter.host import (
    assign_host,
    send_host_request,
    handle_host_submission,
)


def test_assign_host_creates_record(app, db_session, newsletter):
    """Test that assigning a host creates a record."""
    result = assign_host(
        newsletter_id=newsletter.id,
        slack_user_id='U123456'
    )

    assert result['success'] is True
    assert result['host_id'] is not None

    # Verify newsletter has host
    from app.newsletter.models import Newsletter
    nl = Newsletter.query.get(newsletter.id)
    assert nl.host is not None
    assert nl.host.slack_user_id == 'U123456'


def test_assign_external_host(app, db_session, newsletter):
    """Test assigning an external guest as host."""
    result = assign_host(
        newsletter_id=newsletter.id,
        external_name='Jane Guest',
        external_email='jane@example.com'
    )

    assert result['success'] is True

    from app.newsletter.models import Newsletter
    nl = Newsletter.query.get(newsletter.id)
    assert nl.host.is_external is True
    assert nl.host.external_name == 'Jane Guest'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_host.py -v`
Expected: FAIL - module not found

**Step 3: Implement host.py**

Create `app/newsletter/host.py`:

```python
"""Newsletter Host system for Monthly Dispatch.

Handles:
- Admin assignment of newsletter host (member or external)
- DM request to host with submission modal
- Processing opener and closer content submissions
"""
import logging
from datetime import datetime
from typing import Any, Optional

from app.models import db
from app.newsletter.models import Newsletter, NewsletterHost
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)


def assign_host(
    newsletter_id: int,
    slack_user_id: Optional[str] = None,
    external_name: Optional[str] = None,
    external_email: Optional[str] = None
) -> dict[str, Any]:
    """Assign a host for the newsletter.

    Args:
        newsletter_id: Newsletter to assign host to
        slack_user_id: Slack user ID if member
        external_name: Name if external guest
        external_email: Email if external guest

    Returns:
        Dict with success status and host_id
    """
    if not slack_user_id and not external_name:
        return {'success': False, 'error': 'Must provide slack_user_id or external_name'}

    try:
        # Check for existing host
        existing = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()

        if existing:
            # Update existing
            existing.slack_user_id = slack_user_id
            existing.external_name = external_name
            existing.external_email = external_email
            existing.status = 'assigned'
            existing.assigned_at = datetime.utcnow()
            existing.submitted_at = None
            existing.opener_content = None
            existing.closer_content = None
            db.session.commit()
            return {'success': True, 'host_id': existing.id, 'updated': True}

        # Create new
        host = NewsletterHost(
            newsletter_id=newsletter_id,
            slack_user_id=slack_user_id,
            external_name=external_name,
            external_email=external_email
        )
        db.session.add(host)
        db.session.commit()

        return {'success': True, 'host_id': host.id, 'updated': False}

    except Exception as e:
        logger.error(f"Failed to assign host: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def send_host_request(newsletter_id: int) -> dict[str, Any]:
    """Send DM to assigned host requesting their content.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter or not newsletter.host:
        return {'success': False, 'error': 'No host assigned'}

    host = newsletter.host

    if not host.slack_user_id:
        return {'success': False, 'error': 'Host is external - cannot DM'}

    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        # Format month name
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter.period_start else 'this month'

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You're the Newsletter Host!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"You've been selected as the Newsletter Host for *{month_name}*! We'd love for you to write the opening and closing sections of our Monthly Dispatch."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Opener (200-400 words):* Set the tone, welcome readers, share what's on your mind about the club or season.\n\n*Closer (100-200 words):* Sign off, share a call to action, or leave readers with something to think about."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Write My Sections",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "host_submission_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=host.slack_user_id,
            text=f"You're the Newsletter Host for {month_name}!",
            blocks=blocks
        )

        return {'success': True, 'message_ts': response['ts']}

    except Exception as e:
        logger.error(f"Failed to send host request: {e}")
        return {'success': False, 'error': str(e)}


def handle_host_submission(
    newsletter_id: int,
    opener_content: str,
    closer_content: str
) -> dict[str, Any]:
    """Handle host submission of opener and closer content.

    Args:
        newsletter_id: Newsletter ID
        opener_content: Opener section content
        closer_content: Closer section content

    Returns:
        Dict with success status
    """
    try:
        host = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()
        if not host:
            return {'success': False, 'error': 'No host assigned'}

        host.opener_content = opener_content
        host.closer_content = closer_content
        host.status = 'submitted'
        host.submitted_at = datetime.utcnow()
        db.session.commit()

        return {'success': True, 'host_id': host.id}

    except Exception as e:
        logger.error(f"Failed to save host submission: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def send_host_reminder(newsletter_id: int) -> dict[str, Any]:
    """Send reminder DM to host if they haven't submitted.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter or not newsletter.host:
        return {'success': False, 'error': 'No host assigned'}

    host = newsletter.host

    if host.status == 'submitted':
        return {'success': True, 'skipped': True, 'reason': 'Already submitted'}

    if not host.slack_user_id:
        return {'success': False, 'error': 'Host is external - cannot DM'}

    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter.period_start else 'this month'

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hey! Just a friendly reminder that we'd love to get your Newsletter Host sections for the *{month_name}* Monthly Dispatch. The newsletter goes out on the 15th!"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Write My Sections",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "host_submission_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=host.slack_user_id,
            text=f"Reminder: Newsletter Host sections needed for {month_name}",
            blocks=blocks
        )

        return {'success': True, 'message_ts': response['ts']}

    except Exception as e:
        logger.error(f"Failed to send host reminder: {e}")
        return {'success': False, 'error': str(e)}
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_host.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add app/newsletter/host.py tests/newsletter/test_host.py
git commit -m "feat(newsletter): add Newsletter Host system"
```

---

## Task 12: Create Coach Rotation Module

**Files:**
- Create: `app/newsletter/coach_rotation.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_coach_rotation.py`:

```python
"""Tests for Coach Rotation system."""
import pytest
from app.newsletter.coach_rotation import (
    get_next_coach,
    assign_coach_for_month,
    handle_coach_submission,
)


def test_get_next_coach_returns_coach_with_oldest_contribution(app, db_session, coaches):
    """Test that rotation selects coach with oldest contribution."""
    # coaches fixture should have coaches with HEAD_COACH/ASSISTANT_COACH tags
    coach = get_next_coach()

    assert coach is not None
    # Coach should be one of our coaches
    assert coach.id in [c.id for c in coaches]


def test_assign_coach_creates_rotation_record(app, db_session, newsletter, coaches):
    """Test that assigning a coach creates a rotation record."""
    result = assign_coach_for_month(newsletter.id)

    assert result['success'] is True
    assert result['coach_id'] is not None


def test_handle_coach_submission_stores_content(app, db_session, newsletter, coaches):
    """Test that coach submission stores content."""
    # First assign a coach
    assign_result = assign_coach_for_month(newsletter.id)

    # Then submit content
    result = handle_coach_submission(
        newsletter_id=newsletter.id,
        content="This month's coaching tip: Stay warm!"
    )

    assert result['success'] is True

    from app.newsletter.models import CoachRotation
    rotation = CoachRotation.query.filter_by(newsletter_id=newsletter.id).first()
    assert rotation.status == 'submitted'
    assert 'Stay warm' in rotation.content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_coach_rotation.py -v`
Expected: FAIL - module not found

**Step 3: Implement coach_rotation.py**

Create `app/newsletter/coach_rotation.py`:

```python
"""Coach Rotation system for Monthly Dispatch.

Handles:
- Automated rotation through coaches (HEAD_COACH, ASSISTANT_COACH tags)
- DM request to assigned coach
- Processing Coaches Corner content submissions
"""
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func

from app.models import db, User, Tag
from app.newsletter.models import Newsletter, CoachRotation
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)


def get_next_coach() -> Optional[User]:
    """Select the next coach in rotation.

    Logic:
    1. Get all users with HEAD_COACH or ASSISTANT_COACH tags
    2. Find most recent contribution per coach via CoachRotation.submitted_at
    3. Select coach with oldest (or no) contribution

    Returns:
        User object for next coach, or None if no coaches exist
    """
    # Get coaches
    coaches = User.query.join(User.tags).filter(
        Tag.name.in_(['HEAD_COACH', 'ASSISTANT_COACH'])
    ).all()

    if not coaches:
        logger.warning("No coaches found with HEAD_COACH or ASSISTANT_COACH tags")
        return None

    # Find most recent contribution for each coach
    coach_contributions = {}
    for coach in coaches:
        last_rotation = CoachRotation.query.filter_by(
            coach_user_id=coach.id,
            status='submitted'
        ).order_by(CoachRotation.submitted_at.desc()).first()

        coach_contributions[coach.id] = {
            'coach': coach,
            'last_submitted': last_rotation.submitted_at if last_rotation else None
        }

    # Select coach with oldest (or no) contribution
    # Sort: None (never contributed) first, then by oldest date
    sorted_coaches = sorted(
        coach_contributions.values(),
        key=lambda x: (x['last_submitted'] is not None, x['last_submitted'] or datetime.min)
    )

    return sorted_coaches[0]['coach'] if sorted_coaches else None


def assign_coach_for_month(newsletter_id: int, coach_user_id: int = None) -> dict[str, Any]:
    """Assign a coach for the newsletter.

    If coach_user_id not provided, uses get_next_coach() for auto-rotation.

    Args:
        newsletter_id: Newsletter to assign coach to
        coach_user_id: Specific coach to assign (optional)

    Returns:
        Dict with success status and coach info
    """
    try:
        # Check for existing rotation
        existing = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if existing:
            return {
                'success': False,
                'error': 'Coach already assigned',
                'coach_id': existing.coach_user_id
            }

        # Get coach
        if coach_user_id:
            coach = User.query.get(coach_user_id)
            if not coach:
                return {'success': False, 'error': 'Coach not found'}
        else:
            coach = get_next_coach()
            if not coach:
                return {'success': False, 'error': 'No coaches available'}

        # Create rotation
        rotation = CoachRotation(
            newsletter_id=newsletter_id,
            coach_user_id=coach.id
        )
        db.session.add(rotation)
        db.session.commit()

        return {
            'success': True,
            'coach_id': coach.id,
            'coach_name': f"{coach.first_name} {coach.last_name}",
            'rotation_id': rotation.id
        }

    except Exception as e:
        logger.error(f"Failed to assign coach: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def send_coach_request(newsletter_id: int) -> dict[str, Any]:
    """Send DM to assigned coach requesting their content.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
    if not rotation:
        return {'success': False, 'error': 'No coach assigned'}

    coach = rotation.coach
    if not coach.slack_user_id:
        return {'success': False, 'error': 'Coach has no Slack user ID'}

    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter and newsletter.period_start else 'this month'

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You're up for Coaches Corner!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hey {coach.first_name}! You've been selected for *Coaches Corner* in the *{month_name}* Monthly Dispatch newsletter."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Write 200-500 words about anything ski-related: a training tip, race recap, technique insight, favorite trail, or whatever's on your mind!"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Write My Section",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "coach_submission_button",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "I Can't This Month",
                            "emoji": True
                        },
                        "action_id": "coach_decline_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        # Get coach's Slack ID from SlackUser if linked
        slack_uid = None
        if coach.slack_user:
            slack_uid = coach.slack_user.slack_uid

        if not slack_uid:
            return {'success': False, 'error': 'Coach has no linked Slack account'}

        response = client.chat_postMessage(
            channel=slack_uid,
            text=f"You're up for Coaches Corner in the {month_name} newsletter!",
            blocks=blocks
        )

        return {'success': True, 'message_ts': response['ts']}

    except Exception as e:
        logger.error(f"Failed to send coach request: {e}")
        return {'success': False, 'error': str(e)}


def handle_coach_submission(newsletter_id: int, content: str) -> dict[str, Any]:
    """Handle coach submission of Coaches Corner content.

    Args:
        newsletter_id: Newsletter ID
        content: The submitted content

    Returns:
        Dict with success status
    """
    try:
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {'success': False, 'error': 'No coach assigned'}

        rotation.content = content
        rotation.status = 'submitted'
        rotation.submitted_at = datetime.utcnow()
        db.session.commit()

        return {'success': True, 'rotation_id': rotation.id}

    except Exception as e:
        logger.error(f"Failed to save coach submission: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def handle_coach_decline(newsletter_id: int) -> dict[str, Any]:
    """Handle coach declining to write this month.

    Marks current rotation as declined and assigns next coach.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status and new coach info
    """
    try:
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {'success': False, 'error': 'No coach assigned'}

        # Mark as declined
        rotation.status = 'declined'
        db.session.commit()

        # Delete rotation so we can assign a new one
        db.session.delete(rotation)
        db.session.commit()

        # Assign next coach
        return assign_coach_for_month(newsletter_id)

    except Exception as e:
        logger.error(f"Failed to handle coach decline: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def send_coach_reminder(newsletter_id: int) -> dict[str, Any]:
    """Send reminder DM to coach if they haven't submitted.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
    if not rotation:
        return {'success': False, 'error': 'No coach assigned'}

    if rotation.status == 'submitted':
        return {'success': True, 'skipped': True, 'reason': 'Already submitted'}

    coach = rotation.coach
    if not coach.slack_user:
        return {'success': False, 'error': 'Coach has no linked Slack account'}

    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter and newsletter.period_start else 'this month'

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hey {coach.first_name}! Just a friendly reminder that we'd love to get your Coaches Corner section for the *{month_name}* Monthly Dispatch. The newsletter goes out on the 15th!"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Write My Section",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "coach_submission_button",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "I Can't This Month",
                            "emoji": True
                        },
                        "action_id": "coach_decline_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=coach.slack_user.slack_uid,
            text=f"Reminder: Coaches Corner section needed for {month_name}",
            blocks=blocks
        )

        return {'success': True, 'message_ts': response['ts']}

    except Exception as e:
        logger.error(f"Failed to send coach reminder: {e}")
        return {'success': False, 'error': str(e)}
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_coach_rotation.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add app/newsletter/coach_rotation.py tests/newsletter/test_coach_rotation.py
git commit -m "feat(newsletter): add Coach Rotation system"
```

---

## Task 13: Create Member Highlight Module

**Files:**
- Create: `app/newsletter/member_highlight.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_member_highlight.py`:

```python
"""Tests for Member Highlight system."""
import pytest
from app.newsletter.member_highlight import (
    nominate_member,
    handle_highlight_submission,
    compose_highlight_with_ai,
    HIGHLIGHT_QUESTIONS,
)


def test_nominate_member_creates_record(app, db_session, newsletter, member):
    """Test that nominating a member creates a highlight record."""
    result = nominate_member(
        newsletter_id=newsletter.id,
        member_user_id=member.id,
        nominated_by='admin@example.com'
    )

    assert result['success'] is True
    assert result['highlight_id'] is not None


def test_handle_highlight_submission_stores_answers(app, db_session, newsletter, member):
    """Test that submitting answers stores them as JSON."""
    # First nominate
    nominate_member(
        newsletter_id=newsletter.id,
        member_user_id=member.id,
        nominated_by='admin@example.com'
    )

    raw_answers = {
        'years_skiing': '10 years',
        'favorite_memory': 'My first Birkie',
        'looking_forward': 'More snow!',
        'classic_or_skate': 'Classic, the OG',
        'wipeout_story': 'Too many to count',
        'anything_else': 'Love this club!'
    }

    result = handle_highlight_submission(
        newsletter_id=newsletter.id,
        raw_answers=raw_answers
    )

    assert result['success'] is True

    from app.newsletter.models import MemberHighlight
    highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter.id).first()
    assert highlight.raw_answers == raw_answers
    assert highlight.status == 'submitted'


def test_highlight_questions_exist():
    """Verify the highlight questions are defined."""
    assert len(HIGHLIGHT_QUESTIONS) >= 5
    assert any('skiing' in q['question'].lower() for q in HIGHLIGHT_QUESTIONS)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_member_highlight.py -v`
Expected: FAIL - module not found

**Step 3: Implement member_highlight.py**

Create `app/newsletter/member_highlight.py`:

```python
"""Member Highlight system for Monthly Dispatch.

Handles:
- Admin nomination of members
- Template-based questions sent via DM
- AI composition of answers into polished prose
"""
import logging
from datetime import datetime
from typing import Any, Optional

from app.models import db, User
from app.newsletter.models import Newsletter, MemberHighlight
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)


# Template questions - mix of fun + meaningful
HIGHLIGHT_QUESTIONS = [
    {
        'id': 'years_skiing',
        'question': 'How long have you been skiing / with the club?',
        'placeholder': 'e.g., "5 years skiing, 2 with TCSC"'
    },
    {
        'id': 'favorite_memory',
        'question': "What's your favorite trail or skiing memory?",
        'placeholder': 'Share a moment that stands out!'
    },
    {
        'id': 'looking_forward',
        'question': 'What are you looking forward to this season?',
        'placeholder': 'A race? More practice? Better technique?'
    },
    {
        'id': 'classic_or_skate',
        'question': 'Classic or skate - and why are you right?',
        'placeholder': 'Defend your choice!'
    },
    {
        'id': 'wipeout_story',
        'question': 'Best wipeout story?',
        'placeholder': "We've all been there..."
    },
    {
        'id': 'anything_else',
        'question': 'Anything else you want to share with the club?',
        'placeholder': 'Optional - tips, shoutouts, random thoughts!'
    },
]


def nominate_member(
    newsletter_id: int,
    member_user_id: int,
    nominated_by: str
) -> dict[str, Any]:
    """Nominate a member for the Member Highlight section.

    Args:
        newsletter_id: Newsletter to add highlight to
        member_user_id: User ID of member to spotlight
        nominated_by: Admin email who made the nomination

    Returns:
        Dict with success status and highlight_id
    """
    try:
        # Check for existing highlight
        existing = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if existing:
            return {
                'success': False,
                'error': 'Highlight already assigned for this newsletter',
                'highlight_id': existing.id
            }

        # Check member exists
        member = User.query.get(member_user_id)
        if not member:
            return {'success': False, 'error': 'Member not found'}

        # Create nomination
        highlight = MemberHighlight(
            newsletter_id=newsletter_id,
            member_user_id=member_user_id,
            nominated_by=nominated_by,
            status='nominated'
        )
        db.session.add(highlight)
        db.session.commit()

        return {
            'success': True,
            'highlight_id': highlight.id,
            'member_name': f"{member.first_name} {member.last_name}"
        }

    except Exception as e:
        logger.error(f"Failed to nominate member: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def send_highlight_request(newsletter_id: int) -> dict[str, Any]:
    """Send DM to nominated member with template questions.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
    if not highlight:
        return {'success': False, 'error': 'No member nominated'}

    member = highlight.member
    if not member.slack_user:
        return {'success': False, 'error': 'Member has no linked Slack account'}

    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter and newsletter.period_start else 'this month'

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You've Been Nominated for Member Highlight!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hey {member.first_name}! You've been nominated for the *Member Highlight* section in the *{month_name}* Monthly Dispatch newsletter!"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "We'd love to feature you! Just answer a few fun questions and we'll take care of the rest."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Answer Questions",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "highlight_submission_button",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Not This Time",
                            "emoji": True
                        },
                        "action_id": "highlight_decline_button",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=member.slack_user.slack_uid,
            text=f"You've been nominated for Member Highlight in the {month_name} newsletter!",
            blocks=blocks
        )

        return {'success': True, 'message_ts': response['ts']}

    except Exception as e:
        logger.error(f"Failed to send highlight request: {e}")
        return {'success': False, 'error': str(e)}


def handle_highlight_submission(
    newsletter_id: int,
    raw_answers: dict
) -> dict[str, Any]:
    """Handle member submission of highlight answers.

    Args:
        newsletter_id: Newsletter ID
        raw_answers: Dict mapping question IDs to answers

    Returns:
        Dict with success status
    """
    try:
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {'success': False, 'error': 'No member nominated'}

        highlight.raw_answers = raw_answers
        highlight.status = 'submitted'
        highlight.submitted_at = datetime.utcnow()
        db.session.commit()

        return {'success': True, 'highlight_id': highlight.id}

    except Exception as e:
        logger.error(f"Failed to save highlight submission: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def mark_highlight_declined(newsletter_id: int) -> dict[str, Any]:
    """Mark that the nominated member declined.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status
    """
    try:
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {'success': False, 'error': 'No member nominated'}

        highlight.status = 'declined'
        db.session.commit()

        return {'success': True}

    except Exception as e:
        logger.error(f"Failed to mark highlight declined: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def compose_highlight_with_ai(newsletter_id: int) -> dict[str, Any]:
    """Use AI to compose the highlight from raw answers.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status and composed content
    """
    highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
    if not highlight:
        return {'success': False, 'error': 'No member nominated'}

    if not highlight.raw_answers:
        return {'success': False, 'error': 'No answers submitted'}

    member = highlight.member
    member_name = f"{member.first_name} {member.last_name}"

    try:
        from app.agent.brain import get_anthropic_client

        client = get_anthropic_client()
        if not client:
            return {'success': False, 'error': 'AI client not available'}

        # Build prompt
        answers_text = "\n".join([
            f"**{q['question']}**\n{highlight.raw_answers.get(q['id'], 'No answer')}\n"
            for q in HIGHLIGHT_QUESTIONS
        ])

        prompt = f"""Compose a warm, engaging Member Highlight section for {member_name} based on their answers below.

Write 200-400 words that:
- Flows naturally as a third-person profile
- Captures their personality from their answers
- Highlights what makes them unique to the club
- Uses a friendly, conversational tone
- Does NOT use excessive exclamation points or overly enthusiastic language

Their answers:
{answers_text}

Write the Member Highlight section:"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Using Sonnet for cost efficiency
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        composed_content = response.content[0].text

        # Save to database
        highlight.ai_composed_content = composed_content
        db.session.commit()

        return {
            'success': True,
            'content': composed_content,
            'highlight_id': highlight.id
        }

    except Exception as e:
        logger.error(f"Failed to compose highlight with AI: {e}")
        return {'success': False, 'error': str(e)}


def get_previous_highlight_dates(member_user_id: int) -> list[datetime]:
    """Get dates when a member was previously highlighted.

    Args:
        member_user_id: User ID to check

    Returns:
        List of datetime objects when member was featured
    """
    highlights = MemberHighlight.query.filter_by(
        member_user_id=member_user_id,
        status='submitted'
    ).all()

    return [h.submitted_at for h in highlights if h.submitted_at]
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_member_highlight.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add app/newsletter/member_highlight.py tests/newsletter/test_member_highlight.py
git commit -m "feat(newsletter): add Member Highlight system with AI composition"
```

---

## Task 14: Create Photos Module

**Files:**
- Create: `app/newsletter/photos.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_photos.py`:

```python
"""Tests for Photo Gallery system."""
import pytest
from datetime import datetime
from app.newsletter.photos import (
    collect_month_photos,
    select_photos,
    get_selected_photos,
)


def test_select_photos_marks_selected(app, db_session, newsletter, photo_submissions):
    """Test that selecting photos marks them as selected."""
    photo_ids = [photo_submissions[0].id, photo_submissions[2].id]

    result = select_photos(newsletter.id, photo_ids)

    assert result['success'] is True
    assert result['selected_count'] == 2

    selected = get_selected_photos(newsletter.id)
    assert len(selected) == 2


def test_select_photos_deselects_previous(app, db_session, newsletter, photo_submissions):
    """Test that new selection deselects previous."""
    # First selection
    select_photos(newsletter.id, [photo_submissions[0].id])

    # Second selection (different photos)
    select_photos(newsletter.id, [photo_submissions[1].id, photo_submissions[2].id])

    selected = get_selected_photos(newsletter.id)
    assert len(selected) == 2
    assert photo_submissions[0].id not in [p.id for p in selected]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_photos.py -v`
Expected: FAIL - module not found

**Step 3: Implement photos.py**

Create `app/newsletter/photos.py`:

```python
"""Photo Gallery system for Monthly Dispatch.

Handles:
- Collecting photos from #photos channel
- Admin curation of selected photos
- Publishing photo gallery as thread reply
"""
import logging
from datetime import datetime
from typing import Any, Optional

from app.models import db
from app.newsletter.models import Newsletter, PhotoSubmission
from app.slack.client import get_slack_client, get_channel_id_by_name

logger = logging.getLogger(__name__)


def collect_month_photos(
    newsletter_id: int,
    channel: str = 'photos',
    month_start: datetime = None,
    month_end: datetime = None
) -> dict[str, Any]:
    """Collect photos from channel for the month.

    Args:
        newsletter_id: Newsletter to associate photos with
        channel: Channel name to scan
        month_start: Start of collection period
        month_end: End of collection period

    Returns:
        Dict with success status and count of photos collected
    """
    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    try:
        channel_id = get_channel_id_by_name(channel)
        if not channel_id:
            return {'success': False, 'error': f'Channel #{channel} not found'}

        # If no dates provided, get from newsletter
        newsletter = Newsletter.query.get(newsletter_id)
        if newsletter:
            month_start = month_start or newsletter.period_start
            month_end = month_end or newsletter.period_end

        # Convert to Slack timestamps
        oldest = str(month_start.timestamp()) if month_start else None
        latest = str(month_end.timestamp()) if month_end else None

        # Fetch files from channel
        files_response = client.files_list(
            channel=channel_id,
            ts_from=oldest,
            ts_to=latest,
            types='images'
        )

        collected = 0
        for file_info in files_response.get('files', []):
            # Check if already collected
            existing = PhotoSubmission.query.filter_by(
                newsletter_id=newsletter_id,
                slack_file_id=file_info['id']
            ).first()

            if existing:
                continue

            # Get reaction count
            reaction_count = sum(
                r.get('count', 0) for r in file_info.get('reactions', [])
            )

            # Create submission
            photo = PhotoSubmission(
                newsletter_id=newsletter_id,
                slack_file_id=file_info['id'],
                slack_permalink=file_info.get('permalink'),
                submitted_by_user_id=file_info.get('user'),
                caption=file_info.get('title') or file_info.get('name'),
                reaction_count=reaction_count,
                posted_at=datetime.fromtimestamp(file_info.get('timestamp', 0)) if file_info.get('timestamp') else None
            )
            db.session.add(photo)
            collected += 1

        db.session.commit()

        return {
            'success': True,
            'collected': collected,
            'total_files': len(files_response.get('files', []))
        }

    except Exception as e:
        logger.error(f"Failed to collect photos: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def get_photo_submissions(newsletter_id: int) -> list[PhotoSubmission]:
    """Get all collected photos for a newsletter, sorted by popularity.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of PhotoSubmission objects sorted by reaction_count desc
    """
    return PhotoSubmission.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(PhotoSubmission.reaction_count.desc()).all()


def select_photos(newsletter_id: int, photo_ids: list[int]) -> dict[str, Any]:
    """Mark selected photos for inclusion in newsletter.

    Args:
        newsletter_id: Newsletter ID
        photo_ids: List of photo IDs to select

    Returns:
        Dict with success status
    """
    try:
        # Deselect all first
        PhotoSubmission.query.filter_by(newsletter_id=newsletter_id).update(
            {'selected': False}
        )

        # Select the specified ones
        if photo_ids:
            PhotoSubmission.query.filter(
                PhotoSubmission.id.in_(photo_ids),
                PhotoSubmission.newsletter_id == newsletter_id
            ).update({'selected': True}, synchronize_session=False)

        db.session.commit()
        return {'success': True, 'selected_count': len(photo_ids)}

    except Exception as e:
        logger.error(f"Failed to select photos: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def get_selected_photos(newsletter_id: int) -> list[PhotoSubmission]:
    """Get selected photos for rendering in newsletter.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of selected PhotoSubmission objects
    """
    return PhotoSubmission.query.filter_by(
        newsletter_id=newsletter_id,
        selected=True
    ).order_by(PhotoSubmission.reaction_count.desc()).all()


def post_photo_gallery_thread(
    newsletter_id: int,
    parent_message_ts: str,
    channel_id: str
) -> dict[str, Any]:
    """Post photo gallery as thread reply to published newsletter.

    Args:
        newsletter_id: Newsletter ID
        parent_message_ts: Timestamp of parent message to reply to
        channel_id: Channel ID where parent message is

    Returns:
        Dict with success status and thread_ts
    """
    client = get_slack_client()
    if not client:
        return {'success': False, 'error': 'Slack client not available'}

    photos = get_selected_photos(newsletter_id)
    if not photos:
        return {'success': True, 'skipped': True, 'reason': 'No photos selected'}

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        month_name = newsletter.period_start.strftime('%B %Y') if newsletter and newsletter.period_start else 'This Month'

        # Build blocks for photo gallery
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Photo Gallery - {month_name}",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"{len(photos)} photos from #photos this month"
                    }
                ]
            },
            {"type": "divider"}
        ]

        # Add each photo
        for photo in photos:
            if photo.slack_permalink:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{photo.caption or 'Photo'}*"
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": photo.slack_permalink,
                        "alt_text": photo.caption or "Photo"
                    }
                })
            else:
                # Fallback if no permalink
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{photo.caption or 'Photo'}* (image unavailable)"
                    }
                })

        # Post as thread reply
        response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=parent_message_ts,
            text=f"Photo Gallery - {month_name}",
            blocks=blocks
        )

        return {
            'success': True,
            'thread_ts': response['ts'],
            'photos_included': len(photos)
        }

    except Exception as e:
        logger.error(f"Failed to post photo gallery: {e}")
        return {'success': False, 'error': str(e)}
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_photos.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add app/newsletter/photos.py tests/newsletter/test_photos.py
git commit -m "feat(newsletter): add Photo Gallery system"
```

---

## Task 15: Update Config with Monthly Structure

**Files:**
- Modify: `config/newsletter.yaml`

**Step 1: Backup existing config**

Run: `cp config/newsletter.yaml config/newsletter.yaml.bak`

**Step 2: Update config with monthly structure**

Replace content with:

```yaml
# TCSC Monthly Dispatch Newsletter Configuration
# See docs/WEEKLY_DISPATCH.md for full documentation

newsletter:
  enabled: true
  dry_run: false  # Set false for production

dispatch:
  frequency: monthly
  publish_day: 15
  timezone: America/Chicago

sections:
  - id: opener
    name: Opener
    ai_generated: false
    owner: newsletter_host
    required: true

  - id: qotm
    name: Question of the Month
    ai_generated: false
    required: true

  - id: coaches_corner
    name: Coaches Corner
    ai_generated: false
    owner: rotating_coach
    required: true

  - id: member_heads_up
    name: TCSC Member Heads Up
    ai_generated: true
    required: true

  - id: upcoming_events
    name: Upcoming Races & Events
    ai_generated: true
    sources:
      - skinnyski_races
      - club_calendar
    required: true

  - id: member_highlight
    name: Member Highlight in Residence
    ai_generated: true  # AI composes from template answers
    template_based: true
    required: false  # Optional if no nomination

  - id: month_in_review
    name: Month in Review
    ai_generated: true
    includes_slack_recap: true
    required: true

  - id: from_the_board
    name: From the Board
    ai_generated: true
    source_channels:
      - pattern: "leadership-*"
    required: true

  - id: closer
    name: Closer
    ai_generated: false
    owner: newsletter_host
    required: true

  - id: photo_gallery
    name: Photo Gallery
    ai_generated: false
    source_channel: photos
    publish_as: thread_reply
    required: false

schedule:
  host_dm: 1  # Day of month (after manual assignment)
  coach_assignment: 1
  qotm_send: 1
  highlight_request: 5
  host_reminder: 10
  coach_reminder: 10
  ai_draft_generation: 12
  living_post_creation: 12
  final_reminders: 13
  review_buttons: 14
  publish_deadline: 15

channels:
  living_post: tcsc-logging
  publish: announcements-tcsc
  admin_review: newsletter-admin
  photos: photos
  qotm_post: chat

private_channels:
  - pattern: "leadership-*"

news_sources:
  skinnyski:
    enabled: true
    news_url: "https://www.skinnyski.com/"
    max_articles: 5

  loppet:
    enabled: true
    url: "https://www.loppet.org/"
    max_articles: 3

  three_rivers:
    enabled: true
    url: "https://www.threeriversparks.org/"
    max_articles: 3

trail_conditions:
  enabled: true
  locations:
    - "Theodore Wirth"
    - "Elm Creek"
    - "Hyland Lake"
    - "Lebanon Hills"

generation:
  model: "claude-opus-4-5-20251101"
  max_tokens: 64000
  temperature: 1.0
  extended_thinking:
    enabled: true
    budget_tokens: 32000

review:
  approval_timeout_hours: 4
  max_feedback_iterations: 3
```

**Step 3: Verify config loads**

Run: `python -c "import yaml; print(yaml.safe_load(open('config/newsletter.yaml')))"`
Expected: Config dictionary printed without errors

**Step 4: Commit**

```bash
git add config/newsletter.yaml
git commit -m "feat(newsletter): update config for monthly dispatch structure"
```

---

## Task 16: Add Admin Trigger Endpoints

**Files:**
- Modify: `app/routes/admin_scheduled_tasks.py`

**Step 1: Add newsletter trigger endpoints**

Add these routes to the admin scheduled tasks blueprint:

```python
@admin_tasks_bp.route('/newsletter/trigger/qotm', methods=['POST'])
@admin_required
def trigger_qotm():
    """Trigger posting QOTM to #chat."""
    from app.newsletter.qotm import post_qotm_to_channel
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    db.session.commit()

    question = request.json.get('question') if request.is_json else None
    if not question and newsletter.qotm_question:
        question = newsletter.qotm_question

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    result = post_qotm_to_channel(newsletter.id, question)
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/coach', methods=['POST'])
@admin_required
def trigger_coach():
    """Trigger coach assignment and DM."""
    from app.newsletter.coach_rotation import assign_coach_for_month, send_coach_request
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    db.session.commit()

    # Assign coach if not already assigned
    assign_result = assign_coach_for_month(newsletter.id)
    if not assign_result['success'] and 'already assigned' not in assign_result.get('error', ''):
        return jsonify(assign_result)

    # Send request
    result = send_coach_request(newsletter.id)
    result['assignment'] = assign_result
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/host', methods=['POST'])
@admin_required
def trigger_host():
    """Trigger host DM (host must be assigned first via admin UI)."""
    from app.newsletter.host import send_host_request
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    db.session.commit()

    result = send_host_request(newsletter.id)
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/highlight', methods=['POST'])
@admin_required
def trigger_highlight():
    """Trigger highlight request (member must be nominated first)."""
    from app.newsletter.member_highlight import send_highlight_request
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    result = send_highlight_request(newsletter.id)
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/ai-drafts', methods=['POST'])
@admin_required
def trigger_ai_drafts():
    """Trigger AI draft generation for all AI-assisted sections."""
    from app.newsletter.service import generate_ai_drafts
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    db.session.commit()

    result = generate_ai_drafts(newsletter.id)
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/living-post', methods=['POST'])
@admin_required
def trigger_living_post():
    """Trigger creation/update of living post."""
    from app.newsletter.slack_actions import create_or_update_living_post
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()
    db.session.commit()

    result = create_or_update_living_post(newsletter.id)
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/trigger/reminders', methods=['POST'])
@admin_required
def trigger_reminders():
    """Trigger all reminders (host, coach, highlight)."""
    from app.newsletter.host import send_host_reminder
    from app.newsletter.coach_rotation import send_coach_reminder
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()

    results = {
        'host': send_host_reminder(newsletter.id),
        'coach': send_coach_reminder(newsletter.id),
    }
    return jsonify(results)


@admin_tasks_bp.route('/newsletter/trigger/photo-thread', methods=['POST'])
@admin_required
def trigger_photo_thread():
    """Trigger photo gallery thread reply."""
    from app.newsletter.photos import post_photo_gallery_thread
    from app.newsletter.models import Newsletter

    newsletter = Newsletter.get_or_create_current_month()

    if not newsletter.publish_message_ts or not newsletter.publish_channel_id:
        return jsonify({'error': 'Newsletter not published yet'}), 400

    result = post_photo_gallery_thread(
        newsletter.id,
        newsletter.publish_message_ts,
        newsletter.publish_channel_id
    )
    return jsonify(result)


@admin_tasks_bp.route('/newsletter/create', methods=['POST'])
@admin_required
def create_newsletter():
    """Create newsletter for a specific month."""
    from app.newsletter.models import Newsletter

    month_year = request.json.get('month_year') if request.is_json else None

    newsletter = Newsletter.get_or_create_current_month(month_year)
    db.session.commit()

    return jsonify({
        'success': True,
        'newsletter_id': newsletter.id,
        'month_year': newsletter.month_year
    })
```

**Step 2: Verify routes load**

Run: `flask routes | grep newsletter`
Expected: New routes listed

**Step 3: Commit**

```bash
git add app/routes/admin_scheduled_tasks.py
git commit -m "feat(newsletter): add admin trigger endpoints for monthly dispatch"
```

---

## Task 17: Update Scheduler with Monthly Orchestrator

**Files:**
- Modify: `app/scheduler.py`

**Step 1: Add monthly orchestrator job function**

Add after `run_newsletter_sunday_job`:

```python
def run_newsletter_monthly_orchestrator_job(app: Flask):
    """Execute the monthly newsletter orchestrator job.

    Single daily job that checks what day of the month it is and
    triggers the appropriate newsletter actions.

    Runs at 8am daily.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    with app.app_context():
        from app.newsletter.service import run_monthly_orchestrator

        central_tz = ZoneInfo('America/Chicago')
        now = datetime.now(central_tz)
        today = now.day

        app.logger.info("=" * 60)
        app.logger.info(f"Newsletter Monthly Orchestrator - Day {today}")
        app.logger.info("=" * 60)

        try:
            result = run_monthly_orchestrator(today)

            app.logger.info(f"Orchestrator complete: {result.get('actions', [])}")

            if result.get('errors'):
                for error in result['errors'][:5]:
                    app.logger.warning(f"Orchestrator error: {error}")

        except Exception as e:
            app.logger.error(f"Newsletter orchestrator failed: {e}", exc_info=True)
```

**Step 2: Replace newsletter jobs with orchestrator**

In `init_scheduler`, comment out the existing newsletter jobs and add:

```python
    # ========================================================================
    # Newsletter Jobs (Monthly Dispatch)
    # ========================================================================

    # Monthly orchestrator: 8:00 AM daily - checks day of month
    scheduler.add_job(
        func=run_newsletter_monthly_orchestrator_job,
        args=[app],
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone='America/Chicago'
        ),
        id='newsletter_monthly_orchestrator',
        name='Newsletter Monthly Orchestrator',
        replace_existing=True,
        misfire_grace_time=3600
    )
```

**Step 3: Add orchestrator to trigger function**

Update `trigger_skipper_job_now` to include the orchestrator:

```python
    job_map = {
        # ... existing entries ...
        'newsletter_monthly_orchestrator': run_newsletter_monthly_orchestrator_job,
    }
```

**Step 4: Commit**

```bash
git add app/scheduler.py
git commit -m "feat(newsletter): add monthly orchestrator to scheduler"
```

---

## Task 18: Implement Monthly Orchestrator in Service

**Files:**
- Modify: `app/newsletter/service.py`

**Step 1: Add run_monthly_orchestrator function**

Add at the end of service.py:

```python
def run_monthly_orchestrator(day_of_month: int) -> dict[str, Any]:
    """Run the monthly newsletter orchestrator for a given day.

    Checks what actions need to happen based on the day of the month
    and executes them.

    Args:
        day_of_month: Current day (1-31)

    Returns:
        Dict with actions taken and any errors
    """
    result = {
        'day': day_of_month,
        'actions': [],
        'errors': []
    }

    try:
        # Get or create newsletter for current month
        newsletter = Newsletter.get_or_create_current_month()
        db.session.commit()

        result['newsletter_id'] = newsletter.id
        result['month_year'] = newsletter.month_year

        if day_of_month == 1:
            # Day 1: QOTM, coach assignment, host DM (if assigned)
            result['actions'].append('day_1_start')

            # Post QOTM to #chat
            if newsletter.qotm_question:
                from app.newsletter.qotm import post_qotm_to_channel
                qotm_result = post_qotm_to_channel(newsletter.id, newsletter.qotm_question)
                result['qotm'] = qotm_result
                if qotm_result.get('success'):
                    result['actions'].append('qotm_posted')

            # Assign and DM coach
            from app.newsletter.coach_rotation import assign_coach_for_month, send_coach_request
            assign_result = assign_coach_for_month(newsletter.id)
            result['coach_assignment'] = assign_result
            if assign_result.get('success'):
                result['actions'].append('coach_assigned')
                send_result = send_coach_request(newsletter.id)
                result['coach_dm'] = send_result
                if send_result.get('success'):
                    result['actions'].append('coach_dm_sent')

            # DM host if assigned
            if newsletter.host:
                from app.newsletter.host import send_host_request
                host_result = send_host_request(newsletter.id)
                result['host_dm'] = host_result
                if host_result.get('success'):
                    result['actions'].append('host_dm_sent')

        elif day_of_month == 5:
            # Day 5: Send highlight request if nominated
            if newsletter.has_highlight_nomination:
                from app.newsletter.member_highlight import send_highlight_request
                highlight_result = send_highlight_request(newsletter.id)
                result['highlight_dm'] = highlight_result
                if highlight_result.get('success'):
                    result['actions'].append('highlight_dm_sent')

        elif day_of_month == 10:
            # Day 10: Reminders
            from app.newsletter.host import send_host_reminder
            from app.newsletter.coach_rotation import send_coach_reminder

            host_result = send_host_reminder(newsletter.id)
            result['host_reminder'] = host_result
            if host_result.get('success') and not host_result.get('skipped'):
                result['actions'].append('host_reminder_sent')

            coach_result = send_coach_reminder(newsletter.id)
            result['coach_reminder'] = coach_result
            if coach_result.get('success') and not coach_result.get('skipped'):
                result['actions'].append('coach_reminder_sent')

        elif day_of_month == 12:
            # Day 12: Generate AI drafts and create living post
            ai_result = generate_ai_drafts(newsletter.id)
            result['ai_drafts'] = ai_result
            if ai_result.get('success'):
                result['actions'].append('ai_drafts_generated')

            from app.newsletter.slack_actions import create_or_update_living_post
            post_result = create_or_update_living_post(newsletter.id)
            result['living_post'] = post_result
            if post_result.get('success'):
                result['actions'].append('living_post_created')

        elif day_of_month == 13:
            # Day 13: Final reminders
            # Re-use day 10 logic
            from app.newsletter.host import send_host_reminder
            from app.newsletter.coach_rotation import send_coach_reminder

            result['final_reminders'] = {
                'host': send_host_reminder(newsletter.id),
                'coach': send_coach_reminder(newsletter.id)
            }
            result['actions'].append('final_reminders_sent')

        elif day_of_month == 14:
            # Day 14: Add review buttons
            from app.newsletter.slack_actions import add_review_buttons
            buttons_result = add_review_buttons(newsletter)
            result['review_buttons'] = buttons_result
            if buttons_result:
                result['actions'].append('review_buttons_added')

        # Day 15: Manual publish (no automated action)

        if not result['actions']:
            result['actions'].append('no_action_needed')

    except Exception as e:
        logger.error(f"Monthly orchestrator failed: {e}", exc_info=True)
        result['errors'].append(str(e))

    return result


def generate_ai_drafts(newsletter_id: int) -> dict[str, Any]:
    """Generate AI drafts for all AI-assisted sections.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        Dict with success status and drafted sections
    """
    result = {
        'success': False,
        'sections_drafted': [],
        'errors': []
    }

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            result['errors'].append('Newsletter not found')
            return result

        # Compose member highlight if answers submitted
        if newsletter.highlight and newsletter.highlight.raw_answers:
            from app.newsletter.member_highlight import compose_highlight_with_ai
            highlight_result = compose_highlight_with_ai(newsletter_id)
            if highlight_result.get('success'):
                result['sections_drafted'].append('member_highlight')
            else:
                result['errors'].append(f"Highlight: {highlight_result.get('error')}")

        # Collect content for AI generation
        context = collect_newsletter_content(newsletter)

        # Generate other AI sections via existing generator
        gen_result = generate_newsletter_version(newsletter, context, trigger='ai_drafts')

        if gen_result.success:
            result['sections_drafted'].extend([
                'member_heads_up', 'upcoming_events',
                'month_in_review', 'from_the_board'
            ])
            result['success'] = True
        else:
            result['errors'].append(gen_result.error or 'Generation failed')

    except Exception as e:
        logger.error(f"AI draft generation failed: {e}", exc_info=True)
        result['errors'].append(str(e))

    return result
```

**Step 2: Add import for generate_ai_drafts**

The function uses existing imports, no changes needed.

**Step 3: Commit**

```bash
git add app/newsletter/service.py
git commit -m "feat(newsletter): implement monthly orchestrator in service"
```

---

## Summary of Remaining Tasks

The plan continues with additional tasks for:

- **Task 19:** Create Section Editor module for per-section Slack modal editing
- **Task 20:** Create Events module for upcoming races & events
- **Task 21:** Update slack_actions.py for thread-based living post
- **Task 22:** Add Slack Bolt handlers for all modals and buttons
- **Task 23:** Update generator.py for section-specific AI drafts
- **Task 24:** Create test fixtures for newsletter testing
- **Task 25:** Add admin UI for host assignment and highlight nomination
- **Task 26:** Integration tests for full monthly workflow

These tasks follow the same pattern: write failing test, implement, run tests, commit.

---

## Verification Checklist

After completing all tasks:

- [ ] All new models have migrations applied
- [ ] QOTM can be posted to #chat and responses collected
- [ ] Newsletter Host can be assigned and DM sent
- [ ] Coach rotation selects oldest contributor
- [ ] Member Highlight collects answers and AI composes
- [ ] Photos can be collected from #photos and selected
- [ ] Living post creates thread replies for each section
- [ ] All admin trigger endpoints work
- [ ] Monthly orchestrator runs appropriate actions per day
- [ ] pytest passes for all newsletter tests
