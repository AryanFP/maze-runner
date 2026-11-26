"""Turn a runs.csv into the tables and the summary numbers used by the report.

    python -m maze_runner.analysis results/final

Writes results/<suite>/tables/*.csv and results/<suite>/summary.json. Nothing
here runs a search: every number comes from the CSV.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

TARGET = 0.30  # success criterion from the proposal: at least 30% fewer expansions than BFS
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 3346
MAZE_KEYS = ["maze_type", "n_cells", "loop_rate", "mud_rate", "seed"]


def load_runs(suite_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(Path(suite_dir) / "runs.csv")
    df["config"] = [config_label(r) for r in df.itertuples()]
    return df


def config_label(row) -> str:
    if row.algorithm == "bfs":
        return "BFS" if row.goal_test == "generation" else "BFS (goal test at removal)"
    if row.algorithm == "ucs":
        return "UCS"
    if row.algorithm == "greedy":
        return "Greedy"
    if row.heuristic == "zero":
        return "A* (h = 0)"
    tie = "FIFO ties" if row.tie_rule == "fifo" else "larger-g ties"
    if row.weight != 1.0:
        return f"Weighted A* (w = {row.weight:g})"
    return f"A* ({tie})"


def bootstrap_ci(values, level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean, resampling mazes."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2 or np.all(values == values[0]):
        return float(values.mean()), float(values.mean())
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values)))
    means = values[idx].mean(axis=1)
    lo, hi = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def describe(values) -> dict:
    values = np.asarray(values, dtype=float)
    lo, hi = bootstrap_ci(values)
    return {
        "n": int(len(values)),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
        "ci_lo": lo,
        "ci_hi": hi,
        "median": float(np.median(values)),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def paired(df: pd.DataFrame, base: str, other: str, value: str = "expanded") -> pd.DataFrame:
    """One row per maze with the value for two configs side by side and the savings of `other`."""
    wide = df[df["config"].isin([base, other])].pivot(index=MAZE_KEYS, columns="config", values=value)
    out = wide.rename(columns={base: "base", other: "other"}).reset_index()
    out["savings"] = 1.0 - out["other"] / out["base"]
    return out


def savings_table(df: pd.DataFrame, base: str, other: str, by: list[str]) -> pd.DataFrame:
    """Paired expansion savings of `other` relative to `base`, summarised per group."""
    pairs = paired(df, base, other)
    info = df[df["config"] == base].set_index(MAZE_KEYS)[["informedness", "open_cells"]]
    pairs = pairs.join(info, on=MAZE_KEYS)
    rows = []
    for key, g in pairs.groupby(by):
        key = key if isinstance(key, tuple) else (key,)
        d = describe(g["savings"])
        diff = g["base"] - g["other"]
        if (diff != 0).any():
            w = stats.wilcoxon(g["base"], g["other"], alternative="greater")
            w_stat, w_p = float(w.statistic), float(w.pvalue)
        else:
            w_stat, w_p = float("nan"), float("nan")
        rows.append({
            **dict(zip(by, key)),
            "n_mazes": d["n"],
            "base_mean": g["base"].mean(),
            "other_mean": g["other"].mean(),
            "savings_mean": d["mean"],
            "savings_std": d["std"],
            "savings_ci_lo": d["ci_lo"],
            "savings_ci_hi": d["ci_hi"],
            "savings_median": d["median"],
            "savings_min": d["min"],
            "savings_max": d["max"],
            "savings_of_means": 1.0 - g["other"].mean() / g["base"].mean(),
            "wins": int((diff > 0).sum()),
            "ties": int((diff == 0).sum()),
            "losses": int((diff < 0).sum()),
            "wilcoxon_stat": w_stat,
            "wilcoxon_p": w_p,
            "informedness_mean": g["informedness"].mean(),
            "base_fraction_explored": (g["base"] / g["open_cells"]).mean(),
            "other_fraction_explored": (g["other"] / g["open_cells"]).mean(),
            "target_met": bool(d["mean"] >= TARGET),
            "target_met_ci": bool(d["ci_lo"] >= TARGET),
        })
    return pd.DataFrame(rows)


def metric_table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Mean, standard deviation and 95% CI of every recorded metric per group."""
    rows = []
    for key, g in df.groupby(by, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(by, key))
        row["n_mazes"] = len(g)
        for col in ("expanded", "generated", "peak_frontier", "reached", "path_len", "path_cost",
                    "time_mean_ms", "time_median_ms"):
            d = describe(g[col])
            row[f"{col}_mean"] = d["mean"]
            row[f"{col}_std"] = d["std"]
            if col in ("expanded", "time_mean_ms"):
                row[f"{col}_ci_lo"] = d["ci_lo"]
                row[f"{col}_ci_hi"] = d["ci_hi"]
        row["fraction_explored_mean"] = (g["expanded"] / g["open_cells"]).mean()
        row["optimal_count"] = int(g["optimal"].sum())
        row["cost_overhead_mean"] = (g["path_cost"] / g["optimal_cost"] - 1.0).mean()
        row["cost_overhead_max"] = (g["path_cost"] / g["optimal_cost"] - 1.0).max()
        rows.append(row)
    return pd.DataFrame(rows)


