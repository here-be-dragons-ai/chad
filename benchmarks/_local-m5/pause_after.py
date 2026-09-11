#!/usr/bin/env python3
"""Stop the grid run once N complete (task, arm) pairs exist.

`run.py` iterates task-major with the arms inside, so pairs land together and a stop
between them costs nothing. This polls `_runs/grid.json` and terminates the run the
moment the target is reached, so a "pause after the 12th pair" does not depend on
anyone watching the clock.

Rows that died by signal are not counted — the same filter `grid_status.py` applies.
An interrupted cell is recorded like a finished one (598.8 s, 13/20, exit_code -15 is
the shape it takes), and counting it would let one kill satisfy the target that a real
measurement was supposed to.

    uv run python benchmarks/_local-m5/pause_after.py --pairs 12
"""

import argparse
import collections
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(HERE, "_runs", "grid.json")
A3, A4 = "chad+mlx", "chad+mlx-4bit"


def pair_count():
    try:
        rows = [r for r in json.load(open(GRID))
                if r.get("arm") in (A3, A4)
                and not ((r.get("exit_code") or 0) < 0 and not r.get("timed_out"))]
    except Exception:  # noqa: BLE001 — mid-write file: try again next tick
        return None
    seq = collections.defaultdict(list)
    for r in rows:
        seq[(r["task"], r["arm"])].append(r)
    by = collections.defaultdict(dict)
    for (task, arm), rs in seq.items():
        for i, r in enumerate(rs):
            by[(task, i)][arm] = r
    return sum(1 for v in by.values() if A3 in v and A4 in v)


def running():
    return subprocess.run(["pgrep", "-f", "bench_m532.py chad"],
                          capture_output=True).returncode == 0


def stop():
    # Two patterns and two passes: the first kill on the uv wrapper trio did not take
    # when this was done by hand, and the chad child outlives its parent.
    for _ in range(3):
        subprocess.run(["pkill", "-f", "bench_m532.py chad"], capture_output=True)
        subprocess.run(["pkill", "-f", "bin/chad Implement"], capture_output=True)
        time.sleep(3)
        if not running():
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=12)
    ap.add_argument("--poll", type=int, default=15)
    a = ap.parse_args()

    start = pair_count()
    print(f"watching for {a.pairs} pairs (now: {start})", flush=True)
    while True:
        if not running():
            print(f"run ended on its own at {pair_count()} pairs", flush=True)
            return
        n = pair_count()
        if n is not None and n >= a.pairs:
            print(f"{n} pairs reached — stopping the run", flush=True)
            print("stopped" if stop() else "STOP FAILED — kill by hand", flush=True)
            return
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
