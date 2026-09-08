# `benchmarks/matrix/` — nine coding harnesses vs. one laptop

Same weights, same MacBook, same eight tasks, same sampler: what does each coding agent
make a local model *read*, and what does that cost the person waiting? This directory is
the whole instrument — the runner, the forcing proxy, the scorecard, the tasks — and the
three nights it produced (`_runs/rep1-20260901/`, `rep2-20260906/`, `rep3-20260907/`), so
every number in the write-up can be traced to a row.

The question it answers is not "which harness passes more tasks" (the model is the same
in every arm, so that is mostly the weights talking) but **what the harness costs on a
local engine**: how many tokens it prepends to the first turn, how many the server's
prefix cache cannot serve on every later turn, and how many seconds each of those is.

## The runs that are committed

Qwen3.8-27B `UD-Q3_K_XL` on an M4 Pro with 24 GB, one `llama-server` shared by every
harness, 8 Exercism tasks, 1,200 s cap, every harness in its own auto-approve mode.

The same 88-cell grid was measured three times, on 2026-09-01, 09-06 and 09-07: 88 of 88
cells ran every night, 18.0 h + 16.2 h + 17.1 h of cell wall clock (51.3 h, 1,423
generation requests). Each night is a directory under `_runs/`; the scorecard pools them
as reps 0–2 of every cell, so each number below is a median over 24 cells per arm and the
`pass` column counts out of 24. The first night predates the warm-prefix instrument
("got wrong" item 4), which is the one column where it is not interchangeable with the
other two. What repetition changed, and what it did not, is item 6 — and it is the most
useful thing in this file. From `_runs/scorecard.md`:

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| pi+llama            | 2,008                    | 21.6 s                        | 64                              | 1.3 s · 22 s                  | 99%         | 45                     | 8.1        | 19/24 T7    |
| opencode+llama      | 18,046                   | 225.7 s                       | 305                             | 4.6 s · 44 s                  | 99%         | 383                    | 5.7        | 15/24 T13   |
| chad+llama          | 2,562                    | 27.2 s                        | 54                              | 1.1 s · 20 s                  | 99%         | 52                     | 6.9        | 22/24 T2    |
| dsh+llama           | 8,052                    | 94.4 s                        | 110                             | 2.2 s · 34 s                  | 99%         | 133                    | 7.2        | 18/24       |
| goose+llama         | 9,576                    | 112.7 s                       | 2,537                           | 33.2 s · 78 s                 | 78%         | 300                    | 5.0        | 13/24 T5    |
| mini+llama          | 1,171                    | 12.2 s                        | 248                             | 3.6 s · 21 s                  | 96%         | 46                     | 8.0        | 11/24 T14   |
| crush+llama         | 16,263                   | 199.8 s                       | 87                              | 1.8 s · 40 s                  | 100%        | 306                    | 5.8        | 18/24 T8    |
| cline+llama         | 5,876                    | 64.1 s                        | 789                             | 9.9 s · 52 s                  | 94%         | 137                    | 7.3        | 17/24       |
| codex+llama         | 7,804                    | 87.8 s                        | 690                             | 9.6 s · 28 s                  | 94%         | 118                    | 6.9        | 19/24 T5    |
| chad+mlx *          | 2,562                    | 25.3 s †                      | 44                              | 1.0 s · 21 s                  | 99%         | 51                     | 16.0       | 21/24 T4    |
| chad+mlx-nodflash * | 2,564                    | 25.3 s †                      | 48                              | 1.1 s · 18 s                  | 99%         | 53                     | 12.1       | 20/24 T4    |

- **tax** is the first agent request: system prompt + tool schemas + task, in tokens. It is
  paid at least once, and it is how much of a 32k window is gone before you have typed.
- **wait before 1st token** is llama-server's own `prompt_ms` for that request. Every 1,000
  tokens the cache does not hold is ~11 s on this box (prefill 85–95 tok/s, decode ~10,
  flat across every arm).
- **uncached tok / later turn** and **wait / later turn** are the same two numbers on
  agent turns 2+: the part of each turn the cache could not serve, and the pause between
  a tool result landing and the model starting to think.
