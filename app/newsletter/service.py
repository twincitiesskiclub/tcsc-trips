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


def run_monthly_orchestrator(day_of_month: int) -> dict[str, Any]:
    """Run the monthly orchestrator for the Monthly Dispatch newsletter.

    Executes day-of-month-specific actions for newsletter production.
    Each action is wrapped in try/except to ensure one failure doesn't
    stop others from running.

    Monthly Schedule:
    - Day 1: Send host DM (if assigned), assign coach + DM, post QOTM
    - Day 5: Send member highlight request (if nominated)
    - Day 10: Coach reminder, host reminder
    - Day 12: Generate AI drafts, create/update living post
    - Day 13: Final reminders
    - Day 14: Add review buttons
    - Day 15+: Manual publish (admin approval required)

    Args:
        day_of_month: Day of the month (1-31)

    Returns:
        Dict with keys:
        - success: bool (True if all actions completed without critical errors)
        - newsletter_id: int (ID of the newsletter being processed)
        - day: int (day of month processed)
        - actions: list of dicts describing actions taken
        - errors: list of error strings
    """
    result = {
        'success': False,
        'newsletter_id': None,
        'day': day_of_month,
        'actions': [],
        'errors': []
    }

    # Get or create newsletter for current month
    try:
        newsletter = Newsletter.get_or_create_current_month()
        db.session.commit()
        result['newsletter_id'] = newsletter.id
        result['actions'].append({
            'action': 'get_newsletter',
            'success': True,
            'detail': f'Newsletter {newsletter.id} for {newsletter.month_year}'
        })
    except Exception as e:
        logger.error(f"Failed to get/create newsletter: {e}", exc_info=True)
        result['errors'].append(f"Failed to get/create newsletter: {e}")
        return result

    # ========================================================================
    # Day 1: Host DM, Coach assignment, QOTM post
    # ========================================================================
    if day_of_month == 1:
        # Send host request DM (if host has been assigned manually)
        try:
            if newsletter.host:
                from app.newsletter.host import send_host_request
                host_result = send_host_request(newsletter.id)
                if host_result.get('success'):
                    result['actions'].append({
                        'action': 'send_host_request',
                        'success': True,
                        'detail': f"channel_id={host_result.get('channel_id')}"
                    })
                elif host_result.get('error'):
                    result['actions'].append({
                        'action': 'send_host_request',
                        'success': False,
                        'detail': host_result.get('error')
                    })
                    result['errors'].append(f"Host request failed: {host_result.get('error')}")
            else:
                result['actions'].append({
                    'action': 'send_host_request',
                    'success': True,
                    'detail': 'Skipped - no host assigned yet'
                })
        except Exception as e:
            logger.error(f"Host request failed: {e}", exc_info=True)
            result['errors'].append(f"Host request error: {e}")

        # Assign coach (automated rotation)
        try:
            from app.newsletter.coach_rotation import (
                assign_coach_for_month,
                send_coach_request,
            )
            assign_result = assign_coach_for_month(newsletter.id)
            if assign_result.get('success'):
                result['actions'].append({
                    'action': 'assign_coach',
                    'success': True,
                    'detail': f"coach={assign_result.get('coach_name')}"
                })
                # Send coach request DM
                dm_result = send_coach_request(newsletter.id)
                if dm_result.get('success'):
                    result['actions'].append({
                        'action': 'send_coach_request',
                        'success': True,
                        'detail': f"channel_id={dm_result.get('channel_id')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_coach_request',
                        'success': False,
                        'detail': dm_result.get('error')
                    })
                    result['errors'].append(f"Coach request DM failed: {dm_result.get('error')}")
            else:
                result['actions'].append({
                    'action': 'assign_coach',
                    'success': False,
                    'detail': assign_result.get('error')
                })
                result['errors'].append(f"Coach assignment failed: {assign_result.get('error')}")
        except Exception as e:
            logger.error(f"Coach assignment failed: {e}", exc_info=True)
            result['errors'].append(f"Coach assignment error: {e}")

        # Post QOTM to #chat
        try:
            if newsletter.qotm_question:
                from app.newsletter.qotm import post_qotm_to_channel
                qotm_result = post_qotm_to_channel(
                    newsletter.id,
                    newsletter.qotm_question,
                    channel='chat'
                )
                if qotm_result.get('success'):
                    result['actions'].append({
                        'action': 'post_qotm',
                        'success': True,
                        'detail': f"message_ts={qotm_result.get('message_ts')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'post_qotm',
                        'success': False,
                        'detail': qotm_result.get('error')
                    })
                    result['errors'].append(f"QOTM post failed: {qotm_result.get('error')}")
            else:
                result['actions'].append({
                    'action': 'post_qotm',
                    'success': True,
                    'detail': 'Skipped - no QOTM question set'
                })
        except Exception as e:
            logger.error(f"QOTM post failed: {e}", exc_info=True)
            result['errors'].append(f"QOTM post error: {e}")

    # ========================================================================
    # Day 5: Member highlight request (if nominated)
    # ========================================================================
    elif day_of_month == 5:
        try:
            if newsletter.has_highlight_nomination:
                from app.newsletter.member_highlight import send_highlight_request
                highlight_result = send_highlight_request(newsletter.id)
                if highlight_result.get('success'):
                    result['actions'].append({
                        'action': 'send_highlight_request',
                        'success': True,
                        'detail': f"channel_id={highlight_result.get('channel_id')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_highlight_request',
                        'success': False,
                        'detail': highlight_result.get('error')
                    })
                    result['errors'].append(f"Highlight request failed: {highlight_result.get('error')}")
            else:
                result['actions'].append({
                    'action': 'send_highlight_request',
                    'success': True,
                    'detail': 'Skipped - no member highlight nomination'
                })
        except Exception as e:
            logger.error(f"Highlight request failed: {e}", exc_info=True)
            result['errors'].append(f"Highlight request error: {e}")

    # ========================================================================
    # Day 10: Reminders for coach and host
    # ========================================================================
    elif day_of_month == 10:
        # Send coach reminder if not submitted
        try:
            from app.newsletter.coach_rotation import send_coach_reminder
            coach_reminder_result = send_coach_reminder(newsletter.id)
            if coach_reminder_result.get('success'):
                if coach_reminder_result.get('skipped'):
                    result['actions'].append({
                        'action': 'send_coach_reminder',
                        'success': True,
                        'detail': f"Skipped - {coach_reminder_result.get('reason')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_coach_reminder',
                        'success': True,
                        'detail': f"channel_id={coach_reminder_result.get('channel_id')}"
                    })
            else:
                result['actions'].append({
                    'action': 'send_coach_reminder',
                    'success': False,
                    'detail': coach_reminder_result.get('error')
                })
                result['errors'].append(f"Coach reminder failed: {coach_reminder_result.get('error')}")
        except Exception as e:
            logger.error(f"Coach reminder failed: {e}", exc_info=True)
            result['errors'].append(f"Coach reminder error: {e}")

        # Send host reminder if not submitted
        try:
            from app.newsletter.host import send_host_reminder
            host_reminder_result = send_host_reminder(newsletter.id)
            if host_reminder_result.get('success'):
                if host_reminder_result.get('skipped'):
                    result['actions'].append({
                        'action': 'send_host_reminder',
                        'success': True,
                        'detail': f"Skipped - {host_reminder_result.get('reason')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_host_reminder',
                        'success': True,
                        'detail': f"channel_id={host_reminder_result.get('channel_id')}"
                    })
            else:
                result['actions'].append({
                    'action': 'send_host_reminder',
                    'success': False,
                    'detail': host_reminder_result.get('error')
                })
                result['errors'].append(f"Host reminder failed: {host_reminder_result.get('error')}")
        except Exception as e:
            logger.error(f"Host reminder failed: {e}", exc_info=True)
            result['errors'].append(f"Host reminder error: {e}")

    # ========================================================================
    # Day 12: Generate AI drafts and create living post with sections
    # ========================================================================
    elif day_of_month == 12:
        # Generate AI drafts for AI-assisted sections
        result['actions'].append({
            'action': 'start_day_12_ai_drafts',
            'success': True,
            'detail': 'Starting AI draft generation'
        })

        try:
            ai_result = generate_ai_drafts(newsletter.id)
            result['actions'].append({
                'action': 'generate_ai_drafts',
                'success': ai_result.get('success', False),
                'detail': f"Generated {len(ai_result.get('sections', []))} sections"
            })
            if ai_result.get('errors'):
                result['errors'].extend([
                    f"AI draft error: {e.get('section_type') if isinstance(e, dict) else str(e)}: {e.get('error') if isinstance(e, dict) else ''}"
                    for e in ai_result['errors']
                ])
        except Exception as e:
            logger.error(f"AI draft generation failed: {e}", exc_info=True)
            result['errors'].append(f"AI draft generation error: {e}")
            result['actions'].append({
                'action': 'generate_ai_drafts',
                'success': False,
                'detail': str(e)
            })

        # Create/update living post with sections
        try:
            from app.newsletter.slack_actions import create_living_post_with_sections, is_dry_run

            if is_dry_run():
                result['actions'].append({
                    'action': 'create_living_post_with_sections',
                    'success': True,
                    'detail': '[DRY RUN] Would create living post with sections'
                })
            else:
                post_ref = create_living_post_with_sections(newsletter)
                result['actions'].append({
                    'action': 'create_living_post_with_sections',
                    'success': True,
                    'detail': f"message_ts={post_ref.message_ts if post_ref else 'None'}"
                })
        except Exception as e:
            logger.error(f"Living post creation failed: {e}", exc_info=True)
            result['errors'].append(f"Living post error: {e}")
            result['actions'].append({
                'action': 'create_living_post_with_sections',
                'success': False,
                'detail': str(e)
            })

    # ========================================================================
    # Day 13: Final reminders
    # ========================================================================
    elif day_of_month == 13:
        # Coach final reminder
        try:
            from app.newsletter.coach_rotation import send_coach_reminder
            coach_reminder_result = send_coach_reminder(newsletter.id)
            if coach_reminder_result.get('success'):
                if coach_reminder_result.get('skipped'):
                    result['actions'].append({
                        'action': 'send_coach_final_reminder',
                        'success': True,
                        'detail': f"Skipped - {coach_reminder_result.get('reason')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_coach_final_reminder',
                        'success': True,
                        'detail': f"channel_id={coach_reminder_result.get('channel_id')}"
                    })
            else:
                result['actions'].append({
                    'action': 'send_coach_final_reminder',
                    'success': False,
                    'detail': coach_reminder_result.get('error')
                })
                result['errors'].append(f"Final coach reminder failed: {coach_reminder_result.get('error')}")
        except Exception as e:
            logger.error(f"Final coach reminder failed: {e}", exc_info=True)
            result['errors'].append(f"Final coach reminder error: {e}")

        # Host final reminder
        try:
            from app.newsletter.host import send_host_reminder
            host_reminder_result = send_host_reminder(newsletter.id)
            if host_reminder_result.get('success'):
                if host_reminder_result.get('skipped'):
                    result['actions'].append({
                        'action': 'send_host_final_reminder',
                        'success': True,
                        'detail': f"Skipped - {host_reminder_result.get('reason')}"
                    })
                else:
                    result['actions'].append({
                        'action': 'send_host_final_reminder',
                        'success': True,
                        'detail': f"channel_id={host_reminder_result.get('channel_id')}"
                    })
            else:
                result['actions'].append({
                    'action': 'send_host_final_reminder',
                    'success': False,
                    'detail': host_reminder_result.get('error')
                })
                result['errors'].append(f"Final host reminder failed: {host_reminder_result.get('error')}")
        except Exception as e:
            logger.error(f"Final host reminder failed: {e}", exc_info=True)
            result['errors'].append(f"Final host reminder error: {e}")

    # ========================================================================
    # Day 14: Add review/edit buttons
    # ========================================================================
    elif day_of_month == 14:
        try:
            from app.newsletter.slack_actions import add_review_buttons, is_dry_run

            if is_dry_run():
                result['actions'].append({
                    'action': 'add_review_buttons',
                    'success': True,
                    'detail': '[DRY RUN] Would add review buttons'
                })
            else:
                success = add_review_buttons(newsletter)
                if success:
                    result['actions'].append({
                        'action': 'add_review_buttons',
                        'success': True,
                        'detail': 'Review/edit buttons added to living post'
                    })
                else:
                    result['actions'].append({
                        'action': 'add_review_buttons',
                        'success': False,
                        'detail': 'Failed to add review buttons'
                    })
                    result['errors'].append("Failed to add review buttons to living post")
        except Exception as e:
            logger.error(f"Add review buttons failed: {e}", exc_info=True)
            result['errors'].append(f"Add review buttons error: {e}")

    # ========================================================================
    # Other days: No automated actions
    # ========================================================================
    else:
        result['actions'].append({
            'action': 'no_action',
            'success': True,
            'detail': f'No automated actions scheduled for day {day_of_month}'
        })

    # Determine overall success (no critical errors)
    result['success'] = len(result['errors']) == 0

    return result


