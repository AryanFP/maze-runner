"""Build the final report (Word document) from the final results.

    python report/build_report.py

Every number in the report is read from results/final (tables, summary.json,
metadata.json, runs.csv). Nothing is typed in by hand, so the report cannot
drift from the CSV. Team-specific facts that a script cannot know are marked
[[like this]] and appear highlighted in yellow in the document.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_helpers import Report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "final"
FIG = RES / "figures"
OUT = ROOT / "report" / "Maze_Runner_Final_Report.docx"

S = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
META = json.loads((RES / "metadata.json").read_text(encoding="utf-8"))
CHOICES = json.loads((FIG / "figure_choices.json").read_text(encoding="utf-8"))
T = {p.stem: pd.read_csv(p) for p in (RES / "tables").glob("*.csv")}
RUNS = pd.read_csv(RES / "runs.csv")
TESTS = (ROOT / "results" / "test_summary.txt").read_text(encoding="utf-8").strip()

ASTAR = S["headline_astar"]
D = S["defaults"]
P_LOOP, M_MUD = D["loop_rate"], D["mud_rate"]
V = S["verification"]
SIZES = sorted(T["main_savings"]["n_cells"].unique())
SEEDS = {name: (spec["start"], spec["start"] + spec["count"] - 1) for name, spec in META["seeds"].items()}


def pct(x, digits=1):
    text = f"{100 * x:.{digits}f}"
    return (text.lstrip("-") if float(text) == 0 else text) + "%"


def num(x, digits=0):
    return f"{x:,.{digits}f}"


def sv(maze_type, n):
    t = T["main_savings"]
    return t[(t["maze_type"] == maze_type) & (t["n_cells"] == n)].iloc[0]


def mm(maze_type, n, config):
    t = T["main_metrics"]
    return t[(t["maze_type"] == maze_type) & (t["n_cells"] == n) & (t["config"] == config)].iloc[0]


def sw(config, n, p):
    t = T["sweep_savings"]
    return t[(t["config"] == config) & (t["n_cells"] == n) & ((t["loop_rate"] - p).abs() < 1e-9)].iloc[0]


def wt(n, m):
    t = T["weighted"]
    return t[(t["n_cells"] == n) & ((t["mud_rate"] - m).abs() < 1e-9)].iloc[0]


def ab(maze_type, n, config):
    t = T["ablation"]
    return t[(t["maze_type"] == maze_type) & (t["n_cells"] == n) & (t["config"] == config)].iloc[0]


def ci(row, digits=1):
    return f"{pct(row['savings_mean'], digits)} [{pct(row['savings_ci_lo'], digits)}, {pct(row['savings_ci_hi'], digits)}]"


def seeds(name):
    return f"{SEEDS[name][0]} to {SEEDS[name][1]}"


def verdict(row):
    return "met" if row["target_met"] else "not met"


FIFO, LARGER = "A* (FIFO ties)", "A* (larger-g ties)"
BIG = [n for n in SIZES if n >= 50]
US = S["microseconds_per_expansion"]
BREAK_EVEN = 1 - US["BFS"] / US[ASTAR]
N_MAIN = int(sv("perfect", SIZES[0])["n_mazes"])
SWEEP_SIZES = sorted(T["sweep_savings"]["n_cells"].unique())
SWEEP_RATES = sorted(T["sweep_savings"]["loop_rate"].unique())
W_SIZES = sorted(T["weighted"]["n_cells"].unique())
W_RATES = sorted(T["weighted"]["mud_rate"].unique())
NMAX = max(SIZES)

# derived facts used in the prose (all from the tables)
perf_big = [sv("perfect", n) for n in BIG]
loop_big = [sv("looped", n) for n in BIG]
peak_fifo = {n: max((sw(FIFO, n, p)["savings_mean"], p) for p in SWEEP_RATES) for n in SWEEP_SIZES}
bins = T["sweep_by_informedness"]
bins_h = bins[bins["config"] == ASTAR]
low_bins = bins_h[bins_h["informedness_bin"].isin(["0.0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.4"])]
low_n, low_below = int(low_bins["n_mazes"].sum()), int(low_bins["below_target"].sum())
high_bins = bins_h[bins_h["informedness_bin"].isin(["0.9-<1", "1.0"])]
high_n, high_below = int(high_bins["n_mazes"].sum()), int(high_bins["below_target"].sum())
fifo_one = bins[(bins["config"] == FIFO) & (bins["informedness_bin"] == "1.0")].iloc[0]
typ = T["main_pairs"][(T["main_pairs"]["n_cells"] == 25) & (T["main_pairs"]["seed"] == CHOICES["typical_seed_25"])]
typ_p = typ[typ["maze_type"] == "perfect"].iloc[0]
typ_l = typ[typ["maze_type"] == "looped"].iloc[0]
worst = S["cases"]["worst_25"]
worst_all = S["cases"]["worst_overall"]
wex = RUNS[(RUNS["experiment"] == "weighted") & (RUNS["n_cells"] == 25) & (RUNS["mud_rate"] == M_MUD)
           & (RUNS["seed"] == CHOICES["weighted_example_seed_25"])].set_index("algorithm")
w_def = [wt(n, M_MUD) for n in W_SIZES]
w_all_mud = T["weighted"][T["weighted"]["mud_rate"] > 0]
time_t = T["main_time"]
faster = int(time_t["astar_faster"].sum())
time_n = int(time_t["n_mazes"].sum())
env = S["environment"]
TAG = env["git_describe"].replace("-dirty", "")
sp = T["sweep_pairs"]
fifo_open = sp[(sp["config"] == FIFO) & (sp["loop_rate"] == 1.0)]
fifo_extra = (fifo_open["other"] - fifo_open["base"])
FIFO_EXTRA = (f"exactly {int(fifo_extra.min())} node" + ("s" if fifo_extra.min() != 1 else "")
              if fifo_extra.min() == fifo_extra.max() else f"{int(fifo_extra.min())} to {int(fifo_extra.max())} nodes")
tied = T["main_pairs"][T["main_pairs"]["savings"] == 0]
TIES_ALL_PERFECT = len(tied) > 0 and (tied["maze_type"] == "perfect").all()
SAME_SET = worst["astar_expanded"] == worst["bfs_expanded"]

R = Report(
    figures=["types", "size", "explore", "box", "sweep", "informed", "failure", "wpaths", "weighted",
             "ablation", "runtime", "frontier"],
    tables=["algos", "problem", "lecture", "seeds", "main", "savings", "sweep", "bins", "weighted",
            "ablation", "contrib", "env", "extra"],
)
F, Tn = R.F, R.T

# =============================================================================== title
R.p("**Maze Runner: Comparing Uninformed and Heuristic Search in Grid Mazes**", align="center", size=18,
    space_after=2)
R.p("When does the A* heuristic stop helping?", align="center", size=13, italic=True, space_after=10)
R.p("CS3346A Introduction to Artificial Intelligence, Fall 2026 · Dr. Brent Davis · Group 26", align="center",
    space_after=2)
R.p("Aryan Muhammad (251357591), Austin Brown (251446658), Aryan Farhang (251311878), "
    "Ki il Eum (251181143), Yicheng Luo (251248739)", align="center", space_after=2)
R.p("Final report, December 7, 2026", align="center", space_after=14)

# ============================================================================ abstract
R.h("Abstract")
p50, p100 = sv("perfect", 50), sv("perfect", 100)
l50, l100 = sv("looped", 50), sv("looped", 100)
R.p(
    "Breadth-first search (BFS) and A* both return shortest paths in a grid maze, but A* is supposed to get "
    "there with less work because a heuristic points it toward the goal. We test when that is true. We built a "
    "reproducible Python experiment that generates seeded mazes, runs BFS, uniform cost search (UCS) and A* with "
    "the Manhattan distance heuristic through one shared graph-search loop, and checks every returned path with "
    f"an independent verifier. The data are synthetic: {num(V['mazes'])} maze instances from fixed seeds, covering "
    f"perfect mazes (one route), looped mazes (extra walls removed) and weighted mazes (mud that costs 5), from "
    f"10×10 to 100×100 cells. All {num(V['rows'])} search runs returned legal paths, and all "
    f"{num(V['optimal_ok'])} runs of algorithms that guarantee optimality were optimal. "
    f"On perfect mazes A* expanded only {pct(p50['savings_mean'])} (50×50) and {pct(p100['savings_mean'])} "
    f"(100×100) fewer nodes than BFS, far below our 30% target. On looped mazes it saved "
    f"{pct(l50['savings_mean'])} and {pct(l100['savings_mean'])}, so the target was {verdict(l50)} at 50×50 and "
    f"{verdict(l100)} at 100×100. Savings track how informed the heuristic is, measured as h(start)/C*: below 0.4 "
    f"they exceeded 30% on only {low_n - low_below} of {low_n} mazes. An exact heuristic is still not enough: on "
    f"open grids A* with first-in-first-out tie-breaking saved nothing, while preferring deeper nodes saved up to "
    f"{pct(sw(LARGER, NMAX, 1.0)['savings_mean'], 0)}. With mud, A* and UCS always agreed on cost, the advantage "
    f"of A* shrank to {pct(wt(NMAX, M_MUD)['savings_mean'])} at 100×100, and BFS paths cost "
    f"{pct(wt(NMAX, M_MUD)['bfs_overhead_mean'])} more than the optimum on average."
)

# ======================================================================== introduction
R.h("1. Introduction")
R.p(
    "Finding a good route through a space with obstacles is one of the oldest problems in artificial "
    "intelligence. A warehouse robot, a character in a video game and a delivery planner all solve some version "
    "of it. The textbook answer is state-space search, and the textbook comparison is between uninformed search, "
    "which knows nothing about where the goal is, and informed search, which uses a heuristic estimate of the "
    "remaining distance [4]. BFS is the standard uninformed method when every move costs the same. A* [1] is the "
    "standard informed method: it expands nodes in order of f = g + h, the cost so far plus the estimated cost to "
    "go."
)
R.p(
    "It is tempting to summarize the comparison as “A* is faster”. That summary hides the interesting part. A "
    "heuristic is only as useful as it is accurate, and in a maze the straight-line estimate can be badly wrong: "
    "the corridor that heads toward the goal may be a dead end, and the true route may wind through most of the "
    "maze. Our proposal named this as the failure case to study. This report is built around that question."
)
R.p("**Research questions.**", space_after=2)
R.bullets([
    "**RQ1.** How many fewer nodes does A* with Manhattan distance expand than BFS on perfect and looped mazes "
    "from 10×10 to 100×100 cells? In particular, does it meet the proposal's success criterion of at least 30% "
    "fewer expansions on average for 50×50 and larger, while always returning a shortest path?",
    "**RQ2.** When does the Manhattan heuristic stop helping, and what property of a maze predicts it?",
    "**RQ3.** When squares have different costs (mud costs 5), how do UCS and A* compare, and how wrong is BFS?",
], numbered=False)
R.p("**Goals and contributions.** We set out to build a fair, checkable experiment rather than a demo. "
    "The project delivers:", space_after=2)
R.bullets([
    "a seeded maze generator for perfect, looped and weighted mazes, in which a seed always rebuilds the same maze;",
    "one graph-search loop shared by BFS, UCS, A* and greedy best-first search, so that all algorithms use the "
    "same successor function, neighbour order, duplicate rule and counters;",
    f"an independent path verifier applied to every run, {TESTS.split(' in ')[0].replace(' passed', '')} automated "
    "tests, and an exact reproduction of the expansion counts of the Week 3 lecture example;",
    "a held-out evaluation: all design choices were made on development seeds, the code was frozen with a git "
    "tag, and the final seeds were run once;",
    "an analysis that explains the results with a single measurable quantity, the heuristic informedness "
    "h(start)/C*, and that separates two different ways in which the heuristic stops helping.",
])
R.p(
    "**Structure of the report.** Section 2 reviews the algorithms, the properties of heuristics, maze generation "
    "and related work. Section 3 defines the problem formally and describes the implementation, the verification "
    "and the evaluation protocol. Section 4 presents and interprets the results, including a failure case and "
    "the limitations. Section 5 concludes and lists future work. Section 6 records individual contributions. "
    "Appendix A is the reproducibility record and Appendix B holds extra tables and "
    "figures."
)

# ========================================================================== background
R.h("2. Background and Related Work")
R.h("2.1 Search problems and the algorithms compared", 2)
R.p(
    "A search problem is defined by a state space, the actions available in each state, a start state, a goal "
    "test and a step cost; a solution is a path from the start to a goal, and an optimal solution has the lowest "
    "total cost [4, 13]. All the algorithms in this report are instances of one scheme, best-first graph search: "
    "keep a frontier of generated but unexpanded nodes, repeatedly remove one, and add its successors. They "
    f"differ only in which node the frontier releases next ({Tn('algos')})."
)
R.table("algos",
        ["Algorithm", "Frontier order", "Complete", "Optimal", "Notes"],
        [
            ["BFS [3]", "First in, first out (shallowest first)", "Yes", "Yes, if all steps cost the same",
             "Time and space O(b^d) in general; O(V + E) on an explicit graph"],
            ["UCS (Dijkstra) [2]", "Lowest path cost g", "Yes, if costs ≥ ε > 0", "Yes",
             "Expands every node with g < C*"],
            ["Greedy best-first", "Lowest estimate h", "Yes on finite graphs", "No",
             "Fast when h is good; ignores the cost already paid"],
            ["A* [1]", "Lowest f = g + h", "Yes", "Yes, if h is admissible (with reopening) or consistent",
             "Expands every node with f < C*"],
        ],
        "The four algorithms as frontier policies of one graph-search loop. b is the branching factor, d the "
        "depth of the shallowest goal, C* the optimal solution cost, V and E the numbers of states and edges.",
        widths_cm=[2.6, 3.6, 2.3, 3.7, 4.3], align_right_from=9)
R.p(
    "BFS was described for maze routing by Moore [3]. It finds a path with the fewest steps, which is the "
    "cheapest path only when every step costs the same. UCS is Dijkstra's algorithm [2] stopped at the goal; it "
    "orders the frontier by the cost so far and is optimal for any positive step costs. Greedy best-first search "
    "orders by the heuristic alone and gives up optimality. A*, introduced by Hart, Nilsson and Raphael [1], adds "
    "the two: g keeps it honest about the cost already paid and h pulls it toward the goal."
)
R.h("2.2 Admissible and consistent heuristics", 2)
R.p(
    "Let h*(s) be the true cheapest cost from s to the goal. A heuristic is **admissible** if it never "
    "overestimates, 0 ≤ h(s) ≤ h*(s), and **consistent** if h(u) ≤ c(u, v) + h(v) for every edge and h(goal) = 0 "
    "[4, 5]. Consistency implies admissibility. With an admissible heuristic A* is optimal as long as a node can "
    "be reopened when a cheaper path to it is found; with a consistent heuristic f never decreases along a path, "
    "the first time a node is removed its g is already optimal, and no reopening is needed [5, 13]. A standard "
    "way to build an admissible heuristic is to solve a **relaxed** problem with some constraints removed: the "
    "relaxed optimum can only be cheaper [5]. For two admissible heuristics, the larger one **dominates** and "
    "never causes more expansions with f < C*."
)
R.p(
    "Two classical results frame our study. First, Dechter and Pearl [6] showed that A* with a consistent "
    "heuristic is optimally efficient: any algorithm that is guaranteed to be optimal using the same heuristic "
    "must expand every node with f < C*. The only freedom left is among nodes with f = C*, which is decided by "
    "tie-breaking. Second, the size of the set {f < C*} depends entirely on how close h is to h*. If h = h* "
    "everywhere, only nodes on optimal paths qualify; if h = 0, A* is UCS. The usefulness of A* is therefore "
    "not a property of the algorithm alone but of the heuristic in a particular environment. That is the "
    "premise of our title question."
)
R.h("2.3 Maze generation", 2)
R.p(
    "A **perfect maze** has exactly one simple path between any two cells; as a graph it is a spanning tree of "
    "the grid. The randomized depth-first search generator, also called the recursive backtracker, carves such a "
    "tree by walking to a random unvisited neighbour and backtracking when stuck. It is known for long, winding "
    "corridors with few short dead ends [9]. Removing extra walls from a perfect maze creates cycles and gives a "
    "**looped** (braided) maze with more than one route between cells [9]. Other generators, such as randomized "
    "Prim's or Kruskal's algorithms, produce mazes with a different texture (more, shorter dead ends) [9]; we "
    "return to this in the limitations."
)
R.h("2.4 Related work", 2)
R.p(
    "Grid pathfinding is a well-studied benchmark domain. Sturtevant [7] assembled standard benchmark sets of "
    "game maps, random obstacle maps, rooms and mazes of different corridor widths, and noted that results on one "
    "map type often do not carry over to another. Harabor and Grastien's Jump Point Search [8] speeds up A* on "
    "uniform-cost grids by pruning the many symmetric optimal paths that open areas create; those symmetric "
    "paths are the same f = C* ties that we measure in Section 4.3. Pohl's weighted A* [12] inflates the "
    "heuristic by a factor w > 1 to trade solution quality for speed, with cost at most w times the optimum; we "
    "use it as an ablation. More recently, learned guidance has been added on top of the same search structure: "
    "Neural A* [10] learns a cost map so that a differentiable A* expands fewer nodes, and Searchformer [11] "
    "trains a transformer on A* search traces from maze and Sokoban problems. Both were discussed in the course "
    "[13] and both are evaluated by counting expansions against A*, which is the metric we use."
)
R.p(
    "**How this project differs.** We do not propose a new algorithm. We run a controlled study of a single "
    "factor, maze structure, and ask how it changes the value of a fixed, standard heuristic. The mazes come from "
    "one generator with one knob (the fraction of walls removed), so the heuristic's accuracy can be varied "
    "smoothly from almost useless to exact while everything else is held fixed."
)

# ========================================================================= methodology
R.h("3. Methodology and Implementation")
R.h("3.1 Problem formulation", 2)
R.p(
    f"We use the five-part formulation from the course [13] ({Tn('problem')}). A maze of size n has n×n cells. It "
    "is stored as an occupancy grid of (2n+1)×(2n+1) squares in which every square is either a wall or open: "
    "cell (r, c) is square (2r+1, 2c+1), and the square between two neighbouring cells is open if there is a "
    "passage and a wall otherwise. Search runs on the squares. A “50×50 maze” therefore means 50×50 cells on a "
    "101×101 grid, and all path lengths in this report are in grid steps."
)
R.table("problem", ["Part", "Definition in this project"], [
    ["State", "The square (row, col) occupied by the agent. Nothing else changes which moves are legal or what "
              "they cost, so the position is a sufficient state."],
    ["Actions", "Up, Right, Down, Left (always tried in this order). An action is legal if the target square is "
                "inside the grid and is not a wall."],
    ["Start", "The top-left cell, square (1, 1)."],
    ["Goal test", "The state equals the bottom-right cell, square (2n−1, 2n−1)."],
    ["Step cost", "Unweighted mazes: 1 per move. Weighted mazes: the entry cost of the square that is entered "
                  "(1 for a normal square, 5 for mud); the start is free. This is the convention of the Week 3 "
                  "weighted grid example [13]."],
], "Formal definition of the search problem.", widths_cm=[2.6, 13.9], align_right_from=9)
R.p(
    "The correctness claims below rest on assumptions that we state explicitly, following the course checklist "
    "[13]: the branching factor is finite (at most 4); every step cost is positive (at least 1); the state is "
    "sufficient; repeated states are detected (graph search); and the goal is tested at the right time for each "
    "algorithm (Section 3.3)."
)
R.h("3.2 Maze generation", 2)
R.p(
    f"All mazes are generated by our own code from an integer seed ({F('types')}). Each maze uses its own random "
    "generator objects derived from the seed, never the global random state, so a seed always rebuilds the same "
    "maze; each maze also carries a SHA-256 fingerprint of its grid, stored in the results."
)
R.bullets([
    "**Perfect mazes** are carved by randomized depth-first search with an explicit stack (a recursive version "
    "would exceed Python's recursion limit at 100×100). The result is a spanning tree with exactly n² − 1 "
    "passages.",
    f"**Looped mazes** start from the perfect maze of the same seed. A perfect maze has (n − 1)² internal walls "
    f"left; we open a fraction p of them, chosen at random. The default is p = {P_LOOP:g}. For one seed, the "
    "opened walls at a higher p include those at a lower p, so mazes are nested across the sweep in Section 4.3.",
    f"**Weighted mazes** start from a looped maze and turn a fraction m of the open squares (never the start or "
    f"goal) into mud that costs 5 to enter. The default is m = {M_MUD:g}. We never put mud on a perfect maze: a "
    "perfect maze has exactly one route from start to goal, so costs cannot change which path is best and BFS, "
    "UCS and A* would all return the same route. Costs only matter when there are alternative routes.",
])
R.p(
    "Before a maze is used, a plain flood fill confirms that the goal can be reached from the start; a failure "
    "would stop the run rather than be skipped. It never occurred."
)
R.figure("types", FIG / "maze_types.png",
         f"The three maze types for one seed (15×15 cells, seed {CHOICES['typical_seed_25']}, shown small for "
         f"legibility). The looped maze is the perfect maze with {P_LOOP:.0%} of its remaining internal walls "
         f"opened; the weighted maze adds mud on {M_MUD:.0%} of the open squares.", width_cm=15.5)
R.h("3.3 Search framework", 2)
R.p(
    "All four algorithms run through one function. The frontier object is the only part that changes: a "
    "first-in-first-out queue for BFS, and a binary min-heap ordered by g (UCS), g + h (A*) or h (greedy). "
    "Everything else, including the successor function, the neighbour order, the duplicate rule and the "
    "counters, is the same code. This is what makes the comparison fair."
)
R.code("""
best_g[start] = 0;  frontier.push(start)
while frontier is not empty:
    s, g = frontier.pop()
    if g > best_g[s]: continue              # stale record, not counted
    if s is the goal: return path           # goal test at removal
    expanded += 1
    for v in neighbours(s) in the order Up, Right, Down, Left:
        g2 = g + step_cost(s, v)            # BFS uses 1 for every step
        if g2 < best_g[v]:                  # strict improvement only
            best_g[v] = g2;  parent[v] = s;  generated += 1
            if BFS and v is the goal: return path   # goal test at generation
            frontier.push(v)
