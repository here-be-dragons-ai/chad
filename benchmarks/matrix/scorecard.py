"""The local-fitness scorecard: what a person at the laptop felt, per harness, per turn.

`run.py table` says which arm finished the tasks and how fast. This says what the wait
was while it happened, derived from what the SERVER saw — `_runs/turns.jsonl`, written by
the sampler proxy for every generation request, carrying llama-server's own `timings` —
never from anything a harness reports about itself.

THE COLUMNS
-----------
Every request is first classified as a MAIN turn or a SIDE request. A side request is a
generation call that carries no tool schemas while the same run's other calls do: the
session-title / summary calls that opencode, goose, crush and dsh fire beside the agent
loop. They are real load on the only GPU and count toward the model's busy time and the
prefill seconds, but they are not turns of the agent, and letting them into the per-turn
columns produced two wrong numbers in the first version of this scorecard (a "first
prompt" of 228 tokens for goose, whose real first agent request is 9.6k; a "prefix churn"
that was side requests flipping the hash, not the agent prompt changing).

    tax                 prompt tokens of the first MAIN request (prompt_n + cache_n):
                        system prompt + tool schemas + the task. Paid at least once, and
                        how much of the window is gone before the user has typed a word.
    wait, turn 1        llama-server's own `prompt_ms` for that request: the time the
                        model spent reading before it could produce a token.
    uncached / later    `prompt_n` on main turns 2+ — the part of each turn the prefix
                        cache could not serve. Median, pooled over the arm's turns.
    wait / later turn   `prompt_ms` on main turns 2+, median and p90 (nearest rank).
                        The pause between a tool result landing and the model thinking.
    cache reuse         median over main turns 2+ of cache_n / (cache_n + prompt_n).
    prefill s / task    Σ prompt_ms over EVERY request of the run (side requests
                        included), median across tasks.
    exp. tok/s          generated tokens / wall clock for the whole task.
    tools, sys chars    tool schemas and system-message characters on the first main
                        request, as the harness sent them.
    prefix churn        main chat turns whose system-message or tool-list hash differs
                        from the previous main turn's, over turns compared.
    side requests       side requests across the arm's grid: how many ran CONCURRENTLY
                        with a main turn (their time window overlapped one), and how
                        many the harness abandoned before the server answered (the
                        proxy saw the client disconnect; no `timings` came back). Both
                        are load on the only GPU while the user is waiting.
    after side / turn   (JSON only) median `prompt_n` of a main turn — 3rd or later,
                        since the 2nd is every harness's test-file read — that follows
                        a side request, against one that follows a main turn. In the
                        committed run every side request sits beside turn 1, so there
                        is no sample and no column; an earlier draft that compared
                        turn 2 against later turns was measuring the test-file read.
    model busy          Σ (prompt_ms + predicted_ms) / wall. Above 100% means two
                        requests were in flight at once.
    round trips         main turns per task (median).
    ctx at exit         prompt_n + cache_n + predicted_n of the last main turn.
    pass                the gate. Printed, never ranked.

WHY NOT THE PROXY'S TIME-TO-FIRST-BYTE
--------------------------------------
The proxy stamps the first byte it sees back from llama-server, and llama-server starts
emitting bytes on a long prefill BEFORE the prefill is done (the streamed form carries
an early chunk), so that stamp sat at ~30 s for every request over ~3k prompt tokens
whatever the real read time was. The scorecard prints how many requests had a first
byte earlier than their own `prompt_ms`; the column is kept in the data as
`proxy_ttft_*` and used for nothing.

MLX arms have no server to observe. Their rows come from chad's own prefill trace
(`CHAD_PREFILL_TRACE`, same field definitions) and are marked self-reported; their turn-1
wait is a warm prefix loaded from disk, not a cold prefill, and is marked as such.

Each measured night is one run directory. `_runs/` holds one per night
(`repN-YYYYMMDD/`), and the default run is all of them: night k becomes rep k of the same
(arm, task) cell, so the medians below are over reps as well as tasks. The `pass` column
prints the cell count, so a two-night grid reads `13/16`, not `13/8`.

Run:
    uv run python benchmarks/matrix/scorecard.py               # -> _runs/scorecard.md + .json
                                                               #    over every _runs/repN*/
    uv run python benchmarks/matrix/scorecard.py --runs DIR    # one night, or several
    uv run python benchmarks/matrix/scorecard.py --convergence # per-column wobble between
                                                               # nights, and whether the
                                                               # last one still moved it
    uv run python benchmarks/matrix/scorecard.py --legacy      # grid.json + sampler_audit.jsonl
                                                               # only (runs before turns.jsonl)
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUNS_DEFAULT = os.path.join(HERE, "_runs")
MLX_ARMS = ("chad+mlx", "chad+mlx-nodflash")


# -- loading -------------------------------------------------------------------

def _jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _rel(p: str) -> str:
    """A run directory as it goes into the committed JSON: relative to the repo, never
    the absolute path of whoever's laptop ran it."""
    try:
        return os.path.relpath(os.path.abspath(p), ROOT)
    except ValueError:
        return os.path.basename(p.rstrip("/"))


