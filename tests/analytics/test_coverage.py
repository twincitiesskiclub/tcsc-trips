"""Hand-written posts only; no real Slack content."""
import pytest

from app.analytics import CANDIDATE_CHANNELS, TRIP_CHANNEL
from app.analytics.coverage import find_candidates, is_candidate
from app.analytics.drafts import ArchivedMessage

APPLAUSE = frozenset({"heart", "tada", "+1", "clap"})
CH = "C02HXN45214"


def R(name, count):
    return {"name": name, "count": count, "users": [f"UFAKE{i:04d}" for i in range(count)]}


@pytest.mark.parametrize("text", [
    "Hit a :baseball: if you're in",
    "Bop the :pickle: to join",
    "Smash that :party-wfh: button",
    "Please RSVP by reacting with a :white_check_mark: if you can come",
    "React with :bike: if you're IN",
    "give a :white_check_mark: if you're planning to attend",
    "React with :call_me_hand::skin-tone-4: to come",
])
def test_rsvp_phrasing_is_candidate(text):
    assert is_candidate({"text": text, "reactions": []}, APPLAUSE)


def test_applause_only_post_is_not_candidate():
    raw = {"text": "Congrats to our Birkie finishers!", "reactions": [R("heart", 12), R("tada", 9)]}
    assert not is_candidate(raw, APPLAUSE)


def test_five_reactions_on_non_applause_emoji_is_candidate():
    assert is_candidate({"text": "Cider tasting Saturday", "reactions": [R("apple", 5)]}, APPLAUSE)
    assert not is_candidate({"text": "Cider tasting Saturday", "reactions": [R("apple", 4)]}, APPLAUSE)


def _msg(ts, text, reactions=(), channel=CH, **raw):
    return ArchivedMessage(channel, ts, {"ts": ts, "text": text, "reactions": list(reactions), **raw})


def test_find_candidates_skips_resolved_produced_replies_and_system_posts():
    posts = [
        _msg("1.000001", "Bop the :pickle:"),                           # candidate
        _msg("1.000002", "Bop the :pickle:"),                           # skip correction
        _msg("1.000003", "Bop the :pickle:"),                           # produced a session
        _msg("1.000004", "Bop the :pickle:", thread_ts="1.000001"),     # reply
        _msg("1.000005", "x has joined", [R("wave", 9)], subtype="channel_join"),
        _msg("1.000006", "Bop the :pickle:", channel="C047BRZH1LG"),    # never counted
        _msg("1.000007", "Bop the :pickle:"),                           # rsvp_from target
        _msg("1.000008", "Bop the :pickle:"),                           # deleted
    ]
    posts[7] = ArchivedMessage(CH, "1.000008", posts[7].raw, deleted=True)
    corrections = {f"{CH}:1.000002": {"skip": True},
                   "practice:9": {"rsvp_from": [f"{CH}:1.000007"]}}
    produced = {(CH, "1.000003")}
    assert find_candidates(posts, produced, corrections, APPLAUSE) == [f"{CH}:1.000001"]


def test_skin_tones_and_explicit_applause_rsvp():
    assert not is_candidate({"reactions": [R("clap::skin-tone-4", 5)]}, APPLAUSE)
    assert is_candidate({"reactions": [R("call_me_hand::skin-tone-4", 5)]}, APPLAUSE)
    assert is_candidate({"text": "Smash that :heart:", "reactions": []}, APPLAUSE)


def test_reminder_without_rsvp_or_reactions_is_not_candidate():
    assert not is_candidate({"text": "Reminder: bring a water bottle", "reactions": []}, APPLAUSE)


def test_threshold_is_per_emoji():
    assert not is_candidate({"reactions": [R("apple", 3), R("bike", 3)]}, APPLAUSE)


def test_find_candidates_covers_channels_and_sorts_keys():
    posts = [_msg(ts, "Bop the :pickle:", channel=channel)
             for channel in reversed(CANDIDATE_CHANNELS)
             for ts in ("1.000002", "1.000001")]
    assert find_candidates(posts, set(), {}, APPLAUSE) == sorted(
        f"{channel}:{ts}" for channel in CANDIDATE_CHANNELS
        for ts in ("1.000001", "1.000002"))


def test_find_candidates_skips_weekly_previews_and_trip_channel():
    posts = [_msg("1.000001", ":date: • _Week of Jul 13, 2099_\nBop the :pickle:"),
             _msg("1.000002", "Bop the :pickle:", channel=TRIP_CHANNEL)]
    assert find_candidates(posts, set(), {}, APPLAUSE) == []


@pytest.mark.parametrize("suffix", ["", ":main", ":early", ":2099-07-16"])
def test_session_correction_resolves_whole_post(suffix):
    post = _msg("1.000001", "Bop the :pickle:")
    corrections = {f"{CH}:{post.ts}{suffix}": {"ok": True}}
    assert find_candidates([post], set(), corrections, APPLAUSE) == []
