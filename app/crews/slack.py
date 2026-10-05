"""Slack side of crews: read the speedy-group channel, launch one private channel per crew.

Launch is idempotent. Each crew's channel ID is stored on the draft, so running
it again creates nothing new and only invites members who are missing.
Channel names follow crew names: Save and rerun both rename a channel whose
crew was renamed. Not handled (v1): archiving, and removing people who moved
to another crew after launch.
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


def _with_year(name, year):
    return f"{name[:75]}-{year}"


def _wanted(draft, n):
    return channel_name(n, draft.crew_names.get(str(n)))


def _in_line(draft, n, stored_name):
    """A channel named for its crew, or for its crew plus the year after a name_taken retry."""
    wanted = _wanted(draft, n)
    return stored_name in (wanted, _with_year(wanted, draft.season.year))


def launch_plan(draft, crews):
    """One row per crew: target channel name, current name and id if made, members with and without Slack."""
    user_ids = [m["user_id"] for crew in crews for m in crew]
    slack_ids = dict(User.query.join(SlackUser, User.slack_user_id == SlackUser.id)
                     .filter(User.id.in_(user_ids)).with_entities(User.id, SlackUser.slack_uid).all())
    channels = draft.crew_channels or {}
    plan = []
    for n, crew in enumerate(crews, start=1):
        stored = channels.get(str(n)) or {}
        current = stored.get("name")
        linked = {slack_ids[m["user_id"]]: m["name"] for m in crew if slack_ids.get(m["user_id"])}
        plan.append({
            "crew": n, "name": current if current and _in_line(draft, n, current) else _wanted(draft, n),
            "current": current, "channel_id": stored.get("id"), "invite": list(linked), "people": linked,
            "no_slack": [m["name"] for m in crew if not slack_ids.get(m["user_id"])],
        })
    return plan


def _error(e):
    return e.response.get("error", "unknown_error") if isinstance(e, SlackApiError) else str(e)


def _with_retry(call, name, year):
    """call(name); on name_taken, try once more with the season year."""
    try:
        return call(name)["channel"]
    except SlackApiError as e:
        if _error(e) != "name_taken":
            raise
        return call(_with_year(name, year))["channel"]


def _rename(client, draft, n):
    """Rename crew n's channel to match its crew name if it drifted. Updates draft.crew_channels."""
    stored = draft.crew_channels[str(n)]
    if _in_line(draft, n, stored["name"]):
        return False
    channel = _with_retry(lambda name: client.conversations_rename(channel=stored["id"], name=name),
                          _wanted(draft, n), draft.season.year)
    draft.crew_channels = {**draft.crew_channels, str(n): {"id": stored["id"], "name": channel["name"]}}
    return True


def rename_channels(draft):
    """After a Save: bring launched channels in line with crew names. Returns {crew: error}."""
    client, failed = None, {}
    for key in sorted(draft.crew_channels or {}, key=int):
        if _in_line(draft, int(key), draft.crew_channels[key]["name"]):
            continue
        client = client or get_slack_client()
        try:
            _rename(client, draft, int(key))
        except Exception as e:
            failed[int(key)] = _error(e)
    return failed


def _invite(client, channel_id, missing):
    """Invite in one call. force=True keeps going past bad users; returns {slack_uid: error}."""
    try:
        resp = client.conversations_invite(channel=channel_id, users=",".join(missing), force=True)
    except SlackApiError as e:
        resp = e.response
        if not resp.get("errors"):
            return {uid: _error(e) for uid in missing}
    return {err.get("user"): err.get("error") for err in resp.get("errors") or []}


def launch(draft, crews):
    """Create missing channels, rename drifted ones, invite missing members.

    Returns one result per crew: {crew, name, channel_id, created, renamed, rename_error,
    invited, already, failed {slack_uid: error}, no_slack, error}. One crew failing never stops the rest.
    """
    client = get_slack_client()
    year = draft.season.year
    results = []
    for row in launch_plan(draft, crews):
        n = row["crew"]
        result = {**row, "created": False, "renamed": False, "rename_error": None, "invited": 0, "already": 0,
                  "failed": {}, "error": None}
        try:
            if row["channel_id"]:
                try:
                    result["renamed"] = _rename(client, draft, n)
                except Exception as e:  # keep the old name, still invite
                    result["rename_error"] = _error(e)
            else:
                channel = _with_retry(lambda name: client.conversations_create(name=name, is_private=True),
                                      row["name"], year)
                result.update(channel_id=channel["id"], created=True)
                # saved even if a later crew fails
                draft.crew_channels = {**(draft.crew_channels or {}), str(n): {"id": channel["id"], "name": channel["name"]}}
            result["name"] = draft.crew_channels[str(n)]["name"]
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
