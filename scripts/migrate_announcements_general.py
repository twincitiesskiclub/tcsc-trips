"""One-time migration of #announcements-general from public to private.

Copies all human conversation from C02J4GMLMU4 (currently public
#announcements-general) to C0B2VN1LU11 (currently private
#announcements-general-2), preserving author identity via bot
impersonation, threads, reactions, and file attachments. Then deletes
the source content.

Spec: docs/superpowers/specs/2026-05-11-announcements-general-migration-design.md

Usage:
    python scripts/migrate_announcements_general.py copy [--limit N] [--since YYYY-MM-DD]
    python scripts/migrate_announcements_general.py delete [--no-dry-run]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

load_dotenv()

SOURCE_CHANNEL = "C02J4GMLMU4"
DEST_CHANNEL = "C0B2VN1LU11"

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
MANIFEST_PATH = OUTPUT_DIR / "migration_manifest.json"
FILES_DIR = OUTPUT_DIR / "files"
TRANSCRIPT_PATH = OUTPUT_DIR / "announcements_general_transcript.txt"

POST_DELAY_SECONDS = 0.3  # explicit pacing between chat.postMessage calls


def get_bot_client() -> WebClient:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("ERROR: SLACK_BOT_TOKEN not set in .env")
    return WebClient(token=token, retry_handlers=[RateLimitErrorRetryHandler(max_retry_count=5)])


def get_user_client() -> WebClient:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        sys.exit("ERROR: SLACK_USER_TOKEN not set in .env")
    return WebClient(token=token, retry_handlers=[RateLimitErrorRetryHandler(max_retry_count=5)])


def verify_channel_access(bot: WebClient, channel_id: str, label: str) -> None:
    try:
        info = bot.conversations_info(channel=channel_id)
    except SlackApiError as e:
        sys.exit(f"ERROR: cannot read {label} channel {channel_id}: {e.response['error']}")
    if not info["channel"].get("is_member"):
        sys.exit(f"ERROR: bot is not a member of {label} channel {channel_id} (#{info['channel']['name']}). Invite the bot and re-run.")
    print(f"  bot is in {label}={channel_id} (#{info['channel']['name']})")


def probe_copy_scopes(bot: WebClient) -> None:
    """Verify chat:write, chat:write.customize, and bot membership in DEST.

    Posts an impersonated probe message in DEST and deletes it. Aborts on any failure.
    """
    print("Probing copy scopes (impersonate + delete in DEST)...")
    try:
        resp = bot.chat_postMessage(
            channel=DEST_CHANNEL,
            text="[probe] migration scope check — will be deleted",
            username="Migration Probe",
            icon_emoji=":construction:",
        )
    except SlackApiError as e:
        err = e.response["error"]
        needed = e.response.get("needed", "?")
        sys.exit(f"ERROR: copy-phase probe post failed ({err}, needed scope: {needed})")
    try:
        bot.chat_delete(channel=DEST_CHANNEL, ts=resp["ts"])
    except SlackApiError as e:
        sys.exit(f"ERROR: copy-phase probe delete failed: {e.response['error']}")
    print("  OK")


def probe_delete_scopes(bot: WebClient, user: WebClient) -> None:
    """Verify admin chat:write on user token via post-then-delete in SOURCE.

    Posts a bot message in SOURCE then deletes it via user token.
    """
    print("Probing delete scopes (admin chat:write in SOURCE via user token)...")
    try:
        resp = bot.chat_postMessage(channel=SOURCE_CHANNEL, text="[probe] migration delete scope check — will be deleted")
    except SlackApiError as e:
        sys.exit(f"ERROR: delete-phase probe post failed: {e.response['error']}")
    try:
        user.chat_delete(channel=SOURCE_CHANNEL, ts=resp["ts"])
    except SlackApiError as e:
        err = e.response["error"]
        needed = e.response.get("needed", "?")
        # Best-effort cleanup before aborting
        try:
            bot.chat_delete(channel=SOURCE_CHANNEL, ts=resp["ts"])
        except SlackApiError:
            pass
        sys.exit(f"ERROR: user-token delete failed ({err}, needed scope: {needed})")
    print("  OK")


def build_user_cache(bot: WebClient) -> dict[str, dict]:
    """Return {slack_uid: {display_name, real_name, image_72}} for all workspace users."""
    print("Fetching workspace users...")
    cache: dict[str, dict] = {}
    cursor = None
    while True:
        params = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        resp = bot.users_list(**params)
        for user in resp["members"]:
            if user.get("deleted"):
                # Still cache deactivated users — their messages will reference them
                pass
            profile = user.get("profile", {})
            cache[user["id"]] = {
                "display_name": profile.get("display_name") or profile.get("real_name") or user["id"],
                "real_name": profile.get("real_name", ""),
                "image_72": profile.get("image_72", ""),
            }
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    print(f"  cached {len(cache)} users")
    return cache


def resolve_author(msg: dict, user_cache: dict[str, dict]) -> dict:
    """Return {display_name, icon_url, icon_emoji} for the author of msg.

    Precedence: user_cache → msg.user_profile → 'Former member' fallback.
    """
    user_id = msg.get("user", "")
    if user_id in user_cache:
        cached = user_cache[user_id]
        return {
            "display_name": cached["display_name"],
            "icon_url": cached["image_72"] or None,
            "icon_emoji": None if cached["image_72"] else ":bust_in_silhouette:",
        }
    # Slack embeds user_profile on messages for users who left
    profile = msg.get("user_profile")
    if profile:
        return {
            "display_name": profile.get("display_name") or profile.get("real_name") or "Former member",
            "icon_url": profile.get("image_72") or None,
            "icon_emoji": None if profile.get("image_72") else ":bust_in_silhouette:",
        }
    return {"display_name": "Former member", "icon_url": None, "icon_emoji": ":ghost:"}


def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    print(f"Scopes OK, user cache loaded ({len(user_cache)} users). Copy implementation pending.")


def cmd_delete(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    user = get_user_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    probe_delete_scopes(bot, user)
    print(f"Scopes OK. Delete implementation pending. (dry_run={not args.no_dry_run})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="phase", required=True)

    p_copy = sub.add_parser("copy", help="Copy messages from source to dest (resumable)")
    p_copy.add_argument("--limit", type=int, default=None, help="Copy only the oldest N root messages")
    p_copy.add_argument("--since", type=str, default=None, help="Copy only messages on or after YYYY-MM-DD (UTC)")
    p_copy.set_defaults(func=cmd_copy)

    p_delete = sub.add_parser("delete", help="Delete messages from source channel (dry-run by default)")
    p_delete.add_argument("--no-dry-run", action="store_true", help="Actually delete (otherwise just preview)")
    p_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
