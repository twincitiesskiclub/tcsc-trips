"""Admin crews pages."""
import re
from unittest.mock import patch

import pytest

from app.crews.models import CrewConfig, CrewDraft
from app.crews.service import DRAFTS_PER_BATCH, FIRST_SEED
from app.models import db


@pytest.fixture
def season(world):
    names = [("Ann", "she/her", True), ("Ben", "he/him", True), ("Cat", "she/her", False),
             ("Dan", "he/him", False), ("Eve", None, False), ("Fox", "they/them", False)]
    world.people = {n: world.member(n, "Test", pronouns=p, board=b, slack_uid=f"UCREW{n.upper()}{world.tag}")
                    for n, p, b in names}
    db.session.commit()
    return world.fall


def url(season, path=""):
    return f"/admin/crews/season/{season.id}{path}"


def settings_form(**over):
    form = {"crews": "2", "board_rule": "on",
            **{f"level_{t}": "normal" for t in ("thot", "tenure", "gender", "ski", "age")}}
    form.update(over)
    return form


def make_drafts(admin_client, season):
    admin_client.post(url(season, "/settings"), data=settings_form())
    return admin_client.post(url(season, "/drafts"))


def crews(draft):
    return {m["user_id"]: m["crew"] for m in draft.members}


def test_requires_admin(client, season):
    assert client.get(url(season)).status_code == 302
    assert client.post(url(season, "/drafts")).status_code == 302


def test_season_page_shows_summary_and_defaults_without_saving(admin_client, season):
    r = admin_client.get(url(season))
    html = r.data.decode()
    assert r.status_code == 200
    assert "6 members" in html and "Board members 2" in html and "Final crews:" in html
    assert f"Make {DRAFTS_PER_BATCH} drafts" in html
    assert re.search(r'name="crews"[^>]*value="12"', html)
    assert "Fox Test" in html and "BOARD_MEMBER" in html
    assert CrewConfig.query.filter_by(season_id=season.id).count() == 0  # a GET writes nothing


def test_save_settings_and_reject_bad_crew_count(admin_client, season):
    admin_client.post(url(season, "/settings"), data=settings_form(crews="3", level_gender="high"))
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.settings == {"crews": 3, "board_rule": True,
                               "levels": {"thot": "normal", "tenure": "normal", "gender": "high",
                                          "ski": "normal", "age": "normal"}}
    r = admin_client.post(url(season, "/settings"), data=settings_form(crews="1"), follow_redirects=True)
    assert b"between 2 and 40" in r.data
    db.session.refresh(config)
    assert config.settings["crews"] == 3


def test_member_overrides_keep_only_differences(admin_client, season, world):
    computed = {"Ann": "F", "Ben": "M", "Cat": "F", "Dan": "M", "Eve": "?", "Fox": "X"}
    form = {f"gender_{world.people[n].id}": g for n, g in computed.items()}
    eve = world.people["Eve"]
    form.update({f"gender_{eve.id}": "F", f"thot_{eve.id}": "on",
                 f"board_{world.people['Ann'].id}": "on", f"board_{world.people['Ben'].id}": "on"})
    admin_client.post(url(season, "/members"), data=form)
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.overrides == {str(eve.id): {"gender": "F", "thot": True}}
    admin_client.post(url(season, "/members/clear"))
    db.session.refresh(config)
    assert config.overrides == {}


def test_rules_add_and_delete(admin_client, season, world):
    a, b = world.people["Cat"].id, world.people["Dan"].id
    admin_client.post(url(season, "/settings"), data=settings_form())
    admin_client.post(url(season, "/rules"), data={"kind": "apart", "a": a, "b": b})
    admin_client.post(url(season, "/rules"), data={"kind": "pin", "a": a, "crew": "9"})  # bad crew
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.rules == [{"kind": "apart", "a": a, "b": b}]
    admin_client.post(url(season, "/rules/0/delete"))
    db.session.refresh(config)
    assert config.rules == []


def test_make_drafts_picks_seeds_and_labels(admin_client, season):
    make_drafts(admin_client, season)
    admin_client.post(url(season, "/drafts"))
    drafts = CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.seed).all()
    assert [d.seed for d in drafts] == list(range(FIRST_SEED, FIRST_SEED + 2 * DRAFTS_PER_BATCH))
    assert drafts[0].label == "Draft 1" and drafts[-1].label == f"Draft {2 * DRAFTS_PER_BATCH}"
    assert all(len(d.members) == 6 for d in drafts)
    html = admin_client.get(url(season)).data.decode()
    assert "Draft 1" in html and "Best" in html


