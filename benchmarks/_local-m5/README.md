# Local benchmark: shipped 3-bit vs. cached 4-bit + lifted drafter

Apple M5 Pro, 48 GB, chad 2.0.3, 2026-09-11. Untracked local run — not part of the repo's
committed benchmark set under `benchmarks/stock/_runs/`.

Two configurations, both with the DFlash2 block drafter engaged:

- **3-bit shipped** — `nathansutton/Qwen3.8-27B-UD-Q3_K_XL-DFlash2-MLX`, drafter bundled.
  Launched by `~/.local/bin/chad3`.
- **4-bit + drafter** — `mlx-community/Qwen3.8-27B-4bit` paired with the drafter lifted out
  of the shipped repo via `CHAD_DFLASH_PATH`. Launched by `~/.local/bin/chad4`. No 4-bit
  release with a drafter exists upstream; the pairing works because `load_drafter` binds to
  the target's own `embed_tokens`/`lm_head` and validates only shape.

## `chad-bench` — synthetic ceiling

| Config | Prefill (5000 tok) | Decode (128 tok) | Warm step |
|---|---|---|---|
| 4-bit + drafter | 472 tok/s | **78.9 tok/s** | 0.41 s |
| 4-bit serial (`CHAD_NO_DFLASH=1`) | 476 tok/s | 18.2 tok/s | 0.41 s |
| 3-bit + drafter | 454 tok/s | **78.9 tok/s** | 0.42 s |
| 3-bit serial | 456 tok/s | 22.2 tok/s | 0.38 s |

Both drafter configs land on the same number because this benchmark's prompt is tiled code
the drafter reads easily — acceptance saturates and the body's quant stops mattering. The
README says as much. Do not read a config choice off this table.

## `chad prove` — four real agentic tasks, 2 runs each, means

| Task | 3-bit gen | 4-bit gen | 3-bit wall | 4-bit wall | 3-bit tok/s | 4-bit tok/s |
|---|---|---|---|---|---|---|
| casual_typo_fix | 230 | 278 | 10.0 s | 10.9 s | 46.8 | 47.4 |
| add_function | 344 | 510 | 11.1 s | 14.6 s | 40.3 | 44.5 |
| locate_and_fix | 759 | 967 | 21.4 s | 25.1 s | 44.0 | 46.4 |
| fix_bug_midtext | 688 | 1052 | 20.9 s | 27.1 s | 40.4 | 44.3 |
| **total** | **2022** | **2807** | **63.4 s** | **77.8 s** | 42.9 | 45.6 |

8/8 tasks passed in every run, both configs.

**The 4-bit model decodes 6.5% faster per token but emits 39% more tokens to solve the same
task, so it finishes 23% slower in wall clock.** The direction holds for the mean of every
task, but not for every individual run: in run 1, 4-bit `locate_and_fix` emitted 688 tokens
against 3-bit's 772 and finished faster (18.8 s vs 21.7 s). Every other task/run pair goes the
other way, and the per-run spread on the long tasks is wide (4-bit `locate_and_fix`: 688 and
1246 generated tokens). Raw tok/s is the misleading metric here: chad's agent loop, prompt and
stop heuristics are tuned on the shipped checkpoint, and that shows up as token economy rather
than speed.

The 4-bit rows were produced by overriding `cli._HF_MODEL` in-process, since `chad prove`
pins the shipped model on purpose. That override is measurement-only; nothing in the repo
was modified.

**Verdict: use `chad3`.** `chad4` earns its keep as the A/B control that isolates what the
fitted checkpoint is actually worth — not as a lighter fallback: the 4-bit checkpoint is the
*bigger* one (15 GB in the HF cache against 12 GB) and loads slower (2.5 s vs 1.9 s).
