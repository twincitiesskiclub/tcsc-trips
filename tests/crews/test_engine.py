"""Crew engine: pure functions, no database."""
from collections import Counter

import pytest

from app.crews.engine import (
    Person, Rule, Settings, broken_rules, crew_rows, generate, score, spread,
)


def roster(n=48, board=4, thot=4):
    """Hand-made members: a spread of genders, ages, ski levels and tenure."""
    genders, skis = ["F", "M", "F", "M", "X", "?"], ["1-3", "3-7", "7+", "7+"]
    return [
        Person(key=i, name=f"Member {i:03d}", gender=genders[i % 6], age=22 + (i * 7) % 16,
               ski=skis[i % 4], tenure=(i * 5) % 9, thot=i < thot, board=board <= i < 2 * board)
        for i in range(n)
    ]


def crews_of(result, k):
    out = [[] for _ in range(k)]
    for key, c in result.assignment.items():
        out[c].append(key)
    return out


def test_same_seed_same_crews_and_new_seed_differs():
    people, s = roster(), Settings(crews=4)
    a, b, c = generate(people, s, seed=7), generate(people, s, seed=7), generate(people, s, seed=8)
    assert a.assignment == b.assignment
    assert a.assignment != c.assignment


def test_every_person_assigned_and_sizes_even():
    people = roster(n=50)
    result = generate(people, Settings(crews=4), seed=1)
    assert set(result.assignment) == {p.key for p in people}
    assert sorted(Counter(result.assignment.values()).values()) == [12, 12, 13, 13]


def test_board_rule_puts_a_board_member_in_every_crew():
    people = roster(board=4)
    for seed in range(5):
        result = generate(people, Settings(crews=4), seed=seed)
        boards = {p.key for p in people if p.board}
        assert all(any(k in boards for k in crew) for crew in crews_of(result, 4))


def test_board_rule_off_scores_no_penalty_for_missing_board():
    people = roster(board=0)
    on = generate(people, Settings(crews=4, board_rule=True), seed=3)
    off = generate(people, Settings(crews=4, board_rule=False), seed=3)
    assert on.score - off.score == pytest.approx(400, abs=1e-6)


def test_balance_pass_never_makes_it_worse_and_keeps_bands():
    people = roster()
    result = generate(people, Settings(crews=4), seed=2)
    assert result.score <= result.raw_score
    by_band = {}
    for key, band in result.bands.items():
        by_band.setdefault(band, []).append(result.assignment[key])
    for crews in by_band.values():
        assert len(crews) == len(set(crews))  # one per crew within a band


def test_speedy_group_spread_across_crews():
    people = roster(thot=8)
    result = generate(people, Settings(crews=4), seed=5)
    counts = Counter(result.assignment[p.key] for p in people if p.thot)
    assert sorted(counts.values()) == [2, 2, 2, 2]


def test_off_trait_is_ignored_by_score():
    people = roster()
    s_on = Settings(crews=4)
    s_off = Settings(crews=4, levels={"gender": "off"})
    result = generate(people, s_on, seed=4)
    # Same assignment scored with gender off is lower or equal: one fewer term.
    assert score(people, result.assignment, s_off) <= score(people, result.assignment, s_on)
    assert "gender" not in spread(people, result.assignment, s_off)


def test_high_weight_beats_low_weight_for_that_trait():
    people = roster(n=96)
    hi = generate(people, Settings(crews=8, levels={"ski": "high"}), seed=9)
    lo = generate(people, Settings(crews=8, levels={"ski": "low"}), seed=9)
    assert spread(people, hi.assignment, Settings(crews=8))["ski"] <= \
        spread(people, lo.assignment, Settings(crews=8))["ski"]


def test_pin_puts_person_in_that_crew():
    people = roster()
    result = generate(people, Settings(crews=4, rules=[Rule("pin", a=10, crew=3)]), seed=1)
    assert result.assignment[10] == 2  # crews are 1-based in rules, 0-based inside
    assert result.broken == []


def test_together_keeps_people_in_one_crew():
    people = roster()
    rules = [Rule("together", a=11, b=12), Rule("together", a=12, b=30)]
    for seed in range(5):
        result = generate(people, Settings(crews=4, rules=rules), seed=seed)
        assert result.assignment[11] == result.assignment[12] == result.assignment[30]
        assert result.broken == []


def test_apart_keeps_people_in_different_crews():
    people = roster()
    rules = [Rule("apart", a=20, b=21), Rule("apart", a=20, b=22), Rule("apart", a=21, b=22)]
    for seed in range(8):
        result = generate(people, Settings(crews=4, rules=rules), seed=seed)
        assert len({result.assignment[k] for k in (20, 21, 22)}) == 3
        assert result.broken == []


def test_rules_keep_sizes_within_one():
    people = roster(n=50)
    rules = [Rule("together", a=1, b=2), Rule("together", a=2, b=3), Rule("pin", a=40, crew=1)]
    result = generate(people, Settings(crews=4, rules=rules), seed=6)
    sizes = Counter(result.assignment.values()).values()
    assert max(sizes) - min(sizes) <= 1


def test_impossible_rules_are_reported_not_raised():
    people = roster()
    rules = [Rule("pin", a=5, crew=1), Rule("pin", a=6, crew=2), Rule("together", a=5, b=6)]
    result = generate(people, Settings(crews=4, rules=rules), seed=1)
    assert len(result.broken) == 1
    assert broken_rules(result.assignment, rules, {p.key: p.name for p in people}) == result.broken


def test_rules_naming_unknown_people_are_skipped():
    people = roster()
    result = generate(people, Settings(crews=4, rules=[Rule("together", a=1, b=9999)]), seed=1)
    assert set(result.assignment) == {p.key for p in people}


def test_crew_rows_summarize_each_crew_and_total():
    people = roster(n=8, board=2, thot=2)
    assignment = {p.key: p.key % 2 for p in people}
    rows = crew_rows(people, assignment, 2)
    assert [r["label"] for r in rows] == ["1", "2", "All"]
    assert rows[-1]["size"] == 8 and rows[0]["size"] + rows[1]["size"] == 8
    assert rows[-1]["thot"] == 2 and rows[-1]["board"] == 2
    assert sum(rows[-1]["gender"].values()) == 8
    assert set(rows[-1]["tenure"]) == {"new", "1-2", "3-5", "6+"}


def test_more_crews_than_people_does_not_crash():
    people = roster(n=3, board=1, thot=0)
    result = generate(people, Settings(crews=5), seed=1)
    assert set(result.assignment) == {0, 1, 2}


def test_board_weight_follows_the_board_rule():
    assert Settings(board_rule=True).weight("board") == 1.0
    assert Settings(board_rule=False).weight("board") == 0.0
    assert "board" not in spread(roster(), {p.key: p.key % 4 for p in roster()}, Settings(crews=4))