- **cache reuse** is `cache_n / (cache_n + prompt_n)` on those turns.
- **prefill s / task** counts every request of the task, side requests included.
- **exp. tok/s** is generated tokens over wall clock. Across three nights an arm's own
  value spreads by 10% at the median and 51% at the worst, so nothing between pi, chad,
  mini, cline and codex here is a finding. The 10–40x gaps in the wait columns are.
- **pass** is a gate, not a ranking, `T` counts timeouts, and even at 24 cells it is the
  least trustworthy column here — 33 of the 88 (arm, task) cells did not give the same
  verdict on all three nights, and three arms moved by 3 of 8 (item 6). Read it as "did
  this harness function", not as a score.
- `*` the two MLX rows are chad on its own in-process engine, self-reported from its
  prefill trace with the same definitions — there is no server to observe. `†` their
  turn-1 wait includes the system-prompt prefix chad prefills *before* its first step
  when its disk checkpoint misses — and on a fresh directory it always misses (item 4
  below). Only the second and third nights' traces record that prefix, so those two rows'
  turn-1 wait and prefill columns are over 16 cells, not 24; the scorecard says so in its
  own footnote rather than averaging instrumented nights with a blind one. The chad+llama
  row is the cold prefill of the same prompt through llama-server; the two should agree,
  and they do.

The second table in `_runs/scorecard.md` has the shape of each harness (tool count,
system-prompt size, prefix churn, side requests fired beside the agent loop and whether
they overlapped an agent turn), `_runs/tables.md` has pass/wall/prefill/generated totals
and the per-task grid, and `_runs/scorecard.json` has every derived number.

### Things the data says that the first draft of this scorecard got wrong

The first scorecard had two broken columns and this file exists partly so the fixes are
on the record:

1. **The proxy's time-to-first-byte is not the wait.** llama-server emits a first streamed
   chunk before a long prefill finishes, so the proxy's stamp sat at ~30 s for every
   request over ~3k tokens; across the three nights it was earlier than the server's own
   `prompt_ms` on 331 of 1,130 requests. The scorecard prints that count and uses `prompt_ms` everywhere.
