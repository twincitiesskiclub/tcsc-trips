"""Split members into balanced crews. Pure functions, no database.

Method (Mitchell's proposal plus a tidy-up pass; defaults reproduce the
2026-10-05 scratchpad draw):
  1. Pinned people and keep-together groups are placed first and never move.
  2. Board rule on: shuffle the free board members and deal one per crew,
     starting with crews that have none yet.
  3. Everyone else is sorted so similar people sit together (speedy group,
     tenure, gender, ski experience, age; only the traits that are on), cut
     into bands of K and dealt one per crew, smallest crews first.
  4. Even-out pass: trade two free people from the same band when it lowers
     the imbalance score. Then fix keep-apart pairs and level crew sizes with
     single moves.

Score = sum over crews and traits of weight * (count - expected)^2, plus an
age-mean term, 100 per crew with no board member (board rule on) and 1000 per
broken rule. Same people + settings + seed = same crews.
"""
import random
import statistics
from collections import Counter
from dataclasses import dataclass, field

SKI_ORDER = ["1-3", "3-7", "7+"]
TENURE_ORDER = ["new", "1-2", "3-5", "6+", "?"]
GENDER_ORDER = ["F", "M", "X", "?"]
TRAITS = ["thot", "tenure", "gender", "ski", "age", "board"]
TRAIT_LABELS = {"thot": "Speedy group", "tenure": "Tenure", "gender": "Gender",
                "ski": "Ski experience", "age": "Age", "board": "Board members"}
BASE_WEIGHTS = {"gender": 1.0, "ski": 1.0, "tenure": 1.0, "age": 1.0, "thot": 2.0, "board": 1.0}
LEVELS = {"off": 0.0, "low": 0.5, "normal": 1.0, "high": 2.0}
NO_BOARD_PENALTY = 100.0
BROKEN_RULE_PENALTY = 1000.0
# Score terms in a fixed order: float sums must not depend on dict order.
_SCORED = ["gender", "ski", "tenure", "age", "thot", "board"]


@dataclass
class Person:
    key: int
    name: str
    gender: str = "?"
    age: int | None = None
    ski: str = "?"
    tenure: int | None = None
    thot: bool = False
    board: bool = False


@dataclass
class Rule:
    kind: str  # together | apart | pin
    a: int
    b: int | None = None
    crew: int | None = None  # 1-based, for pin

    def describe(self, names):
        a = names.get(self.a, f"#{self.a}")
        if self.kind == "pin":
            return f"pin {a} to crew {self.crew}"
        return f"keep {self.kind} {a} and {names.get(self.b, f'#{self.b}')}"


@dataclass
class Settings:
    crews: int = 12
    levels: dict = field(default_factory=dict)  # trait -> off|low|normal|high
    board_rule: bool = True
    rules: list = field(default_factory=list)

    def weight(self, trait):
        return BASE_WEIGHTS[trait] * LEVELS.get(self.levels.get(trait, "normal"), 1.0)


@dataclass
class Result:
    assignment: dict  # key -> crew (0-based)
    bands: dict       # key -> band number (-1 = placed by a rule)
    score: float
    raw_score: float
    broken: list


def tenure_group(n):
    if n is None:
        return "?"
    return "new" if n == 0 else "1-2" if n <= 2 else "3-5" if n <= 5 else "6+"


def age_band(a):
    if a is None:
        return "?"
    return "under 30" if a < 30 else "30-39" if a < 40 else "40-49" if a < 50 else "50+"


def _rank(value, order):
    return order.index(value) if value in order else len(order)


def _value(p, trait):
    if trait == "tenure":
        return tenure_group(p.tenure)
    if trait == "age":
        return age_band(p.age)
    return getattr(p, trait)


