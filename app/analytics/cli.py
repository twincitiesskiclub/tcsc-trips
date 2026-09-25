"""Operator commands for the analytics archive and derived data."""
from datetime import datetime, timezone
import json
from pathlib import Path

import click
from flask.cli import AppGroup

from app.analytics.archive import import_channel, sync_recent
from app.analytics.corrections import export_corrections, import_corrections, load_corrections
from app.analytics.jobs import run_nightly
from app.analytics.lineage import build_lineage
from app.analytics.rebuild import flagged_sessions, load_inputs, load_rebuild_config, rebuild
from app.analytics.weather import fetch_missing_weather
from app.models import AppConfig, db
from app.slack.client import get_slack_client, get_slack_user_client
from app.utils import utc_naive_to_central_naive

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
    """List review sessions and possible misses without changing the DB."""
    inputs = load_inputs()
    messages = inputs[0]
    lineage = build_lineage(*inputs, load_rebuild_config(), load_corrections())
    by_id = {message.archive_id: message for message in messages if message.archive_id is not None}
    by_key = {f"{message.channel_id}:{message.ts}": message for message in messages}
    sessions = []
    for session in flagged_sessions():
        message = by_id.get(session.source_message_id) or by_key.get(session.group_key)
        post_key = f"{message.channel_id}:{message.ts}" if message else session.group_key
        sessions.append({
            "session_key": session.session_key, "post_key": post_key,
            "date": session.date.isoformat(), "title": session.title,
            "flags": session.flags, "format": session.format, "rsvp_count": session.rsvp_count,
            "text": message.raw.get("text", "") if message else "",
            "replies": [reply.get("text", "") for reply in message.replies] if message else [],
        })
        click.echo(f"{session.date}  {session.session_key}  {','.join(session.flags)}  {session.title}")
    misses = []
    for key in lineage.possible_misses:
        message = by_key[key]
        posted_at = datetime.fromtimestamp(float(message.ts), timezone.utc).replace(tzinfo=None)
        day = utc_naive_to_central_naive(posted_at).date().isoformat()
        misses.append({
            "post_key": key, "date": day, "text": message.raw.get("text", ""),
            "reactions": {reaction["name"]: reaction.get("count", 0)
                          for reaction in message.raw.get("reactions", [])},
        })
        click.echo(f"{day}  {key}  possible_miss")
    if json_path:
        Path(json_path).write_text(json.dumps({
            "flagged_sessions": sessions, "possible_misses": misses,
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
