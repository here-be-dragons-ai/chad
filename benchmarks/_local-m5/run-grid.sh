#!/bin/bash
# chad3 / chad4 / pi+m532 / pi+m532-lean — one pass of the 8-task grid.
#
# Two phases, because 48 GB does not hold both engines at once: the mlx-vlm server is
# ~16 GiB resident plus its APC snapshots, and chad's in-process engine is another ~15.
# Phase 1 runs the pi arms with the server up; phase 2 stops it and runs the in-process
# arms. `bench_m532.py chad` refuses to start while the server answers, so the ordering
# is enforced by the runner, not by this file remembering to do it.
#
# Usage:  benchmarks/_local-m5/run-grid.sh [reps]
set -uo pipefail

REPS="${1:-1}"
CHAD="$HOME/src/chad"
M532="$HOME/src/m532"
OUT="$CHAD/benchmarks/_local-m5/_runs"
LOG="$OUT/grid-$(date +%Y%m%d-%H%M).log"
mkdir -p "$OUT"

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

server_up() { curl -sS -m 5 -o /dev/null http://127.0.0.1:8888/health 2>/dev/null; }

stop_server() {
    pkill -f "mlx_vlm.server" 2>/dev/null
    for _ in $(seq 1 30); do server_up || return 0; sleep 2; done
    say "WARNING: server still answering after 60 s"
    return 1
}

say "=== phase 1/2: pi arms (m532 server up), reps=$REPS ==="
if ! server_up; then
    say "starting m532 server"
    ( cd "$M532" && nohup ./start-mlx_qwen3.8.sh > "$OUT/m532-server.log" 2>&1 & )
    for _ in $(seq 1 90); do server_up && break; sleep 5; done
fi
if ! server_up; then say "FATAL: m532 server never came up — see $OUT/m532-server.log"; exit 1; fi
say "server up: $(curl -sS -m 5 http://127.0.0.1:8888/health | python3 -c 'import json,sys; print(json.load(sys.stdin)["loaded_model"])')"

cd "$CHAD"
uv run python benchmarks/_local-m5/bench_m532.py pi \
    --arms pi+m532,pi+m532-lean --reps "$REPS" 2>&1 | tee -a "$LOG"

say "=== phase 2/2: chad arms (server down) ==="
stop_server
say "server stopped; letting the GPU settle"
sleep 15

uv run python benchmarks/_local-m5/bench_m532.py chad \
    --arms chad+mlx,chad+mlx-4bit --reps "$REPS" 2>&1 | tee -a "$LOG"

say "=== table ==="
uv run python benchmarks/_local-m5/bench_m532.py table 2>&1 | tee -a "$LOG"
say "done — rows in $OUT/grid.json, turns in $OUT/turns.jsonl, log $LOG"
