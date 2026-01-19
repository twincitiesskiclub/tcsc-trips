"""
Database models for the Weekly Dispatch newsletter system.

Models:
- Newsletter: Main newsletter record for each week
- NewsletterVersion: Version history for each regeneration
- NewsletterSubmission: Member-submitted content via /dispatch
- NewsletterDigest: Collected Slack messages
- NewsletterNewsItem: Scraped news from external sources
- NewsletterPrompt: Database-editable prompts (override file defaults)
"""

from datetime import datetime
from typing import Optional

from app.models import db
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


class Newsletter(db.Model):
    """Main newsletter record for each week.

    Tracks the current state of a weekly newsletter, including
    the living post reference in Slack and version counter.
    """
    __tablename__ = 'newsletters'

    id = db.Column(db.Integer, primary_key=True)

    # Week boundaries
    week_start = db.Column(db.DateTime, nullable=False)
    week_end = db.Column(db.DateTime, nullable=False)

    # Monthly dispatch fields (nullable for migration)
    month_year = db.Column(db.String(7))  # e.g., "2026-01"
    period_start = db.Column(db.DateTime)  # Generic, works for weekly or monthly
    period_end = db.Column(db.DateTime)
    publish_target_date = db.Column(db.DateTime)  # 15th of month
    qotm_question = db.Column(db.Text)  # Question of the Month

    # Current state
    status = db.Column(
        db.String(50),
        nullable=False,
        default=NewsletterStatus.BUILDING.value
    )
    current_content = db.Column(db.Text)
    current_version = db.Column(db.Integer, default=0)

    # Slack references for living post
    slack_channel_id = db.Column(db.String(50))
    slack_main_message_ts = db.Column(db.String(50))  # Main living post

    # Publish references (after approval)
    publish_channel_id = db.Column(db.String(50))
    publish_message_ts = db.Column(db.String(50))
    published_at = db.Column(db.DateTime)
    published_by_slack_uid = db.Column(db.String(50))

    # Collection tracking
    last_collected_at = db.Column(db.DateTime)

    # Admin feedback for regeneration
    admin_feedback = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    versions = db.relationship(
        'NewsletterVersion',
        backref='newsletter',
        lazy='dynamic',
        order_by='NewsletterVersion.version_number.desc()'
    )
    submissions = db.relationship(
        'NewsletterSubmission',
        backref='newsletter',
        lazy='dynamic'
    )
    digests = db.relationship(
        'NewsletterDigest',
        backref='newsletter',
        lazy='dynamic'
    )
    news_items = db.relationship(
        'NewsletterNewsItem',
        backref='newsletter',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Newsletter {self.id} week={self.week_start.strftime("%Y-%m-%d")}>'

    @classmethod
    def get_current_week(cls) -> Optional['Newsletter']:
        """Get newsletter for the current week."""
        now = datetime.utcnow()
        return cls.query.filter(
            cls.week_start <= now,
            cls.week_end >= now
        ).first()

    @classmethod
    def get_or_create_current_week(cls, week_start: datetime, week_end: datetime) -> 'Newsletter':
        """Get existing newsletter for week or create new one."""
        newsletter = cls.query.filter(
            cls.week_start == week_start,
            cls.week_end == week_end
        ).first()

        if not newsletter:
            newsletter = cls(
                week_start=week_start,
                week_end=week_end,
                status=NewsletterStatus.BUILDING.value
            )
            db.session.add(newsletter)
            db.session.flush()  # Get ID without committing

        return newsletter

    @property
    def is_finalized(self) -> bool:
        """Check if newsletter is past building phase."""
        return self.status != NewsletterStatus.BUILDING.value

    @property
    def is_published(self) -> bool:
        """Check if newsletter has been published."""
        return self.status == NewsletterStatus.PUBLISHED.value

    @classmethod
    def get_or_create_current_month(cls, month_year: str = None) -> 'Newsletter':
        """Get or create newsletter for the specified or current month.

        Args:
            month_year: Month in YYYY-MM format, or None for current month

        Returns:
            Newsletter instance for the month
        """
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
            # Set week_start/week_end for compatibility (required fields)
            # Monthly newsletters use period_start/period_end for date range logic
            week_start=period_start,
            week_end=period_end,
            status=NewsletterStatus.BUILDING.value
        )
        db.session.add(newsletter)
        db.session.flush()

        return newsletter

    @property
    def has_highlight_nomination(self) -> bool:
        """Check if newsletter has a member highlight nomination.

        Note: Requires 'highlight' relationship to be added by MemberHighlight model.
        Returns False until that relationship exists.
        """
        return hasattr(self, 'highlight') and self.highlight is not None


class NewsletterVersion(db.Model):
    """Version history for each newsletter regeneration.

    Each daily update creates a new version, preserving the full
    content and metadata for review and rollback.
    """
    __tablename__ = 'newsletter_versions'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Version info
    version_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)

    # What triggered this version
    trigger_type = db.Column(
        db.String(50),
        nullable=False,
        default=VersionTrigger.SCHEDULED.value
    )

    # Slack thread reference (version posted as reply)
    slack_thread_ts = db.Column(db.String(50))

    # Generation metadata
    model_used = db.Column(db.String(100))
    tokens_used = db.Column(db.Integer)
    generation_time_ms = db.Column(db.Integer)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<NewsletterVersion {self.newsletter_id}:v{self.version_number}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'version_number',
            name='uq_newsletter_version'
        ),
    )


