"""scorecard.py with this grid's extra in-process arm registered.

`scorecard.py` carries `MLX_ARMS` as a literal tuple, so `chad+mlx-4bit` falls through to
the server-accounting path and prints `–` in every per-turn column: its numbers live in a
prefill trace, and nothing told the scorecard to look for one. Patched here rather than
in the committed file, for the same reason `bench_m532.py` registers its arms at runtime.

    uv run python benchmarks/_local-m5/scorecard_local.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "matrix"))

import scorecard  # noqa: E402

scorecard.MLX_ARMS = ("chad+mlx", "chad+mlx-nodflash", "chad+mlx-4bit")

if __name__ == "__main__":
    runs = os.path.join(HERE, "_runs")
    raise SystemExit(scorecard.main(
        sys.argv[1:] or ["--runs", runs, "--out", os.path.join(runs, "scorecard.md")]))