def run_dirs(runs) -> list:
    """The run directories behind `runs`: a path that has a grid.json is one itself,
    anything else is scanned for `repN*` children that do, in name order. So `_runs`
    means every night measured so far, and a single night is still addressable."""
    out = []
    for p in ([runs] if isinstance(runs, str) else list(runs)):
        if os.path.exists(os.path.join(p, "grid.json")):
            out.append(p)
            continue
        out += sorted(d for d in glob.glob(os.path.join(p, "rep[0-9]*"))
                      if os.path.exists(os.path.join(d, "grid.json")))
    return out


def load(runs) -> tuple:
    """Rows, turn records and sampler audit across the run directories behind `runs`.

    Each directory is one rep of the same grid: its rows and turns are re-keyed to its
    index, since every night numbers its own reps from 0 and the (arm, task, rep) key
    would otherwise collide between nights. The row keeps the directory it came from and
    the rep it was written with, which is what its trace is filed under on disk."""
    rows, turns, audit = [], [], []
    for rep, d in enumerate(run_dirs(runs)):
        grid = os.path.join(d, "grid.json")
        for r in (json.load(open(grid)) if os.path.exists(grid) else []):
            rows.append({**r, "rep": rep, "src_rep": r.get("rep", 0), "src_dir": d})
        turns += [{**t, "rep": rep} for t in _jsonl(os.path.join(d, "turns.jsonl"))
                  if isinstance(t.get("rep"), int) and t["rep"] >= 0]
        audit += _jsonl(os.path.join(d, "sampler_audit.jsonl"))
    return rows, turns, audit


# -- one request, normalised ---------------------------------------------------

def norm_turn(t: dict) -> dict | None:
    """One proxy row -> {prompt_n, cache_n, predicted_n, prompt_ms, predicted_ms, ...}.
    Prefers llama-server's `timings`; falls back to an OpenAI `usage` block (no ms)."""
    tm = t.get("timings") if isinstance(t.get("timings"), dict) else None
    us = t.get("usage") if isinstance(t.get("usage"), dict) else None
    base = {"ttft": t.get("ttft_s"), "sys_sha": t.get("sys_sha"),
            "tools_sha": t.get("tools_sha"), "shape": t.get("shape"),
            "n_tools": t.get("n_tools"), "sys_chars": t.get("sys_chars"),
            "t": t.get("t_arrive"), "t_end": t.get("t_last_byte"),
            "abandoned": bool(t.get("client_disconnected")), "measured": True}
    if tm and tm.get("prompt_n") is not None:
        return {"prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n") or 0,
                "predicted_n": tm.get("predicted_n") or 0,
                "prompt_ms": tm.get("prompt_ms"), "predicted_ms": tm.get("predicted_ms"),
                **base}
    if us:
        pt = us.get("prompt_tokens", us.get("input_tokens"))
        det = us.get("prompt_tokens_details") or us.get("input_tokens_details") or {}
        cached = det.get("cached_tokens") or 0
        if pt is not None:
            return {"prompt_n": pt - cached, "cache_n": cached,
                    "predicted_n": us.get("completion_tokens", us.get("output_tokens")) or 0,
                    "prompt_ms": None, "predicted_ms": None, **base}
    if t.get("status") == 200:
        # The server accepted it and the harness walked away before it answered (a
        # title call cancelled once the agent turn came back, typically). No numbers
        # came back, but it held a slot for as long as it ran; it is counted, not
        # measured.
        return {"prompt_n": None, "cache_n": None, "predicted_n": None,
                "prompt_ms": None, "predicted_ms": None, **base, "measured": False}
    return None


def norm_trace(r: dict) -> dict:
    """One CHAD_PREFILL_TRACE row -> the same shape. chad's `prompt_tokens` already
    excludes the cached prefix, so it maps onto llama-server's `prompt_n` directly."""
    return {"prompt_n": r.get("prompt_tokens", 0), "cache_n": r.get("cached_tokens", 0),
            "predicted_n": r.get("gen_tokens", 0),
            "prompt_ms": (r.get("prefill_s") or 0) * 1000.0,
            "predicted_ms": (r.get("gen_s") or 0) * 1000.0,
            "ttft": r.get("prefill_s"), "sys_sha": None, "tools_sha": None,
            "shape": "completion", "n_tools": None, "sys_chars": None,
            "t": r.get("seq", 0), "t_end": None, "abandoned": False, "measured": True}