class _State:
    def __init__(self, people, settings):
        self.people, self.s, self.k = people, settings, max(1, settings.crews)
        self.n = len(people)
        self.by_key = {p.key: p for p in people}
        self.names = {p.key: p.name for p in people}
        self.weights = {t: settings.weight(t) for t in _SCORED}
        self.totals = {t: Counter(_value(p, t) for p in people) for t in _SCORED}
        ages = [p.age for p in people if p.age is not None]
        self.mean_age = statistics.mean(ages) if ages else 0
        self.rules = [r for r in settings.rules if self._known(r)]
        self.crew, self.band, self.fixed = {}, {}, set()

    def _known(self, r):
        if r.a not in self.by_key:
            return False
        if r.kind == "pin":
            return r.crew is not None and 1 <= r.crew <= self.k
        return r.b in self.by_key and r.b != r.a

    def sizes(self):
        sizes = [0] * self.k
        for c in self.crew.values():
            sizes[c] += 1
        return sizes

    def score(self):
        groups = [[] for _ in range(self.k)]
        for p in self.people:
            groups[self.crew[p.key]].append(p)
        s = 0.0
        for g in groups:
            size = len(g)
            for t in _SCORED:
                w = self.weights[t]
                if not w:
                    continue
                counts = Counter(_value(p, t) for p in g)
                for cat, tot in self.totals[t].items():
                    s += w * (counts[cat] - size * tot / self.n) ** 2
            ages = [p.age for p in g if p.age is not None]
            if ages and self.weights["age"]:
                s += (self.weights["age"] / BASE_WEIGHTS["age"]) * ((statistics.mean(ages) - self.mean_age) / 2) ** 2
            if self.s.board_rule and not any(p.board for p in g):
                s += NO_BOARD_PENALTY
        return s + BROKEN_RULE_PENALTY * len(broken_rules(self.crew, self.rules, self.names))

    # -- placement ---------------------------------------------------------

    def _groups(self):
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for r in self.rules:
            if r.kind == "together":
                parent[find(r.a)] = find(r.b)
        pins = {r.a: r.crew - 1 for r in self.rules if r.kind == "pin"}
        groups = {}
        for key in set(parent) | set(pins):
            groups.setdefault(find(key), []).append(key)
        return [(sorted(g), next((pins[k] for k in sorted(g) if k in pins), None)) for g in groups.values()]

    def _apart_partners(self, key):
        return {r.b if r.a == key else r.a for r in self.rules
                if r.kind == "apart" and key in (r.a, r.b)}

    def _conflicts(self, keys, crew):
        return sum(1 for k in keys for other in self._apart_partners(k)
                   if self.crew.get(other) == crew)

    def place_fixed(self, rng):
        groups = self._groups()
        # pinned first, then bigger groups, so free groups fit around pins
        groups.sort(key=lambda g: (g[1] is None, -len(g[0]), g[0]))
        for keys, pin in groups:
            sizes = self.sizes()
            crew = pin if pin is not None else min(
                range(self.k), key=lambda c: (self._conflicts(keys, c), sizes[c], rng.random()))
            for key in keys:
                self.crew[key], self.band[key] = crew, -1
                self.fixed.add(key)

    def deal(self, rng):
        free = [p for p in self.people if p.key not in self.fixed]
        bands = []
        if self.s.board_rule:
            board = [p for p in free if p.board]
            rng.shuffle(board)
            bands.append(("board", board[: self.k]))
            rest = board[self.k:] + [p for p in free if not p.board]
        else:
            rest = list(free)
        on = {t for t in TRAITS if self.weights.get(t)}
        tiebreak = {p.key: rng.random() for p in rest}
        rest.sort(key=lambda p: (
            (not p.thot) if "thot" in on else 0,
            _rank(tenure_group(p.tenure), TENURE_ORDER) if "tenure" in on else 0,
            p.gender if "gender" in on else "",
            _rank(p.ski, SKI_ORDER) if "ski" in on else 0,
            (p.age if p.age is not None else 999) if "age" in on else 0,
            tiebreak[p.key]))
        bands += [("rest", rest[j: j + self.k]) for j in range(0, len(rest), self.k)]
        sizes = self.sizes()
        has_board = [False] * self.k
        for key, c in self.crew.items():
            has_board[c] = has_board[c] or self.by_key[key].board
        number = 0
        for kind, band in bands:
            if not band:
                continue
            order = sorted(range(self.k), key=lambda c: (
                has_board[c] if kind == "board" else False, sizes[c], rng.random()))
            for p, c in zip(band, order):
                self.crew[p.key], self.band[p.key] = c, number
                sizes[c] += 1
                has_board[c] = has_board[c] or p.board
            number += 1

    # -- improvement -------------------------------------------------------

    def _try(self, best, change, undo):
        change()
        s = self.score()
        if s < best - 1e-9:
            return s, True
        undo()
        return best, False

    def _swap(self, i, j):
        self.crew[i], self.crew[j] = self.crew[j], self.crew[i]

    def balance(self, best):
        improved = True
        while improved:
            improved = False
            for b in sorted({v for v in self.band.values() if v >= 0}):
                band = [p.key for p in self.people if self.band[p.key] == b]
                in_band = {self.crew[i] for i in band}
                for x in range(len(band)):
                    for y in range(x + 1, len(band)):
                        i, j = band[x], band[y]
                        best, ok = self._try(best, lambda: self._swap(i, j), lambda: self._swap(i, j))
                        improved |= ok
                # a short band: move someone to a smaller crew with nobody from this band
                for i in band:
                    for c in range(self.k):
                        sizes = self.sizes()
                        if c in in_band or sizes[c] >= sizes[self.crew[i]]:
                            continue
                        old = self.crew[i]
                        best, ok = self._try(best, lambda: self.crew.__setitem__(i, c),
                                             lambda: self.crew.__setitem__(i, old))
                        if ok:
                            improved = True
                            in_band = {self.crew[t] for t in band}
        return best

    def repair(self, best):
        """Cross-band moves: split keep-apart pairs, then level crew sizes."""
        free = [p.key for p in self.people if p.key not in self.fixed]
        for r in self.rules:
            if r.kind != "apart" or self.crew[r.a] != self.crew[r.b]:
                continue
            mover = r.b if r.b not in self.fixed else r.a if r.a not in self.fixed else None
            if mover is None:
                continue
            candidates = [j for j in free if self.crew[j] != self.crew[mover]]
            options = []
            for j in candidates:
                self._swap(mover, j)
                options.append((self.score(), j))
                self._swap(mover, j)
            if options:
                s, j = min(options)
                self._swap(mover, j)
                best = s
        while True:
            sizes = self.sizes()
            big, small = max(range(self.k), key=lambda c: sizes[c]), min(range(self.k), key=lambda c: sizes[c])
            if sizes[big] - sizes[small] <= 1:
                return best
            options = []
            for i in (key for key in free if self.crew[key] == big):
                self.crew[i] = small
                options.append((self.score(), i))
                self.crew[i] = big
            if not options:
                return best
            best, i = min(options)
            self.crew[i] = small
            self.band[i] = -1