def test_make_drafts_respects_rules(admin_client, season, world):
    a, b = world.people["Cat"].id, world.people["Dan"].id
    admin_client.post(url(season, "/settings"), data=settings_form())
    admin_client.post(url(season, "/rules"), data={"kind": "together", "a": a, "b": b})
    admin_client.post(url(season, "/drafts"))
    for d in CrewDraft.query.filter_by(season_id=season.id):
        assert crews(d)[a] == crews(d)[b]


def test_save_draft_moves_people_and_names_crews(admin_client, season, world):
    make_drafts(admin_client, season)
    draft = CrewDraft.query.filter_by(season_id=season.id, seed=FIRST_SEED).one()
    cat, dan = world.people["Cat"].id, world.people["Dan"].id
    before = crews(draft)
    form = {f"crew_{uid}": str(c) for uid, c in before.items()}
    form.update({f"crew_{cat}": str(before[dan]), f"crew_{dan}": str(before[cat]),
                 "name_1": "Brave Badgers", "name_2": "", "label": "Mitchell's pick"})
    r = admin_client.post(f"/admin/crews/draft/{draft.id}", data=form, follow_redirects=True)
    assert r.status_code == 200 and b"Brave Badgers" in r.data
    db.session.refresh(draft)
    assert crews(draft)[cat] == before[dan] and crews(draft)[dan] == before[cat]
    assert draft.crew_names == {"1": "Brave Badgers"} and draft.label == "Mitchell's pick"


def test_save_draft_rejects_a_bad_crew(admin_client, season, world):
    make_drafts(admin_client, season)
    draft = CrewDraft.query.filter_by(season_id=season.id, seed=FIRST_SEED).one()
    before = crews(draft)
    r = admin_client.post(f"/admin/crews/draft/{draft.id}",
                          data={f"crew_{world.people['Cat'].id}": "7"}, follow_redirects=True)
    assert b"Pick a crew from 1 to 2" in r.data
    db.session.refresh(draft)
    assert crews(draft) == before


def test_only_one_final_draft_per_season(admin_client, season):
    make_drafts(admin_client, season)
    d1, d2 = CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.seed).limit(2).all()
    admin_client.post(f"/admin/crews/draft/{d1.id}/final")
    admin_client.post(f"/admin/crews/draft/{d2.id}/final")
    db.session.refresh(d1)
    db.session.refresh(d2)
    assert (d1.status, d2.status) == ("draft", "final")


def test_export_csv(admin_client, season):
    make_drafts(admin_client, season)
    draft = CrewDraft.query.filter_by(season_id=season.id, seed=FIRST_SEED).one()
    r = admin_client.get(f"/admin/crews/draft/{draft.id}/export.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    lines = r.data.decode().strip().splitlines()
    assert lines[0].startswith("Crew,Crew name,Name") and len(lines) == 7


def test_refresh_speedy_group_from_slack(admin_client, season, world):
    eve = world.people["Eve"]
    fake = {"members": [f"UCREWEVE{world.tag}", "UBOT"], "response_metadata": {"next_cursor": ""}}
    with patch("app.crews.slack.get_slack_client") as client:
        client.return_value.conversations_members.return_value = fake
        r = admin_client.post(url(season, "/speedy/refresh"), follow_redirects=True)
    assert r.status_code == 200 and b"1 member" in r.data
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.speedy_user_ids == [eve.id] and config.speedy_refreshed_at is not None


def test_refresh_speedy_group_slack_error_is_a_message(admin_client, season):
    with patch("app.crews.slack.get_slack_client", side_effect=ValueError("SLACK_BOT_TOKEN not configured")):
        r = admin_client.post(url(season, "/speedy/refresh"), follow_redirects=True)
    assert r.status_code == 200 and b"Could not read #thots" in r.data


def test_delete_draft(admin_client, season):
    make_drafts(admin_client, season)
    draft = CrewDraft.query.filter_by(season_id=season.id, seed=FIRST_SEED).one()
    admin_client.post(f"/admin/crews/draft/{draft.id}/delete")
    assert CrewDraft.query.filter_by(season_id=season.id).count() == DRAFTS_PER_BATCH - 1
