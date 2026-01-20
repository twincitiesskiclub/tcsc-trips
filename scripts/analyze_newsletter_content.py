#!/usr/bin/env python3
"""
One-time script to analyze 90 days of Slack content and recommend
newsletter categories/sections based on actual community activity.

Usage:
    1. Make sure ./scripts/dev.sh is running (or PostgreSQL is accessible)
    2. Run: python scripts/analyze_newsletter_content.py

This uses the existing newsletter collector utilities to scrape Slack,
then sends the content to Claude Opus 4.5 with extended thinking for
deep analysis. The goal is to identify what categories would resonate
most with the community based on what they're actually talking about -
keeping the newsletter human-driven.

Note: The newsletter is published bi-weekly, but we analyze 90 days
to get a comprehensive view of community patterns.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DATABASE_URL for local dev if not already set
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'

# Must set up Flask app context for database/config access
from app import create_app

app = create_app()


def collect_slack_content(days: int = 90) -> list[dict]:
    """Collect Slack messages from the last N days.

    Args:
        days: Number of days to look back.

    Returns:
        List of message dicts with relevant fields.
    """
    from app.newsletter.collector import collect_all_messages, clear_caches

    clear_caches()
    since = datetime.now() - timedelta(days=days)

    print(f"📥 Collecting messages from the last {days} days...")
    print(f"   Looking back to: {since.strftime('%Y-%m-%d %H:%M')}")

    with app.app_context():
        messages = collect_all_messages(since)

    print(f"✅ Collected {len(messages)} messages")

    # Convert to dicts with only the fields we need for analysis
    return [
        {
            'channel': msg.channel_name,
            'text': msg.text,
            'user': msg.user_name,
            'reactions': msg.reaction_count,
            'replies': msg.reply_count,
            'posted_at': msg.posted_at.isoformat() if msg.posted_at else None,
            'is_thread_reply': msg.thread_ts is not None,
        }
        for msg in messages
    ]


def get_channel_summary(messages: list[dict]) -> dict:
    """Summarize message activity by channel.

    Args:
        messages: List of message dicts.

    Returns:
        Dict with channel stats.
    """
    channel_stats = defaultdict(lambda: {
        'count': 0,
        'reactions': 0,
        'replies': 0,
        'unique_users': set(),
    })

    for msg in messages:
        channel = msg['channel']
        channel_stats[channel]['count'] += 1
        channel_stats[channel]['reactions'] += msg['reactions']
        channel_stats[channel]['replies'] += msg['replies']
        channel_stats[channel]['unique_users'].add(msg['user'])

    # Convert sets to counts for JSON serialization
    return {
        channel: {
            'message_count': stats['count'],
            'total_reactions': stats['reactions'],
            'total_replies': stats['replies'],
            'unique_users': len(stats['unique_users']),
        }
        for channel, stats in sorted(
            channel_stats.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
    }


def chunk_messages(messages: list[dict], max_chars: int = 100000) -> list[list[dict]]:
    """Split messages into chunks that fit within token limits.

    Args:
        messages: List of message dicts.
        max_chars: Approximate max characters per chunk.

    Returns:
        List of message chunks.
    """
    chunks = []
    current_chunk = []
    current_size = 0

    for msg in messages:
        msg_text = msg['text']
        msg_size = len(msg_text) + 100  # Account for metadata

        if current_size + msg_size > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0

        current_chunk.append(msg)
        current_size += msg_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def analyze_content_with_thinking(
    client: anthropic.Anthropic,
    messages: list[dict],
    batch_num: int,
    total_batches: int,
) -> str:
    """Analyze a batch of messages using Opus 4.5 with extended thinking.

    Args:
        client: Anthropic client.
        messages: Message batch to analyze.
        batch_num: Current batch number.
        total_batches: Total number of batches.

    Returns:
        Analysis text from Claude.
    """
    # Create a compact representation for analysis
    content_lines = []
    for msg in messages:
        emoji = "💬" if not msg['is_thread_reply'] else "↳"
        engagement = ""
        if msg['reactions'] > 0 or msg['replies'] > 0:
            engagement = f" [{msg['reactions']}👍 {msg['replies']}💬]"
        content_lines.append(
            f"{emoji} #{msg['channel']} | {msg['user']}: {msg['text'][:500]}{engagement}"
        )

    content_text = "\n".join(content_lines)

    prompt = f"""You are analyzing Slack messages from a ski club to identify themes and conversation topics.

