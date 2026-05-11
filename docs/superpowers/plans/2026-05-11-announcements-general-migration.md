# #announcements-general Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-time, restart-safe script that copies all human conversation (root posts, threaded replies, reactions, files, pins) from public Slack channel `C02J4GMLMU4` to private channel `C0B2VN1LU11`, then deletes the source content — preserving author identity via bot impersonation.

**Architecture:** Single standalone script `scripts/migrate_announcements_general.py` with two CLI subcommands (`copy`, `delete`). No Flask dependency, follows the pattern of `scripts/extract_channel_history.py`. Restart safety via a JSON manifest at `scripts/output/migration_manifest.json` that is flushed after every successful Slack API call. Author impersonation uses `chat.postMessage` `username` / `icon_url` parameters (requires `chat:write.customize`, verified). Deletion uses `chat.delete` with `SLACK_USER_TOKEN` (workspace owner, admin power confirmed).

**Tech Stack:** Python 3.12, `slack_sdk.WebClient` with `RateLimitErrorRetryHandler`, `python-dotenv`, `argparse`, `json` (manifest), `requests` (file downloads).

**Spec:** `docs/superpowers/specs/2026-05-11-announcements-general-migration-design.md`

**Already done in brainstorming:** Scope probe (`scripts/probe_migration_scopes.py`) confirms `chat:write`, `chat:write.customize`, admin `chat:write` on the user token, and bot membership in both channels.

**Testing strategy reminder:** No pytest. Every task ends with running the script against the real Slack workspace with appropriate safety flags (`--limit`, `--dry-run`) and visually verifying the result in Slack. The dest channel `C0B2VN1LU11` is currently empty and used for development testing; any test posts that look wrong can be deleted manually in Slack and the manifest reset (`rm scripts/output/migration_manifest.json`) before re-running.

**Channel constants (used throughout):**

```python
SOURCE_CHANNEL = "C02J4GMLMU4"  # currently #announcements-general, will be renamed to #welcome-to-tcsc
DEST_CHANNEL   = "C0B2VN1LU11"  # currently #announcements-general-2, will be renamed to #announcements-general
```

---

## Task 1: Scaffold the script and CLI

**Files:**
- Create: `scripts/migrate_announcements_general.py`
- Modify: `.gitignore` (ensure `scripts/output/` is ignored — verify only)

- [ ] **Step 1: Verify `scripts/output/` is gitignored**

Run:
```bash
grep -n "scripts/output" .gitignore
```
Expected: a matching line. If missing, append `scripts/output/` to `.gitignore`.

- [ ] **Step 2: Create the script skeleton with argparse and stub functions**

Create `scripts/migrate_announcements_general.py`:

```python
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
```

- [ ] **Step 3: Verify the CLI parses correctly**

Run:
```bash
source env/bin/activate && python scripts/migrate_announcements_general.py --help
python scripts/migrate_announcements_general.py copy --help
python scripts/migrate_announcements_general.py delete --help
python scripts/migrate_announcements_general.py copy --limit 3
python scripts/migrate_announcements_general.py delete
```

Expected output for the last two commands:
```
copy phase: not yet implemented
delete phase: not yet implemented
```

Verify `scripts/output/` and `scripts/output/files/` directories were created.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: scaffold migrate_announcements_general script with CLI"
```

---

## Task 2: Startup auth and scope probes

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Both `copy` and `delete` phases need to verify their required scopes before doing anything else. The probe posts an impersonated message in DEST then deletes it (verifies `chat:write` + `chat:write.customize` + bot membership). The delete probe additionally posts a bot message in SOURCE then deletes via user token (verifies admin `chat:write` on user token).

- [ ] **Step 1: Add the channel-membership and auth probe functions**

Add to `scripts/migrate_announcements_general.py` after `get_user_client()`:

```python
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
```

- [ ] **Step 2: Wire the probes into the cmd_copy and cmd_delete entry points**

Replace `cmd_copy` and `cmd_delete` stubs with:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    print("Scopes OK. Copy implementation pending.")


def cmd_delete(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    user = get_user_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    probe_delete_scopes(bot, user)
    print(f"Scopes OK. Delete implementation pending. (dry_run={not args.no_dry_run})")
```

- [ ] **Step 3: Run both probes against the live workspace**

Run:
```bash
python scripts/migrate_announcements_general.py copy --limit 1
python scripts/migrate_announcements_general.py delete
```

Expected output for each: `Scopes OK.` after the probe lines, with no errors. Verify in Slack that no probe messages remain in either channel.

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: add startup channel-access and scope probes"
```

---

## Task 3: User cache and author resolution

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

We need to know each author's display name and avatar URL to impersonate them. Fetch `users.list` once at startup, cache, and provide a lookup helper that falls back to the message's embedded `user_profile` for deactivated users.

- [ ] **Step 1: Add the user cache and resolver**

Add to `scripts/migrate_announcements_general.py` (after the probe functions):

```python
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
```

- [ ] **Step 2: Wire user cache into cmd_copy and print stats**

Update `cmd_copy`:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    print(f"Scopes OK, user cache loaded ({len(user_cache)} users). Copy implementation pending.")
```

- [ ] **Step 3: Run and verify user cache loads**

Run:
```bash
python scripts/migrate_announcements_general.py copy
```

