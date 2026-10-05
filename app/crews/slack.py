"""Slack side of crews. Today it only reads the speedy-group channel.

Creating one channel per crew (Mitchell does it by hand for now) belongs here
too: take a final CrewDraft, create the channels, invite members by their
slack_users.slack_uid.
"""
from app.models import SlackUser, User
from app.slack.client import get_slack_client

SPEEDY_CHANNEL = "C0ATRS011FA"  # #thots
SPEEDY_CHANNEL_NAME = "#thots"


def channel_member_user_ids(channel_id=SPEEDY_CHANNEL):
    """(user ids of club members in the channel, count of Slack members with no user)."""
    client = get_slack_client()
    uids, cursor = [], None
    while True:
        resp = client.conversations_members(channel=channel_id, limit=200, cursor=cursor)
        uids += resp.get("members", [])
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    matched = (User.query.join(SlackUser, User.slack_user_id == SlackUser.id)
               .filter(SlackUser.slack_uid.in_(uids)).with_entities(User.id, SlackUser.slack_uid).all())
    return sorted(uid for uid, _ in matched), len(set(uids) - {s for _, s in matched})
