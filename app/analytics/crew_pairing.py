"""Join whole crews in pairs and score how often each group has enough people at practice.

Pairing never moves a person, so every hand swap in a draft survives.
"""
from dataclasses import dataclass
from itertools import combinations
from math import ceil
from typing import Callable, Iterator

MIN_GROUP = 4  # a crew works as a practice group with this many people there

Groups = tuple[tuple[int, ...], ...]


@dataclass
class Pick:
    groups: Groups
    share: float   # of (group, practice) slots with MIN_GROUP or more
    broken: int    # groups that join a pair an apart rule forbids


def pairings(crews: list[int], k: int) -> Iterator[Groups]:
    """Every way to join len(crews) - k disjoint pairs, the rest left single."""
    def walk(rest, singles, acc):
        if not rest:
            yield tuple(acc)
            return
        first, others = rest[0], rest[1:]
        if len(rest) > singles:   # pairs still to make
            for i, mate in enumerate(others):
                yield from walk(others[:i] + others[i + 1:], singles, acc + [(first, mate)])
        if singles:
            yield from walk(others, singles - 1, acc + [(first,)])

    crews = sorted(crews)
    singles = 2 * k - len(crews)
    if 0 <= singles <= len(crews):
        yield from walk(crews, singles, [])


def _hits(turnout):
    """Sessions at MIN_GROUP or more for every single crew and every crew pair."""
    hits = {(c,): sum(n >= MIN_GROUP for n in counts) for c, counts in turnout.items()}
    for a, b in combinations(sorted(turnout), 2):
        hits[(a, b)] = sum(x + y >= MIN_GROUP for x, y in zip(turnout[a], turnout[b]))
    return hits


def _tied_best(turnout, k, apart, hits, cap):
    best_key, tied = None, []
    for groups in pairings(list(turnout), k):
        broken = sum(len(g) == 2 and frozenset(g) in apart for g in groups)
        key = (broken, -sum(hits[g] for g in groups))
        if best_key is None or key < best_key:
            best_key, tied = key, [groups]
        elif key == best_key and len(tied) < cap:
            tied.append(groups)
    return best_key, tied


def _share(total_hits, k, turnout):
    sessions = len(next(iter(turnout.values()), []))
    return total_hits / (k * sessions) if sessions else 0.0


def best_pairing(turnout: dict[int, list[int]], k: int, apart: set[frozenset[int]],
                 balance: Callable[[Groups], float] | None = None, tie_cap: int = 2000) -> Pick:
    """Fewest broken apart rules, then most groups at MIN_GROUP, then best balance, then order."""
    hits = _hits(turnout)
    (broken, neg_hits), tied = _tied_best(turnout, k, apart, hits, tie_cap)
    groups = min(tied, key=balance) if balance else tied[0]
    return Pick(groups, _share(-neg_hits, k, turnout), broken)


def share_by_count(turnout: dict[int, list[int]], apart: set[frozenset[int]]) -> list[dict]:
    """The best pairing's share at every crew count from ceil(n/2) to n."""
    hits, n, rows = _hits(turnout), len(turnout), []
    for k in range(ceil(n / 2), n + 1):
        (_, neg_hits), _ = _tied_best(turnout, k, apart, hits, 1)
        rows.append({"crews": k, "share": _share(-neg_hits, k, turnout)})
    return rows
