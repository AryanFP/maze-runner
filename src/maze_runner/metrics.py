"""Timing protocol and environment records."""

from __future__ import annotations

import os
import platform
import statistics
import subprocess
import sys
from importlib import metadata as importlib_metadata

from .problem import GridProblem
from .search import search


def time_search(problem: GridProblem, repeats: int, warmup: int = 1, **search_kwargs) -> dict:
    """Wall-clock time of the search call only, with trace recording off.

    `warmup` untimed runs are followed by `repeats` timed runs. The mean is
    the value promised in the proposal; the median and minimum are kept
    because they are less sensitive to other activity on the machine.
    """
    search_kwargs["record_trace"] = False
    for _ in range(warmup):
        search(problem, **search_kwargs)
    times = [search(problem, **search_kwargs).time_s * 1000.0 for _ in range(repeats)]
    return {
        "time_mean_ms": statistics.fmean(times),
        "time_median_ms": statistics.median(times),
        "time_min_ms": min(times),
        "time_runs": repeats,
    }


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=20, check=False
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def environment_info() -> dict:
    """Everything needed to say where and with what the numbers were produced."""
    packages = {}
    for name in ("numpy", "pandas", "matplotlib", "scipy", "pytest", "pillow", "python-docx"):
        try:
            packages[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            packages[name] = "not installed"
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "cpu_count": os.cpu_count(),
        "packages": packages,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_describe": _git("describe", "--tags", "--always", "--dirty"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
    }
