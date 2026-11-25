"""One command to reproduce everything.

    python run_all.py            tests, final experiments, tables, figures, report
    python run_all.py --quick    tests and a small check run (about a minute)
    python run_all.py --suite dev

Steps: (1) run the test suite, (2) run the experiment suite, (3) build the
tables and summary numbers, (4) draw every figure, (5) for the final suite,
rebuild the report from those numbers.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def step(title: str, *command: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    t0 = time.perf_counter()
    result = subprocess.run([sys.executable, *command], cwd=ROOT, check=False)
    if result.returncode != 0:
        sys.exit(f"step failed: {title}")
    print(f"--- done in {time.perf_counter() - t0:.0f} s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="small sizes and five seeds only")
    parser.add_argument("--suite", default="final", choices=["final", "dev", "quick"])
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--out", default=None, help="results folder (default results/<suite>)")
    args = parser.parse_args()
    suite = "quick" if args.quick else args.suite
    out = args.out or f"results/{suite}"

    if not args.skip_tests:
        step("tests", "-m", "pytest", "-q")
    step(f"experiments ({suite})", "-m", "maze_runner.experiment", f"config/{suite}.json", "--out", out)
    step("tables and summary", "-m", "maze_runner.analysis", out)
    step("figures", "-m", "maze_runner.visualize", out)
    if suite == "final" and args.out is None:
        step("report", "report/build_report.py")
    print(f"\nAll done. Results are in {out}/")


if __name__ == "__main__":
    main()
