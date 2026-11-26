"""Independent checker for search results.

Nothing in this file imports the search code or the GridProblem class. It
works directly on the 2-D cost grid with (row, col) tuples and explicit
bounds checks, so a bug in the search loop or in the padded indexing cannot
hide here.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush

_MOVES = ((-1, 0), (0, 1), (1, 0), (0, -1))


@dataclass(frozen=True)
class VerifyReport:
    legal: bool
    reason: str
    steps: int
    cost: int


def _open_neighbors(grid, r: int, c: int):
    rows, cols = grid.shape
    for dr, dc in _MOVES:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and grid[nr, nc] != 0:
            yield nr, nc


def check_path(grid, start, goal, path, reported_cost=None, reported_len=None) -> VerifyReport:
    """Check that `path` is a legal route from start to goal and recompute its cost."""
    start, goal = tuple(start), tuple(goal)
    if not path:
        return VerifyReport(False, "empty path", -1, -1)
    path = [tuple(p) for p in path]
    if path[0] != start:
        return VerifyReport(False, "path does not begin at the start", -1, -1)
    if path[-1] != goal:
        return VerifyReport(False, "path does not end at the goal", -1, -1)
    rows, cols = grid.shape
    cost = 0
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        if abs(r0 - r1) + abs(c0 - c1) != 1:
            return VerifyReport(False, f"illegal move {(r0, c0)} -> {(r1, c1)}", -1, -1)
        if not (0 <= r1 < rows and 0 <= c1 < cols):
            return VerifyReport(False, f"{(r1, c1)} is outside the grid", -1, -1)
        if grid[r1, c1] == 0:
            return VerifyReport(False, f"{(r1, c1)} is a wall", -1, -1)
        cost += int(grid[r1, c1])
    steps = len(path) - 1
    if reported_cost is not None and reported_cost != cost:
        return VerifyReport(False, f"reported cost {reported_cost} but path costs {cost}", steps, cost)
    if reported_len is not None and reported_len != steps:
        return VerifyReport(False, f"reported length {reported_len} but path has {steps} steps", steps, cost)
    return VerifyReport(True, "ok", steps, cost)


def cost_to_goal(grid, goal) -> dict:
    """True cheapest remaining cost h*(s) for every square that can reach the goal.

    Dijkstra run backwards from the goal. Moving u -> v costs the entry cost
    of v, so walking the edge backwards from v adds grid[v].
    """
    goal = tuple(goal)
    dist = {goal: 0}
    heap = [(0, goal)]
    while heap:
        d, (r, c) = heappop(heap)
        if d > dist[(r, c)]:
            continue
        step = int(grid[r, c])
        for nb in _open_neighbors(grid, r, c):
            nd = d + step
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                heappush(heap, (nd, nb))
    return dist


def optimal_cost(grid, start, goal):
    """Cheapest path cost from start to goal (trusted reference), or None if unreachable."""
    start, goal = tuple(start), tuple(goal)
    dist = {start: 0}
    heap = [(0, start)]
    while heap:
        d, (r, c) = heappop(heap)
        if (r, c) == goal:
            return d
        if d > dist[(r, c)]:
            continue
        for nb in _open_neighbors(grid, r, c):
            nd = d + int(grid[nb])
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                heappush(heap, (nd, nb))
    return None


def optimal_steps(grid, start, goal):
    """Fewest steps from start to goal ignoring costs, or None if unreachable."""
    start, goal = tuple(start), tuple(goal)
    dist = {start: 0}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        if (r, c) == goal:
            return dist[(r, c)]
        for nb in _open_neighbors(grid, r, c):
            if nb not in dist:
                dist[nb] = dist[(r, c)] + 1
                queue.append(nb)
    return None
