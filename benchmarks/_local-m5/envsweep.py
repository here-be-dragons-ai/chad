#!/usr/bin/env python3
"""env-only A/B sweep on this machine: KV width x prefill chunk.

Two defaults in chad were chosen on a 24 GB M4 Pro and are worth re-measuring on an
M5 Pro / 48 GB, because the reason each was chosen no longer holds here:

- **kv_bits=8** (`engine._resolve_kv_bits`) is gated on SHAPE, not on speed: the fused
  quantized-KV kernel covers this attention geometry, so 8-bit is taken. Its two
  justifications were time (60.2 vs 55.8 tok/s @32k, measured on the 35B on an M4 Pro)
  and RAM (half the KV bytes -> ~2x the governor's ctx_limit). On this box the RAM
  half is worth nothing: the governor already sits at the model's 262k window cap with
  ~700k tokens of budget. So only the time half is left, and it has never been
  measured on this chip.
- **chunk 512** (`engine._adaptive_chunk`) is the dense base because "a dense model is
  compute-bound flat across chunk sizes" — measured on a chip without matmul units. On
  a chip that has them, bigger chunks are exactly what fills them, and the memory
  ceiling that keeps chunks small does not bind at 48 GB.

Rep-major order (every arm once, then again) so thermal drift spreads across arms
rather than pooling in whichever ran last. Every run is verified to have actually taken
its arm by reading the measured kv bytes/token back off chad-bench's own config line,
because an A/B whose arm silently fails to apply reports a clean null — which is what
the first pass of this sweep did, before `bench._bench_engine` existed and chad-bench
ignored CHAD_KV_BITS outright.

    uv run python benchmarks/_local-m5/envsweep.py --reps 3
    uv run python benchmarks/_local-m5/envsweep.py --table
"""

import argparse
import json
import os
import re
import subprocess
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_runs")
ROWS = os.path.join(OUT, "envsweep.jsonl")


# (name, kv_bits env or None for the default, chunk arg or None for adaptive)
ARMS = [
    ("kv8-adaptive", None, None),
    ("kv8-c1024", None, 1024),
    ("kv8-c2048", None, 2048),
    ("kv8-c4096", None, 4096),
    ("fp16-adaptive", "0", None),
    ("fp16-c1024", "0", 1024),
    ("fp16-c2048", "0", 2048),
    ("fp16-c4096", "0", 4096),
]

_PREFILL = re.compile(r"prefill \(cold\)\s+(\d+) tok in\s+([\d.]+) s\s+->\s+([\d.]+) tok/s")
_DECODE = re.compile(r"decode\s+(\d+) tok in\s+([\d.]+) s\s+->\s+([\d.]+) tok/s")
_WARM = re.compile(r"([\d.]+) s of prefill for the follow-up turn")
_LOAD = re.compile(r"model load\s+([\d.]+) s")
# chad-bench's own config echo — the arm check. It reports the MEASURED kv bytes/token,
# which is the one number that cannot lie about which cache width actually got built
# (8-bit group-64: 34,816 B/tok; fp16: 65,536). The session log is no use here: the
# explicit-0 branch of _resolve_kv_bits logs nothing at all.
_CONF = re.compile(r"config\s+kv cache (\S+(?: group-64)?) \(([\d,]+) B/tok\) \| "
                   r"prefill chunk (.+)")


