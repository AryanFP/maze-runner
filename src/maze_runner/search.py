"""BFS, UCS, A* and greedy best-first search as one loop with different frontiers.

Rules (graph search, see the report, Section 3.3):

* One loop for every algorithm. Only the frontier policy changes.
* best-g contract: a successor is pushed only if its g strictly improves the
  best known g of that state; a popped record whose g is worse than the best
  known g is stale and is skipped without being counted.
* BFS measures g in steps and tests the goal when it is generated (default)
  or when it is removed. UCS, A* and greedy test the goal when it is removed.
* Counting rule: a node is expanded when it is removed from the frontier,
  passes the stale check, is not the goal, and its successors are generated.
  The goal itself is never counted, because its successors are never
  generated. This is the convention of the Week 3 lecture example.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from heapq import heappop, heappush
from time import perf_counter

from .heuristics import heuristic_table
from .problem import GridProblem

ALGORITHMS = ("bfs", "ucs", "astar", "greedy")
TIE_RULES = ("fifo", "larger_g")
GOAL_TESTS = ("generation", "pop")
_INF = float("inf")


@dataclass
class SearchResult:
    algorithm: str
    heuristic: str
    weight: float
    tie_rule: str
    goal_test: str
    found: bool
    path: list[tuple[int, int]]
    path_len: int  # grid steps
    path_cost: float  # sum of the entry costs of the squares entered
    expanded: int
    generated: int
    peak_frontier: int
    reached: int
    time_s: float
    expansion_order: list[tuple[int, int]] = field(default_factory=list)


class FIFOFrontier:
    """First in, first out. Used by BFS."""

    def __init__(self):
        self._queue = deque()
        self.peak = 0

    def push(self, state: int, g, h) -> None:
        self._queue.append((state, g))
        if len(self._queue) > self.peak:
            self.peak = len(self._queue)

    def pop(self):
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)


class PriorityFrontier:
    """Min heap ordered by (priority, tie key, insertion counter).

    priority: 'g' (UCS), 'f' (A*, g + h) or 'h' (greedy).
    tie rule: 'fifo' orders equal priorities by insertion; 'larger_g' prefers
    the deeper record first and falls back to insertion order.
    The insertion counter keeps the order deterministic and means two states
    are never compared directly.
    """

    def __init__(self, priority: str, tie_rule: str):
        self._heap = []
        self._count = 0
        self._priority = priority
        self._larger_g = tie_rule == "larger_g"
        self.peak = 0

    def push(self, state: int, g, h) -> None:
        if self._priority == "f":
            p = g + h
        elif self._priority == "g":
            p = g
        else:
            p = h
        self._count += 1
        heappush(self._heap, (p, -g if self._larger_g else 0, self._count, state, g))
        if len(self._heap) > self.peak:
            self.peak = len(self._heap)

    def pop(self):
        entry = heappop(self._heap)
        return entry[3], entry[4]

    def __len__(self) -> int:
        return len(self._heap)


def search(
    problem: GridProblem,
    algorithm: str,
    heuristic: str | None = None,
    weight: float = 1.0,
    tie_rule: str = "fifo",
    goal_test: str | None = None,
    record_trace: bool = False,
) -> SearchResult:
    """Run one search. The whole call is timed, including building the heuristic table."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown algorithm {algorithm!r}")
    if tie_rule not in TIE_RULES:
        raise ValueError(f"unknown tie rule {tie_rule!r}")

    t0 = perf_counter()

    if algorithm == "bfs":
        heuristic, weight, tie_rule = "none", 1.0, "fifo"
        goal_test = goal_test or "generation"
        frontier = FIFOFrontier()
        use_costs = False  # BFS counts steps and ignores entry costs
        reopen = True
    else:
        if goal_test not in (None, "pop"):
            raise ValueError("with step costs the goal must be tested when it is popped")
        goal_test = "pop"
        use_costs = True
        if algorithm == "ucs":
            heuristic, weight = "zero", 1.0
            frontier = PriorityFrontier("g", tie_rule)
            reopen = True
        elif algorithm == "astar":
            heuristic = heuristic or "manhattan"
            frontier = PriorityFrontier("f", tie_rule)
            reopen = True
        else:  # greedy best-first: orders by h only and never reopens a state
            heuristic = heuristic or "manhattan"
            frontier = PriorityFrontier("h", tie_rule)
            reopen = False
    if goal_test not in GOAL_TESTS:
        raise ValueError(f"unknown goal test {goal_test!r}")
    test_at_generation = goal_test == "generation"

    cost = problem.cost
    offsets = problem.offsets
    start, goal = problem.start, problem.goal
    h = (
        [0] * len(cost)
        if heuristic in ("none", "zero")
        else heuristic_table(problem, heuristic, weight)
    )

    best_g = [_INF] * len(cost)
    parent = [-1] * len(cost)
    best_g[start] = 0
    reached = 1
    expanded = 0
    generated = 0
    order: list[int] = []
    found = start == goal

    if not found:
        frontier.push(start, 0, h[start])
        while frontier:
            s, g = frontier.pop()
            if g > best_g[s]:
                continue  # stale record: a cheaper arrival was found later
            if s == goal:
                found = True
                break
            expanded += 1
            if record_trace:
                order.append(s)
            for off in offsets:
                v = s + off
                c = cost[v]
                if c == 0:
                    continue  # wall
                g2 = g + (c if use_costs else 1)
                known = best_g[v]
                if known == _INF:
                    reached += 1
                elif not (reopen and g2 < known):
                    continue
                best_g[v] = g2
                parent[v] = s
                generated += 1
                if test_at_generation and v == goal:
                    found = True
                    break
                frontier.push(v, g2, h[v])
            if found:
                break

    path_idx: list[int] = []
    path_cost = 0
    if found:
        s = goal
        while s != -1:
            path_idx.append(s)
            s = parent[s]
        path_idx.reverse()
        path_cost = sum(cost[v] for v in path_idx[1:])
    elapsed = perf_counter() - t0

    to_cell = problem.cell
    return SearchResult(
        algorithm=algorithm,
        heuristic=heuristic,
        weight=float(weight),
        tie_rule=tie_rule,
        goal_test=goal_test,
        found=found,
        path=[to_cell(i) for i in path_idx],
        path_len=len(path_idx) - 1 if found else -1,
        path_cost=path_cost if found else -1,
        expanded=expanded,
        generated=generated,
        peak_frontier=max(frontier.peak, 1),
        reached=reached,
        time_s=elapsed,
        expansion_order=[to_cell(i) for i in order],
    )
