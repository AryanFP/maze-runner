"""Write the experiment configs. The frozen design choices live here, in one place.

    python tools/make_configs.py

The three suites run the same four experiments and differ only in seeds and
sizes, so development (seeds 0 to 99) can never leak into the final test
seeds (10000 and up).
"""

from __future__ import annotations

import json
from pathlib import Path

# ---- choices frozen on development seeds (see DECISIONS.md) -------------------
DEFAULT_LOOP_RATE = 0.10  # fraction of remaining internal walls opened in "looped" mazes
DEFAULT_MUD_RATE = 0.20  # fraction of open squares that are mud in "weighted" mazes
DEFAULT_TIE_RULE = "larger_g"  # A* tie rule for the headline numbers
# ------------------------------------------------------------------------------

SWEEP_LOOP_RATES = [0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.0]
SWEEP_MUD_RATES = [0.0, 0.10, 0.20, 0.40]

BFS = {"algorithm": "bfs", "goal_test": "generation"}
ASTAR = {"algorithm": "astar", "heuristic": "manhattan", "tie_rule": DEFAULT_TIE_RULE}


def experiments(seeds: dict, main_sizes: list[int], other_sizes: list[int]) -> list[dict]:
    return [
        {
            "name": "main",
            "maze_types": ["perfect", "looped"],
            "sizes": main_sizes,
            "seeds": seeds["main"],
            "loop_rates": [DEFAULT_LOOP_RATE],
            "timing_repeats": 5,
            "runs": [BFS, ASTAR],
        },
        {
            "name": "sweep",
            "maze_types": ["looped"],
            "sizes": other_sizes,
            "seeds": seeds["sweep"],
            "loop_rates": SWEEP_LOOP_RATES,
            "timing_repeats": 1,
            "runs": [
                BFS,
                {"algorithm": "astar", "heuristic": "manhattan", "tie_rule": "fifo"},
                {"algorithm": "astar", "heuristic": "manhattan", "tie_rule": "larger_g"},
            ],
        },
        {
            "name": "weighted",
            "maze_types": ["weighted"],
            "sizes": other_sizes,
            "seeds": seeds["weighted"],
            "loop_rates": [DEFAULT_LOOP_RATE],
            "mud_rates": SWEEP_MUD_RATES,
            "timing_repeats": 5,
            "runs": [BFS, {"algorithm": "ucs"}, ASTAR],
        },
        {
            "name": "ablation",
            "maze_types": ["perfect", "looped"],
            "sizes": other_sizes,
            "seeds": seeds["ablation"],
            "loop_rates": [DEFAULT_LOOP_RATE],
            "timing_repeats": 1,
            "runs": [
                BFS,
                {"algorithm": "bfs", "goal_test": "pop"},
                {"algorithm": "astar", "heuristic": "manhattan", "tie_rule": "fifo"},
                {"algorithm": "astar", "heuristic": "manhattan", "tie_rule": "larger_g"},
                {"algorithm": "astar", "heuristic": "zero", "tie_rule": "fifo"},
                {"algorithm": "greedy", "heuristic": "manhattan"},
                {"algorithm": "astar", "heuristic": "manhattan", "weight": 1.5, "tie_rule": DEFAULT_TIE_RULE},
                {"algorithm": "astar", "heuristic": "manhattan", "weight": 2.0, "tie_rule": DEFAULT_TIE_RULE},
                {"algorithm": "astar", "heuristic": "manhattan", "weight": 3.0, "tie_rule": DEFAULT_TIE_RULE},
            ],
        },
    ]


SUITES = {
    # Development: used to debug, to choose the defaults above and to design the charts.
    "dev": {
        "seeds": {name: {"start": 0, "count": 50} for name in ("main", "sweep", "weighted", "ablation")},
        "main_sizes": [10, 25, 50, 100],
        "other_sizes": [25, 50, 100],
    },
    # Final test: run once, after the code freeze.
    "final": {
        "seeds": {
            "main": {"start": 10000, "count": 50},
            "sweep": {"start": 20000, "count": 50},
            "weighted": {"start": 21000, "count": 50},
            "ablation": {"start": 22000, "count": 50},
        },
        "main_sizes": [10, 25, 50, 100],
        "other_sizes": [25, 50, 100],
    },
    # Quick check: small sizes, a few development seeds, about a minute.
    "quick": {
        "seeds": {name: {"start": 90, "count": 5} for name in ("main", "sweep", "weighted", "ablation")},
        "main_sizes": [10, 25],
        "other_sizes": [10, 25],
    },
}


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "config"
    out.mkdir(exist_ok=True)
    for suite, spec in SUITES.items():
        config = {
            "suite": suite,
            "defaults": {
                "loop_rate": DEFAULT_LOOP_RATE,
                "mud_rate": DEFAULT_MUD_RATE,
                "tie_rule": DEFAULT_TIE_RULE,
                "neighbor_order": ["Up", "Right", "Down", "Left"],
            },
            "experiments": experiments(spec["seeds"], spec["main_sizes"], spec["other_sizes"]),
        }
        (out / f"{suite}.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"wrote config/{suite}.json")


if __name__ == "__main__":
    main()