def run_one(arm, kv_bits, chunk, prefill=None, timeout=900):
    """One chad-bench run under `arm`. Returns a row dict, or None if it failed."""
    env = dict(os.environ)
    if kv_bits is not None:
        env["CHAD_KV_BITS"] = kv_bits
    else:
        env.pop("CHAD_KV_BITS", None)
    cmd = ["uv", "run", "chad-bench"]
    if chunk is not None:
        cmd += ["--chunk", str(chunk)]
    if prefill is not None:
        # The kv-width arms only mean something where the cache is big enough to cost
        # something. The default 5,000-token prompt holds ~170 MB of 8-bit KV; the claim
        # this A/B is testing was recorded at 32k.
        cmd += ["--prefill-tokens", str(prefill)]

    t0 = time.time()
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  {arm}: TIMEOUT after {timeout}s", flush=True)
        return None
    wall = time.time() - t0
    out = p.stdout + p.stderr
    mp, md, mw, ml = (_PREFILL.search(out), _DECODE.search(out),
                      _WARM.search(out), _LOAD.search(out))
    if not (mp and md):
        print(f"  {arm}: no numbers parsed (rc={p.returncode})", flush=True)
        print("  " + "\n  ".join(out.strip().splitlines()[-6:]), flush=True)
        return None

    mc = _CONF.search(out)
    return {
        "arm": arm, "kv_bits_env": kv_bits, "chunk": chunk,
        "prefill_tok": int(mp.group(1)), "prefill_s": float(mp.group(2)),
        "prefill_tps": float(mp.group(3)),
        "decode_tok": int(md.group(1)), "decode_s": float(md.group(2)),
        "decode_tps": float(md.group(3)),
        "warm_s": float(mw.group(1)) if mw else None,
        "load_s": float(ml.group(1)) if ml else None,
        "wall_s": round(wall, 1),
        # arm verification, straight out of chad-bench's own config echo
        "kv_label": mc.group(1) if mc else None,
        "kv_bytes_per_token": int(mc.group(2).replace(",", "")) if mc else None,
        "chunk_label": mc.group(3).strip() if mc else None,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def sweep(reps, only=None, prefill=None):
    os.makedirs(OUT, exist_ok=True)
    arms = [a for a in ARMS if not only or a[0] in only]
    n = 0
    for rep in range(reps):
        print(f"=== rep {rep + 1}/{reps} ===", flush=True)
        for arm, kv, chunk in arms:
            label = f"{arm}@{prefill // 1000}k" if prefill else arm
            print(f"  {label} ...", end=" ", flush=True)
            row = run_one(arm, kv, chunk, prefill=prefill)
            if row is None:
                continue
            row["rep"] = rep
            row["arm"] = label
            with open(ROWS, "a") as f:
                f.write(json.dumps(row) + "\n")
            n += 1
            print(f"prefill {row['prefill_tps']:.0f} decode {row['decode_tps']:.1f} "
                  f"warm {row['warm_s']} kv={row['kv_bytes_per_token']} B/tok",
                  flush=True)
    print(f"\n{n} rows -> {ROWS}", flush=True)


def table():
    if not os.path.exists(ROWS):
        sys.exit(f"no rows yet at {ROWS}")
    rows = [json.loads(l) for l in open(ROWS)]
    by: dict = {}
    for r in rows:
        by.setdefault(r["arm"], []).append(r)

    def med(rs, k):
        vals = [r[k] for r in rs if r.get(k) is not None]
        return st.median(vals) if vals else float("nan")

    # Group by prompt size: a kv-width arm at 5k and the same arm at 32k are different
    # measurements of different regimes, and averaging them would hide the only axis
    # this A/B is about. Each group gets its own kv8 baseline.
    groups: dict = {}
    for arm, rs in by.items():
        groups.setdefault(round(med(rs, "prefill_tok") / 1000), {})[arm] = rs

    print(f"\n{'arm':<20} {'n':>2} {'prefill':>9} {'vs base':>8} "
          f"{'decode':>8} {'vs base':>8} {'warm':>6} {'kv B/tok':>9}")
    for ktok in sorted(groups):
        print("-" * 78)
        print(f"-- {ktok}k-token prompt")
        g = groups[ktok]
        base = next((rs for a, rs in g.items() if a.startswith("kv8-adaptive")), None)
        b_p = med(base, "prefill_tps") if base else None
        b_d = med(base, "decode_tps") if base else None
        for arm in sorted(g, key=lambda a: (a.startswith("fp16"), a)):
            rs = g[arm]
            p, d = med(rs, "prefill_tps"), med(rs, "decode_tps")
            dp = f"{(p / b_p - 1) * 100:+.1f}%" if b_p else ""
            dd = f"{(d / b_d - 1) * 100:+.1f}%" if b_d else ""
            kv = {r.get("kv_bytes_per_token") for r in rs}
            print(f"{arm:<20} {len(rs):>2} {p:>7.0f}/s {dp:>8} {d:>6.1f}/s {dd:>8} "
                  f"{med(rs, 'warm_s'):>5.2f}s {str(sorted(x for x in kv if x)):>9}")
    print("\nmedians; 'vs base' is against kv8-adaptive in the same prompt-size group.")
    # The arm check: fp16 arms MUST report a different kv bytes/token than kv8 arms,
    # or CHAD_KV_BITS never reached the engine and the whole fp16 half is a null.
    kv8 = {r["kv_bytes_per_token"] for r in rows
           if r["kv_bits_env"] is None and r.get("kv_bytes_per_token")}
    fp16 = {r["kv_bytes_per_token"] for r in rows
            if r["kv_bits_env"] == "0" and r.get("kv_bytes_per_token")}
    print(f"arm check: kv8 ={sorted(kv8)} B/tok, fp16 ={sorted(fp16)} B/tok -> "
          f"{'DISTINCT (arms applied)' if kv8 and fp16 and not (kv8 & fp16) else 'NOT DISTINCT — arms did not apply, results are void'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--arms", help="comma-separated subset of the arm names")
    ap.add_argument("--prefill", type=int,
                    help="prompt size to pass to chad-bench (default: its 5,000)")
    ap.add_argument("--table", action="store_true", help="print the table and exit")
    a = ap.parse_args()
    if a.table:
        table()
    else:
        sweep(a.reps, only=set(a.arms.split(",")) if a.arms else None,
              prefill=a.prefill)
        table()