Expected: prints `cached N users` where N is roughly 200+ (the TCSC workspace size).

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: add user cache for author impersonation lookups"
```

---

## Task 4: Reaction emoji table and message formatter

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Pure formatting logic: build the impersonated post text body (italic timestamp line + original text + optional reaction footer on root posts).

- [ ] **Step 1: Add the emoji shortcode → unicode table**

Add to `scripts/migrate_announcements_general.py`:

```python
# Minimal Slack shortcode → Unicode emoji table. Unknown shortcodes (including
# custom workspace emoji) stay as :shortcode: text in the reaction footer.
EMOJI_SHORTCODES: dict[str, str] = {
    "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎",
    "heart": "❤️", "fire": "🔥", "tada": "🎉", "rocket": "🚀",
    "white_check_mark": "✅", "x": "❌", "warning": "⚠️", "eyes": "👀",
    "raised_hands": "🙌", "clap": "👏", "100": "💯", "muscle": "💪",
    "skier": "⛷️", "snowboarder": "🏂", "snowflake": "❄️", "snowman": "⛄",
    "joy": "😂", "rofl": "🤣", "smile": "😄", "sob": "😭",
    "thinking_face": "🤔", "pray": "🙏", "wave": "👋", "ok_hand": "👌",
    "point_up": "☝️", "point_right": "👉", "point_left": "👈",
    "heart_eyes": "😍", "cry": "😢", "cold_face": "🥶", "hot_face": "🥵",
    "sunny": "☀️", "cloud": "☁️", "umbrella": "☔", "zap": "⚡",
    "trophy": "🏆", "medal": "🏅", "first_place_medal": "🥇",
    "second_place_medal": "🥈", "third_place_medal": "🥉",
    "beer": "🍺", "wine_glass": "🍷", "coffee": "☕", "pizza": "🍕",
    "question": "❓", "exclamation": "❗", "heavy_check_mark": "✔️",
}


def render_emoji(shortcode: str) -> str:
    """Return Unicode for a known shortcode, or the original :shortcode: text."""
    # Strip skin tone modifiers like ::skin-tone-2
    base = shortcode.split("::")[0]
    return EMOJI_SHORTCODES.get(base, f":{base}:")
```

- [ ] **Step 2: Add the timestamp + body + reaction formatter**

Add:

```python
def format_timestamp_central(ts: str) -> str:
    """Convert Slack ts to 'MMM D, YYYY h:MM AM/PM' string in US Central.

    Uses zoneinfo for tz handling.
    """
    from zoneinfo import ZoneInfo
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(ZoneInfo("America/Chicago"))
    # %-I/%-d for non-zero-padded hours/days (Linux/macOS)
    return dt.strftime("%b %-d, %Y %-I:%M %p")


def build_reaction_footer(reactions: list[dict]) -> str:
    """Return '👍 2 · 😂 1' or '' if no reactions."""
    if not reactions:
        return ""
    parts = []
    for r in reactions:
        emoji = render_emoji(r.get("name", ""))
        count = r.get("count", 0)
        parts.append(f"{emoji} {count}")
    return " · ".join(parts)


def build_post_text(msg: dict, include_reactions: bool) -> str:
    """Build the impersonated post body: italic timestamp, original text, optional footer.

    include_reactions is True for root messages, False for thread replies.
    """
    ts_line = f"*{format_timestamp_central(msg['ts'])}*"
    body = msg.get("text", "") or "_(no text)_"
    parts = [ts_line, body]
    if include_reactions:
        footer = build_reaction_footer(msg.get("reactions", []))
        if footer:
            parts.append("")  # blank line before footer
            parts.append(footer)
    return "\n".join(parts)
```

- [ ] **Step 3: Smoke-test the formatter with a fake message**

Add a temporary smoke-test at the bottom of `cmd_copy` (will be removed in Task 6):

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)

    # Temporary smoke-test of formatter
    fake_msg = {
        "ts": "1745510520.000000",
        "text": "Test message with <@U02JS0R7ZG8> mention and a link <https://example.com|example>",
        "reactions": [
            {"name": "thumbsup", "count": 2},
            {"name": "joy", "count": 1},
            {"name": "tcsc_custom_emoji", "count": 1},
        ],
    }
    print("---")
    print(build_post_text(fake_msg, include_reactions=True))
    print("---")
```

Run:
```bash
python scripts/migrate_announcements_general.py copy
```

Expected output (timestamp depends on local interpretation — should be a sensible 2025 date in Central time):
```
---
*Apr 24, 2025 11:02 AM*
Test message with <@U02JS0R7ZG8> mention and a link <https://example.com|example>

👍 2 · 😂 1 · :tcsc_custom_emoji: 1
---
```

- [ ] **Step 4: Remove the temporary smoke-test from cmd_copy**

Restore `cmd_copy` to:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    print(f"Scopes OK, user cache loaded ({len(user_cache)} users). Copy implementation pending.")
```

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: add reaction emoji table and impersonated message formatter"
```

---

## Task 5: Manifest I/O

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

The manifest is the source of truth for resumability. Loaded at start, flushed after every successful API call.

- [ ] **Step 1: Add manifest load/init/save helpers**

Add to `scripts/migrate_announcements_general.py`:

