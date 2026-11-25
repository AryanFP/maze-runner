"""Known-answer tests: tiny hand-traced grids.

Conventions used in every trace below
  * neighbour order: Up, Right, Down, Left
  * a node is expanded when it is removed from the frontier, is not stale, is
    not the goal, and its successors are generated (the goal is never counted)
  * BFS tests the goal when it is generated unless stated otherwise
  * cells are written (row, col); S = start, G = goal, # = wall
"""

import numpy as np
import pytest

from maze_runner.problem import GridProblem
from maze_runner.search import search


def grid_from(text: str):
    """Build a cost grid. '.', 'S' and 'G' cost 1, '#' is a wall, a digit is an entry cost."""
    rows = [line.split() for line in text.strip().splitlines()]
    grid = np.zeros((len(rows), len(rows[0])), dtype=np.int64)
    start = goal = None
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                continue
            grid[r, c] = int(ch) if ch.isdigit() else 1
            if ch == "S":
                start = (r, c)
            if ch == "G":
                goal = (r, c)
    return grid, start, goal


def run(text, algorithm, **kwargs):
    grid, start, goal = grid_from(text)
    return search(GridProblem(grid, start, goal), algorithm, record_trace=True, **kwargs)


# ---------------------------------------------------------------------------
# 1. Open 3x3 grid
# ---------------------------------------------------------------------------
OPEN_3X3 = """
S . .
. . .
. . G
"""


def test_open_grid_bfs_goal_test_at_generation():
    # queue trace: expand (0,0) -> push (0,1),(1,0)
    #              expand (0,1) -> push (0,2),(1,1)
    #              expand (1,0) -> push (2,0)
    #              expand (0,2) -> push (1,2)
    #              expand (1,1) -> push (2,1)
    #              expand (2,0) -> nothing new
    #              expand (1,2) -> generates the goal (2,2): stop
    r = run(OPEN_3X3, "bfs")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (0, 2), (1, 1), (2, 0), (1, 2)]
    assert r.expanded == 7
    assert r.generated == 8  # every cell except the start
    assert r.path == [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]
    assert r.path_len == 4 and r.path_cost == 4


def test_open_grid_bfs_goal_test_at_removal_expands_one_more():
    # as above, but (2,1) is also expanded before the goal reaches the front of the queue
    r = run(OPEN_3X3, "bfs", goal_test="pop")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (0, 2), (1, 1), (2, 0), (1, 2), (2, 1)]
    assert r.expanded == 8 and r.path_len == 4


def test_open_grid_astar_fifo_ties_expands_everything():
    # every cell has f = g + h = 4 = C*, so FIFO ties make A* behave like BFS with a
    # goal test at removal: all 8 non-goal cells are expanded. This is MORE than BFS
    # with a goal test at generation (7): A* is not guaranteed to beat that baseline.
    r = run(OPEN_3X3, "astar", tie_rule="fifo")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (0, 2), (1, 1), (2, 0), (1, 2), (2, 1)]
    assert r.expanded == 8 and r.path_len == 4


def test_open_grid_astar_larger_g_ties_goes_straight_to_the_goal():
    # among equal f the deepest record is taken first:
    # (0,0) -> (0,1) -> (0,2) -> (1,2) -> goal
    r = run(OPEN_3X3, "astar", tie_rule="larger_g")
    assert r.expansion_order == [(0, 0), (0, 1), (0, 2), (1, 2)]
    assert r.expanded == 4 and r.generated == 6 and r.path_len == 4


def test_open_grid_ucs_matches_bfs_with_goal_test_at_removal():
    r = run(OPEN_3X3, "ucs")
    assert r.expanded == 8 and r.path_cost == 4


# ---------------------------------------------------------------------------
# 2. Single corridor
# ---------------------------------------------------------------------------
CORRIDOR = "S . . . G"