2. **Side requests polluted the per-turn columns.** opencode, goose and crush fire a
   no-tools title/summary call beside the agent loop, and for opencode and crush it is
   the *first* request of the session. Treating it as turn 1 gave opencode a 657-token
   "first prompt" (real: 18,057) and, worse, made its 18k cold prefill count as a "later
   turn" — which is where an earlier draft's "opencode waits 34 s per turn, 240 s p90"
   came from. With side requests classified out, opencode's later turns are 2.5 s median
   and 99% cached. Its cost is the 238 s of tax, the title call running concurrently
   with it, and the window it leaves behind (exits at 22.5k of 32k). The same fix moves
   crush from "4.6 s · 208 s" to "1.9 s · 41 s". goose is the arm whose cache genuinely
   dies every turn: `cache_n` pins at the system prompt (~9.4k) while the uncached count
   climbs 742 → 1,459 → 5,521 → 8,872 across one task. **Why** was a guess ("history
   re-serialised") until the request bodies were captured and diffed
   (`--capture-bodies` + `body_diff.py`, one goose task after the grid): the system
   message and tools are byte-identical turn to turn, and the first differing message
   is the *first user message*, into which goose injects a `<turn-context>` block with
   `<current-time>` at minute resolution. Every turn that crosses a minute boundary
   rewrites message 1, so the server's prefix match ends at the system prompt; the one
   consecutive pair that stayed inside a minute appended cleanly and `cache_n` grew.
   It is a timestamp in the prompt after all — just not in the part the hashes watch.
3. An earlier note claimed a side request makes the *next* agent turn re-prefill
   thousands of tokens (dsh 2,443 vs 89). Every side request in this run sits beside
   turn 1, and turn 2 is every harness's read of the test file, so that comparison was
   measuring the test-file read. The scorecard now only compares turns 3+, finds no
   sample, and prints nothing. dsh's 8 side requests were abandoned by the client before
   the server answered (counted, not measured).
4. **The in-process rows hid a 24 s cold prefill.** The first scorecard printed a
   1.2 s turn-1 wait for both MLX arms and called it "a system-prompt prefix restored
   from disk". It was not restored. chad's warm start hashes the *whole* system message
   — including the working directory and the workspace file listing — so a fresh
   temp directory can never hit the checkpoint, and every one of the first night's 16
   in-process cells prefilled its ~2.5k-token prefix from cold (`~/.cache/chad/kv/`
   gained 16 240 MB checkpoints that night, one per cell). That prefill happens before step 1,
   where `CHAD_PREFILL_TRACE` never saw it: the 1.2 s was step 1's own 73-token append.
   It was first reconstructed from the night's local logs (cell launch stamp vs. the
   trajectory's first step timestamp, minus the "ready in" model load) at 27.5–28.8 s,
   median 28.1 s. chad now writes a `warm_prefix` row (seq 0: hit/miss, prefix tokens,
   seconds) into the trace itself, the scorecard adds a miss to the turn-1 wait and the
   prefill total and prints what it found in the `†` footnote, and the second and third
   nights ran the whole grid with it. Measured directly, all 32 of their in-process cells
   missed, and the hidden prefill was 24.10–24.55 s — a spread of under half a second
   across 32 cells on two different nights, for a prefix that itself varied 2,483–2,493
   tokens, which is what a fixed number of full prefill chunks on an idle GPU looks like.
   That is 14% under the reconstruction and just below the chad+llama row's cold prefill
   of the same prompt, so the reconstruction was the right size and slightly generous,
   and the conclusion is unchanged: the engine cell had *no* prefill advantage in the
   grid; its whole gain over chad+llama is decode (and the drafter). It is also the most
   reproducible number in this directory that is not simply a prompt — which is what a
   cold prefill of a fixed prefix on an idle machine ought to be. The first night's MLX
   cells stay committed and keep counting toward the pass gate and every column the
   prefix does not enter; they are excluded from the two it does. The checkpoint keying itself is a chad bug of the goose kind — a
   volatile string inside the cached prefix — and is not fixed in the version measured
   here. The obvious rejoinder, "llama-server can checkpoint a slot too", was tried
   once on the same build and model (single slot, `--slot-save-path`, chad's real
   2,438-token system prompt): the save wrote 317 MB in 0.05 s and the restore
   reported 2,438 tokens back in 0.02 s, but the next byte-identical request still
   prefilled all 2,438 tokens (`cache_n` 0, 25.0 s) — the same-process prefix cache
   served it in 0.3 s. One attempt, not pursued; noted so nobody repeats it blind.
5. **The in-process timeouts were not engine hangs.** Eight of the 48 in-process cells
   hit the 1,200 s cap with one step still running, spread over all three nights and
   over six different tasks; only two cells ran away twice (chad+mlx bowling, and
   chad+mlx-nodflash book-store), and neither did it three times. Which task runs away
   is mostly not a property of the task. Re-running one of them with the full
   stdout kept showed the step streaming coherent reasoning at ~16 tok/s the whole time:
   a single `<think>` that outlasts the cap. That is a property of this model at
   temperature 1.0, not of the harness — in the same run pi, opencode, codex and cline
   each produced a single 6,300–7,500-token generation (up to 13 minutes at ~10 tok/s),
   dsh hit its own 8,192-token cap twice,
   and chad+mlx spent 530 s on one 10,567-token step. chad ships with no think ceiling
   (`--think-budget` is off by default), so nothing interrupts it. The runner now keeps
   each in-process cell's stdout beside its trace so a killed cell can be told apart:
   tokens still streaming at the cap is a long generation; a stream that stopped early
   is a hang.
6. **Three nights say which columns are worth reading.** The grid was run again,
   unchanged, on 09-06 and 09-07. No cell ever produced the same row twice. Taking each
   arm's own spread across the three nights — `(max − min) / median` — the table splits
   into three tiers that are nothing like each other:

   | column | spread across 3 nights (median · worst) | what it is |
   |---|---|---|
   | tax, system-prompt chars, tool count | 0.0% · 0.4% | the harness's prompt |
   | wait before 1st token | 6.8% · 10.6% | a cold prefill of that prompt |
   | cache reuse | 4.2% · 16.2% | the harness's prompt discipline |
   | prefill s / task, exp. tok/s | 9–12% · 51–55% | how much the model thought |
   | uncached / later turn, wait / later turn | 61–95% · 790–1277% | how much the model thought |
   | pass | 33 of 88 cells disagreed across the three nights | mostly the model |

   (`uv run python benchmarks/matrix/scorecard.py --convergence` prints this table and
   the one below from the committed nights; llama arms only, since the in-process arms'
   turn-1 wait is not comparable across a night the instrument predates.)

   The top tier is not a measurement that happened to repeat; it is what the harness
   sends, which is the same thing every time it starts. That is why the tax column
   carries the argument of this directory: opencode really does prepend 9x what pi does,
   every night, to within a rounding error. The turn-1 wait is the same prompt going
   through a cold prefill, and it holds to ~10%.

   The bottom tiers are the model at temperature 1.0 deciding how much to think, and they
   are close to unusable per-arm at this many reps. opencode's uncached tokens per later
   turn read 113, 36, 1,479 on the three nights; goose's read 3,009, 1,945, 3,846. The
   *finding* survives all three — goose is the only arm whose cache dies every turn (78%
   pooled reuse against 94–99.6% for everyone else, a gap no night narrows), and
   opencode's later turns were cheap on two of the three — but the *size* of either is
   not a number to quote to one significant figure.

   `pass` deserves its own warning, because it is the column a reader instinctively ranks
   on. The per-night totals are stable — 64, 66, 63 of 88 — so the grid measures how hard
   these tasks are for this model quite reliably. What it does not measure reliably is
   *which* arm passed *which* task: **33 of the 88 cells disagreed across the three
   nights**, and three arms swung by 3 of 8 (opencode 3/6/6, goose 6/3/4, crush 5/8/5).
   An aggregate that is steady while its parts are not is exactly the shape that invites
   a false ranking. Three nights is enough to know the ordering is noise; it is not
   enough to fix one.

   **Why it stops at three.** The same command answers whether a fourth night would earn
   its 17 hours, by asking how much adding the third one moved the *pooled* number
   already published:

   | column | move on adding night 3 (median · worst) |
   |---|---|
   | tax, system-prompt chars, tool count | 0.00% · 0.03% |
   | wait before 1st token | 0.57% · 1.36% |
   | cache reuse | 0.19% · 3.82% |
   | prefill s / task, exp. tok/s | 1.2–2.5% · 15–26% |
   | uncached / later turn, wait / later turn | 13–15% · 105–180% |

   The columns this directory argues from are converged: the third night moved every
   arm's tax by 0.00% and the turn-1 wait by half a percent. Another night cannot make
   "opencode prepends 9x what pi does" more true. The columns that are still moving are
   moving by 15% and would keep moving — a per-arm spread near 100% is not closed by one
   more rep but by dozens, which is a different project. So a fourth night would change
   only the numbers already labelled unquotable, and change them enough to need
   rewriting. The honest limit of this grid is not its rep count: it is one machine, one
   model, eight tasks, and no number of nights on this box touches that.

## Setup, exactly

| | |
|---|---|
| machine | Apple M4 Pro, 24 GB unified memory, macOS 26.6.2, nothing else running |
| weights | `unsloth/Qwen3.8-27B-GGUF` · `Qwen3.8-27B-UD-Q3_K_XL.gguf` (llama arms); chad's MLX conversion of the same recipe (MLX arms) |
| engine | llama.cpp build 10470 (Homebrew), `llama-server -c 32768 -ngl 999 --jinja --metrics`, default 4 slots on a unified KV pool |
| sampler | temp 1.0 · top_k 20 · top_p 0.95 · min_p 0.05 · penalties off — **forced on every request by `sampler_proxy.py`**, audited: one parameter set across all 1,423 requests of the three nights, whose summaries are identical (`repN-*/sampler_audit_summary.json`; `run.py table` refuses to pool nights that sampled differently) |
| tasks | `tasks/` — 8 Exercism Python exercises, stub + tests + instructions, pristine from git |
| prompt | one sentence, identical for every arm (`PROMPT` in `run.py`) |
| cap | 1,200 s per (arm, task); the process *group* is killed at the cap |
| pass | `pytest -q` on the task's own test file after the harness exits |
| reps | 3 — the whole grid three times, 2026-09-01, 09-06 and 09-07 |

Harness versions as run (`repN-*/provenance.json`), and how each is installed. Every arm
ran the same version all three nights except cline, which upgraded itself after the first
(3.0.60, then 3.0.61 twice); its pooled rows are that mixture:

| arm | version | install |
|---|---|---|
| pi | 0.80.3 | `npm i -g @earendil-works/pi-coding-agent` |
| opencode | 1.17.12 | `npm i -g opencode-ai` |
| chad | 2.0.2 | this checkout, `uv sync` |
| dsh (deepseek-harness) | 0.1.1-rc.2 | `npm i -g @deepseek-ai/dsh` |
| goose | 1.39.0 | Block's installer |
| mini-swe-agent | 2.4.6 | `uv tool install mini-swe-agent` |
| crush | 0.92.0 | `npm i -g @charmland/crush` |
| cline | 3.0.60, then 3.0.61 | `npm i -g cline` |
| codex | 0.151.0 | `npm i -g @openai/codex` |

Three more were installed and dropped at smoke, with the reason in
each night's `smoke_verdict.json`: **deepagents-code 0.1.65** and **qwen-code 0.22.3** get
`400 failed to parse grammar` from llama-server (their tool JSON schemas, converted to
GBNF under `--jinja`, exceed the rule cap — they cannot drive llama.cpp tool-calling on
this build); **aider 0.86.2** is an edit-block loop with no tool calls and never returns
a server `timings` object, so the instrument cannot measure it.

## Reproduce it

Budget a night: the llama phase alone took 16 h here. One engine resident at a time — a
24 GB box holds exactly one 27B.

```bash
brew install llama.cpp                 # llama-server on PATH
uv sync                                # chad + its venv (every arm gets this venv's python/pytest)
# install whichever harnesses you want as arms (table above); a missing binary is
# skipped by name in provenance, never a crash
# one directory per night; name it repN-YYYYMMDD to have the scorecard pool it with
# the committed nights, anything else to keep it separate
export MATRIX_RUNS=benchmarks/matrix/_runs/rep3-$(date +%Y%m%d)

uv run python benchmarks/matrix/run.py setup            # write each harness's provider config
                                                        # (your originals kept as *.pre-matrix.bak)
uv run python benchmarks/matrix/run.py smoke            # one short task per llama arm -> smoke_verdict.json
uv run python benchmarks/matrix/run.py llama --from-smoke   # 8 tasks x the arms smoke cleared, ONE server
uv run python benchmarks/matrix/run.py mlx              # chad in-process; llama-server must be down
uv run python benchmarks/matrix/run.py table --runs $MATRIX_RUNS   # pass / wall / prefill / generated
uv run python benchmarks/matrix/scorecard.py --runs $MATRIX_RUNS  # the felt table + JSON
```

Both reporting commands take several nights and pool them, one rep each, and a bare
`_runs` means every `repN-*` night in it — which is how the committed tables are made:

```bash
uv run python benchmarks/matrix/run.py table > benchmarks/matrix/_runs/tables.md
uv run python benchmarks/matrix/scorecard.py            # -> _runs/scorecard.md + .json
uv run python benchmarks/matrix/scorecard.py --convergence   # is another night worth a night?
```

`overnight.sh` is the unattended version of the same sequence (smoke → llama → MLX one
task at a time with a settle window, because load/teardown cycling a 12 GB model has
panicked a GPU here) and refuses to start if a previous run's accumulators are present or
a port is already bound. Run it under `caffeinate -is`.

The GGUF is fetched into the shared Hugging Face cache on first use; `STOCK_GGUF=<path>`
points at one you already have. Setting `MATRIX_MINI_YAML` overrides where
mini-swe-agent's bundled config is looked up (it is otherwise resolved through the
`mini` executable's own interpreter).

### What is and is not committed

Each measured night is one directory, `_runs/repN-YYYYMMDD/`, and committed inside it
are: `grid.json` (one row per cell), `turns.jsonl` (one row per generation request, from
the proxy), `sampler_audit.jsonl` and its summary, `smoke.json` + `smoke_verdict.json`,
`provenance.json`, `traces/*/prefill_trace.jsonl` (the MLX arms' in-process equivalent of
a turn record), and that night's own rendered `scorecard.md` / `.json` / `tables.md`.
`_runs/` itself holds only the pooled `scorecard.md` / `.json` / `tables.md` over every
night. `tests/test_matrix_bench.py` regenerates the two pooled markdown files from the
rows and fails if they differ, checks that each night is a complete 88-cell
sampler-verified grid, and checks that the nights pool as distinct reps rather than
overwriting one another — so the tables cannot drift from the data by hand, and a night
cannot go missing quietly.

Not committed: server and proxy logs, the MLX arms' full trajectories and stdout (model
output), kept workdirs, captured request bodies, generated provider configs, and scratch
runs (anything under `_runs/` that is not a `repN-*` night).
Nothing under this directory names the machine it ran on — paths are stored relative to
the repo, harness output is redacted of the home and temp directories and the hostname,
and the same test scans every tracked file for those.

