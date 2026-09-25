from datetime import datetime, timezone

import pytest
from slack_sdk.errors import SlackApiError

from app.analytics.archive import import_channel, sync_recent, upsert_message
from app.analytics.models import SlackArchiveMessage

CH = "CTESTARCH1"


class FakeSlack:
    """Serves conversations.history/replies/reactions.get from dicts."""

    def __init__(self, history, replies=None, full_reactions=None):
        self.history = history            # list of raw messages, newest first
        self.replies = replies or {}      # parent ts -> list of raw replies (parent first, like Slack)
        self.full_reactions = full_reactions or {}
        self.calls = []

    def conversations_history(self, channel, limit=200, cursor=None, oldest=None, **_):
        self.calls.append(("history", cursor, oldest))
        msgs = [m for m in self.history if oldest is None or float(m["ts"]) >= float(oldest)]
        if cursor is None and len(msgs) > 1:   # force one pagination hop
            return {"ok": True, "messages": msgs[:1], "has_more": True,
                    "response_metadata": {"next_cursor": "page2"}}
        start = 1 if cursor == "page2" else 0
        return {"ok": True, "messages": msgs[start:], "has_more": False,
                "response_metadata": {"next_cursor": ""}}

    def conversations_replies(self, channel, ts, limit=200, cursor=None, **_):
        self.calls.append(("replies", ts))
        return {"ok": True, "messages": self.replies.get(ts, []),
                "response_metadata": {"next_cursor": ""}}

    def reactions_get(self, channel, timestamp, full=True, **_):
        self.calls.append(("reactions", timestamp))
        return {"ok": True, "message": {"ts": timestamp,
                                        "reactions": self.full_reactions[timestamp]}}


def _msg(ts, text="hello", **extra):
    return {"type": "message", "ts": ts, "user": "UFAKE0001", "text": text, **extra}


def _rows():
    return {m.ts: m for m in SlackArchiveMessage.query.filter_by(channel_id=CH).all()}


def test_import_pages_threads_and_truncated_reactions(db_session):
    big = [{"name": "white_check_mark", "count": 3, "users": ["UFAKE0001", "UFAKE0002"]}]
    full = [{"name": "white_check_mark", "count": 3,
             "users": ["UFAKE0001", "UFAKE0002", "UFAKE0003"]}]
    parent = _msg("1700000100.000100", reply_count=1, thread_ts="1700000100.000100", reactions=big)
    reply = _msg("1700000200.000200", text="merging tonight", thread_ts="1700000100.000100")
    client = FakeSlack([_msg("1700000300.000300"), parent],
                       replies={parent["ts"]: [parent, reply]},
                       full_reactions={parent["ts"]: full})
    stats = import_channel(client, CH)
    rows = _rows()
    assert stats["messages"] == 2 and stats["replies"] == 1 and stats["reactions_refetched"] == 1
    assert set(rows) == {"1700000100.000100", "1700000200.000200", "1700000300.000300"}
    assert stats["seen"] == set(rows)
    assert ("history", "page2", None) in client.calls
    assert rows["1700000200.000200"].thread_ts == "1700000100.000100"
    users = rows["1700000100.000100"].raw["reactions"][0]["users"]
    assert users == ["UFAKE0001", "UFAKE0002", "UFAKE0003"]
    assert rows["1700000100.000100"].posted_at == datetime.fromtimestamp(1700000100.0001, timezone.utc).replace(tzinfo=None)


def test_import_is_idempotent(db_session):
    client = FakeSlack([_msg("1700000400.000400")])
    import_channel(client, CH)
    import_channel(client, CH)
    assert SlackArchiveMessage.query.filter_by(channel_id=CH, ts="1700000400.000400").count() == 1


def test_sync_marks_deleted_and_updates_edits(db_session):
    now = datetime(2099, 1, 22, 12)
    t_keep, t_gone = "4072435200.000100", "4072435300.000200"   # 2099-01-20-ish
    upsert_message(CH, _msg(t_keep, text="old text"))
    upsert_message(CH, _msg(t_gone))
    db_session.flush()
    edited = _msg(t_keep, text="new text", edited={"ts": "4072435400.000000"})
    client = FakeSlack([edited])
    sync_recent(client, (CH,), days=21, now=now)
    rows = _rows()
    assert rows[t_keep].text == "new text" and rows[t_keep].edited_at is not None
    assert rows[t_gone].deleted_at is not None
    assert rows[t_keep].deleted_at is None


def test_upsert_returns_current_row_preserves_raw_and_leaves_commit_to_caller(db_session, monkeypatch):
    def unexpected_commit():
        pytest.fail("archive functions must leave commits to the caller")

    monkeypatch.setattr(db_session, "commit", unexpected_commit)
    raw = _msg("1700000400.000400", blocks=[{"type": "divider"}],
               attachments=[{"text": "synthetic attachment"}])
    row = upsert_message(CH, raw)
    assert isinstance(row, SlackArchiveMessage)
    assert row.raw == raw
    original_id = row.id
    row.deleted_at = datetime(2099, 1, 1)
    db_session.flush()

    replacement = {"ts": raw["ts"], "bot_id": "BFAKE0001", "subtype": "bot_message",
                   "edited": {"ts": "1700000500.000500"}}
    updated = upsert_message(CH, replacement)
    assert updated is row and updated.id == original_id
    assert row.raw == replacement and row.text == ""
    assert row.user_id is None and row.bot_id == "BFAKE0001"
    assert row.subtype == "bot_message" and row.deleted_at is None
    assert row.edited_at == datetime.fromtimestamp(1700000500.0005, timezone.utc).replace(tzinfo=None)
    assert row.synced_at.tzinfo is None
    import_channel(FakeSlack([_msg(raw["ts"])]), CH)
    sync_recent(FakeSlack([]), (CH,), now=datetime(2099, 1, 22, 12))


