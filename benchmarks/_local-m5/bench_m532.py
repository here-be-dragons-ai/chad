"""chad3 vs. chad4 vs. pi + the local mlx-vlm server — three stacks, one M5 Pro.

Untracked local driver. It imports `benchmarks/matrix/run.py` and registers two extra
arms on top of it; nothing in chad's committed tree is modified, so the harness under
test stays the shipping harness and the grid stays reproducible from upstream's own files.

WHAT THIS ANSWERS THAT THE COMMITTED GRID CANNOT
------------------------------------------------
`benchmarks/matrix/` holds the engine constant (one `llama-server`) to price the harness,
and holds the harness constant (chad) to price the engine. Neither cell covers the setup
this laptop actually runs: `pi` against a *separately tuned* mlx-vlm server
(github.com/here-be-dragons-ai/mlx-qwen38-apple-silicon, "m532"), with its own prefix
cache (APC + SSD tier), its own DFlash2 drafter, and its own memory budget.

    chad+mlx        chad 2.0.3, in-process MLX   3-bit UD-Q3_K_XL + bundled DFlash2
    chad+mlx-4bit   chad 2.0.3, in-process MLX   4-bit + the drafter lifted out of the 3-bit repo
    pi+m532         pi 0.85.1 -> mlx-vlm 0.7.0   4-bit + DFlash2 (block 4), APC on

The middle and the bottom row run **the same weights, byte for byte**:
`~/src/mlx/models/Qwen3.8-27B-MLX-4bit` is a symlink into the same Hugging Face snapshot
`mlx-community/Qwen3.8-27B-4bit` that `CHAD_MODEL` names. So chad+mlx-4bit vs. pi+m532
isolates harness+engine with the checkpoint held fixed, and chad+mlx vs. chad+mlx-4bit
isolates the checkpoint with harness+engine held fixed. Two controlled comparisons that
share one cell, rather than one three-way race where everything moves at once.

WHY THE ACCOUNTING STILL WORKS
------------------------------
m532's server answers with a llama.cpp-shaped `timings` object (`prompt_n`, `cache_n`,
`predicted_n`, `prompt_ms`, `predicted_ms`, plus `draft_n`/`draft_n_accepted`), so
`sampler_proxy.py` records its turns unchanged and `prompt_n` means what it means on
llama-server: tokens actually evaluated, cache excluded. What it does NOT have is
llama-server's Prometheus `/metrics` (its own `/metrics` is a ring buffer of the last
requests, with no cumulative counters and no in-flight gauge), so the two functions
`run_one` uses to bill a cell are replaced here:

  run._metrics  -> the running total of the proxy's own per-turn records
  run._drain    -> quiescence of that record, since there is no `requests_processing`

Both keep the property the committed grid insists on: the tokens are read from something
that is not the harness. The proxy is the neutral observer either way.

SAMPLER
-------
Forced by the proxy exactly as for the llama arms. Verified on this server before the
run: mlx-vlm's request schema accepts `temperature`/`top_p`/`top_k`/`min_p` and passes
all four into `make_sampler`, and it tolerates the llama.cpp-only fields the proxy
neutralizes (`typical_p`, `tfs_z`, `mirostat`, …) rather than 422-ing on them. Those
fields are neutral values, so an engine that ignores them and one that applies them agree.

Run (the m532 server is started by ITS OWN script, never by this file):

    ./start-mlx_qwen3.8.sh                                  # in ~/src/m532
    uv run python benchmarks/_local-m5/bench_m532.py setup
    uv run python benchmarks/_local-m5/bench_m532.py smoke
    uv run python benchmarks/_local-m5/bench_m532.py pi     # server UP
    # stop the server — one engine resident at a time
    uv run python benchmarks/_local-m5/bench_m532.py chad   # server DOWN
    uv run python benchmarks/_local-m5/bench_m532.py table
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MATRIX = os.path.join(os.path.dirname(HERE), "matrix")
sys.path.insert(0, MATRIX)

# Rows go beside this file, not into the committed `benchmarks/matrix/_runs/`: that
# directory is an accumulator for upstream's nights and this is not one of them.
os.environ.setdefault("MATRIX_RUNS", os.path.join(HERE, "_runs"))

import run  # noqa: E402  — after MATRIX_RUNS, which run.py reads at import

# `start_proxy` opens its log here before anything else creates the directory, and
# upstream never hits that because `_runs/` is committed on its side.
os.makedirs(run.RUNS, exist_ok=True)

M532_PORT = 8888
M532_BASE = f"http://127.0.0.1:{M532_PORT}"
M532_MODEL = "Qwen3.8-27B-local"          # the server's alias AND its load path
FOURBIT = "mlx-community/Qwen3.8-27B-4bit"
DRAFTER_REPO = os.path.expanduser(
    "~/.cache/huggingface/hub/models--nathansutton--Qwen3.8-27B-UD-Q3_K_XL-DFlash2-MLX")


def _drafter() -> str:
    """The DFlash2 drafter inside the shipped 3-bit repo, resolved through `refs/main`
    so a re-download does not silently point this at a stale snapshot. Same resolution
    as `~/.local/bin/chad4`; kept here rather than shelling out to it, because an arm
    that depends on a file in `~/.local/bin` is not reproducible from the repo."""
    ref = os.path.join(DRAFTER_REPO, "refs", "main")
    if os.path.exists(ref):
        with open(ref) as f:
            cand = os.path.join(DRAFTER_REPO, "snapshots", f.read().strip(), "dflash")
            if os.path.isfile(os.path.join(cand, "model.safetensors")):
                return cand
    snaps = os.path.join(DRAFTER_REPO, "snapshots")
    for root, dirs, _ in os.walk(snaps):
        if "dflash" in dirs:
            cand = os.path.join(root, "dflash")
            if os.path.isfile(os.path.join(cand, "model.safetensors")):
                return cand
    sys.exit(f"DFlash2 drafter not found under {DRAFTER_REPO} — chad4's arm cannot run")


# -- the two extra arms --------------------------------------------------------
#
# Shaped exactly like the arms they extend: `chad+mlx-4bit` is `chad+mlx` with the
# checkpoint swapped through env (the same mechanism `chad+mlx-nodflash` uses to turn the
# drafter off), and `pi+m532` is upstream's `pi+llama` with only the provider and the
# model id changed. Anything else would make the new rows incomparable to the old ones.

run.ARMS["chad+mlx-4bit"] = lambda p, w, a: ["chad", p, "--yolo"]
run.ARMS["pi+m532"] = lambda p, w, a: ["pi", "-p", p, "--provider", "m532",
                                       "--model", M532_MODEL, "-a"]
# The same pi, with its extension and skill discovery off. This machine's pi instance
# carries the operator's own installed extensions and skills, and they are part of its
# first request: the smoke measured a turn-1 prompt of 11,011 tokens against chad's
# 2,347, and a 22-tool schema. Without this control arm that gap cannot be attributed —
# it is either what pi costs or what THIS pi was configured to cost, and those are
# different findings. Everything else is byte-identical to the arm above.
run.ARMS["pi+m532-lean"] = lambda p, w, a: ["pi", "-p", p, "--provider", "m532",
                                            "--model", M532_MODEL, "-a", "-ne", "-ns"]
run.ARM_ENV["chad+mlx-4bit"] = {"CHAD_MODEL": FOURBIT, "CHAD_DFLASH_PATH": _drafter()}
run.MLX_ARMS.append("chad+mlx-4bit")
# The pi arms bill through the proxy, so they take run_one's server path -- the same one
# the llama arms take. `LLAMA_ARMS` is that path's name upstream, not a claim about the
# engine behind it; the engine is named in the arm and in provenance.
run.LLAMA_ARMS.extend(["pi+m532", "pi+m532-lean"])

ARMS = ["chad+mlx", "chad+mlx-4bit", "pi+m532", "pi+m532-lean"]


# -- accounting ----------------------------------------------------------------

def _turn_totals() -> dict:
    """Running totals over every turn the proxy has recorded, in `_metrics()`'s shape.

    `prompt_n` excludes what the prefix cache served (`cache_n` carries that separately),
    which is the same split llama-server's `prompt_tokens_total` reports and the same one
    `_self_reported` builds for the in-process arms. All three columns therefore mean
    "tokens this engine actually had to evaluate"."""
    tot = {"prompt_tokens_total": 0.0, "tokens_predicted_total": 0.0,
           "cache_tokens_total": 0.0}
    for t in run._turns():
        ti = t.get("timings")
        if not isinstance(ti, dict):
            continue
        tot["prompt_tokens_total"] += ti.get("prompt_n") or 0
        tot["tokens_predicted_total"] += ti.get("predicted_n") or 0
        tot["cache_tokens_total"] += ti.get("cache_n") or 0
    return tot


def _turns_path() -> str:
    return os.path.join(run.RUNS, "turns.jsonl")


def _quiet_drain(timeout: float = 300.0, quiet: float = 4.0) -> bool:
    """Stand in for llama-server's `requests_processing` gauge, which mlx-vlm has not got.

    The concern is the same one upstream documents: a request that outlives the harness
    that asked for it must not land on the next cell's bill. The proxy writes a turn
    record only once a response is finished, so "no new record for `quiet` seconds" is
    the observable that a generation is no longer in flight. Returns False on timeout,
    which marks the row's counts suspect instead of silently wrong."""
    t0 = time.time()
    last_size, last_change = -1, time.time()
    while time.time() - t0 < timeout:
        try:
            size = os.path.getsize(_turns_path())
        except OSError:
            size = 0
        if size != last_size:
            last_size, last_change = size, time.time()
        elif time.time() - last_change >= quiet:
            return True
        time.sleep(0.5)
    return False


