"""Probe whether we have the Slack scopes needed for the channel migration.

Tests in TEST_CHANNEL = C0B2VN1LU11 (#announcements-general-2):
  1. Bot can post a message
  2. Bot can post with username/icon_url impersonation (chat:write.customize)
  3. User token can delete the bot's message (chat:write user scope, admin power)
  4. Bot can delete its own message (chat:write bot scope)
"""

import os
import sys
import time

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

TEST_CHANNEL = "C0B2VN1LU11"

bot_token = os.environ["SLACK_BOT_TOKEN"]
user_token = os.environ["SLACK_USER_TOKEN"]

bot = WebClient(token=bot_token)
user = WebClient(token=user_token)


def header(s: str) -> None:
    print(f"\n=== {s} ===")


def show(ok: bool, label: str, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


# --- Auth introspection ---
header("auth.test (bot)")
try:
    bot_auth = bot.auth_test()
    print(f"  team={bot_auth['team']} user={bot_auth['user']} bot_id={bot_auth.get('bot_id')}")
except SlackApiError as e:
    print(f"  ERROR: {e.response['error']}")
    sys.exit(1)

header("auth.test (user)")
try:
    user_auth = user.auth_test()
    print(f"  team={user_auth['team']} user={user_auth['user']} user_id={user_auth.get('user_id')}")
except SlackApiError as e:
    print(f"  ERROR: {e.response['error']}")
    sys.exit(1)

# --- Test 1: bot can post normally ---
header("Test 1: bot.chat.postMessage (plain)")
plain_ts = None
try:
    r = bot.chat_postMessage(channel=TEST_CHANNEL, text="[probe] plain bot post — will be deleted")
    plain_ts = r["ts"]
    show(True, "bot can post", f"ts={plain_ts}")
except SlackApiError as e:
    show(False, "bot post failed", e.response["error"])

# --- Test 2: bot can impersonate (chat:write.customize) ---
header("Test 2: bot.chat.postMessage (username + icon_url impersonation)")
impersonated_ts = None
try:
    r = bot.chat_postMessage(
        channel=TEST_CHANNEL,
        text="[probe] impersonated post — will be deleted",
        username="Migration Probe",
        icon_emoji=":construction:",
    )
    impersonated_ts = r["ts"]
    show(True, "impersonation works (chat:write.customize present)", f"ts={impersonated_ts}")
except SlackApiError as e:
    err = e.response["error"]
    show(False, "impersonation failed", err)
    if err == "missing_scope":
        needed = e.response.get("needed", "?")
        print(f"    needed scope: {needed}")

# --- Test 3: user token deletes bot's message (admin power) ---
header("Test 3: user.chat.delete on bot's plain message (admin chat:write)")
if plain_ts:
    time.sleep(0.5)
    try:
        user.chat_delete(channel=TEST_CHANNEL, ts=plain_ts)
        show(True, "user token deleted bot's message (admin power confirmed)")
        plain_ts = None
    except SlackApiError as e:
        err = e.response["error"]
        show(False, "user-token delete failed", err)
        if err == "missing_scope":
            print(f"    needed scope: {e.response.get('needed', '?')}")
else:
    show(False, "skipped (no plain message to delete)")

# --- Test 4: bot deletes its own (impersonated) message ---
header("Test 4: bot.chat.delete on bot's own impersonated message")
if impersonated_ts:
    time.sleep(0.5)
    try:
        bot.chat_delete(channel=TEST_CHANNEL, ts=impersonated_ts)
        show(True, "bot deleted its own impersonated message")
        impersonated_ts = None
    except SlackApiError as e:
        show(False, "bot self-delete failed", e.response["error"])

# --- Cleanup any leftovers ---
header("Cleanup")
for label, ts in [("plain", plain_ts), ("impersonated", impersonated_ts)]:
    if not ts:
        continue
    print(f"  Trying to clean up leftover {label} ts={ts}")
    for client_name, client in [("user", user), ("bot", bot)]:
        try:
            client.chat_delete(channel=TEST_CHANNEL, ts=ts)
            print(f"    cleaned via {client_name} token")
            break
        except SlackApiError as e:
            print(f"    {client_name} cleanup failed: {e.response['error']}")

print("\nDone.")
