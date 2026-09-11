#!/usr/bin/env python3
"""Drafter precision A/B: does a higher-precision DFlash2 drafter accept more?

chad ships the drafter at 4-bit group-64 (~1.1 GB) — a size chosen for a 24 GB box,
where 12.1 GB of target weights leave little room. On 48 GB that constraint is gone,
and acceptance is the multiplier on the whole decode path: the drafter forward is a
flat ~0.2 serial steps per round, so every extra accepted position is a whole target
step saved. This measures whether spending ~1 GB of otherwise-idle RAM buys any.

Three arms, all built or loaded through chad's own `mlx_dflash`:

  shipped   the 4-bit sidecar bundled with the weights (the default)
  q4        4-bit, rebuilt HERE from the bf16 source — the CONTROL. Without it,
            "8-bit beats shipped" confounds bit width with build provenance
            (different mlx version, different source snapshot, different machine).
  q8        8-bit, same pipeline, same source

chad's `_quantize` already holds the two selector codebooks at 8-bit whatever `bits`
says (they are Embeddings, and the bilinear score is sensitive to them), so the only
thing changing between q4 and q8 is the linears.

Instrument is `benchmarks/spec_decode.py` on the AGENTIC corpus — real mid-session
contexts out of ~/.chad/sessions, with tool results and schemas in place. chad-bench
is the wrong tool here and says so itself: its prompt is tiled code the drafter reads
easily, acceptance saturates, and both drafter configs land on the same number.

    uv run python benchmarks/_local-m5/drafter_ab.py build
    uv run python benchmarks/_local-m5/drafter_ab.py run
    uv run python benchmarks/_local-m5/drafter_ab.py table

NOTE: needs `mlx_dflash._load_sidecar` to read the width out of the sidecar's own
safetensors metadata. Stock chad quantizes the skeleton at the caller's default of 4
whatever the file holds, so an 8-bit sidecar raises on the shape mismatch inside
`load_drafter`'s catch-all and silently decodes serial — which this A/B would report
as "8-bit is much slower" rather than as the bug it is. The `proposed > 0` check in
`table()` is there to catch exactly that if it ever regresses.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "_runs")
SRC_REPO = "z-lab/Qwen3.8-27B-DFlash2"
BUILT = os.path.expanduser("~/.cache/chad/dflash")

ARMS = ["shipped", "q4", "q8"]


def _src_dir():
    """The downloaded bf16 source snapshot."""
    from huggingface_hub import snapshot_download
    return snapshot_download(SRC_REPO)


def _dest(bits):
    return os.path.join(BUILT, f"m5ab-Qwen3.8-27B-DFlash2-q{bits}g64")


def build():
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from chad.mlx_dflash import build_sidecar

    src = _src_dir()
    print(f"source: {src}", flush=True)
    for bits in (4, 8):
        dest = _dest(bits)
        if os.path.isfile(os.path.join(dest, "model.safetensors")):
            print(f"  q{bits}: exists, skipping ({dest})", flush=True)
            continue
        t0 = time.time()
        build_sidecar(src, dest, bits=bits, gs=64)
        size = os.path.getsize(os.path.join(dest, "model.safetensors")) / 1e9
        print(f"  q{bits}: built in {time.time() - t0:.0f}s, {size:.2f} GB -> {dest}",
              flush=True)


def _run_one(arm, preset, prompts, tokens):
    env = dict(os.environ)
    if arm == "shipped":
        env.pop("CHAD_DFLASH_PATH", None)
    else:
        env["CHAD_DFLASH_PATH"] = _dest(int(arm[1:]))
    out = os.path.join(OUT, f"drafter-{arm}-{preset}.json")
    cmd = [
        "uv", "run", "python", os.path.join(ROOT, "benchmarks", "spec_decode.py"),
        "--corpus", "agentic", "--preset", preset,
        # serial is the drift control: it never touches the drafter, so if it moves
        # between arms the machine moved, not the drafter.
        "--arms", "serial,schedule",
        "--prompts", str(prompts), "--tokens", str(tokens), "--json", out,
    ]
    print(f"  {arm} / {preset} ...", flush=True)
    t0 = time.time()
    p = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        print(f"    FAILED rc={p.returncode}", flush=True)
        print("    " + "\n    ".join((p.stdout + p.stderr).strip().splitlines()[-8:]),
              flush=True)
        return
    print(f"    done in {time.time() - t0:.0f}s -> {out}", flush=True)


def run(prompts, tokens, presets):
    os.makedirs(OUT, exist_ok=True)
    for preset in presets:
        for arm in ARMS:
            _run_one(arm, preset, prompts, tokens)


def table():
    import statistics as st
    print(f"\n{'arm':<10}{'preset':<10}{'n':>3}{'decode':>10}{'floor':>9}"
          f"{'accept':>9}{'tok/round':>11}{'serial':>9}")
    print("-" * 71)
    any_rows = False
    for preset in ("thinking", "greedy"):
        for arm in ARMS:
            path = os.path.join(OUT, f"drafter-{arm}-{preset}.json")
            if not os.path.isfile(path):
                continue
            any_rows = True
            rows = json.load(open(path))
            sch = [r for r in rows if r["arm"] == "schedule"]
            ser = [r for r in rows if r["arm"] == "serial"]
            if not sch:
                continue
            prop = sum(r.get("proposed", 0) for r in sch)
            acc = sum(r.get("accepted", 0) for r in sch)
            rounds = sum(r.get("forwards", 0) for r in sch)
            tps = [r["tok_s"] for r in sch]
            stps = [r["tok_s"] for r in ser] or [float("nan")]
            # proposed == 0 means the drafter never loaded and this arm decoded
            # serially — the silent-fallback failure this A/B is most exposed to.
            flag = "  <- DRAFTER NEVER LOADED" if prop == 0 else ""
            print(f"{arm:<10}{preset:<10}{len(sch):>3}{st.median(tps):>9.1f}/s"
                  f"{min(tps):>8.1f}/s{acc / prop if prop else 0:>8.0%}"
                  f"{(acc + rounds) / rounds if rounds else 0:>10.2f}"
                  f"{st.median(stps):>8.1f}/s{flag}")
    if not any_rows:
        sys.exit("no result files yet — run `drafter_ab.py run` first")
    print("\nmedian and floor (worst prompt) of decode-only tok/s, agentic corpus.")
    print("'serial' is the no-drafter control: it should be flat across arms — if it")
    print("moves, the machine moved and the comparison is not controlled.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "run", "table"])
    ap.add_argument("--prompts", type=int, default=10)
    ap.add_argument("--tokens", type=int, default=384)
    ap.add_argument("--presets", default="thinking")
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    elif a.cmd == "run":
        run(a.prompts, a.tokens, a.presets.split(","))
        table()
    else:
        table()