```python
MANIFEST_SCHEMA_VERSION = 1


def load_or_init_manifest() -> dict:
    """Load manifest from disk, or initialize a new one. Validates schema version."""
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH) as f:
                m = json.load(f)
        except json.JSONDecodeError as e:
            sys.exit(
                f"ERROR: manifest at {MANIFEST_PATH} is corrupted ({e}). "
                f"Rename it (e.g. mv {MANIFEST_PATH} {MANIFEST_PATH}.bad) and re-run."
            )
        if m.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            sys.exit(f"ERROR: manifest schema version mismatch (expected {MANIFEST_SCHEMA_VERSION}, got {m.get('schema_version')})")
        if m.get("channel_from") != SOURCE_CHANNEL or m.get("channel_to") != DEST_CHANNEL:
            sys.exit(
                f"ERROR: manifest channels ({m.get('channel_from')} → {m.get('channel_to')}) "
                f"do not match configured channels ({SOURCE_CHANNEL} → {DEST_CHANNEL})"
            )
        return m
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "channel_from": SOURCE_CHANNEL,
        "channel_to": DEST_CHANNEL,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "copy_completed_at": None,
        "messages": {},
        "pinned_source_ts": [],
        "skipped": {},
    }


def save_manifest(manifest: dict) -> None:
    """Atomically write manifest to disk."""
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    tmp.replace(MANIFEST_PATH)
```

- [ ] **Step 2: Wire manifest load into cmd_copy**

Update `cmd_copy`:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    manifest = load_or_init_manifest()
    save_manifest(manifest)
    print(f"Manifest loaded: {len(manifest['messages'])} messages already copied.")
```

- [ ] **Step 3: Run twice and verify manifest persists**

Run:
```bash
python scripts/migrate_announcements_general.py copy
cat scripts/output/migration_manifest.json
python scripts/migrate_announcements_general.py copy
```

Expected:
- First run prints `Manifest loaded: 0 messages already copied.`
- Manifest file exists with `schema_version=1`, correct channel IDs, empty `messages: {}`
- Second run prints same thing (no change since no messages yet)

- [ ] **Step 4: Test corruption detection**

Run:
```bash
echo "not json" > scripts/output/migration_manifest.json
python scripts/migrate_announcements_general.py copy
```

Expected: script exits with `ERROR: manifest at ... is corrupted ...`. Then restore:

```bash
rm scripts/output/migration_manifest.json
python scripts/migrate_announcements_general.py copy
```

Expected: fresh manifest re-created.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: add restart-safe manifest I/O"
```

---

## Task 6: Copy phase — root messages (no threads, no files)

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Implement the core copy loop for root messages only: paginate history oldest-first, skip system/bot messages, impersonate-post each one in DEST, save manifest after each.

- [ ] **Step 1: Add the system/bot message filter and the history fetcher**

Add to `scripts/migrate_announcements_general.py`:

```python
SYSTEM_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic", "channel_purpose",
    "channel_name", "channel_archive", "channel_unarchive",
    "pinned_item", "unpinned_item", "channel_convert_to_private",
    "channel_convert_to_public", "bot_message", "reminder_add",
    "tombstone",
}


def should_skip(msg: dict) -> str | None:
    """Return a reason string if the message should be skipped, else None."""
    subtype = msg.get("subtype")
    if subtype in SYSTEM_SUBTYPES:
        return f"subtype={subtype}"
    if msg.get("bot_id"):
        return f"bot_message: {msg.get('username', msg.get('bot_id'))}"
    if not msg.get("user") and not msg.get("user_profile"):
        return "no_author"
    return None


def fetch_history_oldest_first(
    bot: WebClient,
    channel: str,
    oldest_ts: str | None = None,
) -> list[dict]:
    """Fetch all root messages from a channel, in oldest-first order."""
    messages: list[dict] = []
    cursor = None
    page = 0
    while True:
        params = {"channel": channel, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        if oldest_ts:
            params["oldest"] = oldest_ts
        resp = bot.conversations_history(**params)
        messages.extend(resp.get("messages", []))
        page += 1
        print(f"  history page {page}: {len(messages)} total so far")
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    # Slack returns newest-first; flip to oldest-first
    messages.reverse()
    return messages
```

- [ ] **Step 2: Add the impersonated-post helper**

Add:

```python
def post_impersonated(
    bot: WebClient,
    channel: str,
    text: str,
    author: dict,
    thread_ts: str | None = None,
) -> str:
    """Post text in channel impersonating author; return new ts.

    author is the dict returned by resolve_author().
    """
    kwargs = {
        "channel": channel,
        "text": text,
        "username": author["display_name"],
        # Disable Slack's link unfurling for re-posts so old links don't generate
        # fresh notification pings or large unfurl previews.
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if author["icon_url"]:
        kwargs["icon_url"] = author["icon_url"]
    elif author["icon_emoji"]:
        kwargs["icon_emoji"] = author["icon_emoji"]
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    resp = bot.chat_postMessage(**kwargs)
    time.sleep(POST_DELAY_SECONDS)
    return resp["ts"]
```

- [ ] **Step 3: Add the root-copy loop and wire into cmd_copy**

Add:

```python
def parse_since(since: str | None) -> str | None:
    if not since:
        return None
    dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return str(dt.timestamp())


def copy_root_messages(
    bot: WebClient,
    user_cache: dict[str, dict],
    manifest: dict,
    limit: int | None,
    since_ts: str | None,
) -> None:
    print(f"Fetching source channel history...")
    history = fetch_history_oldest_first(bot, SOURCE_CHANNEL, oldest_ts=since_ts)
    print(f"  fetched {len(history)} total messages from source")

    copied = 0
    skipped = 0
    already_done = 0
    for msg in history:
        source_ts = msg["ts"]
        if source_ts in manifest["messages"]:
            already_done += 1
            continue
        reason = should_skip(msg)
        if reason:
            manifest["skipped"][source_ts] = reason
            save_manifest(manifest)
            skipped += 1
            continue

        author = resolve_author(msg, user_cache)
        text = build_post_text(msg, include_reactions=True)
        try:
            new_ts = post_impersonated(bot, DEST_CHANNEL, text, author)
        except SlackApiError as e:
            err = e.response["error"]
            if err == "not_in_channel":
                sys.exit("ERROR: bot was removed from DEST during run. Re-add and re-run; manifest will resume.")
            if err == "restricted_action":
                sys.exit("ERROR: DEST has posting permissions that exclude the bot. Adjust and re-run.")
            raise

        manifest["messages"][source_ts] = {
            "author_slack_id": msg.get("user", ""),
            "author_display": author["display_name"],
            "new_ts": new_ts,
            "files": [],
            "deleted": False,
            "replies": {},
        }
        save_manifest(manifest)
        copied += 1

        if limit is not None and copied >= limit:
            print(f"  --limit {limit} reached; stopping")
            break

    print(f"Root copy summary: copied={copied} already_done={already_done} skipped={skipped}")
```

Update `cmd_copy`:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    manifest = load_or_init_manifest()
    save_manifest(manifest)
    print(f"Manifest loaded: {len(manifest['messages'])} root messages already copied.")
    since_ts = parse_since(args.since)
    copy_root_messages(bot, user_cache, manifest, args.limit, since_ts)
```

- [ ] **Step 4: Smoke-test with --limit 3**

Run:
```bash
python scripts/migrate_announcements_general.py copy --limit 3
```

Expected: 3 messages appear in `#announcements-general-2` (`C0B2VN1LU11`), each with the original author's name + avatar + APP badge, italic timestamp, original body, reaction footer if any.

Open Slack and **manually inspect** the 3 copied messages:
- Author name matches original
- Avatar matches original (or default icon for deactivated users)
- APP badge visible
- Timestamp on the first line reads like the original posting date
- Body text preserved (mentions, links, channel refs all intact)
- Reaction footer shows correct emoji + counts on root messages

- [ ] **Step 5: Test resumability**

Run the same command again:
```bash
python scripts/migrate_announcements_general.py copy --limit 3
```

Expected output: `already_done=3 copied=0 skipped=0`. No new messages in Slack.

- [ ] **Step 6: Clean up test posts before continuing**

Manually delete the 3 test posts in Slack and reset manifest:
```bash
rm scripts/output/migration_manifest.json
```