@pytest.mark.parametrize("algorithm,kwargs", [
    ("bfs", {}), ("bfs", {"goal_test": "pop"}), ("ucs", {}),
    ("astar", {"tie_rule": "fifo"}), ("astar", {"tie_rule": "larger_g"}), ("greedy", {}),
])
def test_corridor_every_algorithm_expands_the_four_cells_before_the_goal(algorithm, kwargs):
    r = run(CORRIDOR, algorithm, **kwargs)
    assert r.expansion_order == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert r.expanded == 4 and r.path_len == 4 and r.path_cost == 4
    assert r.peak_frontier == 1


# ---------------------------------------------------------------------------
# 3. Direct route along the top: the heuristic helps
# ---------------------------------------------------------------------------
DIRECT = """
S . . G
. # # .
. . . .
"""


def test_direct_route_bfs():
    # expand (0,0) -> (0,1),(1,0); expand (0,1) -> (0,2); expand (1,0) -> (2,0);
    # expand (0,2) -> generates the goal
    r = run(DIRECT, "bfs")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (0, 2)]
    assert r.expanded == 4 and r.path_len == 3


def test_direct_route_astar_never_leaves_the_top_row():
    # f(0,0)=3, f(0,1)=1+2=3, f(1,0)=1+4=5, f(0,2)=2+1=3, goal f=3
    r = run(DIRECT, "astar")
    assert r.expansion_order == [(0, 0), (0, 1), (0, 2)]
    assert r.expanded == 3 and r.path_len == 3


# ---------------------------------------------------------------------------
# 4. Dead end that points at the goal: the heuristic does not help
# ---------------------------------------------------------------------------
DEAD_END = """
S . # G
. # # .
. . . .
"""
DEAD_END_PATH = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (1, 3), (0, 3)]


def test_dead_end_bfs():
    r = run(DEAD_END, "bfs")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (1, 3)]
    assert r.expanded == 8 and r.path == DEAD_END_PATH and r.path_len == 7


def test_dead_end_astar_saves_nothing():
    # h(start) = 3 but C* = 7. f(0,1) = 1 + 2 = 3 is the smallest value, so the dead end is
    # expanded first. The real route has f = 5, 7, 7, 7, 7, 7, 7 and every cell on it must be
    # expanded. A* expands all 8 non-goal cells, the same as BFS.
    r = run(DEAD_END, "astar")
    assert r.expansion_order == [(0, 0), (0, 1), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (1, 3)]
    assert r.expanded == 8 and r.path == DEAD_END_PATH


def test_dead_end_greedy_also_walks_into_it():
    r = run(DEAD_END, "greedy")
    assert r.expansion_order[:2] == [(0, 0), (0, 1)]
    assert r.path == DEAD_END_PATH


# ---------------------------------------------------------------------------
# 5. Unreachable goal
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("algorithm", ["bfs", "ucs", "astar", "greedy"])
def test_unreachable_goal_returns_failure(algorithm):
    r = run("S . # G", algorithm)
    assert not r.found
    assert r.path == [] and r.path_len == -1 and r.path_cost == -1
    assert r.expanded == 2  # both reachable cells are expanded, then the frontier is empty


def test_start_equals_goal():
    grid = np.ones((2, 2), dtype=np.int64)
    r = search(GridProblem(grid, (0, 0), (0, 0)), "astar")
    assert r.found and r.path == [(0, 0)] and r.path_len == 0 and r.expanded == 0


# ---------------------------------------------------------------------------
# 6. Costs: fewest steps is not lowest cost, and the goal must be tested on removal
# ---------------------------------------------------------------------------
def test_bfs_takes_the_short_expensive_route_and_ucs_astar_the_cheap_one():
    # straight through the expensive cell: 2 steps, cost 9 + 1 = 10
    # around the wall: 6 steps, cost 6
    text = """
    S 9 G
    . # .
    . . .
    """
    bfs, ucs, astar = run(text, "bfs"), run(text, "ucs"), run(text, "astar")
    assert bfs.path_len == 2 and bfs.path_cost == 10
    assert ucs.path_len == 6 and ucs.path_cost == 6
    assert astar.path_len == 6 and astar.path_cost == 6

