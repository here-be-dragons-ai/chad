# Drafts: what goes upstream, and what stays here

Routing rule from `CONTRIBUTING.md`: bug fixes with a repro land easily; anything
model-visible (engine, compaction, prompts) needs an issue first and a pass on the
maintainer's private eval rig, which we cannot run. So facts go up as issues now;
proposals go up as issues and stay unbuilt until he says yes; the 48 GB tier ships as
HF artifacts under our org and never touches his tree.

| # | Finding | Type | Route |
|---|---|---|---|
| A | `chad-bench` ignores `CHAD_KV_BITS` | bug + repro | **filed: [#44](https://github.com/nathansutton/chad/issues/44), PR [#46](https://github.com/nathansutton/chad/pull/46)** |
| B | 12 speculative bit-exactness tests fail on M5 Pro | bug report | **filed: [#45](https://github.com/nathansutton/chad/issues/45)** |
| C | `BLOCK_ROUND_COSTS` is an M4 constant on a per-chip ladder | behavior | holding for the 3-rep grid |
| D | `_resolve_kv_bits` is a shape gate, not a speed gate | behavior | withdrawn — default wins |
| E | bigger prefill chunks fill the M5's matmul units | behavior | withdrawn — flat |
| — | 5/6-bit body + 8-bit drafter for 48 GB | artifact | our HF org, no PR |

---

## A. `chad-bench` silently ignores `CHAD_KV_BITS`, so the KV-width A/B reports a null

**Title:** `chad-bench` ignores `CHAD_KV_BITS` — every run measures the auto width

`cli.main` reads `CHAD_KV_BITS` (`cli.py:787`) and passes it to the Engine
(`cli.py:824`). Both benchmarks in `bench.py` construct the Engine directly
(`bench.py:100`, `bench.py:206`) with `kv_bits` left at its dataclass default, so they
always measure the AUTO width whatever the env says. A `CHAD_KV_BITS=0` arm against the
shipped 8-bit default therefore comes back as a clean null rather than as an error.

Repro on any machine where the fused kernel covers the shape:

```
$ CHAD_SESSION_LOG=1 CHAD_KV_BITS=0 uv run chad-bench
$ grep 'KV cache:' ~/.chad/session.log | tail -1
KV cache: quantized 8-bit group-64 by default (...); CHAD_KV_BITS=0 restores fp16
```

The log line says 8-bit while the env asked for fp16. (The line is also why this hides so
well: the explicit-`0` branch of `_resolve_kv_bits` logs nothing at all, so the *absence*
of a contradicting line reads like success.)

This is the failure shape `cli.SAMPLER_ENV` already documents — sibling settings drift one
at a time, and `chad serve` forgetting all three sampler knobs is the same bug in a
different file. Suggested fix is one constructor both benchmarks share, plus a config echo
line in the report so the arm can be read back off the output:

```
config                   kv cache 8-bit group-64 (34,816 B/tok) | prefill chunk adaptive (base 512)
```

Measured kv bytes/token is the number that cannot lie about which cache actually got
built: 34,816 at 8-bit group-64, 65,536 at fp16. Happy to send the PR — it touches only
`bench.py` and changes no model-visible behavior.

---

## B. 12 speculative-decoding bit-exactness tests fail on an M5 Pro (`applegpu_g17s`)

**Title:** Unit gate red on M5 Pro: 12 dflash/PLD bit-exactness tests fail (green on macos-14 CI)

On an Apple M5 Pro / 48 GB, macOS 26.x, mlx 0.32.0 (the pinned version), `uv run pytest -q`
on unmodified `main` @ 93dd02e fails 12 tests, all of them the speculative-path
bit-exactness assertions:

```
tests/test_engine_dflash.py::test_random_drafter_greedy_is_bit_exact
tests/test_engine_dflash.py::test_no_sliding_window_drafter_is_bit_exact
tests/test_engine_dflash.py::test_oracle_drafter_full_accept_saves_forwards
tests/test_engine_dflash.py::test_second_turn_extends_cleanly
tests/test_engine_pld_hybrid.py  (3 tests)
tests/test_engine_pld_wide.py    (5 tests)
```

Failure shape is a diverged token, not a tolerance miss:

```
assert _ids(text) == ref
At index 13 diff: 1 != 226
```

What we checked:

- **Deterministic.** Same failure set across 3 consecutive runs (the tests seed via
  `mx.random.seed`), so it is not flaky.
- **Not chad's Metal kernels.** Still fails with `CHAD_NO_FASTPATH=1 CHAD_NO_QMM_MMA=1
  CHAD_NO_QSDPA=1`. That leaves stock MLX numerics on this GPU family as the candidate:
  the batched S>1 verify forward and the S=1 decode step disagree by enough to flip an
  argmax on these tiny random-weight models.
- **Chip-specific.** CI (`macos-14`, M1) is green on the same commit and the same pin.
  `mx.device_info()` here reports `architecture: applegpu_g17s`.

Not claiming the shipped 27B diverges in practice — these targets are tiny and
random-weighted, so ties are everywhere and one ulp decides them. But the suite is the
guarantee that exact rejection sampling is actually exact, and on this chip family the
guarantee is currently unverified rather than verified. Happy to run any probe against
g17s that would help narrow it — we have the hardware and no eval rig, which is the
opposite of your problem.

---

## C. The width schedule's cost ladder is an M4 constant, on a quantity that is per-chip

**Title:** `BLOCK_ROUND_COSTS` is measured on one chip; the MMA probe next to it is not

`mlx_dflash.BLOCK_ROUND_COSTS` seeds `WidthPolicy` with `(1.0, 1.76, 1.93, 2.30, 2.18,
2.20, 2.19, 2.20)` — measured on an M4 Pro, where widths 2..4 pay the stock
`quantized_matmul` ladder and 5..8 are flat under `mlx_qmm_mma`. `observe_cost()`
re-anchors the scale online, but the docstring is explicit that the SHAPE is what has to
be right, and the shape is exactly what changes with the chip.

Evidence that it already has changed: `mlx_qmm_mma.calibrate()` — which *is* per-chip —
lands differently here. On this M5 Pro
(`~/.cache/chad/qmm_mma/Apple_M5_Pro-mlx0.32.0-k4.json`) the kernel wins only from **M=6**
on nearly every shape, where the module docstring records it winning from M=5 on the M4
Pro (1.2–1.4x there). So stock `quantized_matmul` at small M improved relative to the
kernel on this chip, the crossover moved, and the ladder the argmax runs over no longer
describes the machine it is running on.

Shape of the change, not a PR: measure `T(d)` at load the way `mlx_qmm_mma` already
measures its own win table, cache it under the same per-chip key, fall back to the current
constants when the probe is unavailable. Purely a seed change — `observe_cost()` still
owns steady state.

This is model-visible by your rule, so: does the idea interest you before anyone builds it?

---

## D. ~~`_resolve_kv_bits` gates on shape where the justification is speed + RAM~~ — WITHDRAWN

**Measured, and the shipped default wins. Nothing to file.**

The argument was: 8-bit KV is justified by time (60.2 vs 55.8 tok/s @32k, on the 35B, on
an M4 Pro) *and* RAM (half the kv bytes → ~2x `ctx_limit`), and on a 48 GB box the RAM half
is worth nothing, because the governor already sits at the 262k window cap with ~700k
tokens of budget. True, but irrelevant — the time half carries it alone, and by more on
this chip than on the one it was measured on:

| prompt | kv8 decode | fp16 decode | delta |
|---|---|---|---|
| 5,000 tok | 78.5 tok/s | 77.1 tok/s | −1.8 % |
| 32,000 tok | 68.1 tok/s | 56.8 tok/s | **−16.6 %** |

(3 reps each, rep-major, `envsweep.py`; prefill identical at 379 tok/s both arms.)

Worth recording as the method lesson: the 5k reading is what the *default* `chad-bench`
prompt measures, and at 5k this A/B looks like a 2 % wash — a number that would have
supported switching to fp16 "for free quality" on a box with spare RAM. The whole effect
lives in the regime the original claim was made in. An A/B run outside its own regime is
worse than no A/B.

## E. ~~Bigger prefill chunks fill the M5's matmul units~~ — WITHDRAWN

`_adaptive_chunk` uses a dense base of 512 because "a dense model is compute-bound flat
across chunk sizes", measured on an M4 Pro. Hypothesis was that a chip with matmul units
would reward bigger chunks. It does not:

| chunk | 512 (adaptive) | 1024 | 2048 | 4096 |
|---|---|---|---|---|
| prefill | 434 tok/s | 438 | 430 | 428 |

±1.4 %, inside the noise, 3 reps each. The M4-era finding holds on M5 — 512 stays.

---

## F/G/H — filed 2026-09-11 evening

| # | Finding | Issue |
|---|---|---|
| F | DFlash sidecar loads at the default width, not its recorded one | [#47](https://github.com/nathansutton/chad/issues/47) |
| G | `spec_decode.py` agentic corpus globs the legacy session layout | [#48](https://github.com/nathansutton/chad/issues/48) |
| H | mlx 0.32.1 is degenerate, 0.32.2 is not — the `==` pin is over-broad | [#50](https://github.com/nathansutton/chad/issues/50) |

### H, in one table

`chad prove`, one machine, back to back, scratch venv, mlx-metal tracking mlx:

| mlx | prove | same prompt, greedy |
|---|---|---|
| 0.32.0 (pinned) | 4/4 | `def sum_list(lst): return sum(lst)` |
| 0.32.1 (excluded) | 0/4, all tasks hit the cap | ` 2  2  2  5  5  5  5  5 ...` |
| 0.32.2 (latest) | 4/4 | byte-identical to 0.32.0 |

And the negative result that matters: the 12 failing speculative tests from #45 are the
**same 12** on all three versions (identical md5 of the sorted failure list). mlx is not
behind them; `applegpu_g17s` remains the hypothesis.

Reproduce with `benchmarks/_local-m5/gen_probe.py` in a venv at the version under test.