def test_import_paginates_replies_and_refetches_their_reactions(db_session):
    parent = _msg("1700000100.000100", reply_count=2)
    first = _msg("1700000200.000200", thread_ts=parent["ts"])
    second = _msg("1700000300.000300", thread_ts=parent["ts"],
                  reactions=[{"name": "zap", "count": 2, "users": ["UFAKE0001"]}])
    full = [{"name": "zap", "count": 2, "users": ["UFAKE0001", "UFAKE0002"]}]

    class PagedReplies(FakeSlack):
        def conversations_replies(self, channel, ts, limit=200, cursor=None, **kwargs):
            assert channel == CH and ts == parent["ts"] and limit == 200
            self.calls.append(("replies", cursor))
            if cursor is None:
                return {"ok": True, "messages": [parent, first],
                        "response_metadata": {"next_cursor": "reply-page2"}}
            assert cursor == "reply-page2"
            return {"ok": True, "messages": [second],
                    "response_metadata": {"next_cursor": ""}}

        def reactions_get(self, channel, timestamp, full=True, **kwargs):
            assert full is True and channel == CH
            return super().reactions_get(channel, timestamp, full=full, **kwargs)

    client = PagedReplies([parent], full_reactions={second["ts"]: full})
    stats = import_channel(client, CH)
    assert stats == {"messages": 1, "replies": 2, "reactions_refetched": 1,
                     "seen": {parent["ts"], first["ts"], second["ts"]}}
    assert _rows()[second["ts"]].raw["reactions"] == full
    assert ("replies", "reply-page2") in client.calls


def test_sync_deletes_only_observable_rows_and_counts_actual_deletions(db_session):
    now = datetime(2099, 1, 22, 12)
    parent = _msg("4072435200.000100", reply_count=1)
    kept_reply = _msg("4072435300.000200", thread_ts=parent["ts"])
    gone_reply = _msg("4072435400.000300", thread_ts=parent["ts"])
    unobserved_reply = _msg("4072435500.000400", thread_ts="1700000100.000100")
    gone_parent = _msg("4072435600.000500", thread_ts="4072435600.000500")
    old = _msg("1700000100.000100")
    for raw in (parent, kept_reply, gone_reply, unobserved_reply, gone_parent, old):
        upsert_message(CH, raw)
    upsert_message("CTESTARCH2", gone_parent)
    client = FakeSlack([parent], replies={parent["ts"]: [parent, kept_reply]})
    stats = sync_recent(client, (CH,), now=now)
    rows = _rows()
    assert rows[gone_reply["ts"]].deleted_at is not None
    assert rows[gone_parent["ts"]].deleted_at is not None
    for raw in (parent, kept_reply, unobserved_reply, old):
        assert rows[raw["ts"]].deleted_at is None
    assert SlackArchiveMessage.query.filter_by(channel_id="CTESTARCH2").one().deleted_at is None
    assert stats == {CH: {"messages": 1, "replies": 1, "reactions_refetched": 0, "deleted": 2}}
    assert sync_recent(client, (CH,), now=now)[CH]["deleted"] == 0


def test_sync_empty_history_marks_recent_top_level_message_deleted(db_session):
    upsert_message(CH, _msg("4072435200.000100"))
    stats = sync_recent(FakeSlack([]), (CH,), now=datetime(2099, 1, 22, 12))
    assert stats[CH]["deleted"] == 1
    assert _rows()["4072435200.000100"].deleted_at is not None


def test_sync_includes_exact_window_boundary(db_session):
    # 2099-01-01 12:00 UTC, exactly 21 days before the injected clock.
    ts = str((datetime(2099, 1, 1, 12) - datetime(1970, 1, 1)).total_seconds())
    upsert_message(CH, _msg(ts))

    class InclusiveHistory(FakeSlack):
        def conversations_history(self, channel, oldest=None, inclusive=False, **kwargs):
            assert oldest == ts
            assert inclusive is True
            return super().conversations_history(channel, oldest=oldest, **kwargs)

    stats = sync_recent(InclusiveHistory([_msg(ts)]), (CH,), now=datetime(2099, 1, 22, 12))
    assert stats[CH]["deleted"] == 0
    assert _rows()[ts].deleted_at is None


def test_sync_propagates_slack_failure_without_marking_deletions(db_session):
    upsert_message(CH, _msg("4072435200.000100"))

    class FailedHistory(FakeSlack):
        def conversations_history(self, **kwargs):
            raise SlackApiError("synthetic failure", {"ok": False, "error": "ratelimited"})

    with pytest.raises(SlackApiError):
        sync_recent(FailedHistory([]), (CH,), now=datetime(2099, 1, 22, 12))
    assert _rows()["4072435200.000100"].deleted_at is None