class NewsletterSubmission(db.Model):
    """Member-submitted content via /dispatch command or App Home.

    Submissions are collected and included in the next newsletter
    generation if approved.
    """
    __tablename__ = 'newsletter_submissions'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=True  # May be submitted before newsletter exists
    )

    # Submitter info
    slack_user_id = db.Column(db.String(50), nullable=False)
    display_name = db.Column(db.String(255))

    # Submission content
    submission_type = db.Column(
        db.String(50),
        nullable=False,
        default=SubmissionType.CONTENT.value
    )
    content = db.Column(db.Text, nullable=False)

    # Attribution preference
    permission_to_name = db.Column(db.Boolean, default=False)

    # Processing status
    status = db.Column(
        db.String(50),
        nullable=False,
        default=SubmissionStatus.PENDING.value
    )
    included_in_version = db.Column(db.Integer)  # Version number if included

    # Timestamps
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<NewsletterSubmission {self.id} type={self.submission_type}>'

    @classmethod
    def get_pending(cls, newsletter_id: Optional[int] = None) -> list['NewsletterSubmission']:
        """Get all pending submissions, optionally for a specific newsletter."""
        query = cls.query.filter_by(status=SubmissionStatus.PENDING.value)
        if newsletter_id:
            query = query.filter(
                (cls.newsletter_id == newsletter_id) | (cls.newsletter_id.is_(None))
            )
        return query.order_by(cls.submitted_at).all()


class NewsletterDigest(db.Model):
    """Collected Slack messages for newsletter content.

    Stores messages from monitored channels with engagement metrics
    for prioritization during generation.
    """
    __tablename__ = 'newsletter_digests'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Message source
    channel_id = db.Column(db.String(50), nullable=False)
    channel_name = db.Column(db.String(255))
    message_ts = db.Column(db.String(50), nullable=False)

    # Message content
    user_id = db.Column(db.String(50))
    user_name = db.Column(db.String(255))
    text = db.Column(db.Text, nullable=False)

    # Slack permalink (null for private channels)
    permalink = db.Column(db.String(500))

    # Engagement metrics for prioritization
    reaction_count = db.Column(db.Integer, default=0)
    reply_count = db.Column(db.Integer, default=0)

    # Privacy level
    visibility = db.Column(
        db.String(50),
        nullable=False,
        default=MessageVisibility.PUBLIC.value
    )

    # When the message was originally posted
    posted_at = db.Column(db.DateTime)

    # When we collected it
    collected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<NewsletterDigest {self.id} channel={self.channel_name}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'channel_id', 'message_ts',
            name='uq_newsletter_digest_message'
        ),
    )

    @property
    def engagement_score(self) -> int:
        """Calculate engagement score for prioritization."""
        return self.reaction_count + (self.reply_count * 2)


class NewsletterNewsItem(db.Model):
    """Scraped external news from ski-related sources.

    Stores articles from SkinnySkI, Loppet Foundation, and
    Three Rivers Parks for inclusion in the newsletter.
    """
    __tablename__ = 'newsletter_news_items'

    id = db.Column(db.Integer, primary_key=True)
    newsletter_id = db.Column(
        db.Integer,
        db.ForeignKey('newsletters.id'),
        nullable=False
    )

    # Source identification
    source = db.Column(db.String(50), nullable=False)  # skinnyski, loppet, three_rivers

    # Article content
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text)
    url = db.Column(db.String(1000), nullable=False)
    image_url = db.Column(db.String(1000))

    # When the article was published (if available)
    published_at = db.Column(db.DateTime)

    # When we scraped it
    scraped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<NewsletterNewsItem {self.id} source={self.source}>'

    __table_args__ = (
        db.UniqueConstraint(
            'newsletter_id', 'url',
            name='uq_newsletter_news_url'
        ),
    )


class NewsletterPrompt(db.Model):
    """Database-editable prompts for newsletter generation.

    Allows admins to modify generation prompts without code changes.
    Falls back to file-based prompts if no active database entry exists.
    """
    __tablename__ = 'newsletter_prompts'

    id = db.Column(db.Integer, primary_key=True)

    # Prompt identification
    name = db.Column(db.String(50), nullable=False)  # 'main', 'quiet', 'final'
    description = db.Column(db.Text)

    # Prompt content
    content = db.Column(db.Text, nullable=False)

    # Version tracking
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)

    # Audit trail
    created_by_email = db.Column(db.String(255))
    updated_by_email = db.Column(db.String(255))

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f'<NewsletterPrompt {self.name} v{self.version}>'

    @classmethod
    def get_active(cls, name: str) -> Optional['NewsletterPrompt']:
        """Get the active prompt by name."""
        return cls.query.filter_by(name=name, is_active=True).first()

    __table_args__ = (
        db.UniqueConstraint(
            'name', 'version',
            name='uq_newsletter_prompt_version'
        ),
    )


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