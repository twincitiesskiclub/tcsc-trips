# #announcements-general Migration

**Date:** 2026-05-11
**Status:** Design approved, ready to plan
**Stakeholders:** Rob

## Problem

`#announcements-general` (Slack channel ID `C02J4GMLMU4`) is the original "general" channel that every workspace member is auto-joined to. Slack does not allow it to be archived, made private, or removed — the channel exists in perpetuity as a public channel that all members can see.

This conflicts with the channel-sync redesign (see `2026-04-24-channel-sync-redesign-design.md`), which requires `#announcements-general` to be **private** and **members-only** so that alumni / single-channel-guest tiers don't see member-only announcements.

The pragmatic workaround:

1. Create a new private channel and treat it as the real `#announcements-general` going forward (already done out of band — `C0B2VN1LU11`, currently named `#announcements-general-2`).
2. **Migrate the conversation history** from the old public channel to the new private channel, preserving author identity, threading, reactions, and attachments.
3. Delete all messages from the old channel.
4. Rename the old channel to `#welcome-to-tcsc`, post a single pinned welcome message, lock down posting.

This spec defines steps 2 and 3 — the one-time migration script. The renames, welcome post, and posting lockdown are manual operational steps done in the Slack UI.

## Design

### Architecture

A single new standalone script at `scripts/migrate_announcements_general.py`, following the same pattern as the existing `scripts/extract_channel_history.py`:

- No Flask dependency.
- Reads `SLACK_BOT_TOKEN` and `SLACK_USER_TOKEN` from `.env` via `python-dotenv`.
- Uses `slack_sdk.WebClient` directly with `RateLimitErrorRetryHandler(max_retry_count=5)`.
- Output written to `scripts/output/` (already gitignored).

File layout:

```
scripts/
  migrate_announcements_general.py
  probe_migration_scopes.py             # already created; kept as diagnostic
  output/                               # gitignored
    migration_manifest.json             # restart-safe state, source-of-truth
    announcements_general_transcript.txt  # readable dump for subagent input
    files/                              # downloaded originals awaiting re-upload
```

### Channels

The script operates entirely on channel IDs, not names. Names will change during the rollout, IDs do not.

| Variable | Channel ID | Current name (at script run time) | Final name (post-rollout) |
|---|---|---|---|
| `SOURCE_CHANNEL` | `C02J4GMLMU4` | `#announcements-general` | `#welcome-to-tcsc` |
| `DEST_CHANNEL` | `C0B2VN1LU11` | `#announcements-general-2` | `#announcements-general` |

Verification at startup calls `conversations.info` on both IDs and confirms the bot is a member of both. It does **not** assert anything about the current channel name — too fluid during this transition.

### CLI

Two separate subcommands. No automatic transition from copy to delete.

```bash
# Copy phase (idempotent, restart-safe, default behavior reads from manifest to resume)
python scripts/migrate_announcements_general.py copy [--limit N] [--since YYYY-MM-DD]

# Delete phase (default = dry-run, must pass --no-dry-run to actually delete)
python scripts/migrate_announcements_general.py delete [--no-dry-run]
```

Flags:

- `--limit N` — copy only the oldest N root messages (plus their threads). Used for the initial smoke test.
- `--since YYYY-MM-DD` — copy only messages on or after this date. Default: no lower bound (copy everything).
- `--no-dry-run` — required on `delete` to actually issue `chat.delete` calls. Default is dry-run preview.

### Attribution: bot impersonates the original author

Verified in `probe_migration_scopes.py`: the bot has the `chat:write.customize` scope, which allows `chat.postMessage` to pass `username` and `icon_url` (or `icon_emoji`) per call. The resulting message renders with the impersonated user's name and avatar, plus a small `APP` badge that Slack appends automatically and that cannot be suppressed.

For this migration the `APP` badge is a feature, not a bug — it signals that the message is a re-posted archive rather than a fresh post, while still preserving who wrote it.

Author lookup precedence:

