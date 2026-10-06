"""Roster: turn a season's ACTIVE members into engine Persons."""
from datetime import date

from app.crews.models import CrewConfig
from app.crews.roster import gender_from_pronouns, load_members
from app.models import db


def test_gender_from_pronouns():
    assert gender_from_pronouns("she/her") == "F"
    assert gender_from_pronouns("He/Him") == "M"
    assert gender_from_pronouns("they/them") == "X"
    assert gender_from_pronouns("she/they") == "X"
    assert gender_from_pronouns("") == "?"
    assert gender_from_pronouns(None) == "?"


def test_members_have_computed_values(world):
    a = world.member("Ada", "Zed", pronouns="she/her", dob=date(1996, 1, 15), ski="3-7", board=True)
    b = world.member("Bo", "Young", seasons=[world.spring])
    db.session.commit()
    rows = load_members(world.fall, None, today=date(2026, 10, 5))
    by_id = {r.user_id: r for r in rows}
    assert set(by_id) == {a.id, b.id}
    ra, rb = by_id[a.id], by_id[b.id]
    assert (ra.person.gender, ra.person.age, ra.person.ski, ra.person.board) == ("F", 30, "3-7", True)
    assert ra.person.tenure == 0 and rb.person.tenure == 1
    assert rb.person.gender == "?" and rb.person.age is None and rb.person.board is False


def test_rows_sorted_by_name(world):
    world.member("Zoe", "Alpha")
    world.member("adam", "Beta")
    db.session.commit()
    assert [r.person.name for r in load_members(world.fall, None)] == ["adam Beta", "Zoe Alpha"]


def test_only_active_members_of_that_season(world):
    a = world.member("Cy", "One")
    db.session.commit()
    from app.models import UserSeason
    UserSeason.query.filter_by(user_id=a.id, season_id=world.fall.id).update({"status": "DROPPED_VOLUNTARY"})
    db.session.commit()
    assert load_members(world.fall, None) == []


def test_tenure_counts_practice_history_before_records(world):
    # Records start at the earliest non-legacy season. Attendance before that counts
    # one season per distinct label; a legacy member with no attendance counts as one.
    a = world.member("Dee", "Vet", seasons=[world.legacy])
    b = world.member("Eli", "Old", seasons=[world.legacy, world.spring])
    world.attended(b, "Winter 22-23", date(2022, 12, 1))
    world.attended(b, "Winter 22-23", date(2023, 1, 5))
    world.attended(b, "Summer 2023", date(2023, 6, 1))
    db.session.commit()
    rows = {r.user_id: r for r in load_members(world.fall, None)}
    assert rows[a.id].person.tenure == 1
    assert rows[b.id].person.tenure == 3  # spring record + two archive seasons


def test_overrides_and_speedy_group_apply(world):
    a = world.member("Fay", "Fast", pronouns="she/her")
    b = world.member("Gus", "Board", board=True)
    db.session.commit()
    config = CrewConfig(season_id=world.fall.id, speedy_user_ids=[a.id],
                        overrides={str(b.id): {"board": False, "gender": "M"}})
    rows = {r.user_id: r for r in load_members(world.fall, config)}
    assert rows[a.id].person.thot is True and rows[a.id].computed["thot"] is True
    assert rows[b.id].person.board is False and rows[b.id].computed["board"] is True
    assert rows[b.id].person.gender == "M" and rows[b.id].overridden == {"board", "gender"}


def test_archive_label_matching_a_registered_season_counts_once(world):
    # Practices dated just before a season's start_date carry that season's name.
    a = world.member("Hal", "Overlap", seasons=[world.spring])
    world.attended(a, world.spring.name, date(1999, 3, 20))
    db.session.commit()
    rows = {r.user_id: r for r in load_members(world.fall, None)}
    assert rows[a.id].person.tenure == 1
