"""Time-limited trip planning: visit as many places as possible.

Problem
-------
There are ``n`` places. Each one takes some time to visit and there is a travel
time between every pair of places. Given a total time budget, find an ordered
route that visits the **largest number of distinct places** without exceeding
the budget. Among routes that visit the same number of places, the one with the
smallest total time wins. The route may start anywhere and does not have to
return to its start.

Three solvers are provided:

* :func:`brute_force` - tries every ordered selection, O(n!) (the original
  approach, kept as a reference and for small inputs).
* :func:`dp_bitmask` - exact Held-Karp style dynamic programming over subsets,
  O(2^n * n^2), practical up to 16 places.
* :func:`greedy` - fast heuristic, O(n^3), no optimality guarantee.
"""

from __future__ import annotations

import itertools
import json
import random
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

MAX_BRUTE_FORCE_PLACES = 10
MAX_DP_PLACES = 16
BENCHMARK_BRUTE_FORCE_LIMIT = 9


@dataclass
class TripProblem:
    """Places, visit times, travel times (minutes) and the time budget."""

    places: list[str]
    visit_times: dict[str, int]
    distances: dict[str, dict[str, int]]
    max_time: int

    def __post_init__(self) -> None:
        if not self.places:
            raise ValueError("at least one place is required")
        if len(set(self.places)) != len(self.places):
            raise ValueError("place names must be unique")
        if self.max_time < 0:
            raise ValueError("max_time must not be negative")
        for place in self.places:
            if place not in self.visit_times:
                raise ValueError(f"missing visit time for {place!r}")
            if self.visit_times[place] < 0:
                raise ValueError(f"visit time for {place!r} must not be negative")
            row = self.distances.get(place, {})
            for other in self.places:
                if other == place:
                    continue
                if other not in row:
                    raise ValueError(f"missing travel time {place!r} -> {other!r}")
                if row[other] < 0:
                    raise ValueError(f"travel time {place!r} -> {other!r} must not be negative")

    def matrices(self) -> tuple[list[int], list[list[int]]]:
        """Visit times and travel times as plain lists indexed like ``places``."""
        visit = [self.visit_times[p] for p in self.places]
        dist = [[0 if p == q else self.distances[p][q] for q in self.places] for p in self.places]
        return visit, dist

    def route_time(self, route: Sequence[str]) -> int:
        """Total time of a route: every visit plus every leg between them."""
        total = 0
        for index, place in enumerate(route):
            total += self.visit_times[place]
            if index:
                total += self.distances[route[index - 1]][place]
        return total

    @classmethod
    def from_dict(cls, data: dict) -> "TripProblem":
        """Build from ``{"max_time": 180, "places": {name: visit}, "distances": {a: {b: t}}}``.

        A travel time given in only one direction is used for both directions.
        """
        if "places" not in data or "max_time" not in data:
            raise ValueError("input needs 'places' and 'max_time'")
        visit = {str(name): int(minutes) for name, minutes in data["places"].items()}
        places = list(visit)
        raw = data.get("distances", {})
        distances: dict[str, dict[str, int]] = {p: {} for p in places}
        for p in places:
            for q in places:
                if p == q:
                    distances[p][q] = 0
                elif q in raw.get(p, {}):
                    distances[p][q] = int(raw[p][q])
                elif p in raw.get(q, {}):
                    distances[p][q] = int(raw[q][p])
                else:
                    raise ValueError(f"no travel time given between {p!r} and {q!r}")
        return cls(places, visit, distances, int(data["max_time"]))

    @classmethod
    def from_json(cls, path: str | Path) -> "TripProblem":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return {
            "max_time": self.max_time,
            "places": dict(self.visit_times),
            "distances": {p: dict(row) for p, row in self.distances.items()},
        }

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


@dataclass
class TripResult:
    route: list[str]
    total_time: int
    algorithm: str

    @property
    def num_places(self) -> int:
        return len(self.route)


def _place_names(count: int) -> list[str]:
    if count <= len(string.ascii_uppercase):
        return list(string.ascii_uppercase[:count])
    return [f"P{i + 1}" for i in range(count)]


