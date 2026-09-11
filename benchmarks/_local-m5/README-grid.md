# chad3 / chad4 / pi + m532 — the harness × engine grid on one M5 Pro

Apple M5 Pro, 48 GB, `iogpu.wired_limit_mb=40960`, 2026-09-11. Untracked local run, driven
by `bench_m532.py` (which registers two extra arms on `benchmarks/matrix/run.py` at runtime
— nothing in chad's committed tree is modified). 8 Exercism tasks, 1 rep, 1,200 s cap,
32 cells, sampler forced identically on every arm and verified.

## The arms

| Arm | Harness | Engine | Weights | Drafter |
|---|---|---|---|---|
| `chad+mlx` (chad3) | chad 2.0.3 | in-process MLX | 3-bit `UD-Q3_K_XL` | DFlash2, bundled |
| `chad+mlx-4bit` (chad4) | chad 2.0.3 | in-process MLX | **4-bit `mlx-community`** | DFlash2, lifted from the 3-bit repo |
| `pi+m532` | pi 0.85.1, as configured here | mlx-vlm 0.7.0 server + APC | **4-bit `mlx-community`** | DFlash2, block 4 |
| `pi+m532-lean` | pi 0.85.1, `-ne -ns` | same server | same | same |

`chad+mlx-4bit` and the two pi arms run **the same weights, byte for byte**: both resolve
to `~/.cache/huggingface/.../models--mlx-community--Qwen3.8-27B-4bit/snapshots/3e6447f0…`
(`bench_m532.py setup` checks this and refuses to call the comparison controlled if the two
paths ever diverge). So:

- **chad4 vs. pi+m532** isolates harness+engine with the checkpoint held fixed.
- **chad3 vs. chad4** isolates the checkpoint with harness+engine held fixed.
- **pi+m532 vs. pi+m532-lean** isolates this machine's pi configuration from pi itself.

## Result

| Arm | Passed | Tests | Median wall (passed) | Total prefill | Total generated |
|---|---|---|---|---|---|
| chad+mlx | **8/8** | 148/148 | 265 s | 47,734 | 62,139 |
| chad+mlx-4bit | **8/8** | 148/148 | 98 s | 26,930 | 31,612 |
| pi+m532 | 5/8 | 102/148 | 120 s | **119,483** | 18,014 |
| pi+m532-lean | 7/8 | 117/148 | 105 s | 63,018 | 14,989 |

| Task | chad+mlx | chad+mlx-4bit | pi+m532 | pi+m532-lean |
|---|---|---|---|---|
| bowling | 265 | 393 | x 0/31 | x 0/31 |
| grade-school | 29 | 56 | 57 | 38 |
| affine-cipher | 125 | 69 | 63 | 40 |
| transpose | 228 | 164 | x 0/12 | 161 |
| wordy | 304 | 183 | 123 | 128 |
| book-store | 209 | 46 | 257 | 116 |
| dominoes | 446 | 69 | 120 | 52 |
| go-counting | 718 | 98 | x 8/11 | 105 |

### What it feels like at the keyboard

| Arm | turn-1 tax (tok) | wait before 1st token | uncached tok / later turn | cache reuse | prefill share of wall | exp. tok/s | round trips |
|---|---|---|---|---|---|---|---|
| pi+m532 | 11,010 | 24.6 s | 532 | 96% | 28% | 18.2 | 4 |
| pi+m532-lean | 3,499 | 7.9 s | 952 | 83% | 21% | 20.2 | 4 |
| chad+mlx | 2,566 | **1.4 s** | 70 | 99% | 7% | 26.3 | 8 |
| chad+mlx-4bit | 2,606 | **1.4 s** | 55 | 99% | 14% | 27.9 | 8 |

## What the numbers say

**1. The gap is prefill, not decode.** On identical weights chad4 makes the engine evaluate
26,930 prompt tokens across the grid; pi makes it evaluate 119,483 — **4.4×** — while
generating *fewer* tokens (18,014 against 31,612). The two harnesses divide the work in
opposite directions: chad thinks, pi reads.

**2. The 17× that a person actually feels is the turn-1 wait: 1.4 s against 24.6 s.**
chad restores its system prefix from its on-disk checkpoint (a `partial` hit — the
project-independent head from disk, only the per-project tail prefilled); pi hands the
server an 11,010-token first request and waits for it. Both engines run APC-class prefix
caching and both hit it on later turns (99% vs 96%), so this is not a caching difference.
It is what each harness *sends*.

**3. This machine's pi configuration costs tasks, not just tokens.** The lean control arm —
same pi, same server, `-ne -ns` — drops from 22 tools to 4 and from an 11,238-char system
prompt to 7,814, cuts the turn-1 tax by 3.1×, the turn-1 wait by 3.1×, total prefill by
1.9×, and solves **7/8 instead of 5/8**. `transpose` and `go-counting` fail *only* with the
extensions loaded. For reference, upstream's committed `pi+llama` arm measures 4 tools and
a 4,052-char system prompt, so the lean arm here is close to stock pi and the configured
one is not.

**4. chad4 beat chad3 on this task set — the opposite of `chad prove`.** Median wall 98 s
against 265 s, total generated 31,612 against 62,139, and chad3 needed 718 s for
`go-counting` where chad4 needed 98. The `prove` measurement earlier the same day found the
3-bit checkpoint 23% *faster* in wall clock on four small fix-it tasks because it emitted
39% fewer tokens. Both cannot be the general case. What differs: these tasks are longer and
harder, and the failure mode they punish is a model that keeps thinking — chad3 generated
almost twice the tokens here. `bowling` also runs the other way (265 s vs. 393 s). **n = 1
per cell**; this contradiction is the most interesting thing in the run and it is not
settled by it.

## Caveats

- **One rep.** Upstream's own three-night grid found 33 of 88 (arm, task) cells changing
  verdict between nights and per-arm wall clock spreading by up to 51%. Every pass/fail
  here is a single measurement. The prefill and tax columns are far more stable than the
  pass column — they are properties of what a harness sends, not of how a sample landed.
- **The chad rows are self-reported** (in-process, from `CHAD_PREFILL_TRACE`); the pi rows
  are read out of the server's own `timings` through the proxy. The definitions are made to
  agree — both are "tokens the engine actually evaluated", cache excluded — but they are
  not the same instrument.
- **Both sides start warm.** chad's disk checkpoint and m532's APC SSD tier both survived
  the smoke run, so neither arm pays a fully cold first prefill. Symmetric, but it means the
  turn-1 numbers are warm-start numbers.
- **`repeat_penalty` / `presence_penalty` / `frequency_penalty`** are forced to neutral
  values by the proxy; mlx-vlm's schema reads `temperature`/`top_p`/`top_k`/`min_p` and
  passes them to `make_sampler`, so the sampler is genuinely shared, but the penalty fields
  may simply be ignored on that side. Neutral values make that harmless.
- **The m532 server was not restarted between the pi arms**, so `pi+m532-lean` ran against
  an APC tier the configured arm had already warmed. That favours the lean arm on turn-1
  restores; it does not explain the tool-count or system-prompt difference, which is where
  its advantage comes from.
- Drafter acceptance on the pi arms: 59% (configured) and 57% (lean), from the server's own
  `draft_n` / `draft_n_accepted`.

## Reproduce

```sh
~/src/m532/start-mlx_qwen3.8.sh                                   # server, phase 1
uv run python benchmarks/_local-m5/bench_m532.py setup            # checks the weights match
uv run python benchmarks/_local-m5/bench_m532.py smoke
benchmarks/_local-m5/run-grid.sh 1                                # both phases, server handled
uv run python benchmarks/_local-m5/scorecard_local.py
```

Rows in `_runs/grid.json`, per-turn records in `_runs/turns.jsonl`, chad's traces in
`_runs/traces/`, the scorecard in `_runs/scorecard.md`.
