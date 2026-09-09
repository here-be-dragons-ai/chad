#!/usr/bin/env bash
# One night, four columns, on chad 2.0.3.
#
#   chad+llama          chad on llama-server — the same engine every other harness gets
#   goose+llama         the harness column, at goose 1.50.0 (turn context now append-only)
#   chad+mlx            chad's own engine, DFlash2 drafter ON  — the shipping config
#   chad+mlx-nodflash   same engine, drafter OFF — the serial control
#
# The two llama arms share ONE server, one prefix cache, one set of weights. The two MLX
# arms are the pair that isolates speculation in wall clock without changing the
# distribution: they run one invocation PER TASK with a settle window, because loading
# and tearing down ~12 GB of weights in a tight loop has panicked this GPU before.
#
# 2.0.3 carries the two-tier warm-prefix fix, so chad+mlx turn 1 is the first number
# here that is not hiding a cold prefill behind a warm-looking checkpoint.
#
# RUN IT FROM A TERMINAL, not as an agent's background task: the previous night was
# killed by a background-task memory watchdog 19 minutes into its second rep.
#
#   caffeinate -is benchmarks/matrix/night-chad-2.0.3.sh 2>&1 \
#     | tee benchmarks/matrix/_runs/night-chad-2.0.3-$(date +%Y%m%d).log
#
# Budget: 4 arms x 8 tasks, 1200 s cap each = 10.7 h worst case, ~5-6 h typical.
set -u
cd "$(dirname "$0")/../.."

R="${MATRIX_RUNS:-benchmarks/matrix/_runs/chad-2.0.3-$(date +%Y%m%d)}"
export MATRIX_RUNS="$R"
mkdir -p "$R"
TIMEOUT=1200
TASKS="bowling,grade-school,affine-cipher,transpose,wordy,book-store,dominoes,go-counting"
LLAMA="chad+llama,goose+llama"
MLX="chad+mlx chad+mlx-nodflash"
WANT="chad 2.0.3"

echo "=== preflight $(date '+%F %H:%M:%S') ==="
echo "run dir  : $R"
echo "free disk: $(df -g /System/Volumes/Data | tail -1 | awk '{print $4}') GB"
WIRED=$(vm_stat | awk '/wired/{printf "%.1f", $4*16384/1073741824}')
echo "wired    : $WIRED GB"

# The engine wants ~13 GB of a 24 GB box. Anything already holding a third of the
# machine is what the night will lose to at 3am, so it is a refusal, not a warning.
if [ "${SKIP_MEM_CHECK:-0}" != "1" ] && awk "BEGIN{exit !($WIRED > 8)}"; then
  echo "REFUSING: $WIRED GB already wired — close the browser/editors first"
  echo "          (SKIP_MEM_CHECK=1 to override)"
  exit 1
fi

# The version under test is the whole point of this night. `uv run` syncs the editable
# install first, so this is the version a subprocess will actually get, not the tree's.
GOT="$(uv run --quiet chad --version 2>/dev/null | tail -1)"
if [ "$GOT" != "$WANT" ]; then
  echo "REFUSING: chad is '$GOT', wanted '$WANT' — git pull --ff-only on main first"
  exit 1
fi
echo "chad     : $GOT"
echo "goose    : $(goose --version 2>/dev/null | tail -1)"

# The accumulators (grid rows, sampler audit, turn records) all append by design, so a
# previous run's files would silently fold into this one.
for f in grid.json smoke.json sampler_audit.jsonl turns.jsonl smoke_verdict.json; do
  if [ -e "$R/$f" ]; then
    echo "REFUSING: $R/$f exists — move it aside first."
    exit 1
  fi
done
if [ -d "$R/traces" ] && [ -n "$(ls -A "$R/traces" 2>/dev/null)" ]; then
  echo "REFUSING: $R/traces/ is not empty — move it aside with grid.json."
  exit 1
fi
rm -f "$R/sampler_audit_summary.json"
# Warn, never kill: force-sweeping a resident engine is how this box panicked before.
for port in 8080 8081; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "REFUSING: port $port is already bound:"
    lsof -nP -iTCP:$port -sTCP:LISTEN
    exit 1
  fi
done
if pgrep -fl "llama-server|mlx_lm" | grep -v night-chad; then
  echo "WARNING: something may already hold the GPU (above). Stop it by hand and rerun."
  exit 1
fi

step() {
  echo
  echo "=== $1 :: $(date '+%H:%M:%S') ==="
  shift
  local t0=$SECONDS
  if "$@"; then echo "--- ok in $(( (SECONDS-t0)/60 )) min"
  else echo "--- FAILED after $(( (SECONDS-t0)/60 )) min — continuing"; fi
}

wait_server_down() {
  for _ in $(seq 30); do pgrep -f llama-server >/dev/null || break; sleep 2; done
  if pgrep -f llama-server >/dev/null; then
    echo "=== llama-server did not exit; stopping here. ==="
    exit 1
  fi
}

step "setup" uv run python benchmarks/matrix/run.py setup --arms "$LLAMA"

# Smoke is llama-side only — the MLX arms need no config written and are never gated by
# it. An arm that cannot reach the server or whose turns cannot be measured is dropped
# HERE with its reason, instead of spending an hour of the night and reporting a loss.
step "smoke (one task per llama arm)" \
  uv run python benchmarks/matrix/run.py smoke --arms "$LLAMA" --timeout 600 --keep
wait_server_down
echo "--- smoke verdict:"
uv run python -c 'import json, os; v=json.load(open(os.path.join(os.environ["MATRIX_RUNS"], "smoke_verdict.json"))); [print("  %-20s %s %s" % (k, "OK  " if x["ok"] else "DROP", x.get("why", ""))) for k, x in v.items()]'

step "llama arms (8 tasks x the arms smoke cleared, one server)" \
  uv run python benchmarks/matrix/run.py llama --from-smoke \
    --arms "$LLAMA" --tasks "$TASKS" --timeout "$TIMEOUT" --keep
wait_server_down

for arm in $MLX; do
  for t in ${TASKS//,/ }; do
    step "$arm :: $t" uv run python benchmarks/matrix/run.py mlx \
      --arms "$arm" --tasks "$t" --timeout "$TIMEOUT" --keep
    sleep 45        # settle between model load/teardown cycles
  done
done

echo
echo "=== tables :: $(date '+%H:%M:%S') ==="
uv run python benchmarks/matrix/run.py table --tasks "$TASKS" 2>&1 | tee "$R/tables.md"
# Explicitly this night: scorecard.py defaults to _runs/, which would pool the three
# committed 2.0.2 nights into a 2.0.3 measurement.
uv run python benchmarks/matrix/scorecard.py --runs "$R" --out "$R/scorecard.md" 2>&1 | tail -3
echo "=== done $(date '+%F %H:%M:%S') ==="
