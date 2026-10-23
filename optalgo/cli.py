"""Command line interface: ``python -m optalgo pipes ...`` / ``python -m optalgo trip ...``."""

from __future__ import annotations

import argparse
import random
import sys

from . import pipe_network, trip_planner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="optalgo",
        description="Pipe-network design (MST) and time-limited trip planning.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    pipes = commands.add_parser("pipes", help="connect all rooms of a building with minimum pipe")
    pipes.add_argument("--rooms", type=int, help="number of rooms (default: random 10-20)")
    pipes.add_argument("--floors", type=int, help="number of floors (default: random 2-6)")
    pipes.add_argument("--seed", type=int, help="random seed for reproducible results")
    pipes.add_argument("--algorithm", choices=["kruskal", "prim"], default="kruskal")
    pipes.add_argument(
        "--same-floor-range", nargs=2, type=int, default=[10, 30], metavar=("MIN", "MAX"),
        help="random pipe length between rooms on one floor in metres (default: 10 30)",
    )
    pipes.add_argument(
        "--between-floor-range", nargs=2, type=int, default=[5, 10], metavar=("MIN", "MAX"),
        help="random pipe length between adjacent floors in metres (default: 5 10)",
    )
    pipes.add_argument("--plot", metavar="FILE", help="save a picture of the network (needs matplotlib)")
    pipes.add_argument(
        "--legacy-check", type=int, metavar="RUNS",
        help="compare the original greedy rule with Kruskal on RUNS random buildings and exit",
    )

    trip = commands.add_parser("trip", help="visit as many places as possible within a time limit")
    trip.add_argument("--places", type=int, default=5, help="number of random places (default: 5)")
    trip.add_argument("--max-time", type=int, default=180, help="time budget in minutes (default: 180)")
    trip.add_argument("--seed", type=int, help="random seed for reproducible results")
    trip.add_argument("--algorithm", choices=sorted(trip_planner.ALGORITHMS), default="dp")
    trip.add_argument("--asymmetric", action="store_true", help="draw each travel direction independently")
    trip.add_argument("--input", metavar="FILE", help="load the problem from a JSON file instead")
    trip.add_argument("--save", metavar="FILE", help="save the problem that was used as JSON")
    trip.add_argument("--plot", metavar="FILE", help="save a timeline picture of the route (needs matplotlib)")
    trip.add_argument("--benchmark", action="store_true", help="time all algorithms and exit")
    return parser


def _run_pipes(args: argparse.Namespace) -> int:
    if args.legacy_check:
        stats = pipe_network.legacy_comparison(args.legacy_check, seed=args.seed or 0)
        runs = stats["runs"]
        print(f"Random buildings tested: {runs}")
        print(
            f"Original greedy rule left rooms disconnected in {stats['legacy_failures']} "
            f"cases ({stats['legacy_failures'] / runs:.1%})"
        )
        print(
            f"Kruskal left rooms disconnected in {stats['kruskal_failures']} "
            f"cases ({stats['kruskal_failures'] / runs:.1%})"
        )
        return 0

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    rng = random.Random(seed)
    n_rooms = args.rooms or rng.randint(10, 20)
    n_floors = args.floors or min(rng.randint(2, 6), n_rooms)
    building = pipe_network.generate_building(
        n_rooms,
        n_floors,
        seed=rng.randrange(2**32),
        same_floor_range=tuple(args.same_floor_range),
        between_floor_range=tuple(args.between_floor_range),
    )

    solver = pipe_network.kruskal if args.algorithm == "kruskal" else pipe_network.prim
    pipes = sorted(solver(building.n_rooms, building.edges))

    print(f"Seed: {seed} (use --seed {seed} to reproduce)")
    print(f"Building: {n_rooms} rooms on {n_floors} floors\n")
    print("Floors")
    for level, floor in enumerate(building.floors, start=1):
        print(f"  Floor {level}: {floor}")
    print(f"\nPipes ({args.algorithm})")
    for pipe in pipes:
        print(f"  room {pipe.a:>2} -- room {pipe.b:>2}   {pipe.length} m")
    print(f"\nTotal pipe length: {pipe_network.total_length(pipes)} m ({len(pipes)} pipes)")

    if args.plot:
        try:
            pipe_network.plot_network(building, pipes, args.plot)
        except ImportError:
            print("error: --plot needs matplotlib (pip install matplotlib)", file=sys.stderr)
            return 1
        print(f"Picture saved to {args.plot}")
    return 0


def _run_trip(args: argparse.Namespace) -> int:
    if args.benchmark:
        rows = trip_planner.benchmark(max_time=args.max_time, seed=args.seed or 0)
        print(f"{'places':>6} {'brute (s)':>10} {'dp (s)':>10} {'greedy (s)':>11} {'optimal':>8} {'greedy':>7}  agree")
        for row in rows:
            brute = "skipped" if row["brute"] is None else f"{row['brute']:.4f}"
            agree = "-" if row["agree"] is None else ("yes" if row["agree"] else "NO")
            print(
                f"{row['places']:>6} {brute:>10} {row['dp']:>10.4f} {row['greedy']:>11.4f} "
                f"{row['optimal_places']:>8} {row['greedy_places']:>7}  {agree}"
            )
        return 0

    if args.input:
        problem = trip_planner.TripProblem.from_json(args.input)
    else:
        seed = args.seed if args.seed is not None else random.randrange(1_000_000)
        problem = trip_planner.generate_problem(
            args.places, args.max_time, seed=seed, symmetric=not args.asymmetric
        )
        print(f"Seed: {seed} (use --seed {seed} to reproduce)\n")
    if args.save:
        problem.to_json(args.save)

    print(f"Time budget: {problem.max_time} min\n")
    print("Places and visit times")
    for place in problem.places:
        print(f"  {place}: {problem.visit_times[place]} min")

    result = trip_planner.solve(problem, args.algorithm)
    print(f"\nAlgorithm: {result.algorithm}")
    if not result.route:
        print("No place can be visited within the time budget.")
        return 0
    print("Best route:", " -> ".join(result.route))
    print(f"Places visited: {result.num_places}")
    print(f"Total time: {result.total_time} min (limit {problem.max_time})")

    if args.plot:
        try:
            trip_planner.plot_route(problem, result, args.plot)
        except ImportError:
            print("error: --plot needs matplotlib (pip install matplotlib)", file=sys.stderr)
            return 1
        print(f"Picture saved to {args.plot}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run_pipes(args) if args.command == "pipes" else _run_trip(args)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
