import random

import pytest

from optalgo.pipe_network import (
    Edge,
    UnionFind,
    brute_force_total,
    generate_building,
    is_spanning_tree,
    kruskal,
    legacy_comparison,
    legacy_greedy,
    prim,
    total_length,
)


def test_union_find_merges_and_counts_components():
    clusters = UnionFind(4)
    assert clusters.components == 4
    assert clusters.union(0, 1) is True
    assert clusters.union(1, 0) is False
    assert clusters.find(0) == clusters.find(1)
    assert clusters.components == 3


def test_generate_building_deals_rooms_evenly():
    building = generate_building(14, 4, seed=1)
    assert sorted(room for floor in building.floors for room in floor) == list(range(14))
    sizes = [len(floor) for floor in building.floors]
    assert max(sizes) - min(sizes) <= 1
    assert building.n_floors == 4


def test_generate_building_is_reproducible():
    assert generate_building(12, 3, seed=5) == generate_building(12, 3, seed=5)


@pytest.mark.parametrize("rooms,floors", [(0, 1), (3, 0), (2, 5)])
def test_generate_building_rejects_impossible_sizes(rooms, floors):
    with pytest.raises(ValueError):
        generate_building(rooms, floors)


@pytest.mark.parametrize("seed", range(40))
def test_kruskal_and_prim_connect_everything_with_equal_length(seed):
    rng = random.Random(seed)
    n_rooms = rng.randint(2, 20)
    n_floors = rng.randint(1, min(6, n_rooms))
    building = generate_building(n_rooms, n_floors, seed=seed)
    by_kruskal = kruskal(n_rooms, building.edges)
    by_prim = prim(n_rooms, building.edges)
    assert is_spanning_tree(n_rooms, by_kruskal)
    assert is_spanning_tree(n_rooms, by_prim)
    assert total_length(by_kruskal) == total_length(by_prim)


@pytest.mark.parametrize("seed", range(15))
def test_kruskal_matches_exhaustive_search_on_small_buildings(seed):
    rng = random.Random(seed)
    n_rooms = rng.randint(3, 6)
    n_floors = rng.randint(1, min(3, n_rooms))
    building = generate_building(n_rooms, n_floors, seed=seed)
    assert total_length(kruskal(n_rooms, building.edges)) == brute_force_total(n_rooms, building.edges)


def test_kruskal_raises_when_rooms_cannot_be_connected():
    with pytest.raises(ValueError):
        kruskal(4, [Edge(1, 0, 1), Edge(2, 2, 3)])


def test_prim_raises_when_rooms_cannot_be_connected():
    with pytest.raises(ValueError):
        prim(4, [Edge(1, 0, 1), Edge(2, 2, 3)])


def test_single_room_needs_no_pipes():
    assert kruskal(1, []) == []
    assert is_spanning_tree(1, [])


def test_legacy_rule_can_leave_two_clusters():
    # Rooms 0-1 and 2-3 are joined by the cheapest pipes, so the legacy rule never
    # adds the pipe that links the two pairs.
    edges = [Edge(1, 0, 1), Edge(1, 2, 3), Edge(5, 1, 2)]
    assert not is_spanning_tree(4, legacy_greedy(4, edges))
    assert is_spanning_tree(4, kruskal(4, edges))


def test_legacy_rule_fails_often_but_kruskal_never_does():
    stats = legacy_comparison(runs=200, seed=0)
    assert stats["legacy_failures"] > 0
    assert stats["kruskal_failures"] == 0
