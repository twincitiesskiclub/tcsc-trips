"""Admin crews pages."""
import io
import re
from unittest.mock import patch

import pytest

from app.crews.models import CrewConfig, CrewDraft
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
    form = {"crews": "2", "board_rule": "on", "speedy_channel": "C0ATRS011FA",
            **{f"level_{t}": "normal" for t in ("thot", "tenure", "gender", "ski", "age", "board")}}
    form.update(over)
    return form


def make_drafts(admin_client, season, count=3):
    admin_client.post(url(season, "/settings"), data=settings_form())
    return admin_client.post(url(season, "/drafts"), data={"count": str(count), "start_seed": "1"})


def test_requires_admin(client, season):
    assert client.get(url(season)).status_code == 302
    assert client.post(url(season, "/drafts"), data={"count": "1"}).status_code == 302


def test_season_page_lists_members_and_defaults(admin_client, season):
    r = admin_client.get(url(season))
    html = r.data.decode()
    assert r.status_code == 200
    assert "Ann Test" in html and "Fox Test" in html
    assert re.search(r'name="crews"[^>]*value="12"', html)
    assert "BOARD_MEMBER" in html  # tells admins where board comes from


def test_save_settings_and_reject_bad_crew_count(admin_client, season, world):
    r = admin_client.post(url(season, "/settings"), data=settings_form(crews="3", level_gender="high"),
                          follow_redirects=True)
    assert r.status_code == 200
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.settings["crews"] == 3 and config.settings["levels"]["gender"] == "high"
    r = admin_client.post(url(season, "/settings"), data=settings_form(crews="1"), follow_redirects=True)
    assert b"between 2 and 40" in r.data
    db.session.refresh(config)
    assert config.settings["crews"] == 3


def test_member_overrides_keep_only_differences(admin_client, season, world):
    eve, ann = world.people["Eve"], world.people["Ann"]
    form = {f"gender_{u.id}": "?" for u in world.people.values()}
    form.update({f"gender_{eve.id}": "F", f"thot_{eve.id}": "on", f"gender_{ann.id}": "F",
                 f"board_{ann.id}": "on", f"board_{world.people['Ben'].id}": "on"})
    for n in ("Ann", "Ben", "Cat", "Dan", "Fox"):
        form[f"gender_{world.people[n].id}"] = {"Ann": "F", "Ben": "M", "Cat": "F", "Dan": "M", "Fox": "X"}[n]
    admin_client.post(url(season, "/members"), data=form)
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.overrides == {str(eve.id): {"gender": "F", "thot": True}}


def test_upload_overrides_csv(admin_client, season, world):
    eve = world.people["Eve"]
    csv_text = f"Name,Email,gender,thot,board\nEve,{eve.email},f,1,\nNobody,nobody@example.com,m,,\n"
    r = admin_client.post(url(season, "/overrides/upload"),
                          data={"file": (io.BytesIO(csv_text.encode()), "sheet.csv")},
                          content_type="multipart/form-data", follow_redirects=True)
    assert b"1 member" in r.data and b"nobody@example.com" in r.data
    config = CrewConfig.query.filter_by(season_id=season.id).one()
    assert config.overrides[str(eve.id)] == {"gender": "F", "thot": True}


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


def test_make_drafts_and_compare(admin_client, season):
    r = make_drafts(admin_client, season, count=3)
    assert r.status_code == 302
    drafts = CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.seed).all()
    assert [d.seed for d in drafts] == [1, 2, 3]
    assert all(len(d.members) == 6 for d in drafts)
    html = admin_client.get(url(season)).data.decode()
    assert "Seed 1" in html and "Seed 3" in html


def test_make_drafts_respects_rules(admin_client, season, world):
    a, b = world.people["Cat"].id, world.people["Dan"].id
    admin_client.post(url(season, "/settings"), data=settings_form())
    admin_client.post(url(season, "/rules"), data={"kind": "together", "a": a, "b": b})
    admin_client.post(url(season, "/drafts"), data={"count": "4", "start_seed": "10"})
    for d in CrewDraft.query.filter_by(season_id=season.id):
        crews = {m["user_id"]: m["crew"] for m in d.members}
        assert crews[a] == crews[b]


