"""Experiment runner: config in, one CSV row per (maze, algorithm setting) out.

    python -m maze_runner.experiment config/final.json

For each maze the runner builds it, computes the trusted optimum with the
independent verifier, runs every configured algorithm on the same instance,
checks every returned path, and writes the row. A metadata JSON with the
environment, the full config and the verification counts is written next to
the CSV. Two runs of the same config give identical CSVs except for the
timing columns.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import verify
from .generator import make_maze
from .heuristics import manhattan
from .metrics import environment_info, time_search
from .problem import NEIGHBOR_ORDER, GridProblem
from .search import search

COLUMNS = [
    "experiment", "maze_type", "n_cells", "grid_size", "seed", "loop_rate", "mud_rate",
    "start", "goal", "open_cells", "mud_cells", "maze_hash",
    "algorithm", "heuristic", "weight", "tie_rule", "goal_test",
    "found", "expanded", "generated", "peak_frontier", "reached",
    "path_len", "path_cost", "optimal_cost", "optimal_steps",
    "verified", "optimal", "expect_optimal",
    "h_start", "informedness", "detour_ratio",
    "time_mean_ms", "time_median_ms", "time_min_ms", "time_runs",
]
TIMING_COLUMNS = ["time_mean_ms", "time_median_ms", "time_min_ms"]

# Settings that are guaranteed to return a cheapest path. A failure on any of
# these rows is a bug and stops the run.
def _expect_optimal(run: dict, maze_type: str) -> bool:
    algo = run["algorithm"]
    if algo == "bfs":
        return maze_type != "weighted"  # BFS minimises steps, not cost
    if algo == "ucs":
        return True
    if algo == "astar":
        return run.get("heuristic", "manhattan") in ("manhattan", "zero") and run.get("weight", 1.0) <= 1.0
    return False  # greedy


def _seed_list(spec) -> list[int]:
    if isinstance(spec, list):
        return [int(s) for s in spec]
    return list(range(int(spec["start"]), int(spec["start"]) + int(spec["count"])))


def _maze_specs(exp: dict):
    """Yield (maze_type, n, seed, loop_rate, mud_rate) in a fixed order."""
    seeds = _seed_list(exp["seeds"])
    for maze_type in exp["maze_types"]:
        loop_rates = [0.0] if maze_type == "perfect" else exp.get("loop_rates", [0.0])
        mud_rates = exp.get("mud_rates", [0.0]) if maze_type == "weighted" else [0.0]
        for n in exp["sizes"]:
            for loop_rate in loop_rates:
                for mud_rate in mud_rates:
                    for seed in seeds:
                        yield maze_type, n, seed, loop_rate, mud_rate


def _build(maze_type, n, seed, loop_rate, mud_rate):
    # A sweep may ask for a "looped" maze with loop rate 0, which is the perfect maze.
    if maze_type == "looped" and loop_rate == 0.0:
        return make_maze("perfect", n, seed)
    if maze_type == "weighted" and mud_rate == 0.0:
        return make_maze("looped", n, seed, loop_rate=loop_rate)
    return make_maze(maze_type, n, seed, loop_rate=loop_rate, mud_rate=mud_rate)


def run_experiment(exp: dict, writer, log=print) -> dict:
    counts = {"mazes": 0, "rows": 0, "verified": 0, "optimal_expected": 0, "optimal_ok": 0}
    repeats = int(exp.get("timing_repeats", 1))
    warmup = int(exp.get("timing_warmup", 1 if repeats > 1 else 0))
    specs = list(_maze_specs(exp))
    t_start = time.perf_counter()
    for i, (maze_type, n, seed, loop_rate, mud_rate) in enumerate(specs, 1):
        maze = _build(maze_type, n, seed, loop_rate, mud_rate)
        problem = GridProblem(maze.grid, maze.start, maze.goal)
        best_cost = verify.optimal_cost(maze.grid, maze.start, maze.goal)
        best_steps = verify.optimal_steps(maze.grid, maze.start, maze.goal)
        if best_cost is None:
            raise RuntimeError(f"maze {maze_type} n={n} seed={seed} has no path")
        h_start = manhattan(maze.start, maze.goal) * problem.min_cost
        counts["mazes"] += 1
        for run in exp["runs"]:
            kwargs = {
                "algorithm": run["algorithm"],
                "heuristic": run.get("heuristic"),
                "weight": float(run.get("weight", 1.0)),
                "tie_rule": run.get("tie_rule", "fifo"),
                "goal_test": run.get("goal_test"),
            }
            result = search(problem, **kwargs)
            report = verify.check_path(
                maze.grid, maze.start, maze.goal, result.path, result.path_cost, result.path_len
            )
            is_optimal = report.legal and report.cost == best_cost
            expect = _expect_optimal(run, maze_type)
            if not report.legal:
                raise RuntimeError(
                    f"verification failed: {result.algorithm} on {maze_type} n={n} seed={seed}: {report.reason}"
                )
            if expect and not is_optimal:
                raise RuntimeError(
                    f"optimality failed: {result.algorithm} on {maze_type} n={n} seed={seed}: "
                    f"cost {report.cost}, optimum {best_cost}"
                )
            timing = time_search(problem, repeats=repeats, warmup=warmup, **kwargs)
            counts["rows"] += 1
            counts["verified"] += int(report.legal)
            counts["optimal_expected"] += int(expect)
            counts["optimal_ok"] += int(expect and is_optimal)
            writer.writerow({
                "experiment": exp["name"],
                "maze_type": maze_type,
                "n_cells": n,
                "grid_size": maze.grid_size,
                "seed": seed,
                "loop_rate": loop_rate,
                "mud_rate": mud_rate,
                "start": f"{maze.start[0]};{maze.start[1]}",
                "goal": f"{maze.goal[0]};{maze.goal[1]}",
                "open_cells": maze.open_cells,
                "mud_cells": maze.mud_cells,
                "maze_hash": maze.maze_hash,
                "algorithm": result.algorithm,
                "heuristic": result.heuristic,
                "weight": result.weight,
                "tie_rule": result.tie_rule,
                "goal_test": result.goal_test,
                "found": result.found,
                "expanded": result.expanded,
                "generated": result.generated,
                "peak_frontier": result.peak_frontier,
                "reached": result.reached,
                "path_len": result.path_len,
                "path_cost": result.path_cost,
                "optimal_cost": best_cost,
                "optimal_steps": best_steps,
                "verified": report.legal,
                "optimal": is_optimal,
                "expect_optimal": expect,
                "h_start": h_start,
                "informedness": round(h_start / best_cost, 6),
                "detour_ratio": round(best_cost / h_start, 6),
                "time_mean_ms": round(timing["time_mean_ms"], 4),
                "time_median_ms": round(timing["time_median_ms"], 4),
                "time_min_ms": round(timing["time_min_ms"], 4),
                "time_runs": timing["time_runs"],
            })
        if i % 200 == 0 or i == len(specs):
            log(f"  [{exp['name']}] {i}/{len(specs)} mazes, {time.perf_counter() - t_start:.0f} s")
    return counts


def run_suite(config_path: Path, out_dir: Path | None = None, log=print) -> Path:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    out_dir = Path(out_dir) if out_dir else Path("results") / config["suite"]
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "runs.csv"
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    per_experiment = {}
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for exp in config["experiments"]:
            log(f"running experiment '{exp['name']}'")
            per_experiment[exp["name"]] = run_experiment(exp, writer, log)
    totals = {k: sum(c[k] for c in per_experiment.values()) for k in next(iter(per_experiment.values()))}
    meta = {
        "suite": config["suite"],
        "config_file": str(config_path).replace("\\", "/"),
        "started_utc": started.isoformat(timespec="seconds"),
        "duration_s": round(time.perf_counter() - t0, 1),
        "environment": environment_info(),
        "neighbor_order": list(NEIGHBOR_ORDER),
        "counts": totals,
        "counts_per_experiment": per_experiment,
        "seeds": {e["name"]: e["seeds"] for e in config["experiments"]},
        "config": config,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(
        f"wrote {csv_path} ({totals['rows']} rows, {totals['mazes']} mazes; "
        f"{totals['verified']}/{totals['rows']} legal, "
        f"{totals['optimal_ok']}/{totals['optimal_expected']} optimal where optimality is guaranteed)"
    )
    return csv_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a Maze Runner experiment suite.")
    parser.add_argument("config", type=Path, help="path to a suite config (JSON)")
    parser.add_argument("--out", type=Path, default=None, help="output folder (default results/<suite>)")
    args = parser.parse_args(argv)
    run_suite(args.config, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