The `harness` digests in `provenance.json` are of the scripts *as they ran*. The
committed scripts differ from them in three ways, none of which touches what the proxy
forces on or records for a request: the task corpus is vendored here instead of read
from a private checkout, paths and harness output are sanitised before being written,
and `scorecard.py` derives the columns as described above.

## Adding an arm, and diagnosing a cache miss

An arm is one entry in `ARMS` in `run.py` (its documented headless argv), plus, where
needed, one in `ARM_ENV` and one in `ARM_SETUP` (the provider-config writer). The
runner hands every arm the same three files, the same prompt and the same timeout, and
the proxy measures it without its cooperation.

The proxy records the *shape* of each request (system-message and tool-list hashes,
sizes, `cache_n`/`prompt_n`), which names a cache miss caused by a changed system prompt
or tool list but not one caused by the conversation body being re-serialised. For that,
capture the bodies and diff consecutive turns:

```bash
uv run python benchmarks/matrix/run.py smoke --arms goose+llama --capture-bodies
uv run python benchmarks/matrix/body_diff.py --all $MATRIX_RUNS/bodies/goose+llama/grade-school--1/
```

`body_diff.py` reports, per consecutive pair, whether the system message and tools are
byte-identical, the first message index at which the two requests differ, and how many
characters of the rendered conversation they share. That is how goose's per-turn cache
miss was pinned to a minute-resolution timestamp in its first user message (above).

