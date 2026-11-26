"""Figures: maze pictures, exploration maps, charts and the BFS vs A* animation.

    python -m maze_runner.visualize results/final

Charts are drawn from the tables written by maze_runner.analysis. Maze
pictures rebuild the maze from its seed and rerun the search with trace
recording on; the counts printed on them are therefore the same numbers as in
the CSV (the search is deterministic).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image, ImageDraw

from .analysis import TARGET, load_runs
from .generator import MUD, WALL, make_maze
from .problem import GridProblem
from .search import search

# Colour follows the entity in every figure.
C_BFS = "#257de0"
C_ASTAR = "#f47230"
C_UCS = "#00b894"
C_GREEDY = "#f2a600"
C_PERFECT = "#6a4ce2"
C_LOOPED = "#008a17"
C_PATH = "#ec4647"
C_WALL = "#2b2b2b"
C_MUD = "#e3d3b0"
INK = "#191919"
INK2 = "#666666"
GRID = "#e7e7e7"
AXIS = "#c2c2c2"
SEQ = ["#84b9f3", "#257de0", "#0f4a96"]  # one hue, light to dark, for ordered values
ORDER_CMAP = LinearSegmentedColormap.from_list("order", ["#cce3fd", "#519ced", "#0e3d7e"])
RATE_CMAP = LinearSegmentedColormap.from_list("rate", ["#cce3fd", "#519ced", "#0e3d7e"])

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 100, "savefig.dpi": 200,
    "savefig.bbox": "tight", "lines.linewidth": 2, "lines.markersize": 6,
})


def _save(fig, out: Path, name: str) -> Path:
    path = out / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _hex(color: str) -> np.ndarray:
    return np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], dtype=float) / 255.0


# ------------------------------------------------------------------ maze pictures
def maze_image(maze, order=None) -> np.ndarray:
    """RGB image: walls dark, open white, mud tan, expanded squares shaded by expansion order."""
    grid = maze.grid
    img = np.ones(grid.shape + (3,))
    img[grid == WALL] = _hex(C_WALL)
    img[grid == MUD] = _hex(C_MUD)
    if order:
        shades = ORDER_CMAP(np.linspace(0.0, 1.0, len(order)))[:, :3]
        for (r, c), shade in zip(order, shades):
            img[r, c] = shade if grid[r, c] != MUD else 0.6 * shade + 0.4 * _hex(C_MUD)
    return img


def draw_maze(ax, maze, result=None, title: str = "", show_order: bool = True) -> None:
    order = result.expansion_order if (result is not None and show_order) else None
    ax.imshow(maze_image(maze, order), interpolation="nearest")
    if result is not None and result.found:
        rows, cols = zip(*result.path)
        ax.plot(cols, rows, color=C_PATH, linewidth=1.6, solid_capstyle="round")
    ax.plot(maze.start[1], maze.start[0], "o", color="#008a17", markersize=6, markeredgecolor="white")
    ax.plot(maze.goal[1], maze.goal[0], "*", color=C_PATH, markersize=11, markeredgecolor="white")
    ax.set_title(title, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)


def _legend_handles(mud: bool = False, order: bool = True) -> list:
    handles = [
        Line2D([], [], marker="o", color="none", markerfacecolor="#008a17", markersize=7, label="Start"),
        Line2D([], [], marker="*", color="none", markerfacecolor=C_PATH, markersize=11, label="Goal"),
        Line2D([], [], color=C_PATH, linewidth=2, label="Returned path"),
    ]
    if order:
        handles += [Patch(color="#cce3fd", label="Expanded early"), Patch(color="#0e3d7e", label="Expanded late")]
    if mud:
        handles.append(Patch(color=C_MUD, label="Mud (cost 5)"))
    return handles


def _run(maze, algorithm, **kwargs):
    return search(GridProblem(maze.grid, maze.start, maze.goal), algorithm, record_trace=True, **kwargs)


def _panel_title(name: str, result) -> str:
    return f"{name}: {result.expanded:,} expanded, path {result.path_len} steps"


def fig_maze_types(out: Path, defaults: dict, seed: int, n: int = 15) -> Path:
    mazes = [
        ("Perfect maze", make_maze("perfect", n, seed)),
        (f"Looped maze (p = {defaults['loop_rate']:g})", make_maze("looped", n, seed, loop_rate=defaults["loop_rate"])),
        (f"Weighted maze (p = {defaults['loop_rate']:g}, m = {defaults['mud_rate']:g})",
         make_maze("weighted", n, seed, loop_rate=defaults["loop_rate"], mud_rate=defaults["mud_rate"])),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.6))
    for ax, (title, maze) in zip(axes, mazes):
        draw_maze(ax, maze, title=title)
    fig.legend(handles=_legend_handles(mud=True, order=False)[:2] + [Patch(color=C_MUD, label="Mud (cost 5)")],
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    return _save(fig, out, "maze_types")


def fig_exploration(out: Path, defaults: dict, seed: int, tie_rule: str, n: int = 25) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 9.6))
    for row, maze in enumerate([
        make_maze("perfect", n, seed),
        make_maze("looped", n, seed, loop_rate=defaults["loop_rate"]),
    ]):
        bfs = _run(maze, "bfs")
        astar = _run(maze, "astar", tie_rule=tie_rule)
        kind = "Perfect" if row == 0 else "Looped"
        draw_maze(axes[row, 0], maze, bfs, _panel_title(f"{kind}, BFS", bfs))
        draw_maze(axes[row, 1], maze, astar, _panel_title(f"{kind}, A*", astar))
    fig.legend(handles=_legend_handles(), loc="lower center", ncol=5, bbox_to_anchor=(0.5, 0.02))
    fig.subplots_adjust(wspace=0.04, hspace=0.10, bottom=0.07)
    return _save(fig, out, "exploration_perfect_vs_looped")


def fig_case(out: Path, case: dict, tie_rule: str, name: str) -> Path:
    if case["maze_type"] == "perfect":
        maze = make_maze("perfect", case["n_cells"], case["seed"])
    else:
        maze = make_maze("looped", case["n_cells"], case["seed"], loop_rate=case["loop_rate"])
    bfs = _run(maze, "bfs")
    astar = _run(maze, "astar", tie_rule=tie_rule)
    assert (bfs.expanded, astar.expanded) == (case["bfs_expanded"], case["astar_expanded"]), "figure does not match CSV"
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.9))
    draw_maze(axes[0], maze, bfs, _panel_title("BFS", bfs))
    draw_maze(axes[1], maze, astar, _panel_title("A*", astar))
    fig.legend(handles=_legend_handles(), loc="lower center", ncol=5, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(wspace=0.04, bottom=0.08)
    return _save(fig, out, name)


def fig_weighted_paths(out: Path, defaults: dict, seed: int, tie_rule: str, n: int = 25) -> Path:
    maze = make_maze("weighted", n, seed, loop_rate=defaults["loop_rate"], mud_rate=defaults["mud_rate"])
    runs = [("BFS", _run(maze, "bfs")), ("UCS", _run(maze, "ucs")), ("A*", _run(maze, "astar", tie_rule=tie_rule))]
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.3))
    for ax, (name, result) in zip(axes, runs):
        draw_maze(ax, maze, result,
                  f"{name}: cost {result.path_cost}, {result.path_len} steps,\n{result.expanded:,} expanded")
    fig.legend(handles=_legend_handles(mud=True), loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(wspace=0.04, bottom=0.08)
    return _save(fig, out, "weighted_paths")


# ------------------------------------------------------------------------- charts
def chart_expanded_vs_size(out: Path, metrics: pd.DataFrame, astar: str) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for config, color, name in (("BFS", C_BFS, "BFS"), (astar, C_ASTAR, "A*")):
        for maze_type, style, marker in (("perfect", "-", "o"), ("looped", "--", "s")):
            g = metrics[(metrics["config"] == config) & (metrics["maze_type"] == maze_type)].sort_values("n_cells")
            err = [g["expanded_mean"] - g["expanded_ci_lo"], g["expanded_ci_hi"] - g["expanded_mean"]]
            ax.errorbar(g["n_cells"], g["expanded_mean"], yerr=err, color=color, linestyle=style, marker=marker,
                        capsize=3, markeredgecolor="white", label=f"{name}, {maze_type}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    sizes = sorted(metrics["n_cells"].unique())
    ax.set_xticks(sizes, [f"{n}×{n}" for n in sizes])
    ax.minorticks_off()
    ax.set_xlabel("Maze size (cells)")
    ax.set_ylabel("Nodes expanded (mean, log scale)")
    ax.legend()
    return _save(fig, out, "expanded_vs_size")


def chart_savings_box(out: Path, pairs: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    sizes = sorted(pairs["n_cells"].unique())
    for offset, maze_type, color in ((-0.2, "perfect", C_PERFECT), (0.2, "looped", C_LOOPED)):
        data = [100 * pairs[(pairs["n_cells"] == n) & (pairs["maze_type"] == maze_type)]["savings"] for n in sizes]
        box = ax.boxplot(data, positions=np.arange(len(sizes)) + offset, widths=0.32, patch_artist=True,
                         showmeans=True, medianprops={"color": INK, "linewidth": 1.4},
                         meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": INK, "markersize": 4},
                         flierprops={"marker": "o", "markersize": 3, "markerfacecolor": color, "markeredgecolor": "none"},
                         whiskerprops={"color": INK2}, capprops={"color": INK2})
        for patch in box["boxes"]:
            patch.set(facecolor=color, alpha=0.75, edgecolor="white")
    ax.axhline(100 * TARGET, color=INK, linestyle="--", linewidth=1)
    ax.text(len(sizes) - 0.5, 100 * TARGET + 1.5, "30% target", ha="right", va="bottom", fontsize=8)
    ax.axhline(0, color=AXIS, linewidth=1)
    ax.set_xticks(range(len(sizes)), [f"{n}×{n}" for n in sizes])
    ax.set_xlabel("Maze size (cells)")
    ax.set_ylabel("Expansion savings of A* over BFS (%)")
    ax.legend(handles=[Patch(color=C_PERFECT, alpha=0.75, label="Perfect"), Patch(color=C_LOOPED, alpha=0.75, label="Looped"),
                       Line2D([], [], marker="D", color="none", markerfacecolor="white", markeredgecolor=INK,
                              markersize=4, label="Mean")], loc="upper left", ncol=3)
    ax.set_ylim(top=ax.get_ylim()[1] + 12)
    ax.grid(axis="x", visible=False)
    return _save(fig, out, "savings_by_size_and_type")


def chart_sweep(out: Path, sweep: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9), sharey=True)
    for ax, config in zip(axes, ("A* (larger-g ties)", "A* (FIFO ties)")):
        t = sweep[sweep["config"] == config]
        for n, color in zip(sorted(t["n_cells"].unique()), SEQ):
            g = t[t["n_cells"] == n].sort_values("loop_rate")
            ax.fill_between(g["loop_rate"], 100 * g["savings_ci_lo"], 100 * g["savings_ci_hi"], color=color,
                            alpha=0.18, linewidth=0)
            ax.plot(g["loop_rate"], 100 * g["savings_mean"], color=color, marker="o", markeredgecolor="white",
                    label=f"{n}×{n}")
        ax.axhline(100 * TARGET, color=INK, linestyle="--", linewidth=1)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_title(config, loc="left")
        ax.set_xlabel("Loop rate p (fraction of internal walls removed)")
    axes[0].set_ylabel("Expansion savings over BFS (%)")
    axes[0].text(1.0, 100 * TARGET + 1.5, "30% target", ha="right", va="bottom", fontsize=8)
    axes[0].legend(title="Maze size", loc="upper left")
    fig.subplots_adjust(wspace=0.06)
    return _save(fig, out, "savings_vs_loop_rate")


def chart_informedness(out: Path, pairs: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0), sharey=True)
    for ax, config in zip(axes, ("A* (larger-g ties)", "A* (FIFO ties)")):
        g = pairs[pairs["config"] == config]
        sc = ax.scatter(g["informedness"], 100 * g["savings"], c=np.sqrt(g["loop_rate"]), cmap=RATE_CMAP, s=9,
                        linewidths=0, alpha=0.8, vmin=0, vmax=1)
        ax.axhline(100 * TARGET, color=INK, linestyle="--", linewidth=1)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_title(config, loc="left")
        ax.set_xlabel("Heuristic informedness  h(start) / C*")
        ax.set_xlim(0, 1.03)
    axes[0].set_ylabel("Expansion savings over BFS (%)")
    axes[0].text(0.02, 100 * TARGET + 1.5, "30% target", ha="left", va="bottom", fontsize=8)
    ticks = [0, 0.02, 0.10, 0.35, 1.0]
    cbar = fig.colorbar(sc, ax=axes, pad=0.015, ticks=np.sqrt(ticks))
    cbar.ax.set_yticklabels([f"{t:g}" for t in ticks])
    cbar.set_label("Loop rate p")
    cbar.outline.set_visible(False)
    return _save(fig, out, "savings_vs_informedness")


def _lines_by_type(ax, table: pd.DataFrame, columns: dict) -> None:
    for column, (color, name) in columns.items():
        for maze_type, style, marker in (("perfect", "-", "o"), ("looped", "--", "s")):
            g = table[table["maze_type"] == maze_type].sort_values("n_cells")
            ax.plot(g["n_cells"], g[column], color=color, linestyle=style, marker=marker, markeredgecolor="white",
                    label=f"{name}, {maze_type}")
    sizes = sorted(table["n_cells"].unique())
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(sizes, [f"{n}×{n}" for n in sizes])
    ax.minorticks_off()
    ax.set_xlabel("Maze size (cells)")
    ax.legend()


def chart_runtime(out: Path, time_table: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    _lines_by_type(ax, time_table, {"bfs_ms": (C_BFS, "BFS"), "astar_ms": (C_ASTAR, "A*")})
    ax.set_ylabel("Search time (ms, mean of 5 runs, log scale)")
    return _save(fig, out, "runtime_vs_size")


def chart_frontier(out: Path, frontier: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    _lines_by_type(ax, frontier, {"bfs_peak": (C_BFS, "BFS"), "astar_peak": (C_ASTAR, "A*")})
    ax.set_ylabel("Peak frontier size (records, mean, log scale)")
    return _save(fig, out, "peak_frontier_vs_size")


def chart_weighted(out: Path, weighted: pd.DataFrame, runs: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))
    for n, color in zip(sorted(weighted["n_cells"].unique()), SEQ):
        g = weighted[weighted["n_cells"] == n].sort_values("mud_rate")
        axes[0].fill_between(g["mud_rate"], 100 * g["savings_ci_lo"], 100 * g["savings_ci_hi"], color=color,
                             alpha=0.18, linewidth=0)
        axes[0].plot(g["mud_rate"], 100 * g["savings_mean"], color=color, marker="o", markeredgecolor="white",
                     label=f"{n}×{n}")
    axes[0].axhline(0, color=AXIS, linewidth=1)
    axes[0].set_xticks(sorted(weighted["mud_rate"].unique()))
    axes[0].set_xlabel("Mud rate m (fraction of open squares that cost 5)")
    axes[0].set_ylabel("Expansion savings of A* over UCS (%)")
    axes[0].set_title("Mud weakens the heuristic", loc="left")
    axes[0].legend(title="Maze size")

    bfs = runs[(runs["experiment"] == "weighted") & (runs["config"] == "BFS") & (runs["mud_rate"] > 0)]
    rates = sorted(bfs["mud_rate"].unique())
    sizes = sorted(bfs["n_cells"].unique())
    for k, (size, color) in enumerate(zip(sizes, SEQ)):
        data = [100 * (g["path_cost"] / g["optimal_cost"] - 1)
                for g in (bfs[(bfs["n_cells"] == size) & (bfs["mud_rate"] == m)] for m in rates)]
        box = axes[1].boxplot(data, positions=np.arange(len(rates)) + (k - 1) * 0.26, widths=0.22, patch_artist=True,
                              medianprops={"color": INK, "linewidth": 1.2},
                              flierprops={"marker": "o", "markersize": 3, "markerfacecolor": color, "markeredgecolor": "none"},
                              whiskerprops={"color": INK2}, capprops={"color": INK2})
        for patch in box["boxes"]:
            patch.set(facecolor=color, edgecolor="white")
    axes[1].set_xticks(range(len(rates)), [f"{m:g}" for m in rates])
    axes[1].set_xlabel("Mud rate m")
    axes[1].set_ylabel("Extra cost of the BFS path over the optimum (%)")
    axes[1].set_title("How wrong is BFS when squares have costs?", loc="left")
    axes[1].legend(handles=[Patch(color=c, label=f"{s}×{s}") for s, c in zip(sizes, SEQ)], title="Maze size")
    axes[1].grid(axis="x", visible=False)
    fig.subplots_adjust(wspace=0.22)
    return _save(fig, out, "weighted_extension")


def chart_ablation(out: Path, ablation: pd.DataFrame) -> Path:
    n = int(ablation["n_cells"].max())
    order = ["BFS (goal test at removal)", "A* (h = 0)", "A* (FIFO ties)", "A* (larger-g ties)",
             "Weighted A* (w = 1.5)", "Weighted A* (w = 2)", "Weighted A* (w = 3)", "Greedy"]
    t = ablation[ablation["n_cells"] == n]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    y = np.arange(len(order))[::-1]
    for offset, maze_type, color in ((0.2, "perfect", C_PERFECT), (-0.2, "looped", C_LOOPED)):
        g = t[t["maze_type"] == maze_type].set_index("config").loc[order]
        bars = ax.barh(y + offset, 100 * g["savings_mean"], height=0.36, color=color, label=maze_type.capitalize())
        labels = []
        for row in g.itertuples():
            text = f"{abs(round(100 * row.savings_mean)):.0f}%" if abs(row.savings_mean) < 0.005 else f"{100 * row.savings_mean:.0f}%"
            if row.cost_overhead_mean > 0:
                text += f"  (path +{100 * row.cost_overhead_mean:.1f}%)"
            labels.append(text)
        ax.bar_label(bars, labels=labels, fontsize=7, padding=3, color=INK2)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.axvline(100 * TARGET, color=INK, linestyle="--", linewidth=1)
    ax.set_yticks(y, order)
    ax.set_xlabel(f"Mean expansion savings over BFS (%), {n}×{n} mazes")
    ax.set_xlim(min(-5, ax.get_xlim()[0]), 118)
    ax.legend(loc="upper right")
    ax.grid(axis="y", visible=False)
    return _save(fig, out, "ablation")


# ---------------------------------------------------------------------- animation
def make_gif(out: Path, defaults: dict, seed: int, tie_rule: str, n: int = 25, scale: int = 8, frames: int = 70) -> Path:
    """Side-by-side animation of BFS and A* expanding the same looped maze."""
    maze = make_maze("looped", n, seed, loop_rate=defaults["loop_rate"])
    runs = [("BFS", _run(maze, "bfs")), ("A*", _run(maze, "astar", tie_rule=tie_rule))]
    longest = max(len(r.expansion_order) for _, r in runs)
    steps = sorted(set(np.linspace(0, longest, frames).astype(int).tolist()))
    size = maze.grid_size * scale
    pad, header = 12, 30
    images = []
    for step in steps:
        canvas = Image.new("RGB", (2 * size + 3 * pad, size + header + pad), "white")
        draw = ImageDraw.Draw(canvas)
        for k, (name, result) in enumerate(runs):
            shown = result.expansion_order[:step]
            img = maze_image(maze)
            for r, c in shown:
                img[r, c] = _hex("#84b9f3")
            done = step >= len(result.expansion_order)
            if done:
                for r, c in result.path:
                    img[r, c] = _hex(C_PATH)
            img[maze.start] = _hex("#008a17")
            img[maze.goal] = _hex(C_PATH)
            panel = Image.fromarray((img * 255).astype(np.uint8)).resize((size, size), Image.NEAREST)
            x = pad + k * (size + pad)
            canvas.paste(panel, (x, header))
            status = f"path {result.path_len} steps" if done else "searching"
            draw.text((x, 9), f"{name}: {len(shown):,} expanded, {status}", fill=INK)
        images.append(canvas)
    path = out / "bfs_vs_astar.gif"
    images[0].save(path, save_all=True, append_images=images[1:], duration=[90] * (len(images) - 1) + [2500], loop=0)
    return path


# --------------------------------------------------------------------------- main
def make_all(suite_dir: Path, log=print) -> dict:
    suite_dir = Path(suite_dir)
    out = suite_dir / "figures"
    out.mkdir(exist_ok=True)
    tables = {p.stem: pd.read_csv(p) for p in (suite_dir / "tables").glob("*.csv")}
    summary = json.loads((suite_dir / "summary.json").read_text(encoding="utf-8"))
    runs = load_runs(suite_dir)
    defaults = summary["defaults"]
    astar = summary["headline_astar"]
    tie = defaults["tie_rule"]

    # Example mazes are chosen by a fixed rule from the results, never by eye.
    pairs = tables["main_pairs"]
    p25 = pairs[(pairs["n_cells"] == 25) & (pairs["maze_type"] == "perfect")]
    typical = int(p25.assign(d=(p25["savings"] - p25["savings"].median()).abs()).sort_values(["d", "seed"]).iloc[0]["seed"])
    wb = runs[(runs["experiment"] == "weighted") & (runs["config"] == "BFS") & (runs["n_cells"] == 25)
              & (runs["mud_rate"] == defaults["mud_rate"])]
    w_seed = int(wb.assign(o=wb["path_cost"] / wb["optimal_cost"]).sort_values(["o", "seed"]).iloc[-1]["seed"])
    chosen = {"typical_seed_25": typical, "weighted_example_seed_25": w_seed}

    files = [
        fig_maze_types(out, defaults, typical),
        fig_exploration(out, defaults, typical, tie),
        fig_case(out, summary["cases"]["worst_25"], tie, "failure_case"),
        fig_case(out, summary["cases"]["best_25"], tie, "best_case"),
        fig_weighted_paths(out, defaults, w_seed, tie),
        chart_expanded_vs_size(out, tables["main_metrics"], astar),
        chart_savings_box(out, pairs),
        chart_sweep(out, tables["sweep_savings"]),
        chart_informedness(out, tables["sweep_pairs"]),
        chart_runtime(out, tables["main_time"]),
        chart_frontier(out, tables["main_frontier"]),
        chart_weighted(out, tables["weighted"], runs),
        chart_ablation(out, tables["ablation"]),
        make_gif(out, defaults, typical, tie),
    ]
    (out / "figure_choices.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    for f in files:
        log(f"wrote {f}")
    return chosen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Draw every figure for a results folder.")
    parser.add_argument("suite_dir", type=Path)
    args = parser.parse_args(argv)
    make_all(args.suite_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
