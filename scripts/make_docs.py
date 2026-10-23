"""Regenerate every picture in docs/ from the real program output.

Run from the repository root:  python scripts/make_docs.py
Needs matplotlib. Nothing here is mocked: command output is captured by running
the actual code, and the charts use measured timings (which vary per machine).
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from optalgo import trip_planner  # noqa: E402
from optalgo.cli import main  # noqa: E402

DOCS = ROOT / "docs"
EXAMPLE = "examples/trip_berlin.json"


def run_cli(argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(argv)
    if code != 0:
        raise SystemExit(f"command failed: {argv}")
    return buffer.getvalue()


def terminal_image(command: str, output: str, path: Path) -> None:
    """Render a command and its output as a dark terminal-style picture."""
    lines = output.rstrip("\n").split("\n")
    char_w, line_h, bar = 0.0836, 0.215, 0.42
    columns = max(len(command) + 2, *(len(line) for line in lines))
    width = columns * char_w + 0.9
    height = (len(lines) + 2) * line_h + 0.5 + bar

    fig = plt.figure(figsize=(width, height), dpi=160)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0.04, 0.04), width - 0.08, height - 0.08,
            boxstyle="round,pad=0,rounding_size=0.12", facecolor="#1e1e1e", edgecolor="#3c3c3c",
        )
    )
    for index, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        ax.add_patch(Circle((0.3 + index * 0.24, height - 0.26), 0.07, color=color))

    mono = {"family": "DejaVu Sans Mono", "fontsize": 10, "va": "center"}
    x0, y = 0.45, height - bar - 0.25
    ax.text(x0, y, "$", color="#27c93f", **mono)
    ax.text(x0 + 2 * char_w, y, command, color="#ffffff", **mono)
    y -= 2 * line_h
    for line in lines:
        color = "#d4d4d4"
        if "passed" in line:
            color = "#27c93f"
        elif line.startswith(("Total", "Best route", "Places visited")):
            color = "#ffd866"
        ax.text(x0, y, line, color=color, **mono)
        y -= line_h

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")


def cli_image(argv: list[str], name: str) -> None:
    terminal_image("python -m optalgo " + " ".join(argv), run_cli(argv), DOCS / name)


def benchmark_chart(path: Path) -> list[dict]:
    rows = trip_planner.benchmark(sizes=(4, 5, 6, 7, 8, 9, 10, 12, 14, 16))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    series = (
        ("brute", "Brute force, O(n!)", "#c0392b", "o"),
        ("dp", "Dynamic programming, O(2^n * n^2)", "#1f77b4", "s"),
        ("greedy", "Greedy heuristic, O(n^3)", "#7f8c8d", "^"),
    )
    for key, label, color, marker in series:
        points = [(row["places"], max(row[key], 1e-5)) for row in rows if row[key] is not None]
        ax.plot(*zip(*points), marker=marker, color=color, label=label, linewidth=2)
    ax.set_yscale("log")
    ax.set_xticks([row["places"] for row in rows])
    ax.set_xlabel("number of places")
    ax.set_ylabel("runtime in seconds (log scale)")
    ax.set_title("Trip planner: solver runtime")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")
    return rows


def main_docs() -> None:
    cli_image(["pipes", "--rooms", "12", "--floors", "3", "--seed", "4"], "pipes_output.png")
    run_cli([
        "pipes", "--rooms", "12", "--floors", "3", "--seed", "4",
        "--between-floor-range", "15", "40", "--plot", str(DOCS / "pipe_network.png"),
    ])
    print("wrote docs/pipe_network.png")
    cli_image(["pipes", "--legacy-check", "3000"], "legacy_check.png")
    cli_image(["trip", "--input", EXAMPLE], "trip_output.png")
    run_cli(["trip", "--input", EXAMPLE, "--plot", str(DOCS / "trip_route.png")])
    print("wrote docs/trip_route.png")

    rows = benchmark_chart(DOCS / "benchmark.png")
    print("\nBenchmark rows (seconds):")
    for row in rows:
        brute = "skipped" if row["brute"] is None else f"{row['brute']:.4f}"
        print(f"| {row['places']} | {brute} | {row['dp']:.4f} | {row['greedy']:.4f} | "
              f"{row['optimal_places']} | {row['greedy_places']} |")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    terminal_image("pytest", result.stdout, DOCS / "tests_output.png")


if __name__ == "__main__":
    main_docs()