1. `users.list` cached map of `{slack_uid: {display_name, real_name, image_72}}` (fetched once at startup)
2. If user not in cache (deactivated, removed from workspace), fall back to `msg.user_profile.display_name` and `msg.user_profile.image_72` which Slack embeds in the message payload
3. If both missing, use `"Former member"` with a default `icon_emoji=":ghost:"` and continue without aborting

### Copy phase: data flow

```
1. Verify SOURCE and DEST channels exist and bot is a member of both.
2. Run startup probe: post an impersonated probe message in DEST, verify it
   appears, delete it. Confirms chat:write, chat:write.customize, and bot
   membership in DEST. Abort with scope guidance if it fails.
3. Fetch users.list once → build user cache for impersonation.
4. Load (or initialize) scripts/output/migration_manifest.json.
5. Page through conversations.history on SOURCE (limit=200, cursor, oldest
   first via reversal — Slack returns newest-first).
6. For each root message:
   - SKIP if any of:
       - subtype indicates a system event (channel_join, channel_leave,
         channel_name, channel_topic, channel_purpose, pinned_item, etc.)
       - msg.bot_id is set OR subtype == "bot_message"
       - source ts already present in manifest.messages
     (Skipped messages are recorded in manifest.skipped with the reason.)
   - Else:
     a. Resolve author from cache or msg.user_profile fallback.
     b. Download files (msg.files): authenticated GET of url_private_download
        using SLACK_BOT_TOKEN as bearer. Saved to scripts/output/files/.
     c. Build formatted text:
          *<formatted timestamp>*
          <original text, preserving Slack mention/channel/URL syntax>
          <reaction footer if reactions exist — only on root>
     d. If files exist:
          - chat.postMessage with username/icon_url, text=formatted
          - files.upload_v2 with channels=DEST, thread_ts=<new_ts>,
            initial_comment="" (files appear as bot-posted threaded reply
            since files.upload_v2 does not support impersonation)
        Else:
          - chat.postMessage with username/icon_url, text=formatted
     e. Append {source_ts: {new_ts, author, files, replies: {}}} to manifest
        and flush to disk.
   - Then if msg.reply_count > 0:
     f. conversations.replies(channel=SOURCE, ts=source_ts), paginate.
     g. For each reply (skipping the duplicated root, skipping system/bot
        subtypes by the same rules as step 6):
          - Resolve author
          - Build formatted text (NO reaction footer for replies)
          - chat.postMessage with thread_ts=<new_ts of root>, username,
            icon_url
     h. Record each reply ts → new_ts in manifest.messages[root].replies
        and flush.
7. Pinned messages: pins.list on SOURCE → for each ts that has a manifest
   entry, pins.add on DEST with the corresponding new_ts.
8. Write the human/subagent-readable transcript dump (same format as
   extract_channel_history.py).
9. Set manifest.copy_completed_at and print summary: messages copied,
   threads copied, files re-uploaded, pinned, skipped (with categorized
   reasons).
```

**Why oldest-first:** Threads attach cleanly (root must exist before replies reference its new ts), and the new channel reads top-down like the original.

**Rate limiting:** `RateLimitErrorRetryHandler(max_retry_count=5)` plus an explicit `time.sleep(0.3)` between `chat.postMessage` calls to stay below Tier 4 burst. Expect 30–60 minutes for a full channel copy.

### Message format

Concrete example. A message originally written by Hannah Delker at 11:02 AM on 2026-04-24 with 3 reactions (👍 ×2, 😂 ×1) becomes:

> *(avatar: Hannah's)* **Hannah Delker** `APP`
> *Apr 24, 2026 11:02 AM*
> @rob is announcements-general supposed to be a public channel? It's showing up with a # for me right now
>
> 👍 2 · 😂 1

Format specifics:

- **Header line** is rendered by Slack from `username` + `icon_url` + the `APP` badge (automatic).
- **Italic timestamp line** is the first line of the message body. Format: `*MMM D, YYYY h:MM AM/PM*` in US Central. Lets readers see when the message was originally posted vs. when the bot re-posted it.
- **Body text** is the original `msg.text` unmodified — Slack mention syntax (`<@U...>`), channel syntax (`<#C...|name>`), broadcast (`<!channel>`, `<!here>`), URL syntax (`<https://...|label>`) all left intact. Slack will resolve and render them.
- **Reaction footer** (root messages only — replies do not get one): blank line, then `EMOJI N · EMOJI N · ...`. Standard Slack emoji shortcodes (`:thumbsup:`) are converted to Unicode (👍) via a lookup table. Custom workspace emoji remain as `:custom_shortcode:` text. Custom emoji used in old reactions but no longer in the workspace will render as the plain `:shortcode:` text.

### Mentions, channel refs, and pings

The new `#announcements-general` (`C0B2VN1LU11`) is a private channel. At copy time, only the bot and Rob (plus any other admins Rob explicitly adds before the run) are members. Slack does not fire mention notifications for users who are not members of a private channel.

Therefore:

- `<@U123>` user mentions in copied content do **not** ping the mentioned users at post time (they aren't members yet).
- `<!channel>` / `<!here>` broadcasts at post time only ping current members of the destination channel — that's Rob + bot. Tolerable.
- After the channel-sync redesign rollout adds users to the new `#announcements-general`, they see the historical messages with mentions rendered correctly but receive no retroactive pings (Slack does not notify for messages posted before they joined).

`<#C02J4GMLMU4|announcements-general>` references in old content will resolve to the same channel ID after the manual rename, rendering as `#welcome-to-tcsc`. Slightly weird in historical context but accurate; not worth special handling.

### Delete phase: data flow

```
1. Load manifest. Abort if manifest.copy_completed_at is null.
2. Verify manifest.channel_from matches configured SOURCE_CHANNEL.
3. Run startup probe: post a bot message in SOURCE, delete it via user
   token. Confirms admin chat:write on the user token. Abort with scope
   guidance if it fails.
4. Build the delete list:
   - All reply ts where reply.deleted == false
   - All root ts where deleted == false
5. Print summary: "Will delete N root messages + M replies in
   C02J4GMLMU4". Stop here if dry-run (default).
6. If --no-dry-run: prompt for literal "yes" at stdin. Anything else aborts.
7. For each ts (replies first, then roots, oldest-first within each group):
   a. user.chat_delete(channel=SOURCE, ts=ts) using SLACK_USER_TOKEN
   b. On success: update manifest entry's deleted flag, flush to disk
   c. On failure:
      - message_not_found → treat as deleted, set flag true (idempotent)
      - rate_limited → SDK handler retries automatically
      - cant_delete_message → log, leave flag false, continue
      - other → log, leave flag false, continue
8. Final summary: deleted N, skipped M with reasons.
```

**Replies before roots:** Slack permits deleting a thread root with extant replies, but the replies become orphaned ("thread of a deleted message"). Deleting leaves first produces a clean channel.

**Pins:** No explicit unpinning. Deleting a message automatically removes it from pins.

### Manifest schema

```json
{
  "schema_version": 1,
  "channel_from": "C02J4GMLMU4",
  "channel_to":   "C0B2VN1LU11",
  "started_at":   "2026-05-12T10:00:00Z",
  "copy_completed_at": "2026-05-12T10:42:00Z",
  "messages": {
    "1700000000.123456": {
      "author_slack_id": "U02JS0R7ZG8",
      "author_display":  "Rob Rutscher",
      "new_ts":          "1778500000.001100",
      "files":           ["F012345"],
      "deleted":         false,
      "replies": {
        "1700000005.654321": {
          "new_ts":  "1778500000.001200",
          "deleted": false
        }
      }
    }
  },
  "pinned_source_ts": ["1700000000.123456"],
  "skipped": {
    "1699999999.000000": "subtype=channel_join",
    "1699999500.000000": "bot_message: Stripe"
  }
}
```

Manifest is flushed to disk after every successful API call to guarantee resumability. A corrupted manifest (unparseable JSON) causes a hard abort with instructions to rename the bad file and start fresh.

### Welcome post: separate concern

The welcome message that will be posted in the renamed `#welcome-to-tcsc` is **out of scope** for the migration script. The decoupling matters because drafting a good welcome post requires reading the existing channel content to capture the club's voice and concerns — and that reading would pollute the main agent's context.

The handoff is via the transcript file the script produces:

1. After the copy phase, `scripts/output/announcements_general_transcript.txt` contains the full readable history.
2. The user dispatches a separate subagent with:
   - The transcript file path
   - Project context (`CLAUDE.md`)
   - This spec for the "why" of the new channel structure
   - The channel-sync redesign spec for the tier model and final channel list
3. Subagent's deliverable: `scripts/output/welcome_draft.md`
4. User reviews/edits the draft and posts it manually in Slack after the renames.

### Error handling

| Failure | Behavior |
|---|---|
| Auth token expired or wrong | Startup probe fails, abort with clear error |
| Bot not a member of source or dest | `conversations.info` returns `not_in_channel`, abort with instruction to invite the bot |
| Missing scope (`chat:write.customize` etc.) | Startup probe fails, abort with the specific scope name from `response["needed"]` |
| Slack 5xx during a post | SDK retry handler covers; if exhausted, raise and abort. Re-run resumes from manifest. |
| Rate limited | SDK retry handler honors `Retry-After` |
| Network blip between two calls (e.g. post succeeded, manifest write didn't) | Worst case: one message is double-posted on resume. Acceptable for a one-time script. |
| Source message deleted between fetch and re-post | Skipped silently — won't appear in `conversations.history` on retry |
| File no longer available (404 on download) | Log; message text gets `[file no longer available]` appended; continue |
| File too large for re-upload | `files.upload_v2` returns error; log; message text gets `[file too large to migrate: <name>]`; continue |
| Deactivated user with no `user_profile` fallback | Use `"Former member"` + `:ghost:` icon_emoji; continue |
| Custom emoji not in workspace | Render as `:shortcode:` text in reaction footer; Slack renders it as plain text |
| `cant_delete_message` during delete phase | Log with ts, leave flag false, continue. Likely a Slack permission edge case worth manual follow-up. |
| Corrupted manifest JSON | Hard abort with rename-the-file instructions |
| `delete` invoked before `copy` completed (manifest.copy_completed_at is null) | Hard abort |
| `delete` invoked against a manifest whose channel_from doesn't match SOURCE_CHANNEL config | Hard abort |

**Explicitly not handled** (out of scope, do not exist in human-authored content):

- Slack `attachments` field (legacy webhook attachments)
- `blocks` field on user messages (Block Kit is bot-only)
- Cross-channel shares (`is_share`)
- Slack Connect / shared channels

### Operational sequence

```
PHASE A — Prep (manual)
  A1. Verify bot is in C02J4GMLMU4 (source). Already true; spot-check.
  A2. Add bot to C0B2VN1LU11 (dest). Only Rob + bot should be in the
      dest channel at migration time.
  A3. Decide whether any other admins should be in dest at copy time so
      they see the history immediately when it lands.

PHASE B — Migration script
  B1. python scripts/migrate_announcements_general.py copy --limit 5
      → spot-check the first 5 messages in dest channel
  B2. python scripts/migrate_announcements_general.py copy
      → full run; 30–60 minutes
  B3. Verify in Slack: scroll dest channel, check impersonation, threads,
      reactions, files
  B4. Investigate any surprising entries in manifest.skipped

PHASE C — Welcome post (subagent + manual)
  C1. Dispatch subagent with the transcript + context
  C2. Review/edit the draft

PHASE D — Destructive
  D1. python scripts/migrate_announcements_general.py delete
      → dry-run preview of counts
  D2. python scripts/migrate_announcements_general.py delete --no-dry-run
      → type "yes" at prompt; 30–60 minutes
  D3. Verify source channel is empty

PHASE E — Rename + lockdown (manual UI)
  E1. Rename C02J4GMLMU4 → #welcome-to-tcsc
  E2. Rename C0B2VN1LU11 → #announcements-general
  E3. Post + pin the welcome message in #welcome-to-tcsc
  E4. Settings → Posting permissions → "Specific people" → admins only
  E5. Spot-check via Slack admin "view as another member" tool

PHASE F — Channel sync rollout
  F1. Resume the broader rollout from
      docs/superpowers/specs/2026-04-24-channel-sync-redesign-design.md
```

**Order constraints:**

- B before C (subagent needs the transcript)
- B before D (can't delete what wasn't copied)
- C before E3
- D before E (don't delete from a mid-rename channel)
- E before F (channel sync resolves channels by name, needs final names)

### Testing strategy

No pytest unit tests. This is a one-time, side-effecty script against a live Slack tenant; mocking out enough of the Slack API to test meaningfully isn't worth it.

The script's safety comes from operational gates:

1. **Startup probes on every run** — `auth.test`, then an impersonation-and-delete probe in dest (for `copy`) or a post-and-delete probe in source via user token (for `delete`). Catches expired tokens and missing scopes before any real work begins.
2. **`--limit 5` smoke test** (operational gate B1) — first five messages get copied; eyeball them before full run.
3. **`delete` defaults to dry-run** (gate D1) — counts only, no API calls.
4. **Interactive `yes` confirmation** in destructive mode (gate D2).
5. **Manifest channel ID check** — `delete` refuses if the manifest's `channel_from` doesn't match the configured source ID.
6. **`copy_completed_at` gate** — `delete` refuses to run if the copy phase didn't finish cleanly.

The existing `scripts/probe_migration_scopes.py` remains in the tree as a diagnostic / documentation of what scopes are required and how they're verified.

### Edge cases

- **Deactivated authors:** Fall back to `msg.user_profile` embedded in message; if missing, use `"Former member"` + `:ghost:` icon.
- **Custom emoji in reactions:** Rendered as `:shortcode:` text. If the emoji still exists in the workspace, Slack auto-renders it; if not, it shows as plain text. Either way the count and identity of the emoji are preserved.
- **Edited messages:** Slack's `conversations.history` only returns the latest version. Edit history is lost. Acceptable.
- **Files-only messages (no text body):** Impersonated post gets `_(attachment below)_` as its body so the threaded file upload makes sense.
- **Pinned message that gets deleted from source between copy and delete phase:** Manifest already has the new_ts; pin already exists in dest; source delete is a no-op (message_not_found). No problem.
- **User running the script is removed from source channel mid-run:** `chat.delete` via user token fails; script logs and continues. Manual cleanup of remainder.
- **Mid-run bot removal from dest:** `chat.postMessage` returns `not_in_channel`. Hard abort with re-add instructions. Manifest preserves progress.
- **Slack workspace plan limitations on history retrieval:** TCSC is on a Pro plan (per existing usage of `users.list` etc. without 90-day limits). `conversations.history` returns full history. No special handling needed.

### Rollback

- **During copy phase:** Re-running picks up where it left off. To start over, delete `migration_manifest.json` and any partially-posted messages in dest manually.
- **After copy, before delete:** If the dest channel looks wrong, manually delete copied messages (the dest is private and lightly populated, so this is tractable for small mistakes). For large-scale rollback, write a one-off script that iterates `manifest.messages` and calls `chat.delete` on each `new_ts` from the dest channel.
- **After delete:** Deleted source messages are not recoverable via API. Slack workspace admin retention policy may allow restoration via Slack support, but treat the deletion as permanent for planning purposes. This is why phase B copying and phase D dry-runs exist.

## Out of scope

- Welcome message content (drafted by a separate subagent — see Section "Welcome post")
- Channel renames (manual, Slack UI)
- Posting permission lockdown on `#welcome-to-tcsc` (manual, Slack UI)
- Adding/removing users to/from the new `#announcements-general` (handled by the channel-sync redesign rollout)
- Updating any `slack_channels.yaml` config (handled by the channel-sync redesign rollout)
- Anything in the `app/` directory — this script is a one-time operation that does not touch the application code