def analyse(suite_dir: Path) -> dict:
    suite_dir = Path(suite_dir)
    df = load_runs(suite_dir)
    meta = json.loads((suite_dir / "metadata.json").read_text(encoding="utf-8"))
    defaults = meta["config"]["defaults"]
    astar = "A* (larger-g ties)" if defaults["tie_rule"] == "larger_g" else "A* (FIFO ties)"
    tables: dict[str, pd.DataFrame] = {}
    summary: dict = {"suite": meta["suite"], "headline_astar": astar, "target": TARGET, "defaults": defaults}

    # ---- verification -------------------------------------------------------
    expect = df[df["expect_optimal"]]
    summary["verification"] = {
        "rows": int(len(df)),
        "mazes": int(df.drop_duplicates(["experiment"] + MAZE_KEYS).shape[0]),
        "distinct_mazes": int(df["maze_hash"].nunique()),
        "legal": int(df["verified"].sum()),
        "optimal_expected": int(len(expect)),
        "optimal_ok": int(expect["optimal"].sum()),
        "per_experiment": {
            name: {"rows": int(len(g)), "mazes": int(g.drop_duplicates(MAZE_KEYS).shape[0])}
            for name, g in df.groupby("experiment", sort=False)
        },
    }

    # ---- main experiment ----------------------------------------------------
    main = df[df["experiment"] == "main"]
    tables["main_metrics"] = metric_table(main, ["maze_type", "n_cells", "config"])
    tables["main_savings"] = savings_table(main, "BFS", astar, ["maze_type", "n_cells"])
    frontier = paired(main, "BFS", astar, "peak_frontier").groupby(["maze_type", "n_cells"])
    tables["main_frontier"] = frontier.agg(bfs_peak=("base", "mean"), astar_peak=("other", "mean")).reset_index()
    times = paired(main, "BFS", astar, "time_mean_ms")
    times["ratio"] = times["other"] / times["base"]
    tables["main_time"] = times.groupby(["maze_type", "n_cells"]).agg(
        bfs_ms=("base", "mean"), astar_ms=("other", "mean"), ratio_mean=("ratio", "mean"),
        astar_faster=("ratio", lambda r: int((r < 1).sum())), n_mazes=("ratio", "size")).reset_index()
    per_node = main.assign(us=main["time_mean_ms"] * 1000.0 / main["expanded"].clip(lower=1))
    summary["microseconds_per_expansion"] = {
        k: float(v) for k, v in per_node[per_node["n_cells"] >= 50].groupby("config")["us"].mean().items()
    }
    main_pairs = paired(main, "BFS", astar)
    info = main[main["config"] == "BFS"].set_index(MAZE_KEYS)[["informedness", "detour_ratio", "path_len", "open_cells"]]
    main_pairs = main_pairs.join(info, on=MAZE_KEYS)
    tables["main_pairs"] = main_pairs
    lengths = main.pivot(index=MAZE_KEYS, columns="config", values="path_len")
    summary["main"] = {
        "mazes": int(len(main_pairs)),
        "same_path_length": int((lengths["BFS"] == lengths[astar]).sum()),
        "astar_wins": int((main_pairs["savings"] > 0).sum()),
        "astar_ties": int((main_pairs["savings"] == 0).sum()),
        "astar_losses": int((main_pairs["savings"] < 0).sum()),
        "spearman_informedness_savings": float(
            stats.spearmanr(main_pairs["informedness"], main_pairs["savings"]).statistic),
    }
    # failure case: the worst maze for A* among those small enough to draw clearly
    drawable = main_pairs[main_pairs["n_cells"] == 25].sort_values(["savings", "seed"])
    worst = drawable.iloc[0]
    best = drawable.iloc[-1]
    overall = main_pairs.sort_values(["savings", "seed"]).iloc[0]
    as_case = lambda r: {
        "maze_type": r["maze_type"], "n_cells": int(r["n_cells"]), "seed": int(r["seed"]),
        "loop_rate": float(r["loop_rate"]), "savings": float(r["savings"]),
        "bfs_expanded": int(r["base"]), "astar_expanded": int(r["other"]),
        "informedness": float(r["informedness"]), "path_len": int(r["path_len"]),
        "open_cells": int(r["open_cells"]),
    }
    summary["cases"] = {"worst_25": as_case(worst), "best_25": as_case(best), "worst_overall": as_case(overall)}

    # ---- loop rate sweep ----------------------------------------------------
    sweep = df[df["experiment"] == "sweep"]
    parts = []
    for config in ("A* (FIFO ties)", "A* (larger-g ties)"):
        t = savings_table(sweep, "BFS", config, ["n_cells", "loop_rate"])
        t.insert(0, "config", config)
        parts.append(t)
    tables["sweep_savings"] = pd.concat(parts, ignore_index=True)
    sweep_pairs = []
    for config in ("A* (FIFO ties)", "A* (larger-g ties)"):
        p = paired(sweep, "BFS", config)
        p["config"] = config
        sweep_pairs.append(p)
    sweep_pairs = pd.concat(sweep_pairs, ignore_index=True).join(
        sweep[sweep["config"] == "BFS"].set_index(MAZE_KEYS)[["informedness", "open_cells"]], on=MAZE_KEYS)
    tables["sweep_pairs"] = sweep_pairs
    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.999, 1.0]
    labels = ["0.0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.4", "0.4-0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8",
              "0.8-0.9", "0.9-<1", "1.0"]
    sweep_pairs["informedness_bin"] = pd.cut(sweep_pairs["informedness"], bins=bins, labels=labels,
                                             include_lowest=True)
    tables["sweep_by_informedness"] = (
        sweep_pairs.groupby(["config", "informedness_bin"], observed=True)
        .agg(n_mazes=("savings", "size"), savings_mean=("savings", "mean"), savings_min=("savings", "min"),
             savings_max=("savings", "max"), below_target=("savings", lambda s: int((s < TARGET).sum())))
        .reset_index())
    summary["sweep"] = {
        "mazes": int(sweep.drop_duplicates(MAZE_KEYS).shape[0]),
        "spearman": {
            config: float(stats.spearmanr(g["informedness"], g["savings"]).statistic)
            for config, g in sweep_pairs.groupby("config")
        },
        "losses": {config: int((g["savings"] < 0).sum()) for config, g in sweep_pairs.groupby("config")},
    }

    # ---- weighted extension -------------------------------------------------
    weighted = df[df["experiment"] == "weighted"]
    wt = savings_table(weighted, "UCS", astar, ["n_cells", "mud_rate"])
    bfs = weighted[weighted["config"] == "BFS"].copy()
    bfs["overhead"] = bfs["path_cost"] / bfs["optimal_cost"] - 1.0
    opt = weighted[weighted["config"] == "UCS"].set_index(MAZE_KEYS)
    bfs = bfs.join(opt[["path_len"]].rename(columns={"path_len": "ucs_steps"}), on=MAZE_KEYS)
    bfs_summary = bfs.groupby(["n_cells", "mud_rate"]).agg(
        bfs_expanded=("expanded", "mean"),
        bfs_cost=("path_cost", "mean"),
        optimal_cost=("optimal_cost", "mean"),
        bfs_overhead_mean=("overhead", "mean"),
        bfs_overhead_max=("overhead", "max"),
        bfs_suboptimal=("overhead", lambda s: int((s > 0).sum())),
        bfs_steps=("path_len", "mean"),
        optimal_route_steps=("ucs_steps", "mean"),
    ).reset_index()
    tables["weighted"] = wt.merge(bfs_summary, on=["n_cells", "mud_rate"])
    same_cost = weighted.pivot(index=MAZE_KEYS, columns="config", values="path_cost")
    summary["weighted"] = {
        "mazes": int(len(same_cost)),
        "ucs_astar_same_cost": int((same_cost["UCS"] == same_cost[astar]).sum()),
    }

    # ---- ablations ----------------------------------------------------------
    ablation = df[df["experiment"] == "ablation"]
    ab = metric_table(ablation, ["maze_type", "n_cells", "config"])
    base = ab[ab["config"] == "BFS"].set_index(["maze_type", "n_cells"])["expanded_mean"]
    ab["savings_of_means_vs_bfs"] = [
        1.0 - r.expanded_mean / base[(r.maze_type, r.n_cells)] for r in ab.itertuples()
    ]
    paired_parts = []
    for config in ab["config"].unique():
        if config == "BFS":
            continue
        t = savings_table(ablation, "BFS", config, ["maze_type", "n_cells"])
        t.insert(0, "config", config)
        paired_parts.append(t)
    ab_pairs = pd.concat(paired_parts, ignore_index=True)
    tables["ablation"] = ab.merge(
        ab_pairs[["config", "maze_type", "n_cells", "savings_mean", "savings_ci_lo", "savings_ci_hi",
                  "wins", "ties", "losses"]],
        on=["config", "maze_type", "n_cells"], how="left")
    removal = savings_table(ablation, "BFS (goal test at removal)", astar, ["maze_type", "n_cells"])
    tables["ablation_vs_bfs_removal"] = removal
    zero = ablation.pivot(index=MAZE_KEYS, columns="config", values="expanded")
    summary["ablation"] = {
        "mazes": int(len(zero)),
        "bfs_removal_extra_mean": float((zero["BFS (goal test at removal)"] - zero["BFS"]).mean()),
        "fifo_minus_larger_g_mean": {
            mt: float((g["A* (FIFO ties)"] - g["A* (larger-g ties)"]).mean())
            for mt, g in zero.groupby(level="maze_type")
        },
    }

    # ---- write --------------------------------------------------------------
    out = suite_dir / "tables"
    out.mkdir(exist_ok=True)
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False, float_format="%.6g")
    summary["environment"] = meta["environment"]
    summary["started_utc"] = meta["started_utc"]
    summary["duration_s"] = meta["duration_s"]
    (suite_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {"tables": tables, "summary": summary, "runs": df}


def print_overview(result: dict) -> None:
    pd.set_option("display.width", 220, "display.max_columns", 30, "display.float_format", "{:.3f}".format)
    s, t = result["summary"], result["tables"]
    v = s["verification"]
    print(f"rows {v['rows']}, legal {v['legal']}, optimal {v['optimal_ok']}/{v['optimal_expected']}")
    print("\nMain: paired expansion savings of", s["headline_astar"], "vs BFS")
    print(t["main_savings"][["maze_type", "n_cells", "n_mazes", "base_mean", "other_mean", "savings_mean",
                             "savings_ci_lo", "savings_ci_hi", "wins", "ties", "losses",
                             "informedness_mean", "target_met"]].to_string(index=False))
    print("\nSweep")
    print(t["sweep_savings"][["config", "n_cells", "loop_rate", "savings_mean", "savings_ci_lo",
                              "savings_ci_hi", "losses", "informedness_mean"]].to_string(index=False))
    print("\nWeighted")
    print(t["weighted"][["n_cells", "mud_rate", "base_mean", "other_mean", "savings_mean", "bfs_overhead_mean",
                         "bfs_overhead_max", "bfs_suboptimal", "informedness_mean"]].to_string(index=False))
    print("\nAblation")
    print(t["ablation"][["maze_type", "n_cells", "config", "expanded_mean", "savings_mean", "losses",
                         "optimal_count", "cost_overhead_mean", "time_mean_ms_mean"]].to_string(index=False))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyse a Maze Runner results folder.")
    parser.add_argument("suite_dir", type=Path)
    args = parser.parse_args(argv)
    print_overview(analyse(args.suite_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
