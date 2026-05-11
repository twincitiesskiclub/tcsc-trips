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

import requests
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
    """Build the impersonated post body: original text, then italic timestamp footer.

    For root messages (include_reactions=True), reactions are joined onto the
    same footer line as the timestamp, separated by ' · '. For thread replies,
    the footer is just the italic timestamp.
    """
    body = msg.get("text", "") or "_(no text)_"
    ts = f"*{format_timestamp_central(msg['ts'])}*"
    if include_reactions:
        reactions = build_reaction_footer(msg.get("reactions", []))
        footer = f"{ts} · {reactions}" if reactions else ts
    else:
        footer = ts
    return f"{body}\n\n{footer}"


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
            # Deactivated users still get cached — their messages reference them.
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


def parse_since(since: str | None) -> str | None:
    if not since:
        return None
    dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return str(dt.timestamp())


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


def copy_root_messages(
    bot: WebClient,
    user_cache: dict[str, dict],
    manifest: dict,
    limit: int | None,
    since_ts: str | None,
) -> list[dict]:
    print(f"Fetching source channel history...")
    history = fetch_history_oldest_first(bot, SOURCE_CHANNEL, oldest_ts=since_ts)
    print(f"  fetched {len(history)} total messages from source")

    copied = 0
    skipped = 0
    already_done = 0
    eligible = 0  # human messages seen (already_done + copied); limit applies to this
    for msg in history:
        source_ts = msg["ts"]

        # Fast-path: already processed (copied or skipped on a prior run)
        if source_ts in manifest["messages"] or source_ts in manifest["skipped"]:
            # Only count previously-copied messages toward the eligible limit, not
            # previously-skipped system messages, so --limit N stays consistent
            # across runs (run 2 with --limit 3 terminates at the same 3 messages).
            if source_ts in manifest["messages"]:
                already_done += 1
                eligible += 1
                if limit is not None and eligible >= limit:
                    print(f"  --limit {limit} reached; stopping")
                    break
            continue

        reason = should_skip(msg)
        if reason:
            manifest["skipped"][source_ts] = reason
            save_manifest(manifest)
            skipped += 1
            continue

        # Eligible human message — count it toward the limit before copying
        eligible += 1
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

        if limit is not None and eligible >= limit:
            print(f"  --limit {limit} reached; stopping")
            break

    print(f"Root copy summary: copied={copied} already_done={already_done} skipped={skipped}")
    return history


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


# Auth-class errors mean the user token is bad/expired. Continuing would just
# log N failures and waste the operator's time — hard-abort so they can refresh
# the cookie and resume from the manifest.
FATAL_DELETE_ERRORS = {
    "not_authed", "invalid_auth", "account_inactive",
    "token_revoked", "token_expired", "no_permission",
}


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
            elif err in FATAL_DELETE_ERRORS:
                sys.exit(f"ERROR: user token failed with {err!r} (auth/permission). Refresh and re-run; manifest will resume.")
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
            elif err in FATAL_DELETE_ERRORS:
                sys.exit(f"ERROR: user token failed with {err!r} (auth/permission). Refresh and re-run; manifest will resume.")
            else:
                print(f"  [warn] root {root_ts} failed: {err}")
                failed += 1

    print(f"Delete summary: deleted={deleted} failed={failed}")


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