(Or leave them — they're real history and will be there when we run the full copy anyway. Reset only if you saw something wrong in the verification.)

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: implement root-message copy with skip filtering and resumability"
```

---

## Task 7: Copy phase — thread replies

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Extend the copy loop so each root message also pulls and copies its threaded replies under the new root ts.

- [ ] **Step 1: Add the thread-reply fetch and copy logic**

Add to `scripts/migrate_announcements_general.py`:

```python
def fetch_replies(bot: WebClient, channel: str, thread_ts: str) -> list[dict]:
    """Fetch all replies in a thread (excluding the root). Oldest-first."""
    replies: list[dict] = []
    cursor = None
    while True:
        params = {"channel": channel, "ts": thread_ts, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        resp = bot.conversations_replies(**params)
        for r in resp.get("messages", []):
            if r.get("ts") == thread_ts:
                continue  # skip the duplicated root
            replies.append(r)
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    # API already returns oldest-first for replies, but be explicit
    replies.sort(key=lambda r: float(r["ts"]))
    return replies


def copy_thread_replies(
    bot: WebClient,
    user_cache: dict[str, dict],
    manifest: dict,
    source_root_ts: str,
    new_root_ts: str,
) -> int:
    """Copy all replies of source_root_ts under new_root_ts. Returns count copied."""
    replies = fetch_replies(bot, SOURCE_CHANNEL, source_root_ts)
    copied = 0
    for reply in replies:
        source_reply_ts = reply["ts"]
        entry = manifest["messages"][source_root_ts]
        if source_reply_ts in entry["replies"]:
            continue  # already done
        reason = should_skip(reply)
        if reason:
            manifest["skipped"][source_reply_ts] = reason
            save_manifest(manifest)
            continue
        author = resolve_author(reply, user_cache)
        text = build_post_text(reply, include_reactions=False)
        new_reply_ts = post_impersonated(bot, DEST_CHANNEL, text, author, thread_ts=new_root_ts)
        entry["replies"][source_reply_ts] = {"new_ts": new_reply_ts, "deleted": False}
        save_manifest(manifest)
        copied += 1
    return copied
```

- [ ] **Step 2: Call copy_thread_replies from copy_root_messages**

Modify `copy_root_messages` — replace the line `manifest["messages"][source_ts] = {...}` block + `copied += 1` with:

```python
        manifest["messages"][source_ts] = {
            "author_slack_id": msg.get("user", ""),
            "author_display": author["display_name"],
            "new_ts": new_ts,
            "files": [],
            "deleted": False,
            "replies": {},
        }
        save_manifest(manifest)
        copied += 1

        if msg.get("reply_count", 0) > 0:
            reply_count = copy_thread_replies(bot, user_cache, manifest, source_ts, new_ts)
            if reply_count:
                print(f"  copied {reply_count} replies under {source_ts}")
```

- [ ] **Step 3: Smoke-test with --limit 5 (likely to include at least one threaded root)**

Run:
```bash
rm -f scripts/output/migration_manifest.json
python scripts/migrate_announcements_general.py copy --limit 5
```

Expected: 5 root messages copied, plus any threaded replies under them. In Slack, threads should nest correctly under their copied roots with the same author impersonation.

- [ ] **Step 4: Inspect replies in Slack**

For at least one copied thread:
- Click the thread in DEST
- Verify replies appear with original author names and timestamps
- Verify replies do NOT have a reaction footer (root only)
- Verify reply ordering matches original (oldest to newest)

- [ ] **Step 5: Clean up test posts**

Manually delete the test posts in Slack and:
```bash
rm scripts/output/migration_manifest.json
```

(Or leave if everything looked correct.)

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: copy threaded replies under impersonated roots"
```

---

## Task 8: Copy phase — file attachments

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Files require two steps: download from Slack with authenticated GET, then re-upload to DEST as a threaded reply under the impersonated text post (since `files.upload_v2` doesn't support impersonation).

- [ ] **Step 1: Add the file download helper**

Add to `scripts/migrate_announcements_general.py`:

```python
import requests  # add to imports at the top of the file


def download_file(file_meta: dict) -> Path | None:
    """Download a Slack file to FILES_DIR. Returns the local path, or None on failure."""
    file_id = file_meta["id"]
    name = file_meta.get("name", file_id)
    url = file_meta.get("url_private_download") or file_meta.get("url_private")
    if not url:
        print(f"    [warn] file {file_id} ({name}): no download URL")
        return None
    # Preserve extension when possible
    suffix = Path(name).suffix or ""
    local_path = FILES_DIR / f"{file_id}{suffix}"
    if local_path.exists():
        return local_path  # already downloaded — restart-safe
    headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
    try:
        r = requests.get(url, headers=headers, timeout=60)
    except requests.RequestException as e:
        print(f"    [warn] file {file_id} ({name}): download failed ({e})")
        return None
    if r.status_code != 200:
        print(f"    [warn] file {file_id} ({name}): HTTP {r.status_code}")
        return None
    local_path.write_bytes(r.content)
    return local_path
```

- [ ] **Step 2: Add the file re-upload helper**

Add:

```python
def upload_files_to_thread(
    bot: WebClient,
    channel: str,
    thread_ts: str,
    file_paths: list[Path],
) -> list[str]:
    """Upload local files as a threaded reply under thread_ts. Returns new Slack file IDs."""
    if not file_paths:
        return []
    file_uploads = [{"file": str(p), "filename": p.name} for p in file_paths]
    try:
        resp = bot.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            initial_comment="",
            file_uploads=file_uploads,
        )
    except SlackApiError as e:
        print(f"    [warn] file upload failed: {e.response['error']}")
        return []
    # files_upload_v2 returns either 'file' (single) or 'files' (multi)
    files = resp.get("files") or ([resp["file"]] if resp.get("file") else [])
    return [f["id"] for f in files]
```

- [ ] **Step 3: Wire file handling into copy_root_messages**

Modify the block in `copy_root_messages` that posts the message. Replace:

```python
        author = resolve_author(msg, user_cache)
        text = build_post_text(msg, include_reactions=True)
        try:
            new_ts = post_impersonated(bot, DEST_CHANNEL, text, author)
        except SlackApiError as e:
```

With:

```python
        author = resolve_author(msg, user_cache)
        files = msg.get("files", []) or []
        downloaded: list[Path] = []
        file_notes: list[str] = []
        for f in files:
            if f.get("mode") == "tombstone":
                file_notes.append(f"[file deleted: {f.get('name', f['id'])}]")
                continue
            local = download_file(f)
            if local is None:
                file_notes.append(f"[file no longer available: {f.get('name', f['id'])}]")
            else:
                downloaded.append(local)

        text = build_post_text(msg, include_reactions=True)
        if downloaded and not msg.get("text"):
            text = build_post_text({**msg, "text": "_(attachment below)_"}, include_reactions=True)
        if file_notes:
            text = text + "\n\n" + "\n".join(file_notes)

        try:
            new_ts = post_impersonated(bot, DEST_CHANNEL, text, author)
        except SlackApiError as e:
```

Then, after the `manifest["messages"][source_ts] = {...}` block but before `save_manifest`, add:

```python
        new_file_ids = upload_files_to_thread(bot, DEST_CHANNEL, new_ts, downloaded)
        manifest["messages"][source_ts]["files"] = new_file_ids
```

(Move the `save_manifest(manifest)` call to AFTER the file upload step so it captures the file IDs.)

The final structure of the root-copy block should be:

```python
        # (resolve_author, download files, build text — as above)
        try:
            new_ts = post_impersonated(bot, DEST_CHANNEL, text, author)
        except SlackApiError as e:
            err = e.response["error"]
            if err == "not_in_channel":
                sys.exit("ERROR: bot was removed from DEST during run. Re-add and re-run; manifest will resume.")
            if err == "restricted_action":
                sys.exit("ERROR: DEST has posting permissions that exclude the bot. Adjust and re-run.")
            raise

        new_file_ids = upload_files_to_thread(bot, DEST_CHANNEL, new_ts, downloaded)

        manifest["messages"][source_ts] = {
            "author_slack_id": msg.get("user", ""),
            "author_display": author["display_name"],
            "new_ts": new_ts,
            "files": new_file_ids,
            "deleted": False,
            "replies": {},
        }
        save_manifest(manifest)
        copied += 1

        if msg.get("reply_count", 0) > 0:
            reply_count = copy_thread_replies(bot, user_cache, manifest, source_ts, new_ts)
            if reply_count:
                print(f"  copied {reply_count} replies under {source_ts}")
```

- [ ] **Step 4: Smoke-test against a section of source channel known to have file attachments**

Pick a `--since` date that captures a few months of messages including known image posts. Run:

```bash
rm -f scripts/output/migration_manifest.json
python scripts/migrate_announcements_general.py copy --limit 10 --since 2024-12-01
```

Adjust `--since` as needed to land on a window with files. Inspect in Slack:
- Each root with a file has the impersonated text post followed by a bot-posted file in the thread
- Images render inline
- PDFs/other files show as downloadable attachments

- [ ] **Step 5: Verify `scripts/output/files/` has the downloaded originals**

Run:
```bash
ls -la scripts/output/files/ | head
```

Expected: one file per downloaded attachment, named `<file_id><ext>`.

- [ ] **Step 6: Add `requests` to imports if not already there**

Verify the top of the script has `import requests`. If not, add it.

Run:
```bash
python -c "import requests; print(requests.__version__)"
```

Expected: version string (requests is already a transitive dep of slack_sdk).

- [ ] **Step 7: Clean up test posts and commit**

Clean up if desired (delete test posts in Slack, `rm scripts/output/migration_manifest.json`).

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: download and re-upload file attachments as threaded replies"
```

---

## Task 9: Copy phase — pinned messages + transcript dump + completion

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Final touches on the copy phase: re-pin pinned messages in DEST, write the readable transcript dump for the welcome-post subagent, mark `copy_completed_at`.

- [ ] **Step 1: Add pin discovery and re-pinning**

Add to `scripts/migrate_announcements_general.py`:

```python
def copy_pins(bot: WebClient, manifest: dict) -> None:
    """For each pinned source message that was copied, pin the new copy in DEST."""
    print("Copying pinned messages...")
    try:
        resp = bot.pins_list(channel=SOURCE_CHANNEL)
    except SlackApiError as e:
        print(f"  [warn] pins.list failed: {e.response['error']}")
        return
    pinned_ts = []
    for item in resp.get("items", []):
        msg = item.get("message")
        if msg and msg.get("ts"):
            pinned_ts.append(msg["ts"])
    manifest["pinned_source_ts"] = pinned_ts
    save_manifest(manifest)

    pinned_count = 0
    for ts in pinned_ts:
        entry = manifest["messages"].get(ts)
        if not entry:
            print(f"  [skip] pinned source ts {ts} was not copied (filtered out)")
            continue
        new_ts = entry["new_ts"]
        try:
            bot.pins_add(channel=DEST_CHANNEL, timestamp=new_ts)
            pinned_count += 1
        except SlackApiError as e:
            err = e.response["error"]
            if err == "already_pinned":
                pinned_count += 1
            else:
                print(f"  [warn] pins.add failed for new_ts {new_ts}: {err}")
    print(f"  pinned {pinned_count} messages in DEST")
```

- [ ] **Step 2: Add transcript dump**

Add:

```python
def write_transcript(bot: WebClient, user_cache: dict[str, dict], history: list[dict]) -> None:
    """Write a readable transcript of source channel content for the welcome-post subagent."""
    print(f"Writing transcript to {TRANSCRIPT_PATH}...")
    lines: list[str] = []
    for msg in history:
        if should_skip(msg):
            continue
        author = resolve_author(msg, user_cache)
        ts_str = format_timestamp_central(msg["ts"])
        text = msg.get("text", "")
        lines.append(f"[{ts_str}] {author['display_name']}: {text}")
        files = msg.get("files") or []
        if files:
            names = ", ".join(f.get("name", f["id"]) for f in files)
            lines.append(f"    [files: {names}]")
        if msg.get("reply_count", 0) > 0:
            replies = fetch_replies(bot, SOURCE_CHANNEL, msg["ts"])
            for r in replies:
                if should_skip(r):
                    continue
                r_author = resolve_author(r, user_cache)
                r_ts = format_timestamp_central(r["ts"])
                r_text = r.get("text", "")
                lines.append(f"    [{r_ts}] {r_author['display_name']} (reply): {r_text}")
    TRANSCRIPT_PATH.write_text("\n".join(lines))
    print(f"  wrote {len(lines)} lines")
```

- [ ] **Step 3: Wire pins, transcript, and completion timestamp into cmd_copy**

Update `copy_root_messages` to return the fetched history (so we can reuse it for the transcript). Change its signature and add `return history` at the end:

```python
def copy_root_messages(
    bot: WebClient,
    user_cache: dict[str, dict],
    manifest: dict,
    limit: int | None,
    since_ts: str | None,
) -> list[dict]:
    # ... existing implementation ...
    return history
```

Update `cmd_copy`:

```python
def cmd_copy(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    verify_channel_access(bot, DEST_CHANNEL, "DEST")
    probe_copy_scopes(bot)
    user_cache = build_user_cache(bot)
    manifest = load_or_init_manifest()
    save_manifest(manifest)
    print(f"Manifest loaded: {len(manifest['messages'])} root messages already copied.")
    since_ts = parse_since(args.since)
    history = copy_root_messages(bot, user_cache, manifest, args.limit, since_ts)

    # Only do the post-copy steps when the run was unlimited and complete
    if args.limit is None:
        copy_pins(bot, manifest)
        write_transcript(bot, user_cache, history)
        manifest["copy_completed_at"] = datetime.now(timezone.utc).isoformat()
        save_manifest(manifest)
        print(f"Copy phase complete. Manifest: {MANIFEST_PATH}")
    else:
        print(f"Limited run (--limit {args.limit}); pins/transcript/completion-stamp skipped.")
```

- [ ] **Step 4: Smoke-test the full copy phase**

Note: this is the FULL run. Only proceed once Tasks 1–8 are verified. Estimated time 30–60 minutes.

Run:
```bash
rm -f scripts/output/migration_manifest.json scripts/output/files/*
python scripts/migrate_announcements_general.py copy
```

Expected output ends with: `Copy phase complete. Manifest: scripts/output/migration_manifest.json`.

Verify:
- `scripts/output/migration_manifest.json` has `copy_completed_at` populated and `messages` is densely populated.
- `scripts/output/announcements_general_transcript.txt` exists and is readable.
- In Slack: `#announcements-general-2` now has all the history, impersonated, threaded, with files and pins. Scroll through and spot-check a sample.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: re-pin pinned messages, write transcript dump, mark copy complete"
```

---

## Task 10: Delete phase

**Files:**
- Modify: `scripts/migrate_announcements_general.py`

Implement the destructive phase. Dry-run by default, requires `--no-dry-run` plus interactive `yes` to actually delete. Refuses to run if copy didn't finish.

- [ ] **Step 1: Add delete-list builder**

Add to `scripts/migrate_announcements_general.py`:

```python
def build_delete_list(manifest: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (reply_pairs, roots) pending deletion.

    reply_pairs: list of (root_ts, reply_ts) pairs, oldest reply_ts first.
    roots: list of root_ts, oldest first.
    Both filtered to entries with deleted == False.
    Replies are returned first so callers delete them before roots, which
    avoids leaving orphaned 'thread of deleted message' artifacts in Slack.
    """
    reply_pairs: list[tuple[str, str]] = []
    roots: list[str] = []
    for root_ts, entry in manifest["messages"].items():
        if not entry.get("deleted"):
            roots.append(root_ts)
        for reply_ts, reply in entry.get("replies", {}).items():
            if not reply.get("deleted"):
                reply_pairs.append((root_ts, reply_ts))
    reply_pairs.sort(key=lambda p: float(p[1]))
    roots.sort(key=lambda ts: float(ts))
    return reply_pairs, roots
```

- [ ] **Step 2: Add the deletion loop**

Add:

```python
def delete_from_source(user: WebClient, manifest: dict) -> None:
    reply_pairs, roots = build_delete_list(manifest)
    print(f"Deleting {len(reply_pairs)} replies, then {len(roots)} roots from {SOURCE_CHANNEL}...")

    # Replies first
    deleted = 0
    failed = 0
    for root_ts, reply_ts in reply_pairs:
        try:
            user.chat_delete(channel=SOURCE_CHANNEL, ts=reply_ts)
            manifest["messages"][root_ts]["replies"][reply_ts]["deleted"] = True
            save_manifest(manifest)
            deleted += 1
        except SlackApiError as e:
            err = e.response["error"]
            if err == "message_not_found":
                manifest["messages"][root_ts]["replies"][reply_ts]["deleted"] = True
                save_manifest(manifest)
                deleted += 1
            else:
                print(f"  [warn] reply {reply_ts} failed: {err}")
                failed += 1

    # Then roots
    for root_ts in roots:
        try:
            user.chat_delete(channel=SOURCE_CHANNEL, ts=root_ts)
            manifest["messages"][root_ts]["deleted"] = True
            save_manifest(manifest)
            deleted += 1
        except SlackApiError as e:
            err = e.response["error"]
            if err == "message_not_found":
                manifest["messages"][root_ts]["deleted"] = True
                save_manifest(manifest)
                deleted += 1
            else:
                print(f"  [warn] root {root_ts} failed: {err}")
                failed += 1

    print(f"Delete summary: deleted={deleted} failed={failed}")
```

- [ ] **Step 3: Wire up cmd_delete with safety gates**

Replace `cmd_delete`:

```python
def cmd_delete(args: argparse.Namespace) -> None:
    bot = get_bot_client()
    user = get_user_client()
    print(f"Verifying channel access...")
    verify_channel_access(bot, SOURCE_CHANNEL, "SOURCE")
    probe_delete_scopes(bot, user)
    manifest = load_or_init_manifest()
    if manifest.get("copy_completed_at") is None:
        sys.exit("ERROR: manifest.copy_completed_at is null — copy phase did not finish. Run copy without --limit first.")
    if manifest.get("channel_from") != SOURCE_CHANNEL:
        sys.exit(f"ERROR: manifest channel_from {manifest.get('channel_from')} != configured SOURCE {SOURCE_CHANNEL}")

    reply_pairs, roots = build_delete_list(manifest)
    print(f"Pending deletes: {len(reply_pairs)} replies, {len(roots)} root messages in {SOURCE_CHANNEL}.")

    if not args.no_dry_run:
        print("Dry-run only (default). Pass --no-dry-run to actually delete.")
        return

    print(f"\nThis will permanently delete {len(reply_pairs) + len(roots)} messages from {SOURCE_CHANNEL}.")
    print("Type 'yes' to confirm:")
    confirm = input().strip()
    if confirm != "yes":
        sys.exit("Aborted.")

    delete_from_source(user, manifest)
    print(f"Delete phase complete.")
```

- [ ] **Step 4: Test the dry-run gate**

Run:
```bash
python scripts/migrate_announcements_general.py delete
```

Expected: prints counts, says "Dry-run only (default).", does NOT delete anything. Verify in Slack that source channel is unchanged.

- [ ] **Step 5: Test the no-completion gate by tampering**

Temporarily corrupt the manifest's `copy_completed_at`:

```bash
python -c "import json; m=json.load(open('scripts/output/migration_manifest.json')); m['copy_completed_at']=None; json.dump(m, open('scripts/output/migration_manifest.json','w'))"
python scripts/migrate_announcements_general.py delete
```

Expected: exits with `ERROR: manifest.copy_completed_at is null ...`.

Restore by re-running copy (it will pick up where it left off and write the timestamp) — or manually set it back:

```bash
python -c "import json, datetime; m=json.load(open('scripts/output/migration_manifest.json')); m['copy_completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(m, open('scripts/output/migration_manifest.json','w'))"
```

- [ ] **Step 6: Test the confirmation prompt**

Run with `--no-dry-run`, but type `no` at the prompt:

```bash
echo "no" | python scripts/migrate_announcements_general.py delete --no-dry-run
```

Expected: prints `Aborted.` and exits without deleting.

- [ ] **Step 7: Commit (do NOT run actual deletion yet)**

```bash
git add scripts/migrate_announcements_general.py
git commit -m "feat: implement delete phase with dry-run, confirmation, and safety gates"
```

---

## Task 11: End-to-end operational verification

This task is not code — it's the actual one-time execution of the script and the documented manual operational steps. It assumes Tasks 1–10 are committed and Phase B of the spec has been spot-checked.

- [ ] **Step 1: Confirm prerequisites with the user before any destructive action**

Ask the user to confirm:
1. They have spot-checked the dest channel after the full copy run (Task 9 Step 4).
2. They have run the welcome-post subagent against the transcript and have a `welcome_draft.md` they're happy with.
3. They are ready to proceed with the destructive delete.

If any answer is "no", pause here.

- [ ] **Step 2: Run the dry-run delete one more time**

```bash
python scripts/migrate_announcements_general.py delete
```

Expected: prints the count of pending deletes. Sanity-check the count looks roughly equal to the number of messages copied.

- [ ] **Step 3: Run the actual delete**

```bash
python scripts/migrate_announcements_general.py delete --no-dry-run
```

Type `yes` at the prompt. Expect 30–60 minutes for completion. Watch the output for any `[warn]` lines and note their ts values for manual follow-up.

- [ ] **Step 4: Verify the source channel is empty**

Open `#announcements-general` (`C02J4GMLMU4`) in Slack. Confirm it is empty (or only has any messages flagged in Step 3 warnings).

- [ ] **Step 5: Hand off to manual operational steps (Phases E and F of the spec)**

Print/share with the user the remaining manual checklist from the spec:
- E1. Rename `C02J4GMLMU4` → `#welcome-to-tcsc`
- E2. Rename `C0B2VN1LU11` → `#announcements-general`
- E3. Post + pin the welcome message in `#welcome-to-tcsc`
- E4. Settings → Posting permissions → admins only on `#welcome-to-tcsc`
- E5. Spot-check via Slack admin "view as another member"
- F. Resume the channel-sync redesign rollout

- [ ] **Step 6: Final commit (no-op if no code changed)**

```bash
git status
```

If there are uncommitted changes (e.g. tweaks during real-run), commit them:

```bash
git add scripts/migrate_announcements_general.py
git commit -m "chore: post-run tweaks to migration script"
```

If nothing changed, this task is done.

---

## Spec coverage check

Mapping spec sections to plan tasks (verified during self-review):

| Spec section | Task(s) |
|---|---|
| Architecture / file layout | Task 1 |
| Channels | Task 1 (constants), Task 2 (verification) |
| CLI | Task 1 |
| Attribution / impersonation | Task 3 (resolver), Task 6 (post helper) |
| Copy phase data flow | Tasks 6, 7, 8, 9 |
| Message format | Task 4 |
| Mentions / channel refs / pings | Task 4 (preserved as-is; no transformation) |
| Delete phase data flow | Task 10 |
| Manifest schema | Task 5 (I/O), Tasks 6/7/8/9 (writes), Task 10 (reads) |
| Welcome post (separate concern) | Out of plan scope — Task 11 references it as a prerequisite gate |
| Error handling | Tasks 6 (not_in_channel, restricted_action), 8 (file failures), 10 (message_not_found idempotent), 5 (manifest corruption) |
| Operational sequence | Task 11 (executes Phases B and D; Phases A, C, E, F remain manual) |
| Testing strategy | Embedded throughout — every code task ends with a real-Slack verification step |
| Edge cases | Task 3 (deactivated users), Task 4 (custom emoji), Task 8 (deleted/too-large files), Tasks 6/9 (pinned-but-skipped messages) |
| Rollback | Out of plan scope — covered by manifest design (Task 5) and operational documentation in the spec |
