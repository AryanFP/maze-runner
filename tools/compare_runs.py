"""Check that two runs.csv files are identical except for the timing columns.

    python tools/compare_runs.py results/final/runs.csv results/repro_check/runs.csv
"""

from __future__ import annotations

import sys

import pandas as pd

TIMING = ["time_mean_ms", "time_median_ms", "time_min_ms"]


def main() -> int:
    a, b = (pd.read_csv(path).drop(columns=TIMING) for path in sys.argv[1:3])
    if a.shape != b.shape:
        print(f"DIFFERENT: shapes {a.shape} and {b.shape}")
        return 1
    if a.equals(b):
        print(f"IDENTICAL: {len(a)} rows, {a.shape[1]} columns (timing columns excluded)")
        return 0
    different = (a != b) & ~(a.isna() & b.isna())
    print(f"DIFFERENT: {int(different.any(axis=1).sum())} rows differ; columns: "
          f"{list(different.columns[different.any()])}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