run._metrics = _turn_totals
run._drain = _quiet_drain


# -- provider config -----------------------------------------------------------

def _setup_pi_m532() -> str:
    """Add an `m532` provider beside whatever the user already has in this pi instance.

    It points at the PROXY, not at the server: the whole reason the proxy exists is that
    'configure the harness to match' is not verifiable. The user's own `pi.dev` provider
    (which points straight at :8888) is left exactly as it was, and the file is backed up
    once as *.pre-matrix.bak by run._write."""
    p = run._home(".pi/agent/models.json")
    cfg = json.load(open(p)) if os.path.exists(p) else {"providers": {}}
    src = (cfg.get("providers", {}).get("pi.dev", {}).get("models") or [{}])[0]
    cfg.setdefault("providers", {})["m532"] = {
        "name": "m532 via sampler proxy",
        "baseUrl": f"{run.BASE}/v1",
        "apiKey": run.KEY,
        "api": "openai-completions",
        # The user's own model entry, carried over so context window, thinking map and
        # the deepseek reasoning format stay identical to how they really run it. Only
        # the endpoint changes.
        "models": [{**src, "id": M532_MODEL} if src else
                   {"id": M532_MODEL, "contextWindow": 65536, "maxTokens": 16384}],
    }
    return run._write(p, json.dumps(cfg, indent=2))


