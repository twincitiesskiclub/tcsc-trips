"""
TCSC Weekly Dispatch Newsletter System.

A living newsletter that progressively builds throughout the week,
generating content from Slack activity, member submissions, and local ski news.

Modules:
- models: Database models for newsletters, versions, submissions, digests
- interfaces: Enums and dataclasses for type-safe communication
- collector: Slack message collection from configured channels
- news_scraper: SkinnySkI, Loppet, Three Rivers scrapers
- generator: Claude Opus 4.5 newsletter generation (direct approach)
- mcp_server: MCP tools for agentic newsletter generation
- slack_actions: Living post management and publishing
- modals: Slack modal builders for /dispatch command
- service: Scheduler entry points and orchestration
"""

from app.newsletter.interfaces import (
    # Enums
    NewsletterStatus,
    SubmissionStatus,
    SubmissionType,
    VersionTrigger,
    MessageVisibility,
    NewsSource,
    # Dataclasses
    SlackMessage,
    NewsItem,
    MemberSubmission,
    TrailConditionSummary,
    NewsletterContext,
    GenerationResult,
    SlackPostReference,
    PublishResult,
)

from app.newsletter.models import (
    Newsletter,
    NewsletterVersion,
    NewsletterSubmission,
    NewsletterDigest,
    NewsletterNewsItem,
    NewsletterPrompt,
)

from app.newsletter.slack_actions import (
    # Configuration
    get_living_post_channel,
    get_publish_channel,
    is_dry_run,
    reload_config,
    # Living Post Management
    create_living_post,
    update_living_post,
    add_version_to_thread,
    add_review_buttons,
    remove_review_buttons,
    # Section-based Living Post
    create_living_post_with_sections,
    build_section_blocks_with_edit_buttons,
    # Publishing
    publish_to_announcement_channel,
    # Feedback
    post_feedback_request,
    post_approval_notice,
    # Utilities
    get_newsletter_permalink,
)

from app.newsletter.news_scraper import (
    # Main scraper functions
    scrape_skinnyski_news,
    scrape_loppet_news,
    scrape_three_rivers_news,
    scrape_all_news,
    # Utilities
    clear_cache as clear_news_cache,
    get_scraper_status,
)

from app.newsletter.service import (
    run_daily_update,
    run_sunday_finalize,
    regenerate_newsletter,
    get_newsletter_status,
    get_week_boundaries,
    collect_newsletter_content,
    generate_newsletter_version,
)

from app.newsletter.generator import (
    generate_newsletter,
    generate_fallback_newsletter,
    get_newsletter_prompt,
    build_generation_context,
)

from app.newsletter.modals import (
    build_dispatch_submission_modal,
    build_dispatch_confirmation_blocks,
)

# Section editor
from app.newsletter.section_editor import (
    build_section_edit_modal,
    get_section_for_editing,
    save_section_edit,
    get_all_sections_for_newsletter,
    initialize_sections_for_newsletter,
    get_section_display_name,
)

# Monthly generator
from app.newsletter.monthly_generator import (
    generate_section_draft,
    generate_all_ai_sections,
    build_section_context,
    AI_DRAFTED_SECTIONS,
)

from app.newsletter.mcp_server import (
    # Tool definitions
    NEWSLETTER_TOOLS,
    # Individual tool handlers
    tool_collect_slack_messages,
    tool_get_member_submissions,
    tool_scrape_ski_news,
    tool_get_trail_conditions,
    tool_get_prior_newsletter,
    tool_save_newsletter_version,
    tool_update_living_post,
    # Tool dispatcher
    execute_tool,
    # Agentic generation
    run_newsletter_agent,
    generate_newsletter_with_mcp,
)

__all__ = [
    # Enums
    'NewsletterStatus',
    'SubmissionStatus',
    'SubmissionType',
    'VersionTrigger',
    'MessageVisibility',
    'NewsSource',
    # Dataclasses
    'SlackMessage',
    'NewsItem',
    'MemberSubmission',
    'TrailConditionSummary',
    'NewsletterContext',
    'GenerationResult',
    'SlackPostReference',
    'PublishResult',
    # Models
    'Newsletter',
    'NewsletterVersion',
    'NewsletterSubmission',
    'NewsletterDigest',
    'NewsletterNewsItem',
    'NewsletterPrompt',
    # Slack Actions - Configuration
    'get_living_post_channel',
    'get_publish_channel',
    'is_dry_run',
    'reload_config',
    # Slack Actions - Living Post Management
    'create_living_post',
    'update_living_post',
    'add_version_to_thread',
    'add_review_buttons',
    'remove_review_buttons',
    # Slack Actions - Section-based Living Post
    'create_living_post_with_sections',
    'build_section_blocks_with_edit_buttons',
    # Slack Actions - Publishing
    'publish_to_announcement_channel',
    # Slack Actions - Feedback
    'post_feedback_request',
    'post_approval_notice',
    # Slack Actions - Utilities
    'get_newsletter_permalink',
    # News Scrapers
    'scrape_skinnyski_news',
    'scrape_loppet_news',
    'scrape_three_rivers_news',
    'scrape_all_news',
    'clear_news_cache',
    'get_scraper_status',
    # Service Functions (Scheduler Entry Points)
    'run_daily_update',
    'run_sunday_finalize',
    'regenerate_newsletter',
    'get_newsletter_status',
    'get_week_boundaries',
    'collect_newsletter_content',
    'generate_newsletter_version',
    # Generator Functions
    'generate_newsletter',
    'generate_fallback_newsletter',
    'get_newsletter_prompt',
    'build_generation_context',
    # Modals
    'build_dispatch_submission_modal',
    'build_dispatch_confirmation_blocks',
    # MCP Tools
    'NEWSLETTER_TOOLS',
    'tool_collect_slack_messages',
    'tool_get_member_submissions',
    'tool_scrape_ski_news',
    'tool_get_trail_conditions',
    'tool_get_prior_newsletter',
    'tool_save_newsletter_version',
    'tool_update_living_post',
    'execute_tool',
    'run_newsletter_agent',
    'generate_newsletter_with_mcp',
    # Section Editor
    'build_section_edit_modal',
    'get_section_for_editing',
    'save_section_edit',
    'get_all_sections_for_newsletter',
    'initialize_sections_for_newsletter',
    'get_section_display_name',
    # Monthly Generator
    'generate_section_draft',
    'generate_all_ai_sections',
    'build_section_context',
    'AI_DRAFTED_SECTIONS',
]
