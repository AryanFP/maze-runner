"""Generator tests: reproducibility and the structure of each maze type."""

import random

import numpy as np
import pytest

from maze_runner.generator import OPEN, WALL, is_reachable, make_maze

SIZES = [2, 3, 5, 10, 25]
SEEDS = [0, 1, 2, 7, 42]


def _component_count_and_edges(grid):
    """Count connected components and edges of the open squares (4-neighbour graph)."""
    open_squares = {(int(r), int(c)) for r, c in np.argwhere(grid != WALL)}
    edges = sum(((r + 1, c) in open_squares) + ((r, c + 1) in open_squares) for r, c in open_squares)
    seen, components = set(), 0
    for sq in open_squares:
        if sq in seen:
            continue
        components += 1
        stack = [sq]
        seen.add(sq)
        while stack:
            r, c = stack.pop()
            for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if nb in open_squares and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
    return components, edges, len(open_squares)


@pytest.mark.parametrize("maze_type,kwargs", [
    ("perfect", {}),
    ("looped", {"loop_rate": 0.1}),
])
def test_same_seed_rebuilds_the_same_maze(maze_type, kwargs):
    a = make_maze(maze_type, 25, 77, **kwargs)
    b = make_maze(maze_type, 25, 77, **kwargs)
    assert a.maze_hash == b.maze_hash
    assert np.array_equal(a.grid, b.grid)


def test_different_seeds_give_different_mazes():
    hashes = {make_maze("perfect", 10, seed).maze_hash for seed in range(50)}
    assert len(hashes) == 50


def test_generation_does_not_touch_global_random_state():
    random.seed(123)
    expected = random.random()
    random.seed(123)
    make_maze("looped", 10, 5, loop_rate=0.1)
    assert random.random() == expected


@pytest.mark.parametrize("n", SIZES)
@pytest.mark.parametrize("seed", SEEDS)
def test_perfect_maze_is_a_spanning_tree(n, seed):
    maze = make_maze("perfect", n, seed)
    assert maze.grid.shape == (2 * n + 1, 2 * n + 1)
    assert maze.passages == n * n - 1
    assert maze.open_cells == 2 * n * n - 1  # n^2 cells plus n^2 - 1 passages
    components, edges, nodes = _component_count_and_edges(maze.grid)
    assert components == 1  # every cell reachable
    assert edges == nodes - 1  # connected with nodes - 1 edges means no cycles


@pytest.mark.parametrize("n", [5, 10, 25])
@pytest.mark.parametrize("seed", SEEDS)
def test_looped_maze_structure(n, seed):
    perfect = make_maze("perfect", n, seed)
    looped = make_maze("looped", n, seed, loop_rate=0.1)
    extra = round(0.1 * (n - 1) ** 2)  # a perfect maze has (n-1)^2 internal walls left
    assert looped.passages == perfect.passages + extra
    components, edges, nodes = _component_count_and_edges(looped.grid)
    assert components == 1
    assert edges == nodes - 1 + extra  # each opened wall adds exactly one cycle
    # the looped maze only ever opens squares of the perfect maze of the same seed
    assert np.all(looped.grid[perfect.grid == OPEN] == OPEN)
    # outer border intact, pillars intact
    g = looped.grid
    assert not g[0, :].any() and not g[-1, :].any() and not g[:, 0].any() and not g[:, -1].any()
    assert not g[::2, ::2].any()


def test_loop_rates_are_nested_for_one_seed():
    low = make_maze("looped", 25, 3, loop_rate=0.05)
    high = make_maze("looped", 25, 3, loop_rate=0.35)
    assert np.all(high.grid[low.grid == OPEN] == OPEN)
    assert high.passages > low.passages


def test_loop_rate_one_opens_every_internal_wall():
    n = 10
    maze = make_maze("looped", n, 0, loop_rate=1.0)
    assert maze.passages == 2 * n * (n - 1)


@pytest.mark.parametrize("n", SIZES)
def test_start_and_goal_are_corner_cells_and_connected(n):
    maze = make_maze("perfect", n, 9)
    assert maze.start == (1, 1) and maze.goal == (2 * n - 1, 2 * n - 1)
    assert is_reachable(maze.grid, maze.start, maze.goal)


def test_reachability_check_detects_a_blocked_goal():
    grid = np.array([[1, 0, 1]], dtype=np.uint8)
    assert not is_reachable(grid, (0, 0), (0, 2))


def test_large_maze_does_not_hit_the_recursion_limit():
    maze = make_maze("perfect", 100, 0)
    assert maze.passages == 100 * 100 - 1
