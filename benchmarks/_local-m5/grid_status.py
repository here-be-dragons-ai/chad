#!/usr/bin/env python3
"""Running verdict on chad3 vs chad4, from whatever rows exist right now.

The grid is expected to be interrupted, so this reads `_runs/grid.json` and reports the
paired comparison over the cells that are actually finished — never waiting for the run
to complete, never guessing at the ones that have not.

Pairing is by OCCURRENCE ORDER within a task, not by the `rep` field. Every run so far
was launched with `--reps 1` and therefore stamped `rep: 0`, and no timestamp or run id
is written per row — so keying on `rep` silently overwrites one run's cell with another's
(it hid the afternoon's `bowling` 265 s behind the evening's 535 s, which is the single
noisiest cell in the set). `run.py` iterates task-major with the arms inside, so within a
run a pair is adjacent in the file and the i-th chad3 row for a task belongs with the
i-th chad4 row. An interruption lands between tasks and leaves whole pairs behind.

READ THE BIAS NOTE. The remaining tasks are run cheapest-pair-first, and cost correlates
with the effect under test: the expensive cells are expensive because chad3 struggled in
them (go-counting 718 s vs 98 s in rep 1). So an interrupted run systematically OMITS
chad4's best evidence. A partial result that still favours chad4 is therefore stronger
than it looks; a partial result that does not is inconclusive rather than negative.

    uv run python benchmarks/_local-m5/grid_status.py
"""

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = os.path.join(HERE, "_runs", "grid.json")
A3, A4 = "chad+mlx", "chad+mlx-4bit"


def _secs(r):
    return r.get("wall_s") or r.get("seconds") or 0.0


def main():
    if not os.path.isfile(GRID):
        sys.exit(f"no grid rows at {GRID}")
    rows = [r for r in json.load(open(GRID)) if r.get("arm") in (A3, A4)]
    seq = collections.defaultdict(list)          # (task, arm) -> rows, in file order
    for r in rows:
        seq[(r["task"], r["arm"])].append(r)
    by = collections.defaultdict(dict)
    for (task, arm), rs in seq.items():
        for i, r in enumerate(rs):
            by[(task, i)][arm] = r

    pairs = {k: v for k, v in by.items() if A3 in v and A4 in v}
    if not pairs:
        sys.exit("no complete (task, rep) pairs yet")

    print(f"\n{'task':<15}{'run':>4}{'chad3 s':>10}{'chad4 s':>10}{'ratio':>8}"
          f"{'chad3 gen':>11}{'chad4 gen':>11}{'winner':>9}")
    print("-" * 78)
    w3 = w4 = 0
    g3 = g4 = 0
    for (task, run) in sorted(pairs):
        p = pairs[(task, run)]
        s3, s4 = _secs(p[A3]), _secs(p[A4])
        n3 = p[A3].get("generated") or p[A3].get("gen") or 0
        n4 = p[A4].get("generated") or p[A4].get("gen") or 0
        g3 += n3
        g4 += n4
        win = "chad4" if s4 < s3 else "chad3"
        w4 += win == "chad4"
        w3 += win == "chad3"
        print(f"{task:<15}{run:>4}{s3:>10.0f}{s4:>10.0f}{s3 / s4 if s4 else 0:>8.2f}"
              f"{n3:>11,}{n4:>11,}{win:>9}")

    n = len(pairs)
    print("-" * 78)
    print(f"{'':<15}{'':>4}{'':>10}{'':>10}{'':>8}{g3:>11,}{g4:>11,}")
    print(f"\n{n} complete pairs — chad4 faster in {w4}, chad3 in {w3}")
    if g4:
        print(f"generated tokens: chad3 {g3:,} vs chad4 {g4:,} "
              f"({g3 / g4:.2f}x)")
        # The roofline break-even, computed rather than asserted: the 4-bit body reads
        # 15 GB/token against 12.07, and decode sits at ~94% of this machine's 290 GB/s,
        # so 4-bit costs 18% per token and has to emit at least that much less to win.
        need = 1 / (1 - 0.18)
        print(f"break-even on token economy is {need:.2f}x "
              f"({'CLEARED' if g3 / g4 >= need else 'NOT cleared'} at {g3 / g4:.2f}x)")

    missing = [t for t in ("book-store", "transpose", "wordy", "dominoes", "go-counting")
               if sum(1 for (tk, _) in pairs if tk == t) < 2]
    if missing:
        print(f"\nstill at n=1 (cheapest first): {', '.join(missing)}")
        print("partial runs omit the expensive cells, which is where chad4 won biggest")
        print("in rep 1 — so a partial result is biased AGAINST chad4, not for it.")


if __name__ == "__main__":
    main()
