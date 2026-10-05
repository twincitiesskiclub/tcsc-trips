"""Crew channels in Slack. Slack is a fake here: nothing reaches the real workspace."""
from unittest.mock import patch

import pytest
from slack_sdk.errors import SlackApiError

from app.crews.models import CrewDraft
from app.crews.service import FIRST_SEED
from app.crews.slack import channel_name
from app.models import db


def test_channel_name_rule():
    assert channel_name(1, "Brave Badgers") == "crew-brave-badgers"
    assert channel_name(2, "  Swift   Swallows!! ") == "crew-swift-swallows"
    assert channel_name(3, "") == "crew-3"
    assert channel_name(4, None) == "crew-4"
    assert channel_name(5, "Über Ötters") == "crew-ber-tters"
    long = channel_name(6, "x" * 200)
    assert len(long) == 80 and long.startswith("crew-x")


class FakeSlack:
    """Just enough of conversations.* for a launch, with knobs for failures."""

    def __init__(self, taken=(), fail_create=(), bad_users=()):
        self.channels, self.taken, self.fail_create, self.bad_users = {}, set(taken), set(fail_create), set(bad_users)
        self.created, self.invite_calls = [], []

    def _err(self, error, **extra):
        raise SlackApiError(error, {"ok": False, "error": error, **extra})

    def conversations_create(self, name, is_private):
        assert is_private is True
        if name in self.fail_create:
            self._err("ratelimited")
        if name in self.taken or any(c["name"] == name for c in self.channels.values()):
            self._err("name_taken")
        cid = f"G{len(self.channels) + 1:03d}"
        self.channels[cid] = {"name": name, "members": {"UBOT"}}
        self.created.append(name)
        return {"ok": True, "channel": {"id": cid, "name": name}}

    def conversations_members(self, channel, limit, cursor=None):
        return {"ok": True, "members": sorted(self.channels[channel]["members"]), "response_metadata": {}}

    def conversations_invite(self, channel, users, force):
        self.invite_calls.append((channel, users.split(",")))
        errors = []
        for uid in users.split(","):
            if uid in self.bad_users:
                errors.append({"user": uid, "ok": False, "error": "user_not_found"})
            else:
                self.channels[channel]["members"].add(uid)
        if errors:
            self._err("user_not_found", errors=errors)
        return {"ok": True}


@pytest.fixture
def final_draft(admin_client, world):
    people = [("Ann", True), ("Ben", True), ("Cat", False), ("Dan", False), ("Eve", False)]
    world.people = {n: world.member(n, "Test", board=b, slack_uid=None if n == "Eve" else f"U{n.upper()}{world.tag}")
                    for n, b in people}
    db.session.commit()
    form = {"crews": "2", "board_rule": "on", **{f"level_{t}": "normal" for t in ("thot", "tenure", "gender", "ski", "age")}}
    admin_client.post(f"/admin/crews/season/{world.fall.id}/settings", data=form)
    admin_client.post(f"/admin/crews/season/{world.fall.id}/drafts")
    draft = CrewDraft.query.filter_by(season_id=world.fall.id, seed=FIRST_SEED).one()
    admin_client.post(f"/admin/crews/draft/{draft.id}", data={
        **{f"crew_{m['user_id']}": str(m["crew"]) for m in draft.members}, "name_1": "Brave Badgers"})
    admin_client.post(f"/admin/crews/draft/{draft.id}/final")
    return draft


def launch(admin_client, draft, fake):
    with patch("app.crews.slack.get_slack_client", return_value=fake):
        return admin_client.post(f"/admin/crews/draft/{draft.id}/launch").data.decode()


def test_launch_needs_a_final_draft(admin_client, final_draft):
    admin_client.post(f"/admin/crews/draft/{final_draft.id}/final")  # still final
    other = CrewDraft.query.filter(CrewDraft.season_id == final_draft.season_id,
                                   CrewDraft.id != final_draft.id).first()
    fake = FakeSlack()
    with patch("app.crews.slack.get_slack_client", return_value=fake):
        r = admin_client.post(f"/admin/crews/draft/{other.id}/launch", follow_redirects=True)
    assert b"Mark this draft as final" in r.data and fake.created == []


def test_confirm_page_lists_channels_counts_and_unlinked(admin_client, final_draft):
    fake = FakeSlack()
    with patch("app.crews.slack.get_slack_client", return_value=fake):
        html = admin_client.get(f"/admin/crews/draft/{final_draft.id}/launch").data.decode()
    assert "#crew-brave-badgers" in html and "#crew-2" in html
    assert "Eve Test" in html and "1 member can" in html
    assert fake.created == [] and fake.invite_calls == []  # the confirm page changes nothing


def test_launch_creates_private_channels_invites_and_stores_ids(admin_client, final_draft):
    fake = FakeSlack()
    html = launch(admin_client, final_draft, fake)
    assert fake.created == ["crew-brave-badgers", "crew-2"]
    db.session.refresh(final_draft)
    assert final_draft.crew_channels == {"1": {"id": "G001", "name": "crew-brave-badgers"},
                                         "2": {"id": "G002", "name": "crew-2"}}
    invited = set().union(*(c["members"] for c in fake.channels.values())) - {"UBOT"}
    assert len(invited) == 4  # Eve has no Slack account
    assert "Done. Every crew has its channel." in html and "Eve Test" in html


def test_second_launch_creates_nothing_and_invites_only_missing(admin_client, final_draft):
    fake = FakeSlack()
    launch(admin_client, final_draft, fake)
    fake.created.clear()
    fake.invite_calls.clear()
    html = launch(admin_client, final_draft, fake)
    assert fake.created == [] and fake.invite_calls == []
    assert "Invited 0" in html and ">New<" not in html
    # someone removed from a channel by hand gets invited back
    cid = "G001"
    gone = sorted(fake.channels[cid]["members"] - {"UBOT"})[0]
    fake.channels[cid]["members"].discard(gone)
    launch(admin_client, final_draft, fake)
    assert fake.invite_calls == [(cid, [gone])]


def test_name_taken_retries_with_the_season_year(admin_client, final_draft, world):
    fake = FakeSlack(taken={"crew-brave-badgers"})
    launch(admin_client, final_draft, fake)
    db.session.refresh(final_draft)
    assert final_draft.crew_channels["1"]["name"] == f"crew-brave-badgers-{world.fall.year}"


def test_one_crew_failing_does_not_stop_the_others(admin_client, final_draft, world):
    fake = FakeSlack(fail_create={"crew-brave-badgers"}, bad_users={f"U{n}{world.tag}" for n in ("ANN", "BEN", "CAT", "DAN")})
    html = launch(admin_client, final_draft, fake)
    db.session.refresh(final_draft)
    assert set(final_draft.crew_channels) == {"2"}
    assert "Stopped: ratelimited" in html and "1 crew had a problem" in html
    assert "user_not_found" in html  # crew 2 still ran its invites
    fake.fail_create.clear()
    launch(admin_client, final_draft, fake)
    db.session.refresh(final_draft)
    assert set(final_draft.crew_channels) == {"1", "2"}