def classify(turns: list) -> None:
    """Mark each turn `side` (a no-tools call beside a tool-bearing agent loop) or not.

    In place, on an ordered list of normalised turns from ONE run. A harness that never
    sends tool schemas (mini-swe-agent, chad's raw completion path) has no side
    requests by this rule — every call is the agent loop."""
    has_tools = any((t.get("n_tools") or 0) >= 1 for t in turns)
    for t in turns:
        t["side"] = bool(has_tools and not (t.get("n_tools") or 0))


# -- per (arm, task, rep) ------------------------------------------------------

def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _p90(xs):
    """Nearest-rank 90th percentile; None when empty."""
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[max(0, math.ceil(0.9 * len(xs)) - 1)]


def _s(ms):
    return None if ms is None else ms / 1000.0


def _overlaps(a: dict, b: dict) -> bool:
    """Two requests whose time windows at the proxy intersect."""
    if a["t"] is None or b["t"] is None:
        return False
    a_end, b_end = a.get("t_end") or a["t"], b.get("t_end") or b["t"]
    return a["t"] < b_end and b["t"] < a_end


def run_metrics(row: dict, turns: list, warm: dict | None = None) -> dict:
    """Derived numbers for one run. `turns` is normalised, ordered and classified.
    `warm` is the in-process arm's warm-prefix row, if its trace recorded one: the
    system-prompt prefix chad prefills (miss) or restores from disk (hit) before step 1.
    A miss is prefill the user waits through before the first token, so it is added to
    the turn-1 wait and to the run's prefill total; a hit costs the load time only."""
    m = _run_metrics(row, turns)
    if warm is None:
        m["warm_status"] = None
        return m
    warm_s = float(warm.get("prefill_s") or 0.0)
    m["warm_status"] = warm.get("status")
    m["warm_s"] = warm_s
    m["warm_tokens"] = warm.get("prefix_tokens")
    if warm.get("status") == "miss":
        m["wait_first"] = (m.get("wait_first") or 0.0) + warm_s
        m["prefill_s"] = (m.get("prefill_s") or 0.0) + warm_s
        wall = row.get("wall_s") or 0
        pm = sum(t["prompt_ms"] for t in turns if t.get("measured") and t["prompt_ms"] is not None) / 1000.0 + warm_s
        gm = sum(t["predicted_ms"] for t in turns if t.get("measured") and t["predicted_ms"] is not None) / 1000.0
        if pm + gm > 0:
            m["prefill_share"] = pm / (pm + gm)
            m["model_busy"] = (pm + gm) / wall if wall else None
    return m


