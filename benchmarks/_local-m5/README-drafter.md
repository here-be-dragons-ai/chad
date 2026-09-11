# Drafter precision: 8-bit buys nothing

Apple M5 Pro, 48 GB, chad 2.0.3 + the two fixes below, 2026-09-11. Thinking preset
(temp 1.0 / top_p 0.95 / top_k 20), `spec_decode.py` agentic corpus — 10 real
mid-session contexts out of `~/.chad/sessions`, 5,450–19,776 tokens, 384-token decodes.

## The hypothesis

chad ships the DFlash2 drafter at 4-bit group-64 (~1.1 GB), a size chosen for a 24 GB
box. On 48 GB that constraint is gone, and acceptance is the multiplier on the whole
decode path: a drafter forward is a flat ~0.2 serial steps per round, so every extra
accepted position is a whole target step saved. Spending ~1 GB of idle RAM on a
higher-precision drafter looked like the cheapest real speedup available.

## Result

| arm | decode (median) | floor | serial control | speedup | acceptance | tok/round |
|---|---|---|---|---|---|---|
| shipped 4-bit | 35.6 tok/s | 26.9 | 21.7 | 1.639× | 39.9 % | 3.52 |
| q4 (rebuilt here) | 34.7 | 23.1 | 21.6 | 1.607× | 37.6 % | 3.37 |
| q8 | 34.2 | 23.7 | 21.0 | 1.626× | 38.8 % | 3.57 |

**Doubling the drafter's precision moves acceptance by 1.2 pp (37.6 → 38.8 %) and
decode by nothing.** Normalized against the serial control the three arms sit within
2 % of each other, which is the drift the control itself shows across the run
(21.7 → 21.0 as the machine warms). q8 commits marginally more per round (3.57 vs 3.37)
and pays it straight back in a dearer drafter forward.

The reading: 40 % acceptance is a property of what the drafter was *trained* to predict
and of what the model is writing at the time (`<think>` tokens are the hard case), not
of how finely its weights are quantized. 4-bit is not costing chad anything here, and
the 24 GB-era choice survives a box with 4× the headroom.

`q4` is the control that makes this readable. Without it, "8-bit ≈ shipped" would
confound bit width with build provenance — the shipped sidecar comes from a different
source snapshot (`incoai/…` vs `z-lab/…`), a different mlx, a different machine. q4 and
q8 share everything but the width, and they differ by nothing that matters.

## What the run was worth anyway

**The M5 Pro real-session baseline at the preset chad actually runs**, which did not
exist before (the committed numbers are M4 Pro):

| | M4 Pro (docs) | M5 Pro | |
|---|---|---|---|
| serial, thinking | 13.9 tok/s | **21.7** | 1.56× |
| schedule, thinking | 27.6 tok/s | **35.6** | 1.29× |
| floor (worst prompt) | 17.7 | 26.9 | 1.52× |

Note how much smaller the drafted gain is than the serial gain: the M5's speculation
multiplier is 1.64× where the M4's was 1.99×. The chip narrowed the gap speculation was
closing — more of the win is now in the serial step itself.

**And two bugs**, both found by trying to run this A/B rather than by reading code:

- `mlx_dflash._load_sidecar` quantized the skeleton at the caller's default (4) instead
  of at the width recorded in the sidecar's own safetensors metadata. An 8-bit sidecar
  therefore raised on the shape mismatch inside `load_drafter`'s catch-all and decoded
  serially — this A/B would have reported "8-bit is 40 % slower" and been believed. The
  `proposed == 0` check in `drafter_ab.py` exists so that can never read as a slow arm.
- `spec_decode.py`'s agentic corpus globbed `~/.chad/sessions/*.json`, the *legacy*
  single-slot layout (`session.py:19`). Current chad writes `<cwdhash>/<id>.json`, so on
  any machine with only modern sessions the corpus was empty — surfacing several steps
  later as `min() arg is an empty sequence` in the benchmark's warmup.

## Reproduce

```sh
uv run hf download z-lab/Qwen3.8-27B-DFlash2
uv run python benchmarks/_local-m5/drafter_ab.py build   # q4 + q8 sidecars, ~1 s each
uv run python benchmarks/_local-m5/drafter_ab.py run
uv run python benchmarks/_local-m5/drafter_ab.py table
```

Rows in `_runs/drafter-{shipped,q4,q8}-thinking.json`.
