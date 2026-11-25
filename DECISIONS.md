# Decisions log

Every design choice that could change a number, written down before the final
test seeds were run. All evidence quoted here comes from the development
seeds (0 to 49, `results/dev/`). The final test seeds (10000 and up) were not
generated or looked at until after the code freeze tag `v1.0-final-run`.

Date of all entries: 2026-11-24.

## D1. Maze representation
An n×n maze is stored as a (2n+1)×(2n+1) occupancy grid; search runs on the
squares of that grid. A "50×50 maze" is a 101×101 grid. Path lengths are in
grid steps. Start is the top-left cell (1, 1), goal is the bottom-right cell
(2n−1, 2n−1).

## D2. Neighbour order
Up, Right, Down, Left, for every algorithm.

## D3. Counting rule (differs from the wording in PLAN.md, on purpose)
A node is expanded when it is removed from the frontier, passes the stale
check, **is not the goal**, and its successors are generated. The goal is
never counted.

PLAN.md suggested counting the goal when it is popped. The Week 3 lecture
example (slide 19) only reproduces under the rule above: UCS gives 26 and A*
with FIFO ties gives 25; counting the goal would give 27 and 26. The lecture
is the reference, so its convention wins. The rule is also the only one that
treats BFS with a goal test at generation (goal never removed) and the heap
algorithms (goal removed) the same way.

## D4. BFS baseline
Headline numbers use BFS with the goal test at generation, its strongest
fair version for unit costs. The goal-test-at-removal version is run only in
the ablation. On dev seeds the difference is tiny (about 2 to 7 expansions
per maze), so the choice does not drive any conclusion.

## D5. Loop rate for "looped" mazes: p = 0.10
Dev sweep, 50×50, mean informedness h(start)/C*: 0.15 at p = 0, 0.37 at
0.02, 0.55 at 0.05, 0.73 at 0.10, 0.90 at 0.20, 0.99 at 0.35. p = 0.10 sits
in the middle of the range: clearly different from a perfect maze, still a
maze with real detours (the shortest path is about 1.4 times the straight
line distance), and not yet in the regime where the heuristic is almost
exact. The whole range is reported anyway in the sweep.

## D6. Mud rate for "weighted" mazes: m = 0.20, mud cost 5
Dev weighted runs: at m = 0.20 the BFS path is more expensive than the
optimum on 40/50 (25×25), 49/50 (50×50) and 49/50 (100×100) mazes, with the
largest mean extra cost of the three rates tried (4.8%, 5.9%, 6.2%). Mud is
placed uniformly at random on open squares, never on start or goal.
Weighted mazes are always built on looped mazes (PLAN R1): a perfect maze
has one route, so costs cannot change which path is best.

## D7. A* tie rule for headline numbers: prefer larger g
Heap order is (f, −g, insertion counter). On dev seeds larger-g ties were
never worse on average than FIFO ties at any size or loop rate, and never
lost to BFS on any maze, while FIFO ties lost to BFS on all 150 mazes at
p = 1.0. FIFO is still run everywhere in the sweep and the ablation, because
the gap between the two rules is itself a result.

## D8. Seeds
| Set | Seeds | Use |
|---|---|---|
| Development | 0 to 49 (experiments), 0 to 99 (tests, quick check) | debugging, choices D5 to D7, chart design |
| Final main | 10000 to 10049 | headline results |
| Final sweep | 20000 to 20049 | loop rate sweep |
| Final weighted | 21000 to 21049 | weighted extension |
| Final ablation | 22000 to 22049 | ablations |

For one seed the looped maze is the perfect maze plus opened walls, and a
higher loop rate (or mud rate) contains everything a lower one has. This
pairing removes maze-to-maze noise from comparisons across p and m.

## D9. Timing
One untimed warm-up run, then five timed runs with trace recording off, for
the main and weighted experiments (mean, median and minimum stored). The
sweep and the ablation are timed once without warm-up; their times are not
used for any claim. The whole search call is timed, including building the
heuristic table.

## D10. Statistics
Paired per-maze expansion savings 1 − A*/BFS. Mean with a 95% percentile
bootstrap interval (10,000 resamples of mazes, fixed seed 3346), plus a
one-sided Wilcoxon signed-rank test and win/tie/loss counts. The success
criterion is "mean per-maze savings ≥ 30%"; the ratio of mean expansions is
reported next to it.

## D11. Example figures are chosen by rule
Typical maze: the 25×25 perfect maze of the main experiment whose savings is
closest to the median. Failure case: the 25×25 maze with the lowest savings.
Weighted example: the 25×25, m = 0.20 maze with the largest BFS extra cost.

## D12. Python version
The proposal named Python 3.12. The machine used has Python 3.13.6; nothing
in the code depends on the difference. Recorded in the metadata.