def generate_problem(
    n_places: int = 5,
    max_time: int = 180,
    seed: int | None = None,
    visit_range: tuple[int, int] = (30, 100),
    distance_range: tuple[int, int] = (10, 50),
    symmetric: bool = True,
) -> TripProblem:
    """Create a random problem (defaults match the original exercise).

    With ``symmetric=True`` the trip from A to B takes as long as B to A; the
    original exercise drew each direction independently (``symmetric=False``).
    """
    if n_places < 1:
        raise ValueError("n_places must be at least 1")
    rng = random.Random(seed)
    names = _place_names(n_places)
    visit = {p: rng.randint(*visit_range) for p in names}
    distances: dict[str, dict[str, int]] = {p: {} for p in names}
    for i, p in enumerate(names):
        for j, q in enumerate(names):
            if i == j:
                distances[p][q] = 0
            elif symmetric and j < i:
                distances[p][q] = distances[q][p]
            else:
                distances[p][q] = rng.randint(*distance_range)
    return TripProblem(names, visit, distances, max_time)


def brute_force(problem: TripProblem) -> TripResult:
    """Try every ordered selection, longest first. O(n!)."""
    n = len(problem.places)
    if n > MAX_BRUTE_FORCE_PLACES:
        raise ValueError(f"brute force is limited to {MAX_BRUTE_FORCE_PLACES} places")
    visit, dist = problem.matrices()
    limit = problem.max_time

    for size in range(n, 0, -1):
        best_time: int | None = None
        best_order: tuple[int, ...] = ()
        for order in itertools.permutations(range(n), size):
            elapsed = visit[order[0]]
            if elapsed > limit:
                continue
            for k in range(1, size):
                elapsed += dist[order[k - 1]][order[k]] + visit[order[k]]
                if elapsed > limit:
                    break
            else:
                if best_time is None or elapsed < best_time:
                    best_time, best_order = elapsed, order
        if best_time is not None:
            return TripResult([problem.places[i] for i in best_order], best_time, "brute")
    return TripResult([], 0, "brute")