def _build_monthly_dispatch_content(newsletter: Newsletter) -> dict:
    """Build content dict for Monthly Dispatch living post.

    Aggregates content from all newsletter sections into a structured
    dict that can be rendered by the Block Kit templates.

    Args:
        newsletter: Newsletter instance

    Returns:
        Dict with section content for template rendering
    """
    from app.newsletter.qotm import get_selected_qotm_for_newsletter

    content = {
        'month_year': newsletter.month_year,
        'status': newsletter.status,
        'sections': {}
    }

    # Opener from host
    if newsletter.host and newsletter.host.opener_content:
        content['sections']['opener'] = {
            'content': newsletter.host.opener_content,
            'author': newsletter.host.display_name,
        }

    # Coaches Corner
    if newsletter.coach_rotation and newsletter.coach_rotation.content:
        coach = newsletter.coach_rotation.coach
        content['sections']['coaches_corner'] = {
            'content': newsletter.coach_rotation.content,
            'author': coach.full_name if coach else 'Anonymous Coach',
        }

    # Member Highlight
    highlight = newsletter.highlight if hasattr(newsletter, 'highlight') else None
    if highlight:
        # Prefer final edited content, then AI composed, then raw
        highlight_content = (
            highlight.content or
            highlight.ai_composed_content or
            str(highlight.raw_answers)
        )
        member = highlight.member
        content['sections']['member_highlight'] = {
            'content': highlight_content,
            'member_name': member.full_name if member else 'Featured Member',
        }

    # QOTM and responses
    if newsletter.qotm_question:
        selected_responses = get_selected_qotm_for_newsletter(newsletter.id)
        content['sections']['qotm'] = {
            'question': newsletter.qotm_question,
            'responses': [
                {'user_name': r.user_name, 'response': r.response}
                for r in selected_responses
            ]
        }

    # Closer from host
    if newsletter.host and newsletter.host.closer_content:
        content['sections']['closer'] = {
            'content': newsletter.host.closer_content,
            'author': newsletter.host.display_name,
        }

    return content