def generate(people, settings, seed):
    people = list(people)
    st = _State(people, settings)
    if not people:
        return Result({}, {}, 0.0, 0.0, [])
    rng = random.Random(seed)
    st.place_fixed(rng)
    st.deal(rng)
    raw = st.score()
    final = st.repair(st.balance(raw))
    final = st.balance(final) if st.rules else final
    return Result(dict(st.crew), dict(st.band), final, raw,
                  broken_rules(st.crew, st.rules, st.names))


def score(people, assignment, settings):
    st = _State(list(people), settings)
    st.crew = dict(assignment)
    return st.score()


def broken_rules(assignment, rules, names):
    out = []
    for r in rules:
        a, b = assignment.get(r.a), assignment.get(r.b) if r.b is not None else None
        if a is None or (r.kind != "pin" and b is None):
            continue
        if (r.kind == "together" and a != b) or (r.kind == "apart" and a == b) or \
                (r.kind == "pin" and a != r.crew - 1):
            out.append(r.describe(names))
    return out


def spread(people, assignment, settings):
    """Per trait that is on: the worst |count - even share| over crews and groups."""
    people = list(people)
    k, n = max(1, settings.crews), len(people)
    groups = [[] for _ in range(k)]
    for p in people:
        groups[assignment[p.key]].append(p)
    out = {}
    for t in TRAITS:
        if not settings.weight(t):
            continue
        totals = Counter(_value(p, t) for p in people)
        worst = 0.0
        for g in groups:
            counts = Counter(_value(p, t) for p in g)
            for cat, tot in totals.items():
                if cat != "?":
                    worst = max(worst, abs(counts[cat] - len(g) * tot / n))
        out[t] = round(worst, 1)
    return out


def crew_rows(people, assignment, k):
    """Balance-table rows: one per crew plus an 'All' row."""
    people = list(people)
    groups = [[] for _ in range(max(1, k))]
    for p in people:
        groups[assignment[p.key]].append(p)

    def row(label, g):
        ages = [p.age for p in g if p.age is not None]
        tenure = Counter(tenure_group(p.tenure) for p in g)
        genders = Counter(p.gender for p in g)
        return {
            "label": label, "size": len(g), "board": sum(p.board for p in g),
            "thot": sum(p.thot for p in g),
            "gender": {x: genders[x] for x in GENDER_ORDER if x != "?" or genders[x]},
            "ski": Counter(p.ski for p in g),
            "age_avg": round(statistics.mean(ages)) if ages else None,
            "age_min": min(ages) if ages else None, "age_max": max(ages) if ages else None,
            "tenure": {t: tenure.get(t, 0) for t in TENURE_ORDER if t != "?" or tenure.get(t)},
        }

    return [row(str(i + 1), g) for i, g in enumerate(groups)] + [row("All", people)]
