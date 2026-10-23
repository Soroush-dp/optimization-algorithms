from pathlib import Path

import pytest

from optalgo.cli import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "trip_berlin.json"


def test_pipes_command(capsys):
    assert main(["pipes", "--rooms", "12", "--floors", "3", "--seed", "1"]) == 0
    assert "Total pipe length" in capsys.readouterr().out


def test_pipes_command_is_reproducible(capsys):
    main(["pipes", "--seed", "7"])
    first = capsys.readouterr().out
    main(["pipes", "--seed", "7"])
    assert capsys.readouterr().out == first


def test_pipes_legacy_check(capsys):
    assert main(["pipes", "--legacy-check", "50"]) == 0
    assert "Kruskal left rooms disconnected in 0" in capsys.readouterr().out


def test_pipes_plot_creates_a_picture(tmp_path):
    pytest.importorskip("matplotlib")
    target = tmp_path / "network.png"
    assert main(["pipes", "--rooms", "10", "--floors", "3", "--seed", "2", "--plot", str(target)]) == 0
    assert target.stat().st_size > 0


def test_pipes_rejects_more_floors_than_rooms(capsys):
    assert main(["pipes", "--rooms", "2", "--floors", "5"]) == 2
    assert "error" in capsys.readouterr().err


def test_trip_command(capsys):
    assert main(["trip", "--places", "6", "--seed", "2"]) == 0
    assert "Places visited" in capsys.readouterr().out


def test_trip_from_json_file(capsys):
    assert main(["trip", "--input", str(EXAMPLE)]) == 0
    assert "Best route" in capsys.readouterr().out


def test_trip_missing_file_returns_error_code(capsys):
    assert main(["trip", "--input", "does-not-exist.json"]) == 2
    assert "error" in capsys.readouterr().err


def test_pipes_custom_length_ranges(capsys):
    argv = ["pipes", "--rooms", "6", "--floors", "2", "--seed", "3",
            "--same-floor-range", "40", "50", "--between-floor-range", "41", "42"]
    assert main(argv) == 0
    assert "Total pipe length" in capsys.readouterr().out


def test_trip_plot_creates_a_picture(tmp_path):
    pytest.importorskip("matplotlib")
    target = tmp_path / "route.png"
    assert main(["trip", "--input", str(EXAMPLE), "--plot", str(target)]) == 0
    assert target.stat().st_size > 0
