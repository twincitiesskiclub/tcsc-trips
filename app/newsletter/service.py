"""
Service functions for newsletter scheduled jobs.

These are the entry points called by the scheduler for daily and Sunday jobs.
They orchestrate the collection, generation, and posting of newsletter content.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import yaml

from app.models import db
from app.newsletter.models import (
    Newsletter,
    NewsletterVersion,
    NewsletterSubmission,
    NewsletterDigest,
    NewsletterNewsItem,
)
from app.newsletter.interfaces import (
    NewsletterStatus,
    NewsletterContext,
    GenerationResult,
    SlackMessage,
    NewsItem,
    MemberSubmission,
    TrailConditionSummary,
    MessageVisibility,
    SubmissionStatus,
    SubmissionType,
    NewsSource,
    VersionTrigger,
)

logger = logging.getLogger(__name__)


def _load_config() -> dict:
    """Load newsletter configuration from YAML file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config',
        'newsletter.yaml'
    )
    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load newsletter config: {e}")
        return {}


def get_week_boundaries(reference_date: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Calculate newsletter week boundaries.

    Week runs Monday 00:00 UTC to Sunday 23:59:59 UTC.

    Args:
        reference_date: Date to calculate week for (defaults to now)

    Returns:
        Tuple of (week_start, week_end) datetimes in UTC.
    """
    if reference_date is None:
        reference_date = datetime.utcnow()

    # Find Monday of the week containing reference_date
    days_since_monday = reference_date.weekday()
    week_start = (reference_date - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # Sunday 23:59:59
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return week_start, week_end


def get_pending_submissions(newsletter_id: Optional[int] = None) -> list[MemberSubmission]:
    """Get pending member submissions.

    Args:
        newsletter_id: Optional newsletter ID to filter by

    Returns:
        List of MemberSubmission dataclass objects
    """
    db_submissions = NewsletterSubmission.get_pending(newsletter_id)

    submissions = []
    for s in db_submissions:
        try:
            sub_type = SubmissionType(s.submission_type)
        except ValueError:
            sub_type = SubmissionType.CONTENT

        submissions.append(MemberSubmission(
            id=s.id,
            slack_user_id=s.slack_user_id,
            display_name=s.display_name or 'Anonymous',
            submission_type=sub_type,
            content=s.content,
            permission_to_name=s.permission_to_name or False,
            submitted_at=s.submitted_at,
        ))

    return submissions


def get_trail_conditions() -> list[TrailConditionSummary]:
    """Get trail conditions from the existing integration.

    Returns:
        List of TrailConditionSummary objects for monitored locations
    """
    config = _load_config()
    trail_config = config.get('newsletter', {}).get('trail_conditions', {})

    if not trail_config.get('enabled', True):
        logger.info("Trail conditions disabled in config")
        return []

    locations = trail_config.get('locations', [])
    if not locations:
        return []

    conditions = []

    try:
        from app.integrations.trail_conditions import get_trail_conditions as fetch_trail_conditions

        for location_name in locations:
            try:
                trail = fetch_trail_conditions(location_name)
                if trail:
                    conditions.append(TrailConditionSummary(
                        location=trail.location,
                        trails_open=trail.trails_open,
                        ski_quality=trail.ski_quality,
                        groomed=trail.groomed,
                        groomed_for=trail.groomed_for,
                        report_date=trail.report_date,
                        notes=trail.notes,
                    ))
            except Exception as e:
                logger.warning(f"Failed to get conditions for {location_name}: {e}")
                continue

    except ImportError:
        logger.warning("Trail conditions module not available")

    return conditions


def get_prior_newsletter() -> Optional[str]:
    """Get the most recently published newsletter content for continuity.

    Returns:
        Content of prior newsletter or None if not found
    """
    prior = Newsletter.query.filter(
        Newsletter.status == NewsletterStatus.PUBLISHED.value
    ).order_by(Newsletter.published_at.desc()).first()

    if prior and prior.current_content:
        return prior.current_content

    return None


def collect_newsletter_content(newsletter: Newsletter) -> NewsletterContext:
    """Collect all content needed for newsletter generation.

    Orchestrates:
    1. Slack message collection
    2. Pending member submissions
    3. External news scraping
    4. Trail conditions
    5. Prior newsletter for continuity

    Args:
        newsletter: Newsletter to collect content for

    Returns:
        NewsletterContext with all collected data
    """
    logger.info("=" * 60)
    logger.info(f"NEWSLETTER SERVICE: Collecting content for newsletter {newsletter.id}")
    logger.info(f"  Week: {newsletter.week_start.strftime('%Y-%m-%d')} to {newsletter.week_end.strftime('%Y-%m-%d')}")
    logger.info("=" * 60)

    context = NewsletterContext(
        week_start=newsletter.week_start,
        week_end=newsletter.week_end,
    )

    # 1. Collect Slack messages
    try:
        from app.newsletter.collector import collect_all_messages

        messages = collect_all_messages(since=newsletter.week_start)
        context.slack_messages = messages
        logger.info(f"  Collected {len(messages)} Slack messages")

        # Persist to digest table
        for msg in messages:
            existing = NewsletterDigest.query.filter_by(
                newsletter_id=newsletter.id,
                channel_id=msg.channel_id,
                message_ts=msg.message_ts
            ).first()

            if not existing:
                digest = NewsletterDigest(
                    newsletter_id=newsletter.id,
                    channel_id=msg.channel_id,
                    channel_name=msg.channel_name,
                    message_ts=msg.message_ts,
                    user_id=msg.user_id,
                    user_name=msg.user_name,
                    text=msg.text,
                    permalink=msg.permalink,
                    reaction_count=msg.reaction_count,
                    reply_count=msg.reply_count,
                    visibility=msg.visibility.value,
                    posted_at=msg.posted_at,
                )
                db.session.add(digest)

        db.session.commit()

    except Exception as e:
        logger.error(f"  Failed to collect Slack messages: {e}")

    # 2. Get pending submissions
    try:
        context.submissions = get_pending_submissions(newsletter.id)
        logger.info(f"  Found {len(context.submissions)} pending submissions")
    except Exception as e:
        logger.error(f"  Failed to get submissions: {e}")

    # 3. Scrape external news
    try:
        from app.newsletter.news_scraper import scrape_all_news

        news_items = scrape_all_news(since=newsletter.week_start)
        context.news_items = news_items
        logger.info(f"  Scraped {len(news_items)} news items")

        # Persist to database
        for item in news_items:
            existing = NewsletterNewsItem.query.filter_by(
                newsletter_id=newsletter.id,
                url=item.url
            ).first()

            if not existing:
                db_item = NewsletterNewsItem(
                    newsletter_id=newsletter.id,
                    source=item.source.value,
                    title=item.title,
                    summary=item.summary,
                    url=item.url,
                    image_url=item.image_url,
                    published_at=item.published_at,
                )
                db.session.add(db_item)

        db.session.commit()

    except Exception as e:
        logger.error(f"  Failed to scrape news: {e}")

    # 4. Get trail conditions
    try:
        context.trail_conditions = get_trail_conditions()
        logger.info(f"  Got {len(context.trail_conditions)} trail condition reports")
    except Exception as e:
        logger.error(f"  Failed to get trail conditions: {e}")

    # 5. Get prior newsletter for continuity
    try:
        context.prior_newsletter_content = get_prior_newsletter()
        if context.prior_newsletter_content:
            logger.info("  Loaded prior newsletter for continuity")
    except Exception as e:
        logger.error(f"  Failed to get prior newsletter: {e}")

    # Update collection timestamp
    newsletter.last_collected_at = datetime.utcnow()
    db.session.commit()

    logger.info("=" * 60)
    logger.info("NEWSLETTER SERVICE: Content collection complete")
    logger.info("=" * 60)

    return context


def generate_newsletter_version(
    newsletter: Newsletter,
    context: NewsletterContext,
    trigger: str = 'scheduled',
    use_mcp: bool = False
) -> GenerationResult:
    """Generate a new newsletter version using Claude.

    Args:
        newsletter: Newsletter to generate for
        context: Collected content context
        trigger: What triggered this generation
        use_mcp: If True, use MCP agentic approach where Claude calls tools.
                 If False (default), use direct generation with pre-collected data.

    Returns:
        GenerationResult with success status and content
    """
    is_final = (trigger == 'sunday_finalize')

    if use_mcp:
        # Use MCP agentic approach - Claude orchestrates tool calls
        from app.newsletter.mcp_server import run_newsletter_agent
        result = run_newsletter_agent(newsletter, is_final=is_final)
    else:
        # Use direct generation with pre-collected context
        from app.newsletter.generator import generate_newsletter, save_newsletter_version
        result = generate_newsletter(context, is_final=is_final)

        if result.success:
            version = save_newsletter_version(newsletter, result, trigger=trigger)
            result.version_number = version.version_number

    # Mark any included submissions as included (for both modes)
    if result.success and context.submissions:
        for sub in context.submissions:
            db_sub = NewsletterSubmission.query.get(sub.id)
            if db_sub:
                db_sub.status = SubmissionStatus.INCLUDED.value
                db_sub.included_in_version = result.version_number
                db_sub.processed_at = datetime.utcnow()

        db.session.commit()

    return result


def run_daily_update() -> dict[str, Any]:
    """Run the daily newsletter update job (8am).

    This job:
    1. Ensures a newsletter exists for the current week
    2. Collects new Slack messages from monitored channels
    3. Scrapes external news sources for new content
    4. Regenerates the newsletter with Claude Opus 4.5
    5. Updates the living post in Slack

    Returns:
        Dict with job results including version number and any errors.
    """
    logger.info("Starting newsletter daily update")

    result = {
        'success': False,
        'newsletter_id': None,
        'version_number': 0,
        'messages_collected': 0,
        'news_items_scraped': 0,
        'errors': []
    }

    try:
        week_start, week_end = get_week_boundaries()

        # Get or create newsletter for this week
        newsletter = Newsletter.get_or_create_current_week(week_start, week_end)
        db.session.commit()

        result['newsletter_id'] = newsletter.id

        # Skip if already finalized
        if newsletter.is_finalized:
            logger.info(f"Newsletter {newsletter.id} already finalized, skipping daily update")
            result['success'] = True
            result['skipped'] = True
            result['reason'] = 'Newsletter already finalized'
            return result

        # Collect all content
        context = collect_newsletter_content(newsletter)
        result['messages_collected'] = len(context.slack_messages)
        result['news_items_scraped'] = len(context.news_items)

        # Generate newsletter
        gen_result = generate_newsletter_version(newsletter, context, trigger='scheduled')
        result['version_number'] = gen_result.version_number

        if not gen_result.success:
            result['errors'].append(gen_result.error or 'Generation failed')
            return result

        # Update living post in Slack
        try:
            from app.newsletter.slack_actions import (
                create_living_post,
                update_living_post,
                add_version_to_thread,
                is_dry_run,
            )

            if is_dry_run():
                logger.info("DRY RUN: Would update living post")
                result['living_post_updated'] = False
                result['dry_run'] = True
            else:
                # Get the latest version
                version = newsletter.versions.order_by(
                    NewsletterVersion.version_number.desc()
                ).first()

                # Use structured content if available, otherwise fall back to raw content
                content_for_slack = gen_result.structured_content or gen_result.content

                if not newsletter.slack_main_message_ts:
                    # Create new living post
                    post_ref = create_living_post(newsletter, content_for_slack)
                    logger.info(f"Created living post: {post_ref.message_ts if post_ref else 'None'}")
                else:
                    # Update existing post
                    post_ref = update_living_post(newsletter, content_for_slack)
                    logger.info(f"Updated living post: {post_ref.message_ts if post_ref else 'None'}")

                # Add version to thread
                if version:
                    add_version_to_thread(newsletter, version)
                    logger.info(f"Added version {version.version_number} to thread")

                result['living_post_updated'] = True

        except Exception as e:
            logger.error(f"Failed to update living post: {e}")
            result['errors'].append(f"Living post update failed: {e}")
            # Don't fail the whole job for Slack errors

        logger.info(f"Daily update complete for newsletter {newsletter.id}")
        logger.info(f"  Version: {result['version_number']}")
        logger.info(f"  Messages: {result['messages_collected']}")
        logger.info(f"  News items: {result['news_items_scraped']}")

        result['success'] = True

    except Exception as e:
        logger.error(f"Newsletter daily update failed: {e}", exc_info=True)
        result['errors'].append(str(e))

    return result


def run_sunday_finalize() -> dict[str, Any]:
    """Run the Sunday newsletter finalization job (6pm).

    This job:
    1. Marks the newsletter as ready_for_review
    2. Performs final regeneration with review-focused prompt
    3. Adds approve/edit buttons to the living post
    4. Notifies admins that newsletter is ready for review

    Returns:
        Dict with job results including final status.
    """
    logger.info("Starting newsletter Sunday finalization")

    result = {
        'success': False,
        'newsletter_id': None,
        'version_number': 0,
        'previous_status': None,
        'new_status': None,
        'errors': []
    }

    try:
        week_start, week_end = get_week_boundaries()

        # Get newsletter for this week
        newsletter = Newsletter.query.filter(
            Newsletter.week_start == week_start,
            Newsletter.week_end == week_end
        ).first()

        if not newsletter:
            logger.warning("No newsletter found for current week, cannot finalize")
            result['errors'].append('No newsletter found for current week')
            return result

        result['newsletter_id'] = newsletter.id
        result['previous_status'] = newsletter.status

        # Skip if already past building phase
        if newsletter.is_finalized:
            logger.info(f"Newsletter {newsletter.id} already finalized ({newsletter.status})")
            result['success'] = True
            result['skipped'] = True
            result['reason'] = f'Newsletter already in status: {newsletter.status}'
            return result

        # Collect fresh content and generate final version
        context = collect_newsletter_content(newsletter)
        gen_result = generate_newsletter_version(newsletter, context, trigger='sunday_finalize')
        result['version_number'] = gen_result.version_number

        if not gen_result.success:
            result['errors'].append(gen_result.error or 'Final generation failed')

        # Update status to ready_for_review
        newsletter.status = NewsletterStatus.READY_FOR_REVIEW.value
        db.session.commit()

        result['new_status'] = newsletter.status

        # Update living post and add review buttons
        try:
            from app.newsletter.slack_actions import (
                create_living_post,
                update_living_post,
                add_version_to_thread,
                add_review_buttons,
                is_dry_run,
            )

            if is_dry_run():
                logger.info("DRY RUN: Would update living post and add review buttons")
                result['living_post_updated'] = False
                result['review_buttons_added'] = False
                result['dry_run'] = True
            else:
                # Get the latest version
                version = newsletter.versions.order_by(
                    NewsletterVersion.version_number.desc()
                ).first()

                # Use structured content if available, otherwise fall back to raw content
                content_for_slack = gen_result.structured_content or gen_result.content

                # Create or update living post
                if not newsletter.slack_main_message_ts:
                    post_ref = create_living_post(newsletter, content_for_slack)
                    logger.info(f"Created living post: {post_ref.message_ts if post_ref else 'None'}")
                else:
                    post_ref = update_living_post(newsletter, content_for_slack)
                    logger.info(f"Updated living post: {post_ref.message_ts if post_ref else 'None'}")

                # Add version to thread
                if version:
                    add_version_to_thread(newsletter, version)
                    logger.info(f"Added version {version.version_number} to thread")

                result['living_post_updated'] = True

                # Add review buttons for approval workflow
                buttons_added = add_review_buttons(newsletter)
                result['review_buttons_added'] = buttons_added
                if buttons_added:
                    logger.info("Added review buttons to living post")
                else:
                    logger.warning("Failed to add review buttons")

        except Exception as e:
            logger.error(f"Failed to update living post or add buttons: {e}")
            result['errors'].append(f"Slack operations failed: {e}")
            # Don't fail the whole job for Slack errors

        logger.info(f"Newsletter {newsletter.id} finalized: {result['previous_status']} -> {result['new_status']}")

        result['success'] = True

    except Exception as e:
        logger.error(f"Newsletter Sunday finalization failed: {e}", exc_info=True)
        result['errors'].append(str(e))

    return result


def regenerate_newsletter(
    newsletter_id: int,
    feedback: Optional[str] = None
) -> dict[str, Any]:
    """Manually trigger newsletter regeneration.

    Args:
        newsletter_id: ID of newsletter to regenerate
        feedback: Optional admin feedback to incorporate

    Returns:
        Dict with regeneration results
    """
    result = {
        'success': False,
        'newsletter_id': newsletter_id,
        'version_number': 0,
        'error': None,
    }

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            result['error'] = 'Newsletter not found'
            return result

        # Store feedback if provided
        if feedback:
            newsletter.admin_feedback = feedback
            db.session.commit()

        # Collect content
        context = collect_newsletter_content(newsletter)

        # Add feedback to context
        if feedback:
            context.admin_feedback = feedback

        # Generate
        trigger = 'feedback' if feedback else 'manual'
        gen_result = generate_newsletter_version(newsletter, context, trigger=trigger)

        result['version_number'] = gen_result.version_number
        result['success'] = gen_result.success

        if not gen_result.success:
            result['error'] = gen_result.error

        # Clear feedback after successful regeneration
        if gen_result.success and feedback:
            newsletter.admin_feedback = None
            db.session.commit()

    except Exception as e:
        logger.error(f"Newsletter regeneration failed: {e}", exc_info=True)
        result['error'] = str(e)

    return result


def get_newsletter_status(newsletter_id: Optional[int] = None) -> dict[str, Any]:
    """Get status information about a newsletter or current week.

    Args:
        newsletter_id: Specific newsletter ID, or None for current week

    Returns:
        Dict with status information
    """
    if newsletter_id:
        newsletter = Newsletter.query.get(newsletter_id)
    else:
        week_start, week_end = get_week_boundaries()
        newsletter = Newsletter.query.filter(
            Newsletter.week_start == week_start,
            Newsletter.week_end == week_end
        ).first()

    if not newsletter:
        return {
            'exists': False,
            'week_start': None,
            'week_end': None,
        }

    # Count related items
    message_count = NewsletterDigest.query.filter_by(newsletter_id=newsletter.id).count()
    news_count = NewsletterNewsItem.query.filter_by(newsletter_id=newsletter.id).count()
    submission_count = NewsletterSubmission.query.filter_by(newsletter_id=newsletter.id).count()
    version_count = newsletter.versions.count()

    return {
        'exists': True,
        'id': newsletter.id,
        'week_start': newsletter.week_start.isoformat(),
        'week_end': newsletter.week_end.isoformat(),
        'status': newsletter.status,
        'current_version': newsletter.current_version,
        'is_finalized': newsletter.is_finalized,
        'is_published': newsletter.is_published,
        'last_collected_at': newsletter.last_collected_at.isoformat() if newsletter.last_collected_at else None,
        'published_at': newsletter.published_at.isoformat() if newsletter.published_at else None,
        'message_count': message_count,
        'news_count': news_count,
        'submission_count': submission_count,
        'version_count': version_count,
        'has_living_post': bool(newsletter.slack_main_message_ts),
    }