def _server_up() -> bool:
    try:
        with urllib.request.urlopen(f"{M532_BASE}/health", timeout=5) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _server_model() -> str:
    """What the server actually has loaded — the one thing that decides whether the
    pi row and the chad4 row are on the same weights. Read, not assumed."""
    try:
        with urllib.request.urlopen(f"{M532_BASE}/health", timeout=5) as r:
            return json.loads(r.read().decode()).get("loaded_model") or "?"
    except Exception:  # noqa: BLE001
        return "?"


def _same_weights() -> dict:
    """Resolve both sides of the 4-bit comparison to a real path and compare them.

    A symlink that got repointed, or a second snapshot of the same repo, would turn the
    controlled comparison into an uncontrolled one while every label still read '4-bit'."""
    served = os.path.realpath(os.path.expanduser(
        f"~/src/mlx/models/{M532_MODEL}"))
    hub = os.path.expanduser(
        "~/.cache/huggingface/hub/models--mlx-community--Qwen3.8-27B-4bit/snapshots")
    chad_side = ""
    if os.path.isdir(hub):
        snaps = [os.path.join(hub, d) for d in os.listdir(hub)]
        chad_side = os.path.realpath(snaps[0]) if len(snaps) == 1 else ""
    return {"served_by_m532": served, "loaded_by_chad4": chad_side,
            "identical": bool(chad_side) and served == chad_side,
            "snapshots_found": len(os.listdir(hub)) if os.path.isdir(hub) else 0}


# -- commands ------------------------------------------------------------------

def setup(a) -> None:
    print(f"pi provider       -> {_setup_pi_m532()}", flush=True)
    print(f"chad4 drafter     -> {_drafter()}", flush=True)
    w = _same_weights()
    print(f"m532 serves       -> {w['served_by_m532']}", flush=True)
    print(f"chad4 loads       -> {w['loaded_by_chad4'] or '(more than one snapshot)'}",
          flush=True)
    print(f"same weights      -> {'YES' if w['identical'] else 'NO — see above'}",
          flush=True)
    print(f"server up         -> {_server_up()} ({_server_model()})", flush=True)