def dp_bitmask(problem: TripProblem) -> TripResult:
    """Exact solver. ``best[mask][last]`` is the least time needed to visit exactly
    the places in ``mask`` ending at ``last``; states over the budget are pruned."""
    n = len(problem.places)
    if n > MAX_DP_PLACES:
        raise ValueError(f"dp_bitmask is limited to {MAX_DP_PLACES} places; use greedy")
    visit, dist = problem.matrices()
    limit = problem.max_time
    inf = float("inf")

    best = [[inf] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    for i in range(n):
        if visit[i] <= limit:
            best[1 << i][i] = visit[i]

    for mask in range(1, 1 << n):
        for last in range(n):
            elapsed = best[mask][last]
            if elapsed == inf:
                continue
            for nxt in range(n):
                if mask >> nxt & 1:
                    continue
                candidate = elapsed + dist[last][nxt] + visit[nxt]
                if candidate > limit:
                    continue
                new_mask = mask | (1 << nxt)
                if candidate < best[new_mask][nxt]:
                    best[new_mask][nxt] = candidate
                    parent[new_mask][nxt] = last

    best_key: tuple[int, float] | None = None
    best_state = (0, -1)
    for mask in range(1, 1 << n):
        count = mask.bit_count()
        for last in range(n):
            elapsed = best[mask][last]
            if elapsed == inf:
                continue
            key = (count, -elapsed)
            if best_key is None or key > best_key:
                best_key, best_state = key, (mask, last)
    if best_key is None:
        return TripResult([], 0, "dp")

    mask, last = best_state
    order: list[int] = []
    while last != -1:
        order.append(last)
        previous = parent[mask][last]
        mask ^= 1 << last
        last = previous
    order.reverse()
    return TripResult([problem.places[i] for i in order], int(-best_key[1]), "dp")


def greedy(problem: TripProblem) -> TripResult:
    """From every possible start, keep moving to the cheapest reachable next place
    (travel + visit). Fast, but may miss the optimum."""
    n = len(problem.places)
    visit, dist = problem.matrices()
    limit = problem.max_time
    best_key: tuple[int, int] | None = None
    best_order: list[int] = []

    for start in range(n):
        if visit[start] > limit:
            continue
        order = [start]
        elapsed = visit[start]
        while True:
            options = [
                (dist[order[-1]][j] + visit[j], j)
                for j in range(n)
                if j not in order and elapsed + dist[order[-1]][j] + visit[j] <= limit
            ]
            if not options:
                break
            cost, nxt = min(options)
            order.append(nxt)
            elapsed += cost
        key = (len(order), -elapsed)
        if best_key is None or key > best_key:
            best_key, best_order = key, order

    if best_key is None:
        return TripResult([], 0, "greedy")
    return TripResult([problem.places[i] for i in best_order], -best_key[1], "greedy")


ALGORITHMS: dict[str, Callable[[TripProblem], TripResult]] = {
    "brute": brute_force,
    "dp": dp_bitmask,
    "greedy": greedy,
}


def solve(problem: TripProblem, algorithm: str = "dp") -> TripResult:
    try:
        solver = ALGORITHMS[algorithm]
    except KeyError:
        raise ValueError(f"unknown algorithm {algorithm!r}; choose from {sorted(ALGORITHMS)}") from None
    return solver(problem)


def benchmark(
    sizes: Sequence[int] = (5, 6, 7, 8, 9, 12, 14, 16),
    seed: int = 0,
    max_time: int = 180,
) -> list[dict]:
    """Time all solvers on random problems. Brute force is skipped for large sizes."""
    rows: list[dict] = []
    for n in sizes:
        problem = generate_problem(n, max_time, seed=seed + n)
        row: dict = {"places": n}
        results: dict[str, TripResult] = {}
        for name, solver in ALGORITHMS.items():
            if name == "brute" and n > BENCHMARK_BRUTE_FORCE_LIMIT:
                row[name] = None
                continue
            started = time.perf_counter()
            results[name] = solver(problem)
            row[name] = time.perf_counter() - started
        row["optimal_places"] = results["dp"].num_places
        row["greedy_places"] = results["greedy"].num_places
        row["agree"] = (
            None
            if "brute" not in results
            else (results["brute"].num_places, results["brute"].total_time)
            == (results["dp"].num_places, results["dp"].total_time)
        )
        rows.append(row)
    return rows


def plot_route(problem: TripProblem, result: TripResult, path: str | Path) -> None:
    """Save a timeline of the route: visits, travel legs and the time limit (needs matplotlib)."""
    if not result.route:
        raise ValueError("there is no route to plot")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    visit_color, travel_color, limit_color = "#1f77b4", "#e67e22", "#c0392b"
    fig, ax = plt.subplots(figsize=(10, 3.3))
    clock = 0
    for index, place in enumerate(result.route):
        if index:
            leg = problem.distances[result.route[index - 1]][place]
            ax.barh(0, leg, left=clock, height=0.5, color=travel_color, edgecolor="white")
            ax.text(clock + leg / 2, -0.42, str(leg), ha="center", va="top", fontsize=8, color=travel_color)
            clock += leg
        stay = problem.visit_times[place]
        ax.barh(0, stay, left=clock, height=0.5, color=visit_color, edgecolor="white")
        ax.text(clock + stay / 2, 0, place.replace(" ", "\n"), ha="center", va="center", fontsize=8, color="white")
        clock += stay

    ax.axvline(problem.max_time, color=limit_color, linestyle="--", linewidth=1.5)
    ax.set_xlim(0, max(problem.max_time, clock) * 1.03)
    ax.set_ylim(-0.9, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("minutes since start")
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title(f"Route: {result.num_places} places, {result.total_time} of {problem.max_time} min used")
    ax.legend(
        handles=[
            Patch(color=visit_color, label="visit"),
            Patch(color=travel_color, label="travel (minutes shown below the bar)"),
            Line2D([0], [0], color=limit_color, linestyle="--", label="time limit"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.32),
        ncol=3,
        frameon=False,
    )
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
