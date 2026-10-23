"""Pipe-network design for a multi-floor building.

Problem
-------
A building has ``n`` rooms spread over ``m`` floors. Two rooms on the same floor
can be joined by a pipe of some length; rooms on *adjacent* floors can be joined
too (a vertical run whose length depends on the pair of floors). Choose a set of
pipes that connects **every** room using the least total length.

That is the Minimum Spanning Tree (MST) problem. This module solves it with
Kruskal's algorithm (sort the candidate pipes, add a pipe only if it joins two
*different* clusters, tracked with a Union-Find structure) and cross-checks it
with Prim's algorithm and, for tiny inputs, an exhaustive search.

The original exercise used a simpler greedy rule ("add the pipe if at least one
of its rooms is not connected yet"). That rule can start a second, separate
cluster and never join the clusters, so the result is not always a connected
network. It is kept here as :func:`legacy_greedy` so the difference can be
measured (see :func:`legacy_comparison`).
"""

from __future__ import annotations

import heapq
import itertools
import random
from dataclasses import dataclass
from pathlib import Path

MAX_BRUTE_FORCE_ROOMS = 8


@dataclass(frozen=True, order=True)
class Edge:
    """A candidate pipe between rooms ``a`` and ``b`` (ordered by length first)."""

    length: int
    a: int
    b: int


