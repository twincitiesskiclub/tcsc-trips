"""Pairing math for the crews backtest. Pure functions, no database."""
import time

from app.analytics.crew_pairing import best_pairing, pairings, share_by_count


def test_pairings_counts():
    assert len(list(pairings([1, 2, 3, 4], 2))) == 3
    assert list(pairings([1, 2, 3], 3)) == [((1,), (2,), (3,))]
    assert len(list(pairings(list(range(1, 13)), 7))) == 62370
    assert len(list(pairings(list(range(1, 13)), 6))) == 10395


def test_pairings_groups_are_sorted_and_ordered():
    for groups in pairings([1, 2, 3, 4, 5], 3):
        assert all(list(g) == sorted(g) for g in groups)
        assert [g[0] for g in groups] == sorted(g[0] for g in groups)


def test_odd_count_keeps_one_single():
    groups = next(pairings(list(range(1, 12)), 6))
    assert sorted(len(g) for g in groups) == [1, 2, 2, 2, 2, 2]


def test_best_pairing_joins_strong_with_weak():
    turnout = {1: [4, 4], 2: [3, 3], 3: [1, 1], 4: [0, 0]}
    pick = best_pairing(turnout, 2, set())
    # {1,4} and {2,3}: both groups reach 4 at both sessions.
    assert pick.groups == ((1, 4), (2, 3)) and pick.share == 1.0 and pick.broken == 0


def test_apart_beats_share():
    turnout = {1: [4, 4], 2: [3, 3], 3: [1, 1], 4: [0, 0]}
    pick = best_pairing(turnout, 2, {frozenset({1, 4})})
    assert frozenset({1, 4}) not in {frozenset(g) for g in pick.groups} and pick.broken == 0


def test_unavoidable_apart_is_counted():
    pick = best_pairing({1: [0], 2: [0]}, 1, {frozenset({1, 2})})
    assert pick.groups == ((1, 2),) and pick.broken == 1


def test_balance_breaks_ties_then_order():
    turnout = {c: [0] for c in (1, 2, 3, 4)}   # every pairing ties on share
    prefer = {((1, 3), (2, 4)): 0.0}
    pick = best_pairing(turnout, 2, set(), balance=lambda g: prefer.get(g, 1.0))
    assert pick.groups == ((1, 3), (2, 4))
    assert best_pairing(turnout, 2, set()).groups == ((1, 2), (3, 4))   # first in order


def test_no_pairing_keeps_the_draft():
    pick = best_pairing({1: [5, 1], 2: [2, 4]}, 2, set())
    assert pick.groups == ((1,), (2,)) and pick.share == 0.5


def test_share_by_count_range_and_no_sessions():
    turnout = {c: [] for c in range(1, 12)}
    rows = share_by_count(turnout, set())
    assert [r["crews"] for r in rows] == list(range(6, 12)) and all(r["share"] == 0 for r in rows)


def test_twelve_crews_is_fast():
    turnout = {c: [c % 5, (c * 3) % 6] * 6 for c in range(1, 13)}
    start = time.perf_counter()
    share_by_count(turnout, set())
    assert time.perf_counter() - start < 3.0
