"""Tests for the independent verifier and the experiment runner."""

import json

import numpy as np
import pandas as pd

from maze_runner import verify
from maze_runner.experiment import COLUMNS, TIMING_COLUMNS, run_suite

GRID = np.array([
    [1, 1, 1],
    [0, 0, 5],
    [1, 1, 1],
], dtype=np.int64)
GOOD = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]


def test_verifier_accepts_a_legal_path_and_recomputes_its_cost():
    report = verify.check_path(GRID, (0, 0), (2, 2), GOOD, reported_cost=8, reported_len=4)
    assert report.legal and report.cost == 8 and report.steps == 4


def test_verifier_rejects_bad_paths():
    check = lambda path, **kw: verify.check_path(GRID, (0, 0), (2, 2), path, **kw).legal
    assert not check([])
    assert not check(GOOD[1:])  # wrong start
    assert not check(GOOD[:-1])  # wrong end
    assert not check([(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)])  # walks through a wall
    assert not check([(0, 0), (0, 2), (1, 2), (2, 2)])  # jumps two squares
    assert not check([(0, 0), (1, 1), (2, 2)])  # diagonal moves
    assert not check([(0, 0), (0, 1), (0, 2), (0, 3), (1, 2), (2, 2)])  # leaves the grid
    assert not check(GOOD, reported_cost=4)  # wrong reported cost
    assert not check(GOOD, reported_len=5)  # wrong reported length


def test_reference_optimum_by_hand():
    assert verify.optimal_cost(GRID, (0, 0), (2, 2)) == 8
    assert verify.optimal_steps(GRID, (0, 0), (2, 2)) == 4
    assert verify.optimal_cost(GRID, (0, 0), (2, 0)) == 10
    blocked = np.array([[1, 0, 1]])
    assert verify.optimal_cost(blocked, (0, 0), (0, 2)) is None
    assert verify.optimal_steps(blocked, (0, 0), (0, 2)) is None


def test_cost_to_goal_pays_for_the_square_entered():
    dist = verify.cost_to_goal(GRID, (2, 2))
    assert dist[(2, 2)] == 0
    assert dist[(1, 2)] == 1  # entering the goal costs 1
    assert dist[(0, 2)] == 6  # entering the mud costs 5, then 1
    assert dist[(0, 0)] == 8


CONFIG = {
    "suite": "unit",
    "experiments": [
        {
            "name": "main", "maze_types": ["perfect", "looped"], "sizes": [5, 8],
            "seeds": {"start": 0, "count": 3}, "loop_rates": [0.2], "timing_repeats": 2,
            "runs": [{"algorithm": "bfs"}, {"algorithm": "astar", "tie_rule": "larger_g"}],
        },
        {
            "name": "weighted", "maze_types": ["weighted"], "sizes": [8],
            "seeds": [5, 6], "loop_rates": [0.2], "mud_rates": [0.0, 0.3], "timing_repeats": 1,
            "runs": [{"algorithm": "bfs"}, {"algorithm": "ucs"}, {"algorithm": "astar"},
                     {"algorithm": "greedy"}],
        },
    ],
}


def _run(tmp_path, name):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(CONFIG))
    out = tmp_path / name
    run_suite(config_path, out, log=lambda *_: None)
    return pd.read_csv(out / "runs.csv"), json.loads((out / "metadata.json").read_text())


def test_runner_writes_one_verified_row_per_maze_and_setting(tmp_path):
    df, meta = _run(tmp_path, "a")
    assert list(df.columns) == COLUMNS
    assert len(df) == 2 * 2 * 3 * 2 + 1 * 2 * 2 * 4
    assert df["verified"].all()
    assert df.loc[df["expect_optimal"], "optimal"].all()
    assert meta["counts"]["rows"] == len(df) == meta["counts"]["verified"]
    assert meta["counts"]["optimal_ok"] == meta["counts"]["optimal_expected"] == int(df["expect_optimal"].sum())
    assert meta["environment"]["python"]
    # every algorithm saw exactly the same instance
    per_maze = df.groupby(["experiment", "maze_type", "n_cells", "seed", "loop_rate", "mud_rate"])
    assert (per_maze["maze_hash"].nunique() == 1).all()
    assert (per_maze["optimal_cost"].nunique() == 1).all()


def test_runner_is_deterministic_except_for_timing(tmp_path):
    a, _ = _run(tmp_path, "a")
    b, _ = _run(tmp_path, "b")
    pd.testing.assert_frame_equal(a.drop(columns=TIMING_COLUMNS), b.drop(columns=TIMING_COLUMNS))
