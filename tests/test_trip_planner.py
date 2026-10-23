import pytest

from optalgo.trip_planner import (
    MAX_DP_PLACES,
    TripProblem,
    TripResult,
    benchmark,
    brute_force,
    dp_bitmask,
    generate_problem,
    greedy,
    plot_route,
    solve,
)


def small_problem() -> TripProblem:
    return TripProblem(
        places=["A", "B", "C"],
        visit_times={"A": 30, "B": 40, "C": 50},
        distances={
            "A": {"B": 10, "C": 20},
            "B": {"A": 10, "C": 15},
            "C": {"A": 20, "B": 15},
        },
        max_time=100,
    )


def test_route_time_adds_visits_and_legs():
    problem = small_problem()
    assert problem.route_time(["A", "B"]) == 30 + 10 + 40
    assert problem.route_time(["A", "B", "C"]) == 30 + 10 + 40 + 15 + 50
    assert problem.route_time([]) == 0


@pytest.mark.parametrize("solver", [brute_force, dp_bitmask])
def test_exact_solvers_find_the_known_optimum(solver):
    result = solver(small_problem())
    assert result.num_places == 2  # all three places need 145 min, over the 100 min limit
    assert result.total_time == 80


@pytest.mark.parametrize("seed", range(30))
def test_dp_matches_brute_force(seed):
    problem = generate_problem(
        4 + seed % 4, max_time=180 + 10 * (seed % 5), seed=seed, symmetric=bool(seed % 2)
    )
    expected, actual = brute_force(problem), dp_bitmask(problem)
    assert (actual.num_places, actual.total_time) == (expected.num_places, expected.total_time)
    if actual.route:
        assert len(set(actual.route)) == len(actual.route)
        assert problem.route_time(actual.route) == actual.total_time <= problem.max_time


@pytest.mark.parametrize("seed", range(20))
def test_greedy_is_feasible_and_never_beats_the_optimum(seed):
    problem = generate_problem(8, seed=seed)
    heuristic, optimum = greedy(problem), dp_bitmask(problem)
    assert heuristic.num_places <= optimum.num_places
    if heuristic.route:
        assert problem.route_time(heuristic.route) == heuristic.total_time <= problem.max_time


@pytest.mark.parametrize("algorithm", ["brute", "dp", "greedy"])
def test_nothing_fits_returns_an_empty_route(algorithm):
    problem = generate_problem(4, max_time=10, seed=1)
    result = solve(problem, algorithm)
    assert result.route == []
    assert result.total_time == 0


def test_generate_problem_is_reproducible_and_symmetric_by_default():
    first, second = generate_problem(6, seed=3), generate_problem(6, seed=3)
    assert first == second
    assert all(
        first.distances[p][q] == first.distances[q][p] for p in first.places for q in first.places
    )


def test_from_dict_uses_one_direction_for_both():
    problem = TripProblem.from_dict(
        {"max_time": 100, "places": {"X": 10, "Y": 20}, "distances": {"X": {"Y": 7}}}
    )
    assert problem.distances["Y"]["X"] == 7
    assert problem.distances["X"]["X"] == 0


def test_from_dict_rejects_missing_data():
    with pytest.raises(ValueError):
        TripProblem.from_dict({"max_time": 100, "places": {"X": 10, "Y": 20}})
    with pytest.raises(ValueError):
        TripProblem.from_dict({"places": {"X": 10}})


def test_json_round_trip(tmp_path):
    problem = generate_problem(5, seed=9)
    path = tmp_path / "problem.json"
    problem.to_json(path)
    assert TripProblem.from_json(path) == problem


def test_dp_rejects_too_many_places():
    with pytest.raises(ValueError):
        dp_bitmask(generate_problem(MAX_DP_PLACES + 1, seed=0))


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValueError):
        solve(small_problem(), "magic")


def test_benchmark_reports_agreement():
    rows = benchmark(sizes=(4, 5), seed=0)
    assert [row["places"] for row in rows] == [4, 5]
    assert all(row["agree"] for row in rows)


def test_plot_route_needs_a_route(tmp_path):
    with pytest.raises(ValueError):
        plot_route(small_problem(), TripResult([], 0, "dp"), tmp_path / "route.png")