This is batch {batch_num} of {total_batches} batches.

TASK: Read through these messages carefully and identify:
1. Major topics/themes being discussed
2. Types of content (questions, announcements, discussions, photos, etc.)
3. Emotional tone and community dynamics
4. Content that generated high engagement (reactions/replies)

Messages (format: emoji #channel | user: text [engagement]):

{content_text}

Provide a concise analysis in this format:
## Topics Found
- [topic]: brief description and example

## Content Types
- [type]: how common, example

## High Engagement Content
- What topics/posts got the most reactions/replies

## Community Dynamics
- Brief observation about the community voice/culture
"""

    print(f"  🧠 Thinking about batch {batch_num}...", end="", flush=True)

    # Stream with extended thinking
    result_text = ""
    thinking_shown = False

    with client.messages.stream(
        model="claude-opus-4-5-20251101",
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 8000,
        },
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for event in stream:
            if hasattr(event, 'type'):
                if event.type == 'content_block_start':
                    if hasattr(event, 'content_block'):
                        if event.content_block.type == 'thinking':
                            if not thinking_shown:
                                print(" (deep analysis)", end="", flush=True)
                                thinking_shown = True
                elif event.type == 'content_block_delta':
                    if hasattr(event, 'delta'):
                        if hasattr(event.delta, 'text'):
                            result_text += event.delta.text

    print(" ✓")
    return result_text


def synthesize_recommendations_with_thinking(
    client: anthropic.Anthropic,
    batch_analyses: list[str],
    channel_summary: dict,
    current_categories: list[str],
) -> str:
    """Synthesize batch analyses into final recommendations using deep thinking.

    Args:
        client: Anthropic client.
        batch_analyses: List of analysis texts from each batch.
        channel_summary: Channel activity stats.
        current_categories: Current newsletter categories from prompt.

    Returns:
        Final recommendations text.
    """
    analyses_text = "\n\n---\n\n".join([
        f"### Batch {i+1} Analysis\n{analysis}"
        for i, analysis in enumerate(batch_analyses)
    ])

    channel_stats_text = json.dumps(channel_summary, indent=2)

    prompt = f"""You are helping a ski club design their BI-WEEKLY newsletter. You've analyzed 90 days of their Slack conversations to understand community patterns.

## Current Newsletter Categories (from their prompt)
These are the categories they currently cluster content into:
{json.dumps(current_categories, indent=2)}

## Channel Activity Summary
Shows which channels are most active (message count, engagement, unique users):
{channel_stats_text}

## Content Analyses
Here are the themes and topics found across all their Slack content:

{analyses_text}

---

## Your Task

Based on this real community data, recommend the BEST newsletter categories/sections.

CRITICAL CONTEXT:
- This newsletter is published EVERY TWO WEEKS (bi-weekly)
- It should feel HUMAN-DRIVEN, not AI-generated slop
- Categories should reflect what the community ACTUALLY talks about
- The newsletter is meant to be a weekly summary that brings the community together
- It should celebrate member contributions and keep people connected
- Think deeply about what makes this community unique

Please provide:

### 1. RECOMMENDED CATEGORIES
For each category:
- Name (short, fun if appropriate to the community voice)
- Description (what goes here)
- WHY this category based on the data
- Priority (must-have / nice-to-have / occasional)
- Bi-weekly cadence notes (will this have enough content every 2 weeks?)

### 2. CATEGORIES TO DROP OR MERGE
Any current categories that don't match actual community activity

### 3. SPECIAL SECTIONS TO CONSIDER
Rotating or seasonal sections based on the data (especially relevant for a ski club with seasonal activity)

### 4. VOICE/TONE OBSERVATIONS
Based on how the community actually communicates, specific suggestions for the newsletter voice that would feel authentic

### 5. CONTENT GOLDMINES
Specific types of posts/topics that consistently generate engagement - these should be prioritized

### 6. BI-WEEKLY RHYTHM RECOMMENDATIONS
Given the two-week publishing cycle, what's the ideal structure to capture highlights without being overwhelming?

Be specific and ground ALL recommendations in the actual data. Don't suggest generic newsletter categories that every organization has - suggest what THIS community needs based on what you observed.
"""

    print("🧠 Deep thinking about recommendations...", flush=True)

    result_text = ""

    with client.messages.stream(
        model="claude-opus-4-5-20251101",
        max_tokens=32000,
        thinking={
            "type": "enabled",
            "budget_tokens": 16000,
        },
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for event in stream:
            if hasattr(event, 'type'):
                if event.type == 'content_block_start':
                    if hasattr(event, 'content_block'):
                        if event.content_block.type == 'thinking':
                            print("  📊 Analyzing patterns...", flush=True)
                        elif event.content_block.type == 'text':
                            print("  ✍️  Generating recommendations...", flush=True)
                elif event.type == 'content_block_delta':
                    if hasattr(event, 'delta'):
                        if hasattr(event.delta, 'text'):
                            result_text += event.delta.text
                            # Print dots for progress
                            if len(result_text) % 500 == 0:
                                print(".", end="", flush=True)

    print(" ✓")
    return result_text


def main():
    """Main analysis workflow."""
    print("=" * 60)
    print("🎿 TCSC Bi-Weekly Newsletter Category Analysis")
    print("=" * 60)
    print()

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("   Set it with: export ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Current categories from the newsletter prompt
    current_categories = [
        "Training",
        "Trail Conditions",
        "Races/Results",
        "Gear/Wax",
        "Social/Club Ops",
        "Newbie Corner",
        "Photos/Media",
    ]

    # Step 1: Collect Slack content
    print("\n📡 Step 1: Collecting Slack content")
    print("-" * 40)
    messages = collect_slack_content(days=90)

    if not messages:
        print("❌ No messages collected. Check Slack connection.")
        sys.exit(1)

    # Step 2: Get channel summary
    print("\n📊 Step 2: Analyzing channel activity")
    print("-" * 40)
    channel_summary = get_channel_summary(messages)

    print("\nTop channels by activity:")
    for channel, stats in list(channel_summary.items())[:10]:
        print(
            f"  #{channel}: {stats['message_count']} msgs, "
            f"{stats['total_reactions']} reactions, "
            f"{stats['unique_users']} users"
        )

    # Step 3: Chunk messages for analysis
    print("\n🔪 Step 3: Preparing content batches")
    print("-" * 40)
    chunks = chunk_messages(messages, max_chars=80000)
    print(f"Split into {len(chunks)} batches for analysis")

    # Step 4: Analyze each batch with extended thinking
    print("\n🔍 Step 4: Analyzing content themes (with extended thinking)")
    print("-" * 40)
    batch_analyses = []

    for i, chunk in enumerate(chunks):
        print(f"\n  Batch {i+1}/{len(chunks)} ({len(chunk)} messages)")
        analysis = analyze_content_with_thinking(client, chunk, i+1, len(chunks))
        batch_analyses.append(analysis)

    # Step 5: Synthesize recommendations with deep thinking
    print("\n💡 Step 5: Synthesizing recommendations (deep thinking)")
    print("-" * 40)
    recommendations = synthesize_recommendations_with_thinking(
        client,
        batch_analyses,
        channel_summary,
        current_categories,
    )

    # Output results
    print("\n" + "=" * 60)
    print("📝 BI-WEEKLY NEWSLETTER CATEGORY RECOMMENDATIONS")
    print("=" * 60)
    print()
    print(recommendations)

    # Save to file
    output_file = "newsletter_analysis_results.md"
    with open(output_file, 'w') as f:
        f.write("# TCSC Bi-Weekly Newsletter Category Analysis\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Analyzed: {len(messages)} messages from last 90 days\n\n")
        f.write("Newsletter cadence: Every two weeks (bi-weekly)\n\n")

        f.write("## Channel Activity Summary\n\n")
        f.write("| Channel | Messages | Reactions | Users |\n")
        f.write("|---------|----------|-----------|-------|\n")
        for channel, stats in channel_summary.items():
            f.write(
                f"| #{channel} | {stats['message_count']} | "
                f"{stats['total_reactions']} | {stats['unique_users']} |\n"
            )

        f.write("\n## Recommendations\n\n")
        f.write(recommendations)

    print(f"\n✅ Results saved to: {output_file}")
    print()


if __name__ == "__main__":
    main()
