"""Seeded maze generation: perfect, looped and weighted (mud) mazes.

A maze of size n means n x n cells. It is stored as an occupancy grid of
(2n+1) x (2n+1) squares. Cell (r, c) sits at square (2r+1, 2c+1); the square
between two neighbouring cells is either a wall or an open passage; squares at
(even, even) positions are pillars and are always walls.

Square values are entry costs: 0 = wall, 1 = normal open square, 5 = mud.

Every maze is built from local random generators seeded from the maze seed, so
the global random state is never touched and a seed always rebuilds the same
maze.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

import numpy as np

WALL = 0
OPEN = 1
MUD = 5

MAZE_TYPES = ("perfect", "looped", "weighted")

# Cell-level carving directions (row change, column change).
_CELL_DIRS = ((-1, 0), (0, 1), (1, 0), (0, -1))


@dataclass(frozen=True)
class Maze:
    """One generated maze together with everything needed to rebuild it."""

    maze_type: str
    n: int
    seed: int
    loop_rate: float
    mud_rate: float
    grid: np.ndarray
    start: tuple[int, int]
    goal: tuple[int, int]

    @property
    def grid_size(self) -> int:
        return int(self.grid.shape[0])

    @property
    def open_cells(self) -> int:
        """Number of non-wall squares of the occupancy grid."""
        return int(np.count_nonzero(self.grid))

    @property
    def mud_cells(self) -> int:
        return int(np.count_nonzero(self.grid == MUD))

    @property
    def passages(self) -> int:
        """Number of open passages between neighbouring cells."""
        g = self.grid
        return int(np.count_nonzero(g[1::2, 2:-1:2]) + np.count_nonzero(g[2:-1:2, 1::2]))

    @property
    def maze_hash(self) -> str:
        """Short fingerprint of the grid, used to prove a maze was rebuilt identically."""
        h = hashlib.sha256()
        h.update(str(self.grid.shape).encode())
        h.update(np.ascontiguousarray(self.grid, dtype=np.uint8).tobytes())
        return h.hexdigest()[:16]


def _rng(seed: int, stream: str) -> random.Random:
    """Independent, reproducible random stream for one stage of one maze.

    String seeds are hashed with SHA-512 by the standard library, so the
    stream does not depend on the platform or on hash randomisation.
    """
    return random.Random(f"maze-runner/{seed}/{stream}")


def _carve_perfect(n: int, rng: random.Random) -> np.ndarray:
    """Randomized depth-first search (recursive backtracker) with an explicit stack."""
    grid = np.zeros((2 * n + 1, 2 * n + 1), dtype=np.uint8)
    visited = [[False] * n for _ in range(n)]
    visited[0][0] = True
    grid[1, 1] = OPEN
    stack = [(0, 0)]
    while stack:
        r, c = stack[-1]
        options = []
        for dr, dc in _CELL_DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and not visited[nr][nc]:
                options.append((nr, nc))
        if not options:
            stack.pop()
            continue
        nr, nc = rng.choice(options)
        grid[r + nr + 1, c + nc + 1] = OPEN  # the wall square between the two cells
        grid[2 * nr + 1, 2 * nc + 1] = OPEN
        visited[nr][nc] = True
        stack.append((nr, nc))
    return grid


def _internal_walls(grid: np.ndarray, n: int) -> list[tuple[int, int]]:
    """Wall squares between two neighbouring cells (never the outer border), in a fixed order."""
    walls = []
    for r in range(n):
        for c in range(n):
            if c < n - 1 and grid[2 * r + 1, 2 * c + 2] == WALL:
                walls.append((2 * r + 1, 2 * c + 2))
            if r < n - 1 and grid[2 * r + 2, 2 * c + 1] == WALL:
                walls.append((2 * r + 2, 2 * c + 1))
    return walls


def _add_loops(grid: np.ndarray, n: int, loop_rate: float, rng: random.Random) -> None:
    """Open a fraction `loop_rate` of the remaining internal walls.

    The walls are shuffled once and a prefix is opened, so for a fixed seed
    the maze at a higher loop rate contains every passage of the maze at a
    lower loop rate (nested mazes; this removes noise from the sweep).
    """
    walls = _internal_walls(grid, n)
    rng.shuffle(walls)
    for r, c in walls[: round(loop_rate * len(walls))]:
        grid[r, c] = OPEN


def _add_mud(grid: np.ndarray, mud_rate: float, start, goal, rng: random.Random) -> None:
    """Turn a fraction `mud_rate` of the open squares into mud. Start and goal stay normal."""
    candidates = [
        (int(r), int(c)) for r, c in np.argwhere(grid != WALL) if (r, c) != start and (r, c) != goal
    ]
    rng.shuffle(candidates)
    for r, c in candidates[: round(mud_rate * len(candidates))]:
        grid[r, c] = MUD


def is_reachable(grid: np.ndarray, start, goal) -> bool:
    """Plain flood fill from start. Used only as the maze validity check."""
    rows, cols = grid.shape
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        if (r, c) == goal:
            return True
        for dr, dc in _CELL_DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr, nc] != WALL and (nr, nc) not in seen:
                seen.add((nr, nc))
                stack.append((nr, nc))
    return False


def make_maze(
    maze_type: str,
    n: int,
    seed: int,
    loop_rate: float = 0.0,
    mud_rate: float = 0.0,
) -> Maze:
    """Build one maze.

    perfect:  spanning tree, exactly one simple path between any two cells.
    looped:   the perfect maze of the same seed with a fraction `loop_rate`
              of its remaining internal walls opened.
    weighted: a looped maze in which a fraction `mud_rate` of the open squares
              costs 5 to enter. Weighted mazes are never built on perfect
              mazes: with a single route, costs cannot change which path wins.
    """
    if maze_type not in MAZE_TYPES:
        raise ValueError(f"unknown maze type {maze_type!r}")
    if n < 2:
        raise ValueError("maze size n must be at least 2")
    if not 0.0 <= loop_rate <= 1.0 or not 0.0 <= mud_rate <= 1.0:
        raise ValueError("loop_rate and mud_rate must be in [0, 1]")
    if maze_type == "perfect" and (loop_rate != 0.0 or mud_rate != 0.0):
        raise ValueError("a perfect maze has loop_rate 0 and mud_rate 0")
    if maze_type == "looped" and mud_rate != 0.0:
        raise ValueError("a looped maze has mud_rate 0 (use maze_type='weighted')")
    if maze_type == "weighted" and loop_rate <= 0.0:
        raise ValueError("weighted mazes must be built on looped mazes (loop_rate > 0)")

    start = (1, 1)
    goal = (2 * n - 1, 2 * n - 1)
    grid = _carve_perfect(n, _rng(seed, f"carve/{n}"))
    if loop_rate > 0.0:
        _add_loops(grid, n, loop_rate, _rng(seed, f"loops/{n}"))
    if mud_rate > 0.0:
        _add_mud(grid, mud_rate, start, goal, _rng(seed, f"mud/{n}"))

    if not is_reachable(grid, start, goal):
        raise RuntimeError(
            f"generator bug: goal unreachable in {maze_type} maze n={n} seed={seed}"
        )
    grid.setflags(write=False)
    return Maze(maze_type, n, seed, float(loop_rate), float(mud_rate), grid, start, goal)