def _pi_grid(a) -> None:
    """The proxy in front of m532, then the grid. The server is NOT started or stopped
    here: it is the user's own long-running service with its own budget calculation, and
    a benchmark that restarts it would also be measuring its cold APC tier."""
    if not _server_up():
        sys.exit(f"m532 server is not answering on {M532_BASE} — start it with "
                 f"~/src/m532/start-mlx_qwen3.8.sh")
    w = _same_weights()
    if not w["identical"]:
        print(f"WARNING: the served weights and chad4's are NOT the same path:\n"
              f"  m532:  {w['served_by_m532']}\n  chad4: {w['loaded_by_chad4']}\n"
              f"  the 4-bit comparison is no longer controlled — say so in the writeup",
              flush=True)
    run.UPSTREAM_PORT = M532_PORT
    run.UPSTREAM = M532_BASE
    prox = run.start_proxy(a)
    try:
        run._grid([x for x in a.arms if x in run.LLAMA_ARMS], a)
    finally:
        try:
            run._save("sampler_audit_summary", run._assert_sampler_agreement())
        except SystemExit as e:
            print(f"SAMPLER AUDIT FAILED: {e}", flush=True)
        prox.terminate()
        try:
            prox.wait(timeout=20)
        except subprocess.TimeoutExpired:
            prox.kill()
        print("sampler proxy stopped (m532 left running)", flush=True)


def arm_pi(a) -> None:
    _pi_grid(a)


def arm_chad(a) -> None:
    """The in-process arms. Upstream refuses to run these while llama-server is up; the
    same rule applies to m532's server, and for the same reason — 48 GB does not hold a
    33 GiB server and a 15 GiB in-process engine without the numbers becoming noise."""
    if _server_up():
        sys.exit("the m532 server is still up — one engine resident at a time. Stop it "
                 "first (its own script, or kill the mlx_vlm.server process).")
    if subprocess.run(["pgrep", "-f", "llama-server"],
                      capture_output=True, text=True).stdout.strip():
        sys.exit("llama-server is still running — one engine at a time")
    run._grid([x for x in a.arms if x in run.MLX_ARMS], a)


def smoke(a) -> None:
    """One short task per arm, for the two questions that waste a night when unasked:
    does pi reach the model through the proxy at all, and does chad4's lifted drafter
    actually load (a drafter that fails to bind is silently `None` — chad treats DFlash
    as a pure speed feature and decodes serially rather than erroring)."""
    a.grid_name, a.rep_label, a.tasks = "smoke", -1, [run.SMOKE_TASK]
    a.reps = 1
    if any(x in run.LLAMA_ARMS for x in a.arms):
        _pi_grid(a)
    if any(x in run.MLX_ARMS for x in a.arms) and not _server_up():
        run._grid([x for x in a.arms if x in run.MLX_ARMS], a)
    rows = run._load("smoke") or []
    turns = run._turns(rep=-1)
    verdict = run._load("smoke_verdict") or {}
    for arm in a.arms:
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            verdict[arm] = {"ok": False, "why": "did not run"}
            continue
        r = rs[-1]
        if arm in run.LLAMA_ARMS:
            ts = [t for t in turns if t.get("arm") == arm]
            ok200 = [t for t in ts if t.get("status") == 200]
            timed = [t for t in ok200 if isinstance(t.get("timings"), dict)
                     and t["timings"].get("prompt_n") is not None]
            why = ("no request reached the proxy" if not ts else
                   f"every request failed (status {sorted({t.get('status') for t in ts})})"
                   if not ok200 else
                   "server timings missing from responses" if not timed else
                   "never edited the stub" if not (r["passed"] or r.get("stub_changed"))
                   else "")
        else:
            why = ("never edited the stub"
                   if not (r["passed"] or r.get("stub_changed")) else "")
        verdict[arm] = {"ok": not why, "why": why or "ok",
                        "wall_s": r["wall_s"], "passed": r["passed"],
                        "prefill": r["prefill"], "generated": r["generated"]}
        print(f"  {arm:16s} {'OK  ' if not why else 'DROP'} {why or 'ok'}", flush=True)
    run._save("smoke_verdict", verdict)


def table(a) -> None:
    a.runs = a.runs or [run.RUNS]
    run.table(a)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["setup", "smoke", "pi", "chad", "table"],
                    nargs="?", default="table")
    ap.add_argument("--tasks", default=",".join(run.TASKS))
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--capture-bodies", action="store_true")
    ap.add_argument("--unverified", action="store_true")
    ap.add_argument("--runs", nargs="+", default=None)
    # run._grid reads both directly as of #77 (they were getattr defaults before), and
    # only smoke() overrides them — without these, `pi` and `chad` die in the first call.
    ap.set_defaults(grid_name="grid", rep_label=0)
    a = ap.parse_args(argv)
    a.tasks = [x for x in a.tasks.split(",") if x.strip()]
    a.arms = [x for x in a.arms.split(",") if x.strip()]
    unknown = [x for x in a.arms if x not in run.ARMS]
    if unknown:
        sys.exit(f"unknown arms: {unknown}")
    {"setup": setup, "smoke": smoke, "pi": arm_pi, "chad": arm_chad,
     "table": table}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