def _run_metrics(row: dict, turns: list) -> dict:
    rep = row.get("rep", 0)
    wall = row.get("wall_s") or 0
    gen = row.get("generated") or 0
    side_all = [t for t in turns if t.get("side")]
    main_all = [t for t in turns if not t.get("side")]
    out = {"arm": row["arm"], "task": row["task"], "rep": rep,
           "passed": bool(row.get("passed")),
           "timed_out": bool(row.get("timed_out")), "wall_s": wall,
           "tests": f"{row.get('tests_passed', 0)}/{row.get('tests_total', 0)}",
           "exp_toks": gen / wall if wall else None,
           "round_trips": len(main_all),
           "side_requests": len(side_all),
           "side_concurrent": sum(1 for s in side_all
                                  if any(_overlaps(s, m) for m in main_all)),
           "side_abandoned": sum(1 for s in side_all if s.get("abandoned")),
           "unmeasured": sum(1 for t in turns if not t.get("measured"))}
    # Everything numeric below is over requests the server reported on.
    all_turns = turns
    turns = [t for t in turns if t.get("measured")]
    if not turns:
        return out
    main = [t for t in turns if not t.get("side")]
    # Whole-run model time: side requests occupy the GPU too.
    pm = [t["prompt_ms"] for t in turns if t["prompt_ms"] is not None]
    gm = [t["predicted_ms"] for t in turns if t["predicted_ms"] is not None]
    if pm:
        out["prefill_s"] = sum(pm) / 1000.0
    if pm and gm and (sum(pm) + sum(gm)) > 0:
        out["prefill_share"] = sum(pm) / (sum(pm) + sum(gm))
        out["model_busy"] = ((sum(pm) + sum(gm)) / 1000.0) / wall if wall else None
    # Instrument check: proxy first-byte earlier than the server's own prefill time.
    out["ttft_lt_prefill"] = sum(1 for t in turns if t["ttft"] is not None
                                 and t["prompt_ms"] is not None
                                 and t["ttft"] < t["prompt_ms"] / 1000.0 - 0.5)
    out["ttft_checked"] = sum(1 for t in turns if t["ttft"] is not None
                              and t["prompt_ms"] is not None)
    if not main:
        return out
    first, later = main[0], main[1:]
    out["tax"] = (first["prompt_n"] or 0) + (first["cache_n"] or 0)
    out["wait_first"] = _s(first["prompt_ms"])
    out["proxy_ttft_cold"] = first["ttft"]
    out["proxy_ttft_warm"] = [t["ttft"] for t in later if t["ttft"] is not None]
    out["uncached_later"] = [t["prompt_n"] or 0 for t in later]
    out["wait_later"] = [_s(t["prompt_ms"]) for t in later if t["prompt_ms"] is not None]
    out["reuse"] = [t["cache_n"] / (t["cache_n"] + t["prompt_n"])
                    for t in later if (t["cache_n"] or 0) + (t["prompt_n"] or 0) > 0]
    out["n_tools"] = first.get("n_tools")
    out["sys_chars"] = first.get("sys_chars")
    # What a side request costs the NEXT main turn: uncached tokens on a main turn that
    # follows a side request, against one that follows a main turn. Main turns 3+ only:
    # turn 1 is the tax and turn 2 is every harness's test-file read, and a title call
    # fired right after turn 1 would otherwise be "followed" by a 3k-token read that
    # every arm pays anyway.
    # Walks the unfiltered sequence: an abandoned (unmeasured) side request still
    # precedes the turn after it.
    after_side, after_main = [], []
    late = set(id(t) for t in main[2:])
    for prev, cur in zip(all_turns, all_turns[1:]):
        if cur.get("side") or id(cur) not in late:
            continue
        (after_side if prev.get("side") else after_main).append(cur["prompt_n"] or 0)
    out["uncached_after_side"] = after_side
    out["uncached_after_main"] = after_main
    chat = [t for t in main if t.get("shape") == "chat" and t.get("sys_sha")]
    if len(chat) >= 2:
        out["churn"] = sum(1 for a, b in zip(chat, chat[1:])
                           if a["sys_sha"] != b["sys_sha"] or a["tools_sha"] != b["tools_sha"])
        out["churn_of"] = len(chat) - 1
    last = main[-1]
    out["ctx_exit"] = ((last["prompt_n"] or 0) + (last["cache_n"] or 0)
                       + (last["predicted_n"] or 0))
    return out


def _trace_path(row: dict, runs_dir: str) -> str:
    """The MLX arm's prefill trace: the row's own path (relative to the repo root, or
    absolute from an older run), else the deterministic location inside the night the
    row came from. That location is keyed by the rep the night WROTE, not the rep this
    scorecard re-keyed it to, and a night whose directory has since been renamed no
    longer matches its recorded path — so the fallback is the normal case, not the
    exception."""
    d = row.get("src_dir") or runs_dir
    p = row.get("prefill_trace")
    if p:
        for cand in (p, os.path.join(ROOT, p), os.path.join(d, p)):
            if os.path.exists(cand):
                return cand
    return os.path.join(d, "traces",
                        f"{row['arm']}-{row['task']}-{row.get('src_rep', row.get('rep', 0))}",
                        "prefill_trace.jsonl")


def per_run(rows: list, turns: list, runs_dir: str) -> list:
    by_key = defaultdict(list)
    for t in turns:
        n = norm_turn(t)
        if n is not None:
            by_key[(t.get("arm"), t.get("task"), t.get("rep"))].append(n)
    out = []
    for row in rows:
        key = (row["arm"], row["task"], row.get("rep", 0))
        warm = None
        if row["arm"] in MLX_ARMS:
            raw = _jsonl(_trace_path(row, runs_dir))
            # The warm-prefix row (seq 0) is chad prefilling / restoring its system
            # prompt BEFORE step 1. It is not a turn; it is part of the turn-1 wait.
            warm = next((r for r in raw if r.get("kind") == "warm_prefix"), None)
            ts = [norm_trace(r) for r in raw if r.get("kind") != "warm_prefix"]
        else:
            ts = sorted(by_key.get(key, []), key=lambda t: t["t"] or 0)
        classify(ts)
        out.append(run_metrics(row, ts, warm))
    return out


# -- per arm -------------------------------------------------------------------

def _pool(rs, key):
    return [x for r in rs for x in r.get(key, [])]


