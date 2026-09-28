"""Operator commands for the analytics archive and derived data."""
import json
from pathlib import Path

import click
from flask.cli import AppGroup

from app.analytics.archive import import_channel, sync_recent
from app.analytics.corrections import export_corrections, import_corrections, load_corrections
from app.analytics.jobs import run_nightly
from app.analytics.models import SlackArchiveMessage
from app.analytics.rebuild import archive_rows, candidate_rows, flagged_sessions, rebuild
from app.analytics.weather import fetch_missing_weather
from app.models import AppConfig, db
from app.slack.client import get_slack_client, get_slack_user_client

analytics_cli = AppGroup("analytics", help="Import and maintain practice analytics.")


def _print_json(value):
    click.echo(json.dumps(value, indent=2, sort_keys=True))


@analytics_cli.command("import-slack")
@click.option("--channel", required=True, help="Slack channel ID.")
@click.option("--token", type=click.Choice(["bot", "user"]), default="bot", show_default=True)
def import_slack(channel, token):
    """Import a channel's full history and threads."""
    client = get_slack_user_client() if token == "user" else get_slack_client()
    stats = import_channel(client, channel)
    db.session.commit()
    _print_json({key: value for key, value in stats.items() if key != "seen"})


@analytics_cli.command("sync")
@click.option("--days", type=click.IntRange(min=1), default=21, show_default=True)
def sync(days):
    """Refresh recent history using the bot token."""
    stats = sync_recent(get_slack_client(), days=days)
    db.session.commit()
    _print_json(stats)


@analytics_cli.command("rebuild")
def rebuild_command():
    """Rebuild derived sessions and attendance from archived data."""
    _print_json(rebuild())


@analytics_cli.command("fetch-weather")
def fetch_weather():
    """Fetch and apply missing historical weather."""
    _print_json(fetch_missing_weather())


@analytics_cli.command("flags")
@click.option("--json", "json_path", type=click.Path(dir_okay=False, writable=True))
def flags(json_path):
    """List review sessions, candidates, and empty weeks as of the last rebuild."""
    snapshot = AppConfig.get("analytics_coverage", {"candidates": [], "empty_weeks": []})
    sessions = []
    for session in flagged_sessions():
        message = (db.session.get(SlackArchiveMessage, session.source_message_id)
                   if session.source_message_id else None) or archive_rows([session.group_key]).get(session.group_key)
        replies = SlackArchiveMessage.query.filter(
            SlackArchiveMessage.channel_id == message.channel_id, SlackArchiveMessage.thread_ts == message.ts,
            SlackArchiveMessage.ts != message.ts, SlackArchiveMessage.deleted_at.is_(None),
        ).order_by(SlackArchiveMessage.ts).all() if message else []
        sessions.append({
            "session_key": session.session_key,
            "post_key": f"{message.channel_id}:{message.ts}" if message else session.group_key,
            "date": session.date.isoformat(), "title": session.title,
            "flags": session.flags, "format": session.format, "rsvp_count": session.rsvp_count,
            "text": message.text if message else "",
            "replies": [reply.text for reply in replies],
        })
        click.echo(f"{session.date}  {session.session_key}  {','.join(session.flags)}  {session.title}")
    misses = candidate_rows([candidate["post_key"] for candidate in snapshot["candidates"]])
    for miss in misses:
        click.echo(f"{miss['date']}  {miss['post_key']}  candidate")
    for monday in snapshot["empty_weeks"]:
        click.echo(f"{monday}  empty_week")
    if json_path:
        Path(json_path).write_text(json.dumps({
            "flagged_sessions": sessions, "possible_misses": misses, "empty_weeks": snapshot["empty_weeks"],
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@analytics_cli.command("nightly")
def nightly():
    """Run the bot-only sync, rebuild, and weather pipeline."""
    result = run_nightly()
    _print_json(result)
    if not result["ok"]:
        raise click.exceptions.Exit(1)


@analytics_cli.command("set-coach-emoji")
@click.argument("names")
def set_coach_emoji(names):
    """Set comma-separated coach emoji names; use an empty string to clear."""
    names = [name.strip() for name in names.split(",") if name.strip()]
    AppConfig.set("analytics_coach_emoji", names, category="analytics")
    db.session.commit()
    _print_json(names)


@analytics_cli.group("corrections")
def corrections():
    """List, import, or export DB corrections."""


@corrections.command("list")
def list_corrections():
    _print_json(load_corrections())


@corrections.command("import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def import_corrections_command(path):
    count = import_corrections(path)
    db.session.commit()
    click.echo(count)


@corrections.command("export")
@click.argument("path", type=click.Path(dir_okay=False, writable=True))
def export_corrections_command(path):
    click.echo(export_corrections(path))
