"""Heuristics. Each one returns a table with one value per (padded) grid square.

zero:       h = 0. A* with this heuristic must behave exactly like UCS.
manhattan:  h = c_min * (|dr| + |dc|), the exact cost of the relaxed problem
            with every wall removed and every square as cheap as the cheapest
            one. With c_min = 1 (all of our mazes) this is plain Manhattan
            distance. It is admissible and consistent for four-way moves.
weight > 1: h = weight * manhattan. No longer admissible; used only in the
            weighted A* ablation.
"""

from __future__ import annotations

import numpy as np

from .problem import GridProblem

HEURISTICS = ("zero", "manhattan")


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_table(problem: GridProblem, name: str = "manhattan", weight: float = 1.0) -> list:
    size = (problem.rows + 2) * problem.width
    if name == "zero":
        return [0] * size
    if name != "manhattan":
        raise ValueError(f"unknown heuristic {name!r}")
    goal_r, goal_c = divmod(problem.goal, problem.width)
    rows = np.abs(np.arange(problem.rows + 2) - goal_r)[:, None]
    cols = np.abs(np.arange(problem.width) - goal_c)[None, :]
    table = (rows + cols) * problem.min_cost
    if weight != 1.0:
        table = table * float(weight)
    return table.ravel().tolist()