def aggregate(per: list) -> list:
    arms = []
    for arm in dict.fromkeys(r["arm"] for r in per):
        rs = [r for r in per if r["arm"] == arm]
        # A cell whose trace predates the warm-prefix row cannot say what the turn-1
        # wait was. It is not a different quantity measured differently; it is the same
        # quantity measured without the part that dominates it, and taking a median
        # across both would average a known-short number with a right one. The columns
        # the warm prefix enters are therefore taken over the cells that recorded it,
        # and the footnote prints how many of the arm's cells that was.
        wrs = rs
        if any(r.get("warm_status") for r in rs):
            wrs = [r for r in rs if r.get("warm_status")]
        churn = sum(r.get("churn", 0) for r in rs if "churn" in r)
        churn_of = sum(r.get("churn_of", 0) for r in rs if "churn" in r)
        wait_later = _pool(rs, "wait_later")
        arms.append({
            "arm": arm, "n": len(rs),
            "passed": sum(1 for r in rs if r["passed"]),
            "timeouts": sum(1 for r in rs if r["timed_out"]),
            "tax": _med([r.get("tax") for r in rs]),
            "wait_first": _med([r.get("wait_first") for r in wrs]),
            "uncached_later": _med(_pool(rs, "uncached_later")),
            "wait_later": _med(wait_later), "wait_later_p90": _p90(wait_later),
            "later_n": len(wait_later),
            "reuse": _med(_pool(rs, "reuse")),
            "prefill_s": _med([r.get("prefill_s") for r in wrs]),
            "exp_toks": _med([r["exp_toks"] for r in rs]),
            "n_tools": _med([r.get("n_tools") for r in rs]),
            "sys_chars": _med([r.get("sys_chars") for r in rs]),
            "churn": (churn, churn_of) if churn_of else None,
            "side_requests": sum(r.get("side_requests", 0) for r in rs),
            "side_concurrent": sum(r.get("side_concurrent", 0) for r in rs),
            "side_abandoned": sum(r.get("side_abandoned", 0) for r in rs),
            "uncached_after_side": _med(_pool(rs, "uncached_after_side")),
            "uncached_after_main": _med(_pool(rs, "uncached_after_main")),
            "prefill_share": _med([r.get("prefill_share") for r in wrs]),
            "model_busy": _med([r.get("model_busy") for r in wrs]),
            "round_trips": _med([r["round_trips"] for r in rs if r["round_trips"]]),
            "ctx_exit": _med([r.get("ctx_exit") for r in rs]),
            "proxy_ttft_cold": _med([r.get("proxy_ttft_cold") for r in rs]),
            "proxy_ttft_warm": _med(_pool(rs, "proxy_ttft_warm")),
            "ttft_lt_prefill": sum(r.get("ttft_lt_prefill", 0) for r in rs),
            "ttft_checked": sum(r.get("ttft_checked", 0) for r in rs),
            "self_reported": arm in MLX_ARMS,
            "warm_status": sorted({r.get("warm_status") for r in rs
                                   if r.get("warm_status")}),
            "warm_unrecorded": sum(1 for r in rs if r.get("warm_status") is None),
            "warm_n": len(wrs),
            "warm_s": _med([r.get("warm_s") for r in rs if r.get("warm_status") == "miss"]),
        })
    return arms


# -- rendering -----------------------------------------------------------------

def _pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def _num(x, fmt="{:.1f}"):
    return "–" if x is None else fmt.format(x)


def _table(hdr: list, rows: list) -> str:
    w = [max(len(str(r[i])) for r in [hdr] + rows) for i in range(len(hdr))]
    lines = ["| " + " | ".join(str(h).ljust(w[i]) for i, h in enumerate(hdr)) + " |",
             "|" + "|".join("-" * (x + 2) for x in w) + "|"]
    lines += ["| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |"
              for r in rows]
    return "\n".join(lines)


def _gate(a: dict) -> str:
    return f"{a['passed']}/{a['n']}" + (f" T{a['timeouts']}" if a["timeouts"] else "")


def _warm_note(arms: list) -> str:
    """The `†` footnote for the in-process rows. chad prefills (or restores from disk)
    its system-prompt prefix BEFORE its first step, where a per-step trace cannot see
    it. Say exactly what the trace recorded: a miss is a cold prefill of the whole
    prefix and is included in the turn-1 wait; a hit is a disk restore; an older trace
    that has no warm-prefix row understates the wait by that prefill."""
    sr = [a for a in arms if a["self_reported"]]
    if not any(a["warm_status"] for a in sr):
        return ("`†` the trace this run was made with did not record the system-prompt "
                "prefix chad prefills (or restores from disk) before its first step, so "
                "the turn-1 wait shown is the first step's own prefill only and "
                "UNDERSTATES the cold wait by that prefix; the chad+llama row is the cold "
                "number for the same prompt.")
    parts = []
    for a in sr:
        st = "/".join(a["warm_status"]) or "unrecorded"
        miss = f", {a['warm_s']:.1f} s of it" if a["warm_s"] is not None else ""
        parts.append(f"{a['arm']}: {st}{miss}")
    note = ("`†` includes the system-prompt prefix chad prefills before its first step "
            "when its disk checkpoint misses, or restores when it hits (" + "; ".join(parts)
            + "). A miss is the cold prefill of the same prompt the chad+llama row pays; "
            "a hit is a disk restore.")
    # Say it when the arm's cells are not all instrumented, and say which columns that
    # narrows: the alternative is a table that looks like n cells everywhere and is not.
    mixed = [a for a in sr if a["warm_unrecorded"] and a["warm_n"] < a["n"]]
    if mixed:
        w = "; ".join(f"{a['arm']} {a['warm_n']}/{a['n']}" for a in mixed)
        note += (" The turn-1 wait and prefill columns of those rows are over the cells "
                 f"whose trace recorded the prefix ({w}); the rest of the row, and the "
                 "pass gate, are over every cell.")
    return note


