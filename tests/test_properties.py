"""Property tests on many random small mazes (development seeds only)."""

import itertools

import numpy as np
import pytest

from maze_runner import verify
from maze_runner.generator import make_maze
from maze_runner.heuristics import heuristic_table
from maze_runner.problem import GridProblem
from maze_runner.search import search

UNWEIGHTED = [
    ("perfect", {}),
    ("looped", {"loop_rate": 0.1}),
    ("looped", {"loop_rate": 0.5}),
    ("looped", {"loop_rate": 1.0}),
]
WEIGHTED = [
    ("weighted", {"loop_rate": 0.1, "mud_rate": 0.2}),
    ("weighted", {"loop_rate": 0.5, "mud_rate": 0.4}),
]
SIZES = [3, 6, 12]
SEEDS = range(0, 20)


def _cases(kinds):
    return [
        pytest.param(kind, kwargs, n, seed, id=f"{kind}-{'-'.join(map(str, kwargs.values())) or '0'}-n{n}-s{seed}")
        for (kind, kwargs), n, seed in itertools.product(kinds, SIZES, SEEDS)
    ]


def _setup(kind, kwargs, n, seed):
    maze = make_maze(kind, n, seed, **kwargs)
    return maze, GridProblem(maze.grid, maze.start, maze.goal)


def _check(maze, result):
    return verify.check_path(maze.grid, maze.start, maze.goal, result.path, result.path_cost, result.path_len)


@pytest.mark.parametrize("kind,kwargs,n,seed", _cases(UNWEIGHTED))
def test_unweighted_all_optimal_algorithms_agree_and_verify(kind, kwargs, n, seed):
    maze, problem = _setup(kind, kwargs, n, seed)
    best = verify.optimal_steps(maze.grid, maze.start, maze.goal)
    for algorithm, extra in [
        ("bfs", {}), ("bfs", {"goal_test": "pop"}), ("ucs", {}),
        ("astar", {"tie_rule": "fifo"}), ("astar", {"tie_rule": "larger_g"}),
    ]:
        result = search(problem, algorithm, **extra)
        report = _check(maze, result)
        assert report.legal, report.reason
        assert result.path_len == best == result.path_cost
        assert result.expanded <= maze.open_cells - 1  # nothing expanded twice, goal never counted
        assert result.reached <= maze.open_cells


@pytest.mark.parametrize("kind,kwargs,n,seed", _cases(WEIGHTED))
def test_weighted_ucs_and_astar_are_optimal_and_bfs_is_step_optimal(kind, kwargs, n, seed):
    maze, problem = _setup(kind, kwargs, n, seed)
    best_cost = verify.optimal_cost(maze.grid, maze.start, maze.goal)
    best_steps = verify.optimal_steps(maze.grid, maze.start, maze.goal)
    for algorithm, extra in [("ucs", {}), ("astar", {"tie_rule": "fifo"}), ("astar", {"tie_rule": "larger_g"})]:
        result = search(problem, algorithm, **extra)
        assert _check(maze, result).legal
        assert result.path_cost == best_cost
    bfs = search(problem, "bfs")
    assert _check(maze, bfs).legal
    assert bfs.path_len == best_steps
    assert bfs.path_cost >= best_cost


@pytest.mark.parametrize("kind,kwargs,n,seed", _cases(UNWEIGHTED[:2] + WEIGHTED[:1]))
def test_astar_with_zero_heuristic_is_exactly_ucs(kind, kwargs, n, seed):
    maze, problem = _setup(kind, kwargs, n, seed)
    ucs = search(problem, "ucs", record_trace=True)
    astar0 = search(problem, "astar", heuristic="zero", record_trace=True)
    assert astar0.expansion_order == ucs.expansion_order
    assert (astar0.path, astar0.path_cost, astar0.expanded, astar0.generated, astar0.peak_frontier) == (
        ucs.path, ucs.path_cost, ucs.expanded, ucs.generated, ucs.peak_frontier)


@pytest.mark.parametrize("kind,kwargs,n,seed", _cases(UNWEIGHTED[:2] + WEIGHTED))
def test_manhattan_is_consistent_on_every_edge_and_admissible_on_every_square(kind, kwargs, n, seed):
    maze, problem = _setup(kind, kwargs, n, seed)
    h = heuristic_table(problem, "manhattan")
    true_cost = verify.cost_to_goal(maze.grid, maze.goal)
    assert h[problem.goal] == 0
    for r, c in np.argwhere(maze.grid != 0):
        u = problem.index((int(r), int(c)))
        assert 0 <= h[u] <= true_cost[(int(r), int(c))]  # admissible
        for v, step_cost in problem.successors(u):
            assert h[u] <= step_cost + h[v]  # consistent


@pytest.mark.parametrize("kind,kwargs,n,seed", _cases(UNWEIGHTED[:2] + WEIGHTED[:1]))
def test_greedy_and_weighted_astar_return_legal_paths_that_are_never_better_than_optimal(kind, kwargs, n, seed):
    maze, problem = _setup(kind, kwargs, n, seed)
    best_cost = verify.optimal_cost(maze.grid, maze.start, maze.goal)
    for algorithm, extra in [("greedy", {}), ("astar", {"weight": 2.0}), ("astar", {"weight": 3.0})]:
        result = search(problem, algorithm, **extra)
        assert _check(maze, result).legal
        assert result.path_cost >= best_cost
        if algorithm == "astar":  # weighted A* is bounded by w times the optimum
            assert result.path_cost <= extra["weight"] * best_cost


def test_manhattan_scales_with_the_cheapest_entry_cost():
    grid = np.full((3, 3), 2, dtype=np.int64)
    problem = GridProblem(grid, (0, 0), (2, 2))
    h = heuristic_table(problem, "manhattan")
    assert problem.min_cost == 2 and h[problem.start] == 8  # 2 * (2 + 2)
    assert search(problem, "astar").path_cost == 8


def test_an_inconsistent_heuristic_still_gives_the_optimum_because_reopening_is_allowed(monkeypatch):
    #   S A B C G     every square costs 1 to enter except G, which costs 10
    #   . # # . #
    #   . . . . #
    # h(A) = 12 = h*(A) and h = 0 elsewhere: admissible, but inconsistent (h(A) > 1 + h(B)).
    # f(A) = 13, so the search first walks the long lower route and expands C with g = 7 and
    # B with g = 8. When A is finally expanded, B (g = 2) and C (g = 3) are reached more
    # cheaply and must be reopened; with permanent closure the answer would be 17, not 13.
    grid = np.array([
        [1, 1, 1, 1, 10],
        [1, 0, 0, 1, 0],
        [1, 1, 1, 1, 0],
    ], dtype=np.int64)
    problem = GridProblem(grid, (0, 0), (0, 4))
    table = [0] * len(problem.cost)
    table[problem.index((0, 1))] = 12
    import maze_runner.search as search_module
    monkeypatch.setattr(search_module, "heuristic_table", lambda *a, **k: table)
    result = search(problem, "astar", record_trace=True)
    assert result.path == [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]
    assert result.path_cost == 13 == verify.optimal_cost(grid, (0, 0), (0, 4))
    assert result.expansion_order.count((0, 3)) == 2  # C was expanded, then reopened
    assert result.expansion_order.count((0, 2)) == 2  # so was B


def test_same_instance_and_same_settings_give_identical_results():
    maze, problem = _setup("looped", {"loop_rate": 0.1}, 25, 3)
    a = search(problem, "astar", tie_rule="larger_g", record_trace=True)
    b = search(problem, "astar", tie_rule="larger_g", record_trace=True)
    assert a.expansion_order == b.expansion_order and a.path == b.path