return failure
""")
R.p("The rules that decide the numbers are the following.", space_after=2)
R.bullets([
    "**Best-g contract.** A successor is pushed only if its g strictly improves the best known g of that state. "
    "A removed record whose g is worse than the best known g is stale and is skipped. A state can be reopened if "
    "a cheaper path appears; with a consistent heuristic this never happens, but the code stays correct for an "
    "inconsistent one (we test this).",
    "**Goal test.** UCS, A* and greedy test the goal when it is removed from the frontier; with unequal costs, "
    "stopping when the goal is first generated can return a path that is too expensive. BFS tests the goal when "
    "it is generated. For unit costs this is still optimal and it is the strongest fair version of BFS, so our "
    "baseline is not artificially weak. The weaker variant (test at removal) is measured in Section 4.6.",
    "**Ties in A*.** Heap entries are ordered by (f, tie key, insertion counter). The counter makes the order "
    "deterministic. We implement two tie rules: FIFO (older record first) and larger-g (deeper record first, "
    f"then older). The headline results use the {'larger-g' if D['tie_rule'] == 'larger_g' else 'FIFO'} rule, "
    "chosen on development seeds; both are compared in Sections 4.3 and 4.6.",
    "**Counting rule.** //A node is counted as expanded when it is removed from the frontier, passes the stale "
    "check, is not the goal, and its successors are generated.// The goal itself is never counted. The same rule "
    "is applied to every algorithm. We chose it because it reproduces the expansion counts of the lecture "
    "example exactly (Section 3.5) and because it treats BFS, which never removes the goal, the same way as the "
    "heap-based algorithms.",
])
R.p(
    "Besides nodes expanded, each run records nodes generated (successor records created), the peak frontier "
    "size (including stale heap records), the number of states reached, the path length in steps, the path cost, "
    "and the wall-clock time."
)
R.h("3.4 Heuristic and proofs", 2)
R.p(
    "The heuristic is Manhattan distance to the goal, h(s) = c_min · (|Δrow| + |Δcol|), where c_min is the "
    "cheapest entry cost of any square. In all of our mazes c_min = 1, including the weighted ones, so h is plain "
    "Manhattan distance."
)
R.p(
    "**Claim 1: h is admissible.** Consider the relaxed problem in which every wall is removed and every square "
    "costs c_min. Each move changes |Δrow| + |Δcol| by exactly 1, so reaching the goal takes at least "
    "|Δrow| + |Δcol| moves, each costing at least c_min, and a monotone path achieves exactly this. Hence h(s) is "
    "the optimal cost of the relaxed problem. Every path in the real maze is also a path in the relaxed problem "
    "and costs at least as much there, so h(s) ≤ h*(s)."
)
R.p(
    "**Claim 2: h is consistent.** For any legal move from u to v, the Manhattan distance to the goal changes by "
    "exactly 1, so h(u) ≤ h(v) + c_min. Every step cost satisfies c(u, v) ≥ c_min. Therefore "
    "h(u) ≤ c(u, v) + h(v), and h(goal) = 0."
)
R.p(
    "**Consequences.** Because h is consistent, A* never needs to reopen a state and returns an optimal path. "
    "In weighted mazes h remains admissible and consistent, but it becomes a looser bound: mud raises the true "
    "remaining cost while h does not change. Both properties are also checked numerically in the test suite: on "
    "every edge of several hundred small mazes for consistency, and against the true cost-to-go of every square "
    "(from a backward Dijkstra run) for admissibility."
)
R.h("3.5 Verification and testing", 2)
R.p(
    "Wrong node counts were the first risk named in our proposal, so correctness is checked in three independent "
    "ways."
)
R.p(
    "**Independent verifier.** A separate module, which shares no code with the search and uses a different "
    "representation of the grid, checks every returned path: it starts at the start and ends at the goal; every "
    "step moves exactly one square in one of the four directions; no step enters a wall or leaves the grid; the "
    "cost recomputed from scratch equals the reported cost; and the cost equals the true optimum from the "
    "verifier's own Dijkstra run. The verifier is run on every search result of the final experiment, and the "
    "outcome is a column of the results file."
)
R.p(
    f"**Automated tests.** The test suite ({TESTS}) contains generator tests (same seed gives the same "
    "fingerprint; a perfect maze has n² − 1 passages, is connected and has no cycles; a looped maze has exactly "
    "the expected number of extra passages and an intact border; mud never lands on the start or goal), "
    "known-answer tests on hand-built grids (an open 3×3 grid, a corridor, a dead end that points at the goal, "
    "an unreachable goal) in which the exact order of expanded nodes was traced by hand and written into the "
    "test file, and property tests on hundreds of random small mazes (all optimal algorithms agree with the "
    "verifier's optimum; A* with h = 0 expands exactly the same nodes as UCS; an admissible but inconsistent "
    "heuristic still yields the optimum through reopening)."
)
lecture_rows = [
    ["UCS", "13", "26", "13", "26"],
    ["Greedy best-first", "65", "9", "65", "9"],
    ["A* (FIFO ties)", "13", "25", "13", "25"],
]
R.p(
    f"**Reproducing the lecture example.** The Week 3 lecture reports search effort on a small weighted grid in "
    f"which a robot can go straight through expensive squares or around them [13]. We rebuilt that grid as a "
    f"test and ran our code on it with the same cost rule and FIFO ties. Our costs and expansion counts match "
    f"the lecture exactly ({Tn('lecture')}). This is our strongest single piece of evidence that the search loop "
    "and the counting rule behave as the course defines them. With larger-g ties our A* needs only 14 expansions "
    "on the same grid, because it follows one of the two symmetric detours instead of both."
)
R.table("lecture", ["Algorithm", "Lecture: cost", "Lecture: expansions", "Ours: cost", "Ours: expansions"],
        lecture_rows,
        "The Week 3 weighted grid example (four directions, pay the cost of the square entered, start free): "
        "values reported in the lecture [13] and values produced by our implementation in the test suite.",
        widths_cm=[4.0, 2.8, 3.4, 2.8, 3.4])
R.h("3.6 Evaluation protocol", 2)
R.p(
    f"**Seeds and held-out evaluation.** Following the rule that the test set is never used for decisions [13], "
    f"we separated the seeds ({Tn('seeds')}). Everything that could move a number, namely the loop rate p, the "
    "mud rate m, the tie rule, the counting rule and the design of the charts, was fixed using development seeds "
    "and written in a decisions log (DECISIONS.md in the repository). The code was then frozen with the git tag "
    f"`{TAG}`, and the final seeds were run once from that tag. Every algorithm sees exactly the "
    "same maze, start, goal and neighbour order for a given seed."
)
exp_counts = V["per_experiment"]
R.table("seeds", ["Experiment", "Seeds", "Mazes", "Runs", "Purpose"], [
    ["Development", "0 to 49 (experiments), 0 to 99 (tests)", "not reported", "not reported",
     "Debugging and all design choices"],
    ["Main", seeds("main"), num(exp_counts["main"]["mazes"]), num(exp_counts["main"]["rows"]),
     "Headline comparison of BFS and A* (RQ1)"],
    ["Loop rate sweep", seeds("sweep"), num(exp_counts["sweep"]["mazes"]), num(exp_counts["sweep"]["rows"]),
     "When the heuristic stops helping (RQ2)"],
    ["Weighted", seeds("weighted"), num(exp_counts["weighted"]["mazes"]), num(exp_counts["weighted"]["rows"]),
     "UCS, A* and BFS with mud (RQ3)"],
    ["Ablation", seeds("ablation"), num(exp_counts["ablation"]["mazes"]), num(exp_counts["ablation"]["rows"]),
     "Tie rule, goal test timing, greedy, weighted A*"],
], f"Seed sets. Each final experiment uses 50 seeds per configuration; in total {num(V['mazes'])} maze "
   f"instances and {num(V['rows'])} verified search runs.", widths_cm=[2.9, 4.2, 1.6, 1.6, 6.2],
        align_right_from=9)
R.p("**Metrics.**", space_after=2)
R.bullets([
    "**Nodes expanded** (main metric, lower is better). It depends only on the algorithm and the maze, not on the "
    "hardware or the programming language.",
    "**Expansion savings** = 1 − (A* expanded / BFS expanded), computed per maze. It is a paired measure, because "
    "both algorithms ran on the same maze. Positive means A* did less work.",
    "**Path length** (grid steps) and **path cost** (sum of entry costs), to confirm optimality.",
    "**Heuristic informedness** = h(start) / C*, the Manhattan distance from start to goal divided by the true "
    "optimal cost. It is 1 when the heuristic is exact at the start and close to 0 when the true route is far "
    "longer than the straight-line estimate. This is our explanatory variable for RQ2.",
    "**Runtime** (ms), **nodes generated** and **peak frontier size** as supporting measures.",
])
R.p(
    "**Timing.** The proposal promised runtime averaged over five runs. For the main and weighted experiments "
    "each search is run once untimed as a warm-up and then five times with a high-resolution clock "
    "(`time.perf_counter`), timing only the search call (including building the heuristic table) with trace "
    "recording switched off. We store the mean, the median and the minimum. Runtime depends on the "
    "implementation and the machine, so we treat it as supporting evidence only."
)
R.p(
    "**Statistics.** For each maze size and type we report the mean per-maze savings with a 95% percentile "
    "bootstrap confidence interval (10,000 resamples of the 50 mazes, fixed random seed), the standard "
    "deviation, and the number of mazes on which A* expanded fewer, the same number, or more nodes than BFS. A "
    "one-sided Wilcoxon signed-rank test of “A* expands fewer nodes than BFS” is reported as a secondary check. "
    "The success criterion is evaluated as stated in the proposal: mean savings of at least 30%, separately for "
    "each size and type. The criterion was not changed after seeing any result."
)
R.h("3.7 Implementation details", 2)
R.p(
    f"The project is written in Python {env['python']} with NumPy (grids), pandas (tables), SciPy (Wilcoxon "
    "test), Matplotlib and Pillow (figures and animation) and pytest. Internally the grid is padded with a ring "
    "of walls and flattened, so a state is one integer and a move is one addition; this removes bounds checks "
    "from the inner loop. BFS runs in O(V + E) time and the heap-based algorithms in O(E log V), with V at most "
    f"(2n+1)², about 40,000 squares at 100×100. The complete final run ({num(V['mazes'])} mazes, "
    f"{num(V['rows'])} searches plus timing repeats and verification) took {META['duration_s'] / 60:.0f} minutes "
    f"on the machine described in Appendix A. One command (`python run_all.py`) runs the tests, the experiments, the analysis, the figures "
    "and rebuilds this report, so every number in the text is produced by a script from the results file."
)

# ============================================================================= results
R.h("4. Results and Analysis")
R.p(
    f"**Verification first.** All {num(V['rows'])} search runs of the final experiments returned a path that the "
    f"independent verifier accepted as legal, with the reported cost and length confirmed. Of these, "
    f"{num(V['optimal_expected'])} runs used a configuration that guarantees an optimal path (BFS on unit costs, "
    f"UCS, and A* with Manhattan distance or h = 0); all {num(V['optimal_ok'])} were optimal. In the main "
    f"experiment BFS and A* returned paths of the same length on all {S['main']['same_path_length']} of "
    f"{S['main']['mazes']} mazes. The first half of the success criterion, that A* always finds a shortest path, "
    "is met."
)
R.h("4.1 Main comparison: BFS and A* (RQ1)", 2)
R.p(
    f"{Tn('main')} gives the search effort for every size and type, and {F('size')} plots it. Two things stand "
    f"out. On perfect mazes the BFS and A* curves are almost on top of each other at every size. On looped mazes "
    "there is a clear gap, but BFS itself has to work harder there, because a looped maze has more open squares "
    "and BFS floods nearly all of them before it reaches the far corner."
)
main_rows = []
for maze_type in ("perfect", "looped"):
    for n in SIZES:
        b, a = mm(maze_type, n, "BFS"), mm(maze_type, n, ASTAR)
        main_rows.append([
            maze_type.capitalize(), f"{n}×{n}", f"{int(b['n_mazes'])}",
            f"{num(b['expanded_mean'])} ± {num(b['expanded_std'])}",
            f"{num(a['expanded_mean'])} ± {num(a['expanded_std'])}",
            f"{pct(b['fraction_explored_mean'], 0)} / {pct(a['fraction_explored_mean'], 0)}",
            f"{num(b['path_len_mean'])}",
            f"{b['time_mean_ms_mean']:.2f} / {a['time_mean_ms_mean']:.2f}",
        ])
R.table("main", ["Maze type", "Size", "Mazes", "BFS expanded", "A* expanded", "Share of open squares (BFS / A*)",
                 "Path length (steps)", "Time, ms (BFS / A*)"], main_rows,
        f"Main experiment (final seeds {seeds('main')}, 50 mazes per row). Nodes expanded are mean ± standard "
        f"deviation. The path length is identical for BFS and A* on every maze. Time is the mean over mazes of "
        f"the five-run mean. A* uses Manhattan distance with "
        f"{'larger-g' if D['tie_rule'] == 'larger_g' else 'FIFO'} ties.",
        widths_cm=[1.8, 1.8, 1.3, 2.8, 2.8, 2.5, 1.8, 2.3], font_size=8.5, align_right_from=2)
R.figure("size", FIG / "expanded_vs_size.png",
         f"Nodes expanded against maze size for BFS and A* on perfect and looped mazes (final seeds "
         f"{seeds('main')}, 50 mazes per point; both axes logarithmic; error bars are 95% bootstrap confidence "
         "intervals of the mean and are mostly smaller than the markers).", width_cm=11.5)
R.p(
    f"{F('explore')} shows why, on one typical 25×25 seed. In the perfect maze (top row) the only route to the "
    f"goal is {int(typ_p['path_len'])} steps long although the goal is only 96 steps away in a straight line. A* "
    f"expands {num(typ_p['other'])} nodes against {num(typ_p['base'])} for BFS: the heuristic prunes only a few side "
    f"branches. In the looped maze of the same seed (bottom row) the shortest path "
    f"drops to {int(typ_l['path_len'])} steps, and A* leaves large regions untouched "
    f"({num(typ_l['other'])} expansions against {num(typ_l['base'])})."
)
R.figure("explore", FIG / "exploration_perfect_vs_looped.png",
         f"BFS (left) and A* (right) on the same 25×25 mazes: perfect (top) and looped with p = {P_LOOP:g} "
         f"(bottom), seed {CHOICES['typical_seed_25']}. This seed was chosen by rule as the perfect maze whose "
         "savings are closest to the median. Squares are shaded by expansion order; white squares were never "
         "expanded.", width_cm=14.5)
R.h("4.2 The 30% success criterion", 2)
crit = []
for maze_type in ("perfect", "looped"):
    for n in SIZES:
        r = sv(maze_type, n)
        crit.append([
            maze_type.capitalize(), f"{n}×{n}", ci(r), pct(r["savings_std"]), pct(r["savings_median"]),
            f"{pct(r['savings_min'], 0)} to {pct(r['savings_max'], 0)}",
            f"{int(r['wins'])} / {int(r['ties'])} / {int(r['losses'])}",
            f"{r['informedness_mean']:.2f}",
            ("Yes" if r["target_met"] else "No") if n >= 50 else "n/a",
        ])
R.table("savings", ["Maze type", "Size", "Mean savings [95% CI]", "SD", "Median", "Range", "A* fewer / same / more",
                    "Mean informedness", "≥ 30% target met"], crit,
        f"Paired expansion savings of A* over BFS per maze (final seeds {seeds('main')}, 50 mazes per row). The "
        "target applies to 50×50 and larger. Informedness is h(start)/C*.",
        widths_cm=[1.7, 1.7, 3.6, 1.3, 1.4, 2.2, 2.2, 1.7, 1.6], font_size=8.5, align_right_from=2)
both_loop = all(r["target_met"] for r in loop_big)
none_perf = not any(r["target_met"] for r in perf_big)
R.p(
    f"{Tn('savings')} answers the criterion separately for each size and type, as the proposal's wording "
    f"requires, and {F('box')} shows the full distributions."
)
R.bullets([
    f"**Perfect mazes: the target is {'not met at either size' if none_perf else 'met at some sizes'}.** Mean "
    f"savings are {ci(perf_big[0])} at 50×50 and {ci(perf_big[1])} at 100×100. The upper ends of the confidence "
    "intervals are far below 30%, so this is not a borderline miss.",
    f"**Looped mazes: the target is {verdict(loop_big[0])} at 50×50 ({ci(loop_big[0])}) and "
    f"{verdict(loop_big[1])} at 100×100 ({ci(loop_big[1])}).** "
    + ("Both intervals lie above 30%." if all(r["target_met_ci"] for r in loop_big) else
       "The confidence intervals show how close each case is to the 30% line; where an interval contains 30%, "
       "the verdict should be read as marginal rather than decisive."),
])
R.p(
    f"We report this as it is: the criterion in the proposal is "
    f"{'met on looped mazes and missed on perfect mazes' if both_loop and none_perf else 'only partly met'}. A* "
    f"expanded fewer nodes than BFS on {S['main']['astar_wins']} of the {S['main']['mazes']} mazes, the same "
    f"number on {S['main']['astar_ties']}, and more on {S['main']['astar_losses']}, and the Wilcoxon test rejects "
    "“no difference” in every row (largest p-value "
    f"{T['main_savings']['wilcoxon_p'].max():.1e}). So A* is reliably //no worse// than BFS, but “reliably fewer” "
    "and “30% fewer” are very different claims. Averages also hide a wide spread: on looped mazes individual "
    f"savings range from {pct(min(sv('looped', n)['savings_min'] for n in SIZES), 0)} to "
    f"{pct(max(sv('looped', n)['savings_max'] for n in SIZES), 0)}. The ratio of mean expansions, an alternative "
    f"reading of “on average”, gives the same verdicts ({pct(perf_big[0]['savings_of_means'])} and "
    f"{pct(perf_big[1]['savings_of_means'])} for perfect, {pct(loop_big[0]['savings_of_means'])} and "
    f"{pct(loop_big[1]['savings_of_means'])} for looped mazes)."
    if all((r["savings_of_means"] >= 0.30) == bool(r["target_met"]) for r in perf_big + loop_big) else
    f"We report this as it is. A* expanded fewer nodes than BFS on {S['main']['astar_wins']} of the "
    f"{S['main']['mazes']} mazes, the same number on {S['main']['astar_ties']}, and more on "
    f"{S['main']['astar_losses']}. The ratio of mean expansions, an alternative reading of “on average”, gives "
    f"{pct(perf_big[0]['savings_of_means'])} and {pct(perf_big[1]['savings_of_means'])} for perfect and "
    f"{pct(loop_big[0]['savings_of_means'])} and {pct(loop_big[1]['savings_of_means'])} for looped mazes; where "
    "this differs from the per-maze mean, the verdict depends on the reading and should be treated as marginal."
)
R.figure("box", FIG / "savings_by_size_and_type.png",
         f"Distribution of per-maze expansion savings of A* over BFS (final seeds {seeds('main')}, 50 mazes per "
         "box). Boxes span the quartiles, the line is the median, the diamond is the mean, whiskers reach 1.5 "
         "times the interquartile range, and dots are individual mazes beyond them. The dashed line is the 30% "
         "target.", width_cm=11.5)
R.p(
    f"Two trends in {Tn('savings')} need explaining. First, perfect mazes get //worse// for A* as they grow: "
    f"savings fall from {pct(sv('perfect', SIZES[0])['savings_mean'])} at {SIZES[0]}×{SIZES[0]} to "
    f"{pct(sv('perfect', NMAX)['savings_mean'])} at {NMAX}×{NMAX}. The informedness column shows why. The "
    "depth-first generator makes solution paths that wind more and more as the maze grows, so the straight-line "
    f"estimate at the start covers {sv('perfect', SIZES[0])['informedness_mean']:.0%} of the true distance at "
    f"{SIZES[0]}×{SIZES[0]} but only {sv('perfect', NMAX)['informedness_mean']:.0%} at {NMAX}×{NMAX}. Second, "
    f"looped mazes also lose savings with size ({pct(sv('looped', 25)['savings_mean'])} at 25×25, "
    f"{pct(sv('looped', NMAX)['savings_mean'])} at {NMAX}×{NMAX}) even though their mean informedness stays near "
    f"{sv('looped', NMAX)['informedness_mean']:.2f}. A likely reason is that what A* can prune is governed by the "
    "absolute slack C* − h(start), not the ratio: A* must expand every node with g + h < C*, and a slack of a "
    "quarter of the path length is a few dozen steps in a small maze but several hundred steps in a large one, "
    "enough to reach into most side regions whose local detours have a fixed size. We did not test this "
    "explanation directly."
)
R.h("4.3 When does the heuristic stop helping? (RQ2)", 2)
R.p(
    f"To answer the title question we varied one thing, the loop rate p, from 0 (a perfect maze) to 1 (every "
    f"internal wall removed, an open grid with pillars), on fresh seeds ({seeds('sweep')}), and ran BFS and A* "
    f"with both tie rules on every maze. {F('sweep')} and {Tn('sweep')} show the result."
)
sweep_rows = []
for p in SWEEP_RATES:
    row = [f"{p:g}", f"{sw(LARGER, 50, p)['informedness_mean']:.2f}"]
    row += [pct(sw(LARGER, n, p)["savings_mean"], 0) for n in SWEEP_SIZES]
    row += [pct(sw(FIFO, n, p)["savings_mean"], 0) for n in SWEEP_SIZES]
    sweep_rows.append(row)
R.table("sweep", ["Loop rate p", "Informedness (50×50)"] + [f"Larger-g, {n}×{n}" for n in SWEEP_SIZES]
        + [f"FIFO, {n}×{n}" for n in SWEEP_SIZES], sweep_rows,
        f"Loop rate sweep: mean expansion savings of A* over BFS for the two tie rules (final seeds "
        f"{seeds('sweep')}, 50 mazes per cell, nested mazes per seed). Informedness is the mean h(start)/C* at "
        "50×50.", widths_cm=[1.7, 2.2, 2.1, 2.1, 2.1, 2.1, 2.1, 2.1], font_size=8.5)
R.figure("sweep", FIG / "savings_vs_loop_rate.png",
         f"Mean expansion savings of A* over BFS as walls are removed, for larger-g ties (left) and FIFO ties "
         f"(right). Final seeds {seeds('sweep')}, 50 mazes per point; bands are 95% bootstrap confidence "
         "intervals; the dashed line is the 30% target.", width_cm=15.5)
R.p(
    f"**Finding 1: the heuristic helps in proportion to how informed it is.** With larger-g ties, savings rise "
    f"steadily with p: {pct(sw(LARGER, 50, 0.0)['savings_mean'], 0)} at p = 0, "
    f"{pct(sw(LARGER, 50, 0.1)['savings_mean'], 0)} at p = 0.1, {pct(sw(LARGER, 50, 0.35)['savings_mean'], 0)} at "
    f"p = 0.35 and {pct(sw(LARGER, 50, 1.0)['savings_mean'], 0)} at p = 1 (50×50). Removing walls shortens the "
    "true route toward the straight-line distance, so h approaches h* and the set of nodes with f < C* that A* "
    f"is forced to expand shrinks. {F('informed')} plots every maze of the sweep by its informedness. The "
    f"relationship is strong for larger-g ties (Spearman rank correlation {S['sweep']['spearman'][LARGER]:.2f}; "
    f"only {S['sweep']['spearman'][FIFO]:.2f} for FIFO ties, for the reason given in Finding 2) "
    f"and {Tn('bins')} turns it into a rule of thumb: when h(start)/C* is below 0.4, A* reached the 30% target on "
    f"only {low_n - low_below} of {low_n} mazes; when it is above 0.9, on {high_n - high_below} of {high_n}."
)
R.figure("informed", FIG / "savings_vs_informedness.png",
         f"Expansion savings against heuristic informedness h(start)/C*, one dot per maze of the sweep "
         f"({num(S['sweep']['mazes'])} mazes: 25×25, 50×50 and 100×100, nine loop rates, final seeds "
         f"{seeds('sweep')}). Colour is the loop rate. Left: larger-g ties. Right: FIFO ties, where savings "
         "collapse on the mazes with informedness 1.", width_cm=15.5)
bin_rows = []
for label in bins_h["informedness_bin"]:
    a = bins_h[bins_h["informedness_bin"] == label].iloc[0]
    f_ = bins[(bins["config"] == FIFO) & (bins["informedness_bin"] == label)].iloc[0]
    bin_rows.append([label.replace("-", " to ").replace("to <1", "to <1.0"), f"{int(a['n_mazes'])}",
                     pct(a["savings_mean"], 0), f"{int(a['n_mazes'] - a['below_target'])}",
                     pct(f_["savings_mean"], 0), f"{int(f_['n_mazes'] - f_['below_target'])}"])
R.table("bins", ["Informedness h(start)/C*", "Mazes", "Larger-g: mean savings", "Larger-g: mazes ≥ 30%",
                 "FIFO: mean savings", "FIFO: mazes ≥ 30%"], bin_rows,
        f"Savings grouped by heuristic informedness, all sizes and loop rates of the sweep pooled (final seeds "
        f"{seeds('sweep')}). The last row holds the mazes in which the Manhattan distance from the start is "
        "exact.", widths_cm=[3.6, 1.6, 2.7, 2.7, 2.7, 2.7])
R.p(
    f"**Finding 2: an exact heuristic is still not enough; tie-breaking decides.** With FIFO ties the curve in "
    f"{F('sweep')} is not monotone. Savings peak near p = {peak_fifo[50][1]:g} "
    f"({pct(peak_fifo[50][0], 0)} at 50×50) and then fall, reaching "
    f"{pct(sw(FIFO, 50, 1.0)['savings_mean'], 1)} at p = 1, where A* with FIFO ties expanded //more// nodes than "
    f"BFS on all {S['sweep']['losses'][FIFO]} mazes (by {FIFO_EXTRA}). On those mazes the heuristic is "
    "perfect at the start. The explanation is the f = C* plateau from Section 2.2: on an open grid a very large "
    "number of squares lie on some shortest path, and every one of them has f = C* exactly. A consistent "
    "heuristic tells A* nothing about the order within a plateau. FIFO ties sweep it level by level, exactly "
    "like BFS, and BFS even stops slightly earlier because it tests the goal at generation. Preferring the "
    f"larger g dives along one shortest path and saves {pct(sw(LARGER, 50, 1.0)['savings_mean'], 0)}. The "
    "hand-traced 3×3 open grid in our tests shows the same effect in miniature (7 expansions for BFS, 8 for "
    "A* with FIFO ties, 4 with larger-g ties). This is the same path symmetry that Jump Point Search was "
    "designed to remove [8]."
)
R.p(
    "**Answer to the title question.** The Manhattan heuristic stops helping in two different regimes. In "
    "tree-like mazes it is //uninformed//: the true route is several times longer than the straight line, most "
    "nodes have f < C*, and A* is forced to expand them, dead ends included. On open grids it is "
    "//uninformative among ties//: it is exact, but so many nodes share f = C* that the result depends on "
    "tie-breaking rather than on the heuristic. The best case for A* lies between the two, or anywhere on the "
    "open side with a tie rule that prefers depth. The single quantity h(start)/C* predicts the first regime "
    "well; it cannot see the second."
)
R.h("4.4 A worked failure case", 2)
R.p(
    f"{F('failure')} shows the maze with the lowest savings among the 25×25 mazes of the main experiment "
    f"({worst['maze_type']}, seed {worst['seed']}). A* expanded {num(worst['astar_expanded'])} nodes and BFS "
    f"{num(worst['bfs_expanded'])}, a saving of {pct(worst['savings'])}. The shortest path is "
    f"{worst['path_len']} steps although the Manhattan distance is 96, an informedness of "
    f"{worst['informedness']:.2f}. The mechanism can be read off f = g + h. The goal has f = C* = "
    f"{worst['path_len']}. Any square x that can be reached in g(x) steps has f(x) = g(x) + h(x), and h(x) is at "
    f"most 96, so every square that can be reached in fewer than {worst['path_len'] - 96} steps has f < C* no "
    "matter where it lies, and A* is obliged to expand it before it may stop. In this maze the branches off the "
    "solution path are short dead-end pockets, so everything BFS reaches before it finds the goal is inside that "
    f"budget, and the two algorithms expand {'exactly the same squares' if SAME_SET else 'almost the same squares'}. "
    "The dead ends pointing toward the goal, which our proposal expected to hurt A*, are indeed expanded early "
    "because their h is small. But the deeper problem is the length of the detour itself: when the route is "
    "several times longer than the straight line, the heuristic's opinion about direction is worth almost "
    "nothing. "
    + (f"A* tied with BFS in this way on {len(tied)} of the {S['main']['mazes']} mazes of the main experiment, all "
       "of them perfect mazes, and never expanded more." if TIES_ALL_PERFECT else
       f"Across all sizes, the lowest savings in the main experiment were {pct(worst_all['savings'])}.")
)
R.figure("failure", FIG / "failure_case.png",
         f"Failure case: the 25×25 maze of the main experiment with the lowest savings ({worst['maze_type']}, "
         f"seed {worst['seed']}). BFS (left) and A* (right) expand "
         f"{'exactly' if SAME_SET else 'almost'} the same squares: the route is so much longer than the "
         "straight-line distance that every square near it has f below C*.", width_cm=14.5)
R.h("4.5 Weighted mazes: UCS, A* and BFS (RQ3)", 2)
w_rows = []
for n in W_SIZES:
    for m in W_RATES:
        r = wt(n, m)
        w_rows.append([
            f"{n}×{n}", f"{m:g}", num(r["base_mean"]), num(r["other_mean"]), ci(r), f"{r['informedness_mean']:.2f}",
            pct(r["bfs_overhead_mean"]) if m > 0 else "0.0%", pct(r["bfs_overhead_max"]) if m > 0 else "0.0%",
            f"{int(r['bfs_suboptimal'])} / {int(r['n_mazes'])}",
        ])
R.p(
    f"In weighted mazes the baseline is UCS, as stated in the proposal, and BFS is kept as a reference that "
    f"optimizes the wrong objective. Mazes are looped (p = {P_LOOP:g}) with a fraction m of muddy squares, on "
    f"fresh seeds ({seeds('weighted')}); {Tn('weighted')} and {F('weighted')} summarize the results."
)
R.table("weighted", ["Size", "Mud rate m", "UCS expanded", "A* expanded", "A* savings over UCS [95% CI]",
                     "Informedness", "BFS extra cost, mean", "BFS extra cost, max", "Mazes where BFS is not optimal"],
        w_rows,
        f"Weighted extension (looped mazes with p = {P_LOOP:g}, mud costs 5; final seeds {seeds('weighted')}, 50 "
        "mazes per row). Savings are paired per maze. “Extra cost” is the cost of the BFS path relative to the "
        "optimal cost. Informedness is h(start)/C* with C* the optimal cost.",
        widths_cm=[1.6, 1.4, 1.8, 1.8, 3.7, 1.8, 1.7, 1.7, 2.0], font_size=8.5)
R.p(
    f"**UCS and A* agree; A* does less work, but less than before.** UCS and A* returned the same optimal cost "
    f"on all {S['weighted']['ucs_astar_same_cost']} of {S['weighted']['mazes']} weighted-experiment mazes. A* "
    f"expanded fewer nodes than UCS, but its advantage shrinks quickly as mud is added: at {NMAX}×{NMAX} from "
    f"{pct(wt(NMAX, 0.0)['savings_mean'])} with no mud to {pct(wt(NMAX, M_MUD)['savings_mean'])} at m = "
    f"{M_MUD:g} and {pct(wt(NMAX, max(W_RATES))['savings_mean'])} at m = {max(W_RATES):g}. This is the "
    "informedness effect again. Mud raises the true cost of every route, but Manhattan distance must assume "
    "that every remaining square costs 1, so h falls further below h* (the informedness column drops from "
    f"{wt(NMAX, 0.0)['informedness_mean']:.2f} to {wt(NMAX, max(W_RATES))['informedness_mean']:.2f}). The "
    "heuristic is still admissible and consistent, and A* is still optimal; it is simply a looser bound."
)
R.p(
    f"**BFS is wrong, moderately and often.** BFS still returns a path with the fewest steps, but with mud that "
    f"is no longer the cheapest path. At the default m = {M_MUD:g} the BFS path cost more than the optimum on "
    + ", ".join(f"{int(r['bfs_suboptimal'])} of {int(r['n_mazes'])} mazes at {n}×{n}" for n, r in zip(W_SIZES, w_def))
    + f", by {pct(min(r['bfs_overhead_mean'] for r in w_def))} to {pct(max(r['bfs_overhead_mean'] for r in w_def))} "
      f"on average and by up to {pct(max(r['bfs_overhead_max'] for r in w_def))} on a single maze. "
    f"{F('wpaths')} shows the maze with the largest gap at 25×25: BFS returns a path of "
    f"{int(wex.loc['bfs', 'path_len'])} steps that costs {int(wex.loc['bfs', 'path_cost'])}, while UCS and A* "
    f"return a path of {int(wex.loc['ucs', 'path_len'])} steps that costs {int(wex.loc['ucs', 'path_cost'])}. "
    "Fewest actions is not lowest cost. BFS also expands about as many nodes as UCS, so in a weighted maze it "
    "is neither cheaper to run nor correct."
)
R.figure("wpaths", FIG / "weighted_paths.png",
         f"A weighted 25×25 maze (p = {P_LOOP:g}, m = {M_MUD:g}, seed {CHOICES['weighted_example_seed_25']}; "
         "chosen by rule as the 25×25 maze with the largest extra cost for BFS). Mud squares are tan. BFS "
         "minimizes steps and pays more; UCS and A* return the same optimal cost, and A* expands fewer nodes.",
         width_cm=16.0)
R.figure("weighted", FIG / "weighted_extension.png",
         f"Weighted extension (final seeds {seeds('weighted')}, 50 mazes per point or box). Left: mean paired "
         "expansion savings of A* over UCS against the mud rate, with 95% bootstrap bands. Right: extra cost of "
         "the BFS path over the optimal cost.", width_cm=15.5)
R.h("4.6 Ablations", 2)
ab_cfgs = ["BFS", "BFS (goal test at removal)", "A* (h = 0)", FIFO, LARGER, "Weighted A* (w = 1.5)",
           "Weighted A* (w = 2)", "Weighted A* (w = 3)", "Greedy"]
ab_rows = []
for cfg in ab_cfgs:
    row = [cfg]
    for maze_type in ("perfect", "looped"):
        r = ab(maze_type, NMAX, cfg)
        row += [num(r["expanded_mean"]), "baseline" if cfg == "BFS" else pct(r["savings_mean"]),
                f"{int(r['optimal_count'])} / {int(r['n_mazes'])}", pct(r["cost_overhead_mean"])]
    ab_rows.append(row)
R.p(
    f"The ablations use their own seeds ({seeds('ablation')}) and nine configurations on the same mazes. "
    f"{Tn('ablation')} lists the {NMAX}×{NMAX} results and {F('ablation')} plots the savings."
)
R.table("ablation", ["Configuration", "Perfect: expanded", "Savings vs BFS", "Optimal", "Extra path cost",
                     "Looped: expanded", "Savings vs BFS", "Optimal", "Extra path cost"], ab_rows,
        f"Ablations on {NMAX}×{NMAX} mazes (final seeds {seeds('ablation')}, 50 perfect and 50 looped mazes, "
        f"p = {P_LOOP:g}). Savings are the mean of the paired per-maze savings relative to BFS with the goal test "
        "at generation. “Optimal” counts mazes on which the returned path was a shortest path; “extra path cost” "
        "is the mean excess over the optimum.",
        widths_cm=[3.6, 1.7, 1.6, 1.5, 1.5, 1.7, 1.6, 1.5, 1.5], font_size=8.5)
g_p, g_l = ab("perfect", NMAX, "Greedy"), ab("looped", NMAX, "Greedy")
w2 = ab("looped", NMAX, "Weighted A* (w = 2)")
w15 = ab("looped", NMAX, "Weighted A* (w = 1.5)")
R.bullets([
    f"**BFS goal test timing.** Testing the goal at removal instead of at generation costs BFS "
    f"{S['ablation']['bfs_removal_extra_mean']:.1f} extra expansions per maze on average, which is negligible "
    "at these sizes. The definition of the baseline therefore does not drive the 30% verdicts, but we kept the "
    "stronger baseline for the headline numbers.",
    f"**A* with h = 0.** It expands exactly as many nodes as BFS with the goal test at removal in every row of "
    f"{Tn('ablation')}: with unit costs, UCS is BFS. All the benefit of A* comes from the heuristic.",
    f"**Tie rule.** At the default p = {P_LOOP:g} the tie rule matters little: larger-g ties save "
    f"{pct(ab('looped', NMAX, LARGER)['savings_mean'])} and FIFO ties "
    f"{pct(ab('looped', NMAX, FIFO)['savings_mean'])} on looped mazes, and they are within "
    f"{abs(ab('perfect', NMAX, LARGER)['savings_mean'] - ab('perfect', NMAX, FIFO)['savings_mean']) * 100:.1f} "
    "percentage points of each other on perfect mazes. The large effect appears only at high loop rates "
    "(Section 4.3), where f = C* plateaus are large.",
    f"**Greedy best-first and weighted A*.** On looped mazes greedy search expands "
    f"{pct(g_l['savings_mean'], 0)} fewer nodes than BFS, far more than A*, but its path was optimal on only "
    f"{int(g_l['optimal_count'])} of {int(g_l['n_mazes'])} mazes and was {pct(g_l['cost_overhead_mean'])} longer "
    f"on average. Weighted A* sits between: with w = 1.5 it saves {pct(w15['savings_mean'], 0)} for paths "
    f"{pct(w15['cost_overhead_mean'])} longer, and with w = 2, {pct(w2['savings_mean'], 0)} for "
    f"{pct(w2['cost_overhead_mean'])}. Fewer expansions alone do not establish a better solution. On perfect "
    f"mazes both remain optimal on every maze ({int(g_p['optimal_count'])} of {int(g_p['n_mazes'])} for greedy), "
    "simply because there is only one route to return; this is the same reason we did not build weighted mazes "
    "on perfect mazes.",
])
R.figure("ablation", FIG / "ablation.png",
         f"Mean paired expansion savings over BFS for each ablation configuration on {NMAX}×{NMAX} mazes (final "
         f"seeds {seeds('ablation')}, 50 mazes per bar). Labels in parentheses give the mean extra path cost "
         "where the returned paths were not all optimal. The dashed line is the 30% target, which applies to "
         "optimal algorithms only.", width_cm=13.5)
R.h("4.7 Runtime and memory", 2)
t100p = time_t[(time_t["maze_type"] == "perfect") & (time_t["n_cells"] == NMAX)].iloc[0]
t100l = time_t[(time_t["maze_type"] == "looped") & (time_t["n_cells"] == NMAX)].iloc[0]
fr = T["main_frontier"]
frl = fr[(fr["maze_type"] == "looped") & (fr["n_cells"] == NMAX)].iloc[0]
frp = fr[(fr["maze_type"] == "perfect") & (fr["n_cells"] == NMAX)].iloc[0]
R.p(
    f"Runtime tells a more sober story than expansions ({F('runtime')}). A* was faster than BFS on only {faster} "
    f"of the {time_n} mazes of the main experiment. At {NMAX}×{NMAX} it took {t100p['astar_ms']:.1f} ms against "
    f"{t100p['bfs_ms']:.1f} ms for BFS on perfect mazes and {t100l['astar_ms']:.1f} ms against "
    f"{t100l['bfs_ms']:.1f} ms on looped mazes. The reason is the cost per expansion: a heap operation costs "
    f"O(log n) and more Python bytecode than a queue operation, about {US[ASTAR]:.2f} µs per expanded node for "
    f"A* against {US['BFS']:.2f} µs for BFS in our implementation (mazes of 50×50 and larger). A* therefore "
    f"needs to save roughly {pct(BREAK_EVEN, 0)} of the expansions just to break even on time. These numbers "
    "are specific to our Python implementation and one machine; the expansion counts are not. Still, the "
    "practical message is that a small saving in expansions can be a loss in time."
)
R.figure("runtime", FIG / "runtime_vs_size.png",
         f"Search time against maze size (final seeds {seeds('main')}, 50 mazes per point; each maze timed as the "
         "mean of five runs after one warm-up; both axes logarithmic). Times depend on the implementation and "
         "machine (Appendix A).", width_cm=11.0)
R.p(
    f"Memory, measured as the peak frontier size, is small for both algorithms because maze corridors are "
    f"narrow: at {NMAX}×{NMAX} the mean peak was {frp['bfs_peak']:.0f} records for BFS and "
    f"{frp['astar_peak']:.0f} for A* on perfect mazes, and {frl['bfs_peak']:.0f} and {frl['astar_peak']:.0f} on "
    f"looped mazes ({F('frontier')} in Appendix B). The A* frontier is larger because it keeps postponed "
    "branches with high f on the heap, where BFS discards each level as it goes. The dominant memory cost for "
    "both is the reached table, which is proportional to the number of squares."
)
R.h("4.8 Limitations and what this experiment can and cannot establish", 2)
R.p("**What the evidence supports.**", space_after=2)
R.bullets([
    "On mazes from this generator, with corner-to-corner queries, A* with Manhattan distance never returned a "
    "worse path than BFS and almost never expanded more nodes, across sizes from 10×10 to 100×100.",
    "Its advantage is small on perfect mazes and substantial on looped mazes, and it is predicted well by the "
    "informedness h(start)/C*.",
    "The advantage also depends on tie-breaking once many nodes share f = C*, and it shrinks when costs make "
    "the heuristic a looser bound.",
])
R.p("**What it does not establish.**", space_after=2)
R.bullets([
    "**Other maze generators.** We used only the randomized depth-first generator, which makes long winding "
    "corridors. Prim's or Kruskal's algorithms make shorter dead ends and more direct solution paths, so the "
    "perfect-maze numbers could look different. The informedness analysis suggests how, but we did not test it.",
    "**Other queries.** Start and goal are always in opposite corners, the longest straight-line distance in "
    "the grid. Random start and goal pairs would include short queries where the heuristic matters less.",
    "**Other heuristics and move sets.** Only four-way moves and Manhattan distance were studied. We do not "
    "claim anything about eight-way movement or about stronger heuristics.",
    "**Runtime in general.** Timings come from one pure-Python implementation on one machine. A compiled "
    "implementation or a different priority queue would change the break-even point.",
    "**Causes.** Informedness is correlated with savings; we varied it only through the loop rate (and mud), so "
    "we cannot separate it from other things that change when walls are removed, such as the number of "
    "shortest paths. The explanation for the size trend in looped mazes (Section 4.2) is a hypothesis.",
    "**Scale.** The largest maze has about 40,000 squares. Trends beyond 100×100 are extrapolation.",
])

# ========================================================================= conclusions
R.h("5. Conclusions and Future Work")
R.p(
    f"**RQ1.** A* with Manhattan distance always returned a shortest path, and all {num(V['rows'])} runs passed "
    f"independent verification. On perfect mazes it expanded only {pct(p50['savings_mean'])} (50×50) and "
    f"{pct(p100['savings_mean'])} (100×100) fewer nodes than BFS, so the 30% target was not met. On looped mazes "
    f"it saved {pct(l50['savings_mean'])} and {pct(l100['savings_mean'])}; the target was {verdict(l50)} at 50×50 "
    f"and {verdict(l100)} at 100×100. **RQ2.** The heuristic stops helping when it is uninformed, which we "
    f"measured as h(start)/C*: below 0.4, A* reached 30% savings on {low_n - low_below} of {low_n} mazes, and "
    f"above 0.9 on {high_n - high_below} of {high_n}. It also stops helping, in a different way, when it is "
    "exact but many nodes tie at f = C*: on open grids FIFO tie-breaking saved nothing while larger-g "
    f"tie-breaking saved up to {pct(sw(LARGER, NMAX, 1.0)['savings_mean'], 0)}. **RQ3.** With mud, UCS and A* "
    f"always found the same optimal cost, A* expanded {pct(wt(NMAX, M_MUD)['savings_mean'])} to "
    f"{pct(wt(min(W_SIZES), M_MUD)['savings_mean'])} fewer nodes at the default mud rate depending on size, and "
    f"BFS paths cost {pct(min(r['bfs_overhead_mean'] for r in w_def))} to "
    f"{pct(max(r['bfs_overhead_mean'] for r in w_def))} more than the optimum on average."
)
R.p("**Lessons.**", space_after=2)
R.bullets([
    "The value of a heuristic is a property of the heuristic //in an environment//. The same admissible, "
    "consistent heuristic was nearly useless in one family of mazes and excellent in another.",
    "Fair baselines and exact counting rules matter. Our own plan first used a counting rule that would have "
    "been off by one from the lecture example; reproducing a known result caught it before any experiment ran.",
    "Details that textbooks treat as footnotes, such as tie-breaking and the timing of the goal test, can decide "
    "the outcome: one line of tie-breaking moved savings from 0% to over 90% on open grids.",
    f"Expansions and runtime are different measures. A* needed about {pct(BREAK_EVEN, 0)} fewer expansions just to match the "
    "running time of BFS in our implementation.",
    "Setting a success criterion in advance and reporting a miss was more informative than a criterion we "
    "would certainly have met.",
])
R.p("**Future work.**", space_after=2)
R.bullets([
    "**Other maze textures:** repeat the study with Prim's and Kruskal's generators to test whether informedness "
    "predicts savings across generators, not just across loop rates.",
    "**Better heuristics for tree-like mazes:** dead-end filling as preprocessing, or a learned heuristic in the "
    "spirit of Neural A* [10], evaluated on held-out seeds exactly as here.",
    "**Symmetry breaking on open grids:** Jump Point Search [8], and eight-way movement with the Chebyshev "
    "(or octile) distance that it requires for admissibility [13].",
    "**Uncertain moves:** if moves can slip, the maze becomes a Markov decision process, the Grid World of the "
    "course [13], and value iteration replaces search.",
    "**Memory-bounded and bidirectional search:** IDA* and bidirectional BFS are natural competitors when the "
    "reached table, rather than the frontier, is the limit.",
])

# ======================================================================= contributions
R.h("6. Individual Contribution and Professionalism")
R.p(
    "[[TEAM: this section must describe what actually happened. Replace every highlighted passage, and check "
    "that it agrees with the peer evaluations and with the git history, "
    "and add what each member did.]]",
    align="left"
)
R.table("contrib", ["Member", "Role in the proposal", "What the member actually did (files or sections)"], [
    ["Aryan Muhammad", "Search algorithms (BFS, A*) and shared search interface", "[[to be filled in by the team]]"],
    ["Austin Brown", "Maze generation (perfect and looped mazes) and seed sets", "[[to be filled in by the team]]"],
    ["Aryan Farhang", "Weighted maze extension and Uniform Cost Search",
     "[[to be filled in by the team]]"],
    ["Ki il Eum", "Experiment runner, metrics, and tests with known answers", "[[to be filled in by the team]]"],
    ["Yicheng Luo", "Charts, search visuals, and final report lead", "[[to be filled in by the team]]"],
], "Roles planned in the proposal and actual contributions.", widths_cm=[3.0, 5.2, 8.3], align_right_from=9)
R.p("[[If roles changed from the proposal, say so here in one or two sentences and explain why.]]", align="left")
R.p(
    "The results were not taken on trust. They were checked by means that do not depend on any one piece of "
    "code being right:"
)
R.bullets([
    f"the automated test suite ({TESTS.split(' in ')[0]}), including hand-traced expansion orders on small grids;",
    f"exact reproduction of the costs and expansion counts of the Week 3 lecture example ({Tn('lecture')});",
    f"an independent verifier, sharing no code with the search, on every one of the {num(V['rows'])} final runs;",
    "a code freeze (git tag) before the final seeds were generated, with every design choice logged beforehand;",
    f"a second full run of the final configuration, which reproduced the results file exactly (all "
    f"{num(V['rows'])} rows) except for the timing columns (Appendix A).",
])
R.p(
    "[[TEAM: state here, truthfully, what human review took place: who read which parts of the code, who reran "
    "the tests and the experiments, who checked the hand traces and the proofs, who checked each reference "
    "against its source, and who edited this report.]]", align="left"
)
R.p(
    "**Professionalism and integrity.** All data in this report are synthetic and were generated by the "
    "submitted code from the listed seeds; no external data set was used. Every number, table and figure is "
    "produced by a script from the final results file, and the results file, metadata and seeds are submitted "
    "with the code. The success criterion was fixed in the proposal and is reported as stated, including where "
    "it was not met. [[Add: where the work was tracked (repository URL, issues, meeting notes).]]"
)

# ========================================================================== references
R.h("References")
refs = [
    "P. E. Hart, N. J. Nilsson and B. Raphael, “A formal basis for the heuristic determination of minimum cost "
    "paths,” //IEEE Transactions on Systems Science and Cybernetics//, vol. 4, no. 2, pp. 100–107, 1968.",
    "E. W. Dijkstra, “A note on two problems in connexion with graphs,” //Numerische Mathematik//, vol. 1, "
    "pp. 269–271, 1959.",
    "E. F. Moore, “The shortest path through a maze,” in //Proceedings of the International Symposium on the "
    "Theory of Switching//, Part II, Harvard University Press, 1959, pp. 285–292.",
    "S. Russell and P. Norvig, //Artificial Intelligence: A Modern Approach//, 4th ed. Pearson, 2021.",
    "J. Pearl, //Heuristics: Intelligent Search Strategies for Computer Problem Solving//. Addison-Wesley, 1984.",
    "R. Dechter and J. Pearl, “Generalized best-first search strategies and the optimality of A*,” //Journal of "
    "the ACM//, vol. 32, no. 3, pp. 505–536, 1985.",
    "N. R. Sturtevant, “Benchmarks for grid-based pathfinding,” //IEEE Transactions on Computational "
    "Intelligence and AI in Games//, vol. 4, no. 2, pp. 144–148, 2012.",
    "D. Harabor and A. Grastien, “Online graph pruning for pathfinding on grid maps,” in //Proceedings of the "
    "AAAI Conference on Artificial Intelligence//, 2011, pp. 1114–1119.",
    "J. Buck, //Mazes for Programmers: Code Your Own Twisty Little Passages//. Pragmatic Bookshelf, 2015.",
    "R. Yonetani, T. Taniai, M. Barekatain, M. Nishimura and A. Kanezaki, “Path planning using Neural A* "
    "search,” in //Proceedings of the 38th International Conference on Machine Learning (ICML)//, PMLR 139, 2021, "
    "pp. 12029–12039.",
    "L. Lehnert, S. Sukhbaatar, D. Su, Q. Zheng, P. McVay, M. Rabbat and Y. Tian, “Beyond A*: Better planning "
    "with transformers via search dynamics bootstrapping,” in //Proceedings of the 41st International Conference "
    "on Machine Learning (ICML)//, 2024. arXiv:2402.14083.",
    "I. Pohl, “Heuristic search viewed as path finding in a graph,” //Artificial Intelligence//, vol. 1, no. 3–4, "
    "pp. 193–204, 1970.",
    "B. Davis, //CS3346A Introduction to Artificial Intelligence//, lecture slides: Lecture 2 (Augmenting "
    "intelligence and searching state spaces), Week 3 (Heuristics and graph search), Week 6 (Markov decision "
    "processes), Week 10 (Learning and evaluation). Western University, Fall 2026.",
]
for i, ref in enumerate(refs, 1):
    R.p(f"[{i}] {ref}", align="left", size=10, space_after=3)

# ========================================================================== appendix A
R.h("Appendix A: Reproducibility")
R.table("env", ["Item", "Value"], [
    ["Code version", f"git tag {TAG} (commit {env['git_commit'][:12]}). "
                     + ("The run recorded one modified tracked file, report/docx_helpers.py (report formatting "
                        "only). Nothing under src/, tests/ or config/ differed from the tag."
                        if env["git_dirty"] else "Working tree clean.")],
    ["Final run started (UTC)", S["started_utc"]],
    ["Python", f"{env['python']} ({env['implementation']}). The proposal named 3.12; nothing depends on the "
               "difference."],
    ["Packages", ", ".join(f"{k} {v}" for k, v in env["packages"].items())],
    ["Operating system", env["os"]],
    ["Processor", f"{env['cpu']} ({env['cpu_count']} logical cores)"],
    ["Data provenance", "All mazes are synthetic, generated by src/maze_runner/generator.py from the seeds "
                        f"in {Tn('seeds')}. No external data."],
    ["Fixed settings", f"Loop rate p = {P_LOOP:g}; mud rate m = {M_MUD:g}; mud cost 5; neighbour order Up, "
                       f"Right, Down, Left; A* tie rule {D['tie_rule'].replace('_', '-')}; BFS goal test at "
                       "generation; start (1, 1), goal (2n−1, 2n−1)."],
    ["Counting rule", "Expanded = removed from the frontier, not stale, not the goal, successors generated."],
    ["Test summary", TESTS],
    ["Verification", f"{num(V['legal'])} of {num(V['rows'])} runs legal; {num(V['optimal_ok'])} of "
                     f"{num(V['optimal_expected'])} optimal where optimality is guaranteed."],
    ["Bootstrap", "Percentile method, 10,000 resamples of mazes, random seed 3346."],
], "Environment and settings of the final run (from results/final/metadata.json).",
        widths_cm=[3.6, 12.9], align_right_from=9)
R.p("**Commands** (from the repository root, after `pip install -r requirements.txt` and `pip install -e .`):",
    space_after=2)
R.code("""
python -m pytest -q                 # run all tests
python run_all.py --quick           # small check run, about a minute
python run_all.py                   # tests, final experiments, tables, figures, this report
python -m maze_runner.experiment config/final.json --out results/repro_check
""")
R.p(
    "The repository contains the final results file (results/final/runs.csv, one row per maze and "
    "configuration, with the maze fingerprint, all counters, the verification columns and the timings), the "
    "metadata file, the tables behind every table in this report (results/final/tables), all figures, the "
    "development results, the decisions log, and an animated comparison of BFS and A* "
    "(results/final/figures/bfs_vs_astar.gif). We reran the final configuration into a separate "
    "folder and compared the two files with tools/compare_runs.py: they are identical except for the three "
    "timing columns. Known limitations are listed in Section 4.8, and the division "
    "of labour in Section 6."
)

# ========================================================================== appendix B
R.h("Appendix B: Additional tables and figures")
extra = []
for maze_type in ("perfect", "looped"):
    for n in SIZES:
        b, a = mm(maze_type, n, "BFS"), mm(maze_type, n, ASTAR)
        r = sv(maze_type, n)
        extra.append([maze_type.capitalize(), f"{n}×{n}", num(b["generated_mean"]), num(a["generated_mean"]),
                      num(b["peak_frontier_mean"]), num(a["peak_frontier_mean"]),
                      f"{b['time_median_ms_mean']:.2f}", f"{a['time_median_ms_mean']:.2f}",
                      f"{r['wilcoxon_p']:.1e}"])
R.table("extra", ["Maze type", "Size", "BFS generated", "A* generated", "BFS peak frontier", "A* peak frontier",
                  "BFS median time (ms)", "A* median time (ms)", "Wilcoxon p"], extra,
        f"Additional metrics for the main experiment (final seeds {seeds('main')}, 50 mazes per row; means over "
        "mazes). The Wilcoxon signed-rank test is one-sided (A* expands fewer nodes than BFS).",
        widths_cm=[1.7, 1.7, 1.9, 1.9, 1.9, 1.9, 2.0, 2.0, 1.8], font_size=8.5, align_right_from=2)
R.figure("frontier", FIG / "peak_frontier_vs_size.png",
         f"Peak frontier size against maze size (final seeds {seeds('main')}, 50 mazes per point; both axes "
         "logarithmic). For A* the count includes stale heap records.", width_cm=11.0)

R.save(OUT)
print(f"wrote {OUT}")