def render(arms: list, per: list, tasks: list) -> str:
    out = ["### Local-fitness scorecard — same weights, same laptop, same tasks\n",
           "#### What it feels like\n"]
    hdr = ["Arm", "tax: turn-1 prompt (tok)", "wait before 1st token, turn 1",
           "uncached tok / later turn (med)", "wait / later turn (med · p90)",
           "cache reuse", "prefill s / task (med)", "exp. tok/s", "pass (gate)"]
    body = []
    for a in arms:
        mark = " *" if a["self_reported"] else ""
        w1 = _num(a["wait_first"], "{:.1f} s") + (" †" if a["self_reported"] else "")
        body.append([a["arm"] + mark, _num(a["tax"], "{:,.0f}"), w1,
                     _num(a["uncached_later"], "{:,.0f}"),
                     f"{_num(a['wait_later'], '{:.1f} s')} · "
                     f"{_num(a['wait_later_p90'], '{:.0f} s')}",
                     _pct(a["reuse"]), _num(a["prefill_s"], "{:.0f}"),
                     _num(a["exp_toks"]), _gate(a)])
    out.append(_table(hdr, body))
    out.append("""
Every column but the last two is llama-server's own accounting, read through the proxy
(`_runs/turns.jsonl`), never a harness's self-report. **tax** = prompt tokens of the
first agent request (`prompt_n + cache_n`: system prompt + tool schemas + task); **wait,
turn 1** = the server's `prompt_ms` for that request; **uncached / later turn** =
`prompt_n` on agent turns 2+, pooled median; **wait / later turn** = `prompt_ms` on those
turns, median and p90; **cache reuse** = `cache_n / (cache_n + prompt_n)` on those turns;
**prefill s / task** = Σ `prompt_ms` over every request of a task, side requests included;
**exp. tok/s** = generated tokens / wall clock. Side requests (title / summary calls with
no tool schemas) are excluded from the per-turn columns and counted in the next table.
The pass column is a gate, not a ranking.""")
    if any(a["self_reported"] for a in arms):
        out.append("`*` in-process arm: the same fields from chad's own prefill trace, "
                   "self-reported — no server saw it. " + _warm_note(arms))

    out.append("\n#### Shape of the harness\n")
    hdr = ["Arm", "tools", "system prompt (chars)", "prefix churn",
           "side requests (concurrent · abandoned)", "round trips / task",
           "model busy", "prefill share", "ctx at exit"]
    body = []
    for a in arms:
        churn = "–" if not a["churn"] else f"{a['churn'][0]}/{a['churn'][1]}"
        side = (f"{a['side_requests']} ({a['side_concurrent']} · {a['side_abandoned']})"
                if a["side_requests"] else "0")
        body.append([a["arm"] + (" *" if a["self_reported"] else ""),
                     _num(a["n_tools"], "{:.0f}"), _num(a["sys_chars"], "{:,.0f}"),
                     churn, side, _num(a["round_trips"], "{:.0f}"),
                     _pct(a["model_busy"]), _pct(a["prefill_share"]),
                     _num(a["ctx_exit"], "{:,.0f}")])
    out.append(_table(hdr, body))
    out.append("""
**tools** / **system prompt** as the harness sent them on its first agent request;
**prefix churn** = agent turns whose system-message or tool-list hash changed since the
previous agent turn, over turns compared (`–`: chad's raw `/completion` path and the MLX
arms carry no messages to hash — their cache-reuse column is the evidence instead);
**side requests** = no-tools calls beside the agent loop (session titles, summaries),
summed over the arm's grid: how many overlapped an agent turn in time, and how many the
harness abandoned before the server answered (no `timings` came back; counted, not
measured); **model busy** = Σ (`prompt_ms` + `predicted_ms`) /
wall over measured requests — above 100% means two were in flight at once; **round
trips** = agent turns per task; **ctx at exit** = tokens in context at the last agent
turn.""")

    checked = sum(a["ttft_checked"] for a in arms if not a["self_reported"])
    early = sum(a["ttft_lt_prefill"] for a in arms if not a["self_reported"])
    if checked:
        out.append(f"\nInstrument check: the proxy's own first-byte stamp came back "
                   f"earlier than the server's `prompt_ms` on {early} of {checked} "
                   f"requests (llama-server streams a first chunk before a long prefill "
                   f"finishes), so no time-to-first-byte column is printed; the server's "
                   f"prefill time is the wait.")

    out.append("\n#### Per task — cache reuse (median, agent turns 2+) · "
               "wait / later turn (median) · experienced tok/s\n")
    names = [a["arm"] for a in arms]
    body = []
    for task in tasks:
        line = [task]
        for arm in names:
            rs = [r for r in per if r["arm"] == arm and r["task"] == task]
            if not rs:
                line.append("–")
                continue
            r = rs[-1]
            cell = (f"{_pct(_med(r.get('reuse', [])))} · "
                    f"{_num(_med(r.get('wait_later', [])), '{:.1f}s')} · "
                    f"{_num(r['exp_toks'])}")
            if not r["passed"]:
                cell += " (T)" if r["timed_out"] else " (x)"
            line.append(cell)
        body.append(line)
    out.append(_table(["Task"] + names, body))
    out.append("`(x)` failed tests, `(T)` timed out — the numbers still describe the "
               "turns that happened.")
    return "\n".join(out) + "\n"


