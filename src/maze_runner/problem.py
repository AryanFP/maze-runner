"""The grid search problem shared by every algorithm.

State:     a square (row, col) of the grid.
Actions:   Up, Right, Down, Left (always tried in this order).
Step cost: the entry cost of the square that is entered; the start is free.

Internally the grid is padded with one ring of walls and flattened, so a
state is one integer and a move is one addition. All algorithms read the
same `cost` list and the same `offsets`, which is what makes the comparison
fair: one successor function, one neighbour order.
"""

from __future__ import annotations

import numpy as np

NEIGHBOR_ORDER = ("Up", "Right", "Down", "Left")


class GridProblem:
    def __init__(self, grid, start: tuple[int, int], goal: tuple[int, int]):
        grid = np.asarray(grid)
        if grid.ndim != 2:
            raise ValueError("grid must be two dimensional")
        self.rows, self.cols = (int(x) for x in grid.shape)
        self.width = self.cols + 2
        padded = np.zeros((self.rows + 2, self.cols + 2), dtype=np.int64)
        padded[1:-1, 1:-1] = grid
        #: entry cost per padded square, 0 means wall
        self.cost: list[int] = padded.ravel().tolist()
        #: Up, Right, Down, Left as index offsets
        self.offsets: tuple[int, int, int, int] = (-self.width, 1, self.width, -1)
        self.start_cell = (int(start[0]), int(start[1]))
        self.goal_cell = (int(goal[0]), int(goal[1]))
        for name, cell in (("start", self.start_cell), ("goal", self.goal_cell)):
            if not (0 <= cell[0] < self.rows and 0 <= cell[1] < self.cols):
                raise ValueError(f"{name} {cell} is outside the grid")
            if grid[cell] == 0:
                raise ValueError(f"{name} {cell} is a wall")
        self.start = self.index(self.start_cell)
        self.goal = self.index(self.goal_cell)
        positive = padded[padded > 0]
        #: cheapest entry cost of any open square (used to scale Manhattan distance)
        self.min_cost: int = int(positive.min())

    def index(self, cell: tuple[int, int]) -> int:
        return (cell[0] + 1) * self.width + (cell[1] + 1)

    def cell(self, index: int) -> tuple[int, int]:
        r, c = divmod(index, self.width)
        return (r - 1, c - 1)

    def successors(self, index: int) -> list[tuple[int, int]]:
        """(next state, step cost) pairs in the fixed neighbour order."""
        out = []
        for off in self.offsets:
            v = index + off
            c = self.cost[v]
            if c:
                out.append((v, c))
        return out