def generate_ai_drafts(newsletter_id: int) -> dict:
    """Generate AI drafts for all AI-assisted sections.

    Called on day 12 of the month to generate initial drafts
    for editor review.

    Collects context data:
    1. Slack messages from the month using collect_all_messages()
    2. Leadership channel messages (placeholder for now)
    3. Events (placeholder for now)
    4. Member highlight answers if available

    Args:
        newsletter_id: Newsletter ID

    Returns:
        dict with 'success', 'sections', 'errors' keys
    """
    logger.info(f"Generating AI drafts for newsletter {newsletter_id}")

    result = {
        'success': False,
        'sections': [],
        'errors': []
    }

    # Get the newsletter
    try:
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            result['errors'].append(f"Newsletter {newsletter_id} not found")
            return result
    except Exception as e:
        logger.error(f"Error fetching newsletter {newsletter_id}: {e}")
        result['errors'].append(f"Error fetching newsletter: {e}")
        return result

    # Build context data for AI generation
    context_data = {
        'slack_messages': [],
        'leadership_messages': [],  # Placeholder for now
        'events': [],  # Placeholder for now
        'member_highlight_answers': None
    }

    # Collect Slack messages from the month
    if newsletter.period_start and newsletter.period_end:
        try:
            from app.newsletter.collector import collect_all_messages

            messages = collect_all_messages(since=newsletter.period_start)
            context_data['slack_messages'] = messages
            logger.info(f"Collected {len(messages)} Slack messages for AI draft generation")
        except Exception as e:
            logger.error(f"Failed to collect Slack messages: {e}")
            result['errors'].append(f"Failed to collect Slack messages: {e}")
            # Continue with empty messages - AI can still generate with limited context
    else:
        logger.warning(f"Newsletter {newsletter_id} has no period_start/period_end set")

    # Get member highlight answers if available
    highlight = getattr(newsletter, 'highlight', None)
    if highlight and getattr(highlight, 'raw_answers', None):
        try:
            # raw_answers is stored as JSON dict
            context_data['member_highlight_answers'] = highlight.raw_answers
            logger.info("Loaded member highlight answers for AI draft generation")
        except Exception as e:
            logger.warning(f"Failed to load member highlight answers: {e}")

    # Generate all AI sections
    try:
        from app.newsletter.monthly_generator import generate_all_ai_sections

        gen_result = generate_all_ai_sections(newsletter, context_data)

        result['success'] = gen_result.get('success', False)
        result['sections'] = gen_result.get('sections', [])

        if gen_result.get('errors'):
            result['errors'].extend(gen_result['errors'])

        successful_count = sum(1 for s in result['sections'] if s.get('success'))
        total_count = len(result['sections'])
        logger.info(f"AI draft generation complete: {successful_count}/{total_count} sections generated")

    except Exception as e:
        logger.error(f"AI draft generation failed: {e}", exc_info=True)
        result['errors'].append(f"AI draft generation failed: {e}")

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