# -- legacy: what the pre-turns.jsonl artifacts can already say -----------------

def legacy(rows: list, audit: list, tasks: list) -> str:
    """Round trips, prefill per round trip, generated per round trip and experienced
    tok/s from grid.json + the sampler audit alone. For runs made before the proxy
    wrote turn records."""
    rt = defaultdict(int)
    for r in audit:
        rt[(r.get("arm"), r.get("task"))] += 1
    out = ["### What the harness×engine run already says about feel (no turn records)\n"]
    hdr = ["Arm", "pass", "wall (sum)", "generated", "prefill", "round trips",
           "prefill / rt", "gen / rt", "exp. tok/s"]
    body = []
    for arm in dict.fromkeys(r["arm"] for r in rows):
        rs = [r for r in rows if r["arm"] == arm]
        wall = sum(r["wall_s"] for r in rs)
        gen = sum(r["generated"] for r in rs)
        pre = sum(r["prefill"] for r in rs)
        n = sum(rt.get((arm, r["task"]), 0) for r in rs)
        mark = " *" if arm in MLX_ARMS else ""
        body.append([arm + mark, f"{sum(1 for r in rs if r['passed'])}/{len(rs)}",
                     f"{wall:,.0f}s", f"{gen:,}", f"{pre:,}",
                     str(n) if n else "–",
                     f"{pre / n:,.0f}" if n else "–", f"{gen / n:,.0f}" if n else "–",
                     f"{gen / wall:.1f}" if wall else "–"])
    out.append(_table(hdr, body))
    out.append("\n`prefill / rt` is prompt tokens the server evaluated per model call — the "
               "tokens the prefix cache did NOT serve. Same server, same cache, same "
               "tasks; the spread is the harness. `*` self-reported (in-process), no "
               "round-trip count.")
    hdr2 = ["Task"] + [a[0].rstrip(" *") for a in body]
    body2 = []
    for task in tasks:
        line = [task]
        for arm in [a[0].rstrip(" *") for a in body]:
            rs = [r for r in rows if r["arm"] == arm and r["task"] == task]
            if not rs:
                line.append("–")
                continue
            r = rs[-1]
            n = rt.get((arm, task), 0)
            cell = f"{r['generated'] / r['wall_s']:.1f}"
            cell += f" · {r['prefill'] / n:,.0f}/rt" if n else ""
            if not r["passed"]:
                cell += " (T)" if r["timed_out"] else " (x)"
            line.append(cell)
        body2.append(line)
    out.append("\n### Per task — experienced tok/s · prefill tokens per round trip\n")
    out.append(_table(hdr2, body2))
    return "\n".join(out) + "\n"


def build(runs_dir) -> tuple:
    """(markdown, json-able dict) for one or more run directories, or (None, None)
    without rows."""
    rows, turns, _ = load(runs_dir)
    if not rows:
        return None, None
    dirs = run_dirs(runs_dir)
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    # Every row carries the night it came from, so the directory here is only the
    # fallback for a row that does not (an older grid.json).
    per = per_run(rows, turns, dirs[0] if dirs else "")
    arms = aggregate(per)
    return render(arms, per, tasks), {"arms": arms, "per_run": per,
                                      "runs": [_rel(d) for d in dirs]}


# -- convergence: is another night worth a night? ------------------------------

# The columns, in the order the scorecard prints them, with how to format one.
_CONV_COLS = [("tax", "{:,.0f}"), ("sys_chars", "{:,.0f}"), ("n_tools", "{:.0f}"),
              ("wait_first", "{:.1f}"), ("reuse", "{:.3f}"), ("uncached_later", "{:.0f}"),
              ("wait_later", "{:.1f}"), ("prefill_s", "{:.0f}"), ("exp_toks", "{:.1f}")]


