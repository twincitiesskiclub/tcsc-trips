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


def cmd_copy(args: argparse.Namespace) -> None:
    print("copy phase: not yet implemented")


def cmd_delete(args: argparse.Namespace) -> None:
    print("delete phase: not yet implemented")


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
