"""Slack side of crews: read the speedy-group channel, launch one private channel per crew.

Launch is idempotent. Each crew's channel ID is stored on the draft, so running
it again creates nothing new and only invites members who are missing.
Not handled (v1): renaming a channel when a crew is renamed, archiving, and
removing people who moved to another crew after launch.
"""
import re

from slack_sdk.errors import SlackApiError

from app.models import SlackUser, User
from app.slack.client import get_slack_client

SPEEDY_CHANNEL = "C0ATRS011FA"  # #thots
SPEEDY_CHANNEL_NAME = "#thots"
CHANNEL_PREFIX = "crew-"


def channel_member_user_ids(channel_id=SPEEDY_CHANNEL):
    """(user ids of club members in the channel, count of Slack members with no user)."""
    uids = _members(get_slack_client(), channel_id)
    matched = (User.query.join(SlackUser, User.slack_user_id == SlackUser.id)
               .filter(SlackUser.slack_uid.in_(uids)).with_entities(User.id, SlackUser.slack_uid).all())
    return sorted(uid for uid, _ in matched), len(set(uids) - {s for _, s in matched})


def _members(client, channel_id):
    uids, cursor = [], None
    while True:
        resp = client.conversations_members(channel=channel_id, limit=200, cursor=cursor)
        uids += resp.get("members", [])
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return uids


def channel_name(crew_number, crew_name):
    """crew-<name as a Slack-safe slug>, or crew-<number> when the crew has no name."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", (crew_name or "").lower()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)
    return (CHANNEL_PREFIX + (slug or str(crew_number)))[:80].rstrip("-_")


def launch_plan(draft, crews):
    """One row per crew: channel name, existing channel id, members with and without Slack."""
    user_ids = [m["user_id"] for crew in crews for m in crew]
    slack_ids = dict(User.query.join(SlackUser, User.slack_user_id == SlackUser.id)
                     .filter(User.id.in_(user_ids)).with_entities(User.id, SlackUser.slack_uid).all())
    channels = draft.crew_channels or {}
    plan = []
    for n, crew in enumerate(crews, start=1):
        stored = channels.get(str(n)) or {}
        linked = {slack_ids[m["user_id"]]: m["name"] for m in crew if slack_ids.get(m["user_id"])}
        plan.append({
            "crew": n, "name": stored.get("name") or channel_name(n, draft.crew_names.get(str(n))),
            "channel_id": stored.get("id"), "invite": list(linked), "people": linked,
            "no_slack": [m["name"] for m in crew if not slack_ids.get(m["user_id"])],
        })
    return plan


def _error(e):
    return e.response.get("error", "unknown_error") if isinstance(e, SlackApiError) else str(e)


def _create(client, name, year):
    """Create the private channel; on name_taken, try once more with the season year."""
    try:
        return client.conversations_create(name=name, is_private=True)["channel"]
    except SlackApiError as e:
        if _error(e) != "name_taken":
            raise
        return client.conversations_create(name=f"{name[:75]}-{year}", is_private=True)["channel"]


def _invite(client, channel_id, missing):
    """Invite in one call. force=True keeps going past bad users; returns {slack_uid: error}."""
    try:
        resp = client.conversations_invite(channel=channel_id, users=",".join(missing), force=True)
    except SlackApiError as e:
        resp = e.response
        if not resp.get("errors"):
            return {uid: _error(e) for uid in missing}
    return {err.get("user"): err.get("error") for err in resp.get("errors") or []}


def launch(draft, crews, year):
    """Create missing channels and invite missing members. Stores channel ids on the draft.

    Returns one result per crew: {crew, name, channel_id, created, invited, already,
    failed {slack_uid: error}, no_slack, error}. One crew failing never stops the rest.
    """
    client = get_slack_client()
    channels = dict(draft.crew_channels or {})
    results = []
    for row in launch_plan(draft, crews):
        result = {**row, "created": False, "invited": 0, "already": 0, "failed": {}, "error": None}
        try:
            if not row["channel_id"]:
                channel = _create(client, row["name"], year)
                result.update(channel_id=channel["id"], name=channel["name"], created=True)
                channels[str(row["crew"])] = {"id": channel["id"], "name": channel["name"]}
                draft.crew_channels = dict(channels)  # saved even if a later crew fails
            present = set(_members(client, result["channel_id"]))
            missing = [uid for uid in row["invite"] if uid not in present]
            result["already"] = len(row["invite"]) - len(missing)
            if missing:
                failed = _invite(client, result["channel_id"], missing)
                result["already"] += sum(1 for err in failed.values() if err == "already_in_channel")
                result["failed"] = {uid: err for uid, err in failed.items() if err != "already_in_channel"}
                result["invited"] = len(missing) - len(failed)
        except Exception as e:  # rate limit after retries, deleted channel, missing scope
            result["error"] = _error(e)
        results.append(result)
    return results