def _pooled_by_night(dirs: list) -> list:
    """The pooled per-arm numbers after each night is added: [n=1, n=1..2, n=1..3, ...]."""
    out = []
    for n in range(1, len(dirs) + 1):
        rows, turns, _ = load(dirs[:n])
        out.append({a["arm"]: a for a in aggregate(per_run(rows, turns, dirs[0]))})
    return out


def convergence(runs) -> str:
    """Two questions a reader is entitled to ask of a repeated benchmark: how much does a
    column wobble between nights, and does adding another night still move the published
    number? Both are computed over the llama arms only — the in-process arms' turn-1 wait
    and prefill are not comparable across nights the warm-prefix instrument predates
    (item 4 of the README), and pooling them here would report that gap as noise."""
    dirs = run_dirs(runs)
    if len(dirs) < 2:
        return "convergence needs at least two nights\n"
    per_night = []
    for d in dirs:
        r, t, _ = load([d])
        per_night.append({a["arm"]: a for a in aggregate(per_run(r, t, d))})
    pooled = _pooled_by_night(dirs)
    arms = [a for a in per_night[0] if a not in MLX_ARMS]

    out = [f"### Convergence over {len(dirs)} nights "
           f"({', '.join(os.path.basename(d.rstrip('/')) for d in dirs)})\n",
           "Spread = each arm's own `(max - min) / median` across the nights. Move = how "
           "much\nadding the last night changed the pooled number. llama arms only.\n"]
    hdr = ["column", "spread (med · worst)", f"move on adding night {len(dirs)} (med · worst)"]
    body = []
    for col, _fmt in _CONV_COLS:
        sp, mv = [], []
        for a in arms:
            v = [p[a].get(col) for p in per_night]
            if not any(x is None for x in v) and statistics.median(v):
                sp.append((max(v) - min(v)) / statistics.median(v))
            b, c = pooled[-2][a].get(col), pooled[-1][a].get(col)
            if b and c is not None:
                mv.append(abs(c - b) / b)
        if not sp:
            continue
        body.append([col,
                     f"{100 * statistics.median(sp):.1f}% · {100 * max(sp):.1f}%",
                     f"{100 * statistics.median(mv):.2f}% · {100 * max(mv):.2f}%"])
    out.append(_table(hdr, body))

    # The pass column is a per-cell verdict, so it gets a per-cell answer.
    rows, _, _ = load(dirs)
    cells = defaultdict(list)
    for r in rows:
        cells[(r["arm"], r["task"])].append(bool(r.get("passed")))
    split = [c for c, v in cells.items() if len(set(v)) > 1]
    totals = [sum(1 for r in rows if r["rep"] == i and r.get("passed"))
              for i in range(len(dirs))]
    out.append(f"\npass: per-night totals {', '.join(map(str, totals))} of "
               f"{len(cells)}, but {len(split)} of {len(cells)} (arm, task) cells did not "
               f"agree on all {len(dirs)} nights.\n")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", nargs="+", default=[RUNS_DEFAULT],
                    help="run directories, one per rep; a directory holding repN* dirs "
                         "means all of them (default: _runs)")
    ap.add_argument("--legacy", action="store_true")
    ap.add_argument("--convergence", action="store_true",
                    help="how much each column wobbles between nights, and whether the "
                         "last night still moved the pooled number")
    ap.add_argument("--out", default=None, help="markdown path (default: <runs>/scorecard.md)")
    a = ap.parse_args(argv)
    rows, turns, audit = load(a.runs)
    if not rows:
        print(f"no grid.json under {' '.join(a.runs)}")
        return 1
    dirs = run_dirs(a.runs)
    print(f"{len(dirs)} run(s), {len(rows)} cells: "
          + ", ".join(os.path.basename(d.rstrip("/")) for d in dirs), file=sys.stderr)
    if a.convergence:
        print(convergence(a.runs))
        return 0
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    if a.legacy:
        text = legacy(rows, audit, tasks)
        out = a.out or os.path.join(a.runs[0], "scorecard-legacy.md")
    else:
        if not turns and not any(r["arm"] in MLX_ARMS for r in rows):
            print("no turns.jsonl — this run predates the proxy's turn records; "
                  "use --legacy", file=sys.stderr)
            return 1
        text, data = build(a.runs)
        out = a.out or os.path.join(a.runs[0], "scorecard.md")
        with open(os.path.splitext(out)[0] + ".json", "w") as f:
            json.dump(data, f, indent=1)
    with open(out, "w") as f:
        f.write(text)
    print(text)
    print(f"-> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