## Caveats, all of them

- n=3 reps, 8 tasks, one machine. What that buys is in "got wrong" item 6: the prompt
  columns repeat to within 0.4%, the per-turn columns spread by 61–95% at the median,
  and 33 of 88 cells did not give the same verdict on all three nights. Read the tax and
  the 10–40x wait gaps; do not read the ordering of the pass column.
- Three nights on the same box are three samples of one machine, not of the population of
  machines. Nothing here says what this grid would look like on another laptop, and the
  per-arm ordering is not stable enough to be worth carrying to one.
- The two MLX rows are self-reported and in-process. Their turn-1 wait includes the
  prefix prefill chad does before its first step (a disk-checkpoint miss on every fresh
  directory — see "got wrong" item 4); it is a cold number, like the chad+llama row.
  Only the second and third nights recorded that prefix, so those two rows' turn-1 wait
  and prefill columns rest on 16 cells rather than 24.
- The server ran 4 slots on a unified KV pool. The side-request findings are for that
  configuration; a single-slot server would queue them instead, which is a different
  failure, not the absence of one.
- mini-swe-agent does not stream (`stream: false` on every request): whatever the prefill
  number says, the user sees nothing until a turn is done.
- chad+llama drives llama.cpp's raw `/completion` endpoint with token ids, so its
  system/tool hashes are blank in `turns.jsonl`; its 99% reuse and 46 uncached tokens per
  turn are the evidence, and a sceptic cannot diff its prompts from the proxy log.
- `?` on a total in `tables.md` means the server was still busy when that arm's counters
  were read; the number is a floor.
- The GGUF and the MLX checkpoint are the same quantisation recipe, not the same bytes.
- Every harness ran in the auto-approve mode its authors ship. Their prompt and tool
  choices were made for hosted models where prefill is close to free; none of this is a
  bug report against any of them.

Thanks to the llama.cpp maintainers for a server-side prefix cache and a `timings`
object good enough to build the whole instrument on.