def test_draft_page_move_swap_and_names(admin_client, season, world):
    make_drafts(admin_client, season, count=1)
    draft = CrewDraft.query.filter_by(season_id=season.id).one()
    r = admin_client.get(f"/admin/crews/draft/{draft.id}")
    assert r.status_code == 200 and b"Balance" in r.data
    cat = world.people["Cat"].id
    current = {m["user_id"]: m["crew"] for m in draft.members}[cat]
    target = 2 if current == 1 else 1
    r = admin_client.post(f"/admin/crews/draft/{draft.id}/move", data={"user_id": cat, "crew": target})
    assert r.status_code == 200 and b"draft-body" in r.data
    db.session.refresh(draft)
    assert {m["user_id"]: m["crew"] for m in draft.members}[cat] == target
    assert admin_client.post(f"/admin/crews/draft/{draft.id}/move",
                             data={"user_id": cat, "crew": "7"}).status_code == 400
    dan = world.people["Dan"].id
    before = {m["user_id"]: m["crew"] for m in draft.members}
    r = admin_client.post(f"/admin/crews/draft/{draft.id}/swap", data={"a": cat, "b": dan})
    db.session.refresh(draft)
    after = {m["user_id"]: m["crew"] for m in draft.members}
    assert r.status_code == 200 and after[cat] == before[dan] and after[dan] == before[cat]
    admin_client.post(f"/admin/crews/draft/{draft.id}/names", data={"name_1": "Brave Badgers", "name_2": ""})
    db.session.refresh(draft)
    assert draft.crew_names == {"1": "Brave Badgers"}


def test_only_one_final_draft_per_season(admin_client, season):
    make_drafts(admin_client, season, count=2)
    d1, d2 = CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.seed).all()
    admin_client.post(f"/admin/crews/draft/{d1.id}/final")
    admin_client.post(f"/admin/crews/draft/{d2.id}/final")
    db.session.refresh(d1)
    db.session.refresh(d2)
    assert (d1.status, d2.status) == ("draft", "final")


def test_export_csv(admin_client, season):
    make_drafts(admin_client, season, count=1)
    draft = CrewDraft.query.filter_by(season_id=season.id).one()
    r = admin_client.get(f"/admin/crews/draft/{draft.id}/export.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    lines = r.data.decode().strip().splitlines()
    assert lines[0].startswith("Crew,Crew name,Name") and len(lines) == 7


def test_import_draft_csv(admin_client, season, world):
    admin_client.post(url(season, "/settings"), data=settings_form())
    rows = "\n".join(f"{i % 2 + 1},{u.email}" for i, u in enumerate(world.people.values()) if u.first_name != "Fox")
    r = admin_client.post(url(season, "/drafts/import"),
                          data={"file": (io.BytesIO(f"Crew,Email\n{rows}\n".encode()), "crews.csv")},
                          content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    draft = CrewDraft.query.filter_by(season_id=season.id).one()
    assert draft.label.startswith("Imported") and len(draft.members) == 6
    assert b"Fox Test" in r.data  # named as not in the file


def test_refresh_speedy_group_from_slack(admin_client, season, world):
    admin_client.post(url(season, "/settings"), data=settings_form())
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
    assert r.status_code == 200 and b"Could not read the Slack channel" in r.data


def test_delete_draft(admin_client, season):
    make_drafts(admin_client, season, count=1)
    draft = CrewDraft.query.filter_by(season_id=season.id).one()
    admin_client.post(f"/admin/crews/draft/{draft.id}/delete")
    assert CrewDraft.query.filter_by(season_id=season.id).count() == 0


def test_index_redirects_to_a_season(admin_client, season):
    r = admin_client.get("/admin/crews/")
    assert r.status_code in (200, 302)