class UnionFind:
    """Disjoint-set forest with path compression and union by rank."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size
        self.components = size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> bool:
        """Merge the sets of ``a`` and ``b``. Return False if already merged."""
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return False
        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a
        self.parent[root_b] = root_a
        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1
        self.components -= 1
        return True


@dataclass
class Building:
    """Rooms grouped by floor plus every candidate pipe between them."""

    n_rooms: int
    floors: list[list[int]]
    edges: list[Edge]

    @property
    def n_floors(self) -> int:
        return len(self.floors)

    def floor_of(self, room: int) -> int:
        """Zero-based floor index of ``room``."""
        for index, floor in enumerate(self.floors):
            if room in floor:
                return index
        raise ValueError(f"room {room} is not in this building")


def generate_building(
    n_rooms: int,
    n_floors: int,
    seed: int | None = None,
    same_floor_range: tuple[int, int] = (10, 30),
    between_floor_range: tuple[int, int] = (5, 10),
) -> Building:
    """Create a random building.

    Rooms are shuffled and dealt onto floors as evenly as possible. Every pair of
    rooms on one floor gets a random pipe length; every pair of rooms on adjacent
    floors shares one vertical length per floor pair.
    """
    if n_floors < 1:
        raise ValueError("a building needs at least one floor")
    if n_rooms < n_floors:
        raise ValueError("a building needs at least one room per floor")

    rng = random.Random(seed)
    rooms = list(range(n_rooms))
    rng.shuffle(rooms)

    base, extra = divmod(n_rooms, n_floors)
    floors: list[list[int]] = []
    start = 0
    for index in range(n_floors):
        end = start + base + (1 if index < extra else 0)
        floors.append(sorted(rooms[start:end]))
        start = end

    edges: list[Edge] = []
    for floor in floors:
        for a, b in itertools.combinations(floor, 2):
            edges.append(Edge(rng.randint(*same_floor_range), a, b))
    for lower, upper in zip(floors, floors[1:]):
        length = rng.randint(*between_floor_range)
        for a in lower:
            for b in upper:
                edges.append(Edge(length, min(a, b), max(a, b)))
    return Building(n_rooms, floors, edges)


def total_length(pipes: list[Edge]) -> int:
    return sum(pipe.length for pipe in pipes)


def is_spanning_tree(n_rooms: int, pipes: list[Edge]) -> bool:
    """True if ``pipes`` connects all rooms without any redundant pipe."""
    if len(pipes) != n_rooms - 1:
        return False
    clusters = UnionFind(n_rooms)
    return all(clusters.union(pipe.a, pipe.b) for pipe in pipes)


def kruskal(n_rooms: int, edges: list[Edge]) -> list[Edge]:
    """Minimum spanning tree in O(E log E). Raises ValueError if not connectable."""
    if n_rooms < 1:
        raise ValueError("there must be at least one room")
    clusters = UnionFind(n_rooms)
    chosen: list[Edge] = []
    for edge in sorted(edges):
        if clusters.union(edge.a, edge.b):
            chosen.append(edge)
            if len(chosen) == n_rooms - 1:
                break
    if clusters.components != 1:
        raise ValueError("the rooms cannot all be connected with the given pipes")
    return chosen


def prim(n_rooms: int, edges: list[Edge]) -> list[Edge]:
    """Minimum spanning tree with a heap, O(E log V). Used to cross-check Kruskal."""
    if n_rooms < 1:
        raise ValueError("there must be at least one room")
    neighbours: list[list[tuple[int, int, Edge]]] = [[] for _ in range(n_rooms)]
    for edge in edges:
        neighbours[edge.a].append((edge.length, edge.b, edge))
        neighbours[edge.b].append((edge.length, edge.a, edge))

    visited = {0}
    heap = list(neighbours[0])
    heapq.heapify(heap)
    chosen: list[Edge] = []
    while heap and len(visited) < n_rooms:
        _, room, edge = heapq.heappop(heap)
        if room in visited:
            continue
        visited.add(room)
        chosen.append(edge)
        for item in neighbours[room]:
            if item[1] not in visited:
                heapq.heappush(heap, item)
    if len(visited) != n_rooms:
        raise ValueError("the rooms cannot all be connected with the given pipes")
    return chosen


def brute_force_total(n_rooms: int, edges: list[Edge]) -> int:
    """Exhaustive minimum total length. Only for tiny buildings (testing)."""
    if n_rooms > MAX_BRUTE_FORCE_ROOMS:
        raise ValueError(f"brute force is limited to {MAX_BRUTE_FORCE_ROOMS} rooms")
    best: int | None = None
    for subset in itertools.combinations(edges, n_rooms - 1):
        if is_spanning_tree(n_rooms, list(subset)):
            length = total_length(list(subset))
            if best is None or length < best:
                best = length
    if best is None:
        raise ValueError("the rooms cannot all be connected with the given pipes")
    return best


def legacy_greedy(n_rooms: int, edges: list[Edge]) -> list[Edge]:
    """The original exercise's rule, kept only for comparison.

    It takes the shortest pipes first and keeps a pipe whenever at least one of
    its rooms is still unconnected. Two brand-new rooms can therefore form a
    cluster that is never linked to the rest, so the result may be disconnected.
    """
    connected: set[int] = set()
    chosen: list[Edge] = []
    for edge in sorted(edges):
        if edge.a not in connected or edge.b not in connected:
            chosen.append(edge)
            connected.update((edge.a, edge.b))
        if len(connected) == n_rooms:
            break
    return chosen


def legacy_comparison(runs: int = 1000, seed: int = 0) -> dict[str, int]:
    """Run both rules on random buildings (10-20 rooms, 2-6 floors, like the
    original exercise) and count how often each fails to connect every room."""
    legacy_failures = 0
    kruskal_failures = 0
    for index in range(runs):
        rng = random.Random(seed + index)
        n_rooms = rng.randint(10, 20)
        n_floors = rng.randint(2, 6)
        building = generate_building(n_rooms, n_floors, seed=rng.randrange(2**32))
        if not is_spanning_tree(n_rooms, legacy_greedy(n_rooms, building.edges)):
            legacy_failures += 1
        if not is_spanning_tree(n_rooms, kruskal(n_rooms, building.edges)):
            kruskal_failures += 1
    return {
        "runs": runs,
        "legacy_failures": legacy_failures,
        "kruskal_failures": kruskal_failures,
    }


def plot_network(building: Building, pipes: list[Edge], path: str | Path) -> None:
    """Save a picture of the chosen pipes (needs matplotlib)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch

    widest = max(len(floor) for floor in building.floors)
    position: dict[int, tuple[float, float]] = {}
    for level, floor in enumerate(building.floors):
        for index, room in enumerate(floor):
            x = (widest - 1) / 2 if len(floor) == 1 else (widest - 1) * index / (len(floor) - 1)
            position[room] = (x, level * 1.8)

    fig, ax = plt.subplots(figsize=(max(7.0, 1.3 * widest), max(4.5, 1.9 * building.n_floors)))
    same_floor_color, between_floor_color = "#1f77b4", "#e67e22"

    for pipe in pipes:
        start, end = position[pipe.a], position[pipe.b]
        if building.floor_of(pipe.a) == building.floor_of(pipe.b):
            if start[0] > end[0]:
                start, end = end, start
            ax.add_patch(
                FancyArrowPatch(
                    start, end, arrowstyle="-", connectionstyle="arc3,rad=-0.3",
                    color=same_floor_color, linewidth=2, zorder=1,
                )
            )
        else:
            ax.plot(*zip(start, end), color=between_floor_color, linewidth=2, zorder=1)

    for room, (x, y) in position.items():
        ax.scatter([x], [y], s=520, color="white", edgecolor="black", zorder=3)
        ax.text(x, y, str(room), ha="center", va="center", fontsize=9, zorder=4)
    for level in range(building.n_floors):
        ax.text(-0.9, level * 1.8, f"Floor {level + 1}", ha="right", va="center", fontsize=10)

    ax.set_xlim(-2.2, widest - 0.2)
    ax.set_ylim(-1.2, (building.n_floors - 1) * 1.8 + 1.2)
    ax.axis("off")
    ax.set_title(f"Minimum pipe network: {len(pipes)} pipes, {total_length(pipes)} m in total")
    ax.legend(
        handles=[
            Line2D([0], [0], color=same_floor_color, lw=2, label="pipe on one floor"),
            Line2D([0], [0], color=between_floor_color, lw=2, label="pipe between floors"),
        ],
        loc="lower right",
        frameon=False,
    )
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
