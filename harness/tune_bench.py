#!/usr/bin/env python3
"""Glimmer tuning bench for Crucible: direct llama-server instances, timings-based.

Runs one llama-server per config cell on a scratch port (never touches
llama-swap on 8099), measures decode rate, prefill rate, and an agent-like
turn from llama.cpp's own `timings` object, then kills the instance.

Axes (from the Oct 18, 2026 tuning research): DFlash --spec-draft-n-max
(16 deployed / 4 / 3 / off), KV cache type (q8_0 deployed / f16),
--ubatch-size (512 default / 256 / 1024). Everything else replicates the
deployed stanza exactly, including env. Measurement cells run --parallel 1
to isolate per-request timings; validate the winner separately at the
production shape (parallel 2, ctx 131072) with --cell-json.

Usage:
  python3 tune_bench.py [--cells name,name,...] [--cell-json '<json>']
                        [--outdir ~/glimmer-tune]

Safety: aborts if the scratch port answers before we start; always kills
its own child in a finally block; refuses to run while a previous result
file for the same cell set exists in the outdir from the last 10 minutes
(cheap double-run guard is intentionally absent: operator discipline).
Results: results-<ts>.json (raw) and results-<ts>.md (table) in outdir.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BIN = "/home/niclydon/llama.cpp/build/bin/llama-server"
MODEL = "/services/models/muse-glimmer-30b/Muse-Glimmer-30B-UD-Q4_K_XL.gguf"
DRAFT = "/services/models/muse-glimmer-30b/dflash-kquant.gguf"
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"

ENV = dict(os.environ)
ENV.update({
    "ROCBLAS_USE_HIPBLASLT": "0",
    "GPU_MAX_ALLOC_PERCENT": "100",
    "LD_LIBRARY_PATH": "/home/niclydon/llama.cpp/build/bin:/opt/rocm-7.2.1/lib",
})

COMMON = [
    "-ngl", "99", "-fit", "off", "-fa", "on",
    "--host", "127.0.0.1", "--port", str(PORT),
    "--ctx-size", "65536", "--parallel", "1", "--jinja",
    "--alias", "muse-glimmer-30b", "-m", MODEL,
]

SPEC = ["--spec-type", "draft-dflash", "--model-draft", DRAFT]


def cell(name, kv="q8_0", nmax="16", ubatch=None, spec=True, extra=None):
    args = list(COMMON) + ["--cache-type-k", kv, "--cache-type-v", kv]
    if spec:
        args += SPEC + ["--spec-draft-n-max", str(nmax), "--spec-draft-n-min", "3"]
    if ubatch:
        args += ["--ubatch-size", str(ubatch)]
    if extra:
        args += extra
    return {"name": name, "args": args}


CELLS = [
    cell("baseline-nmax16-q8"),
    cell("nmax4-q8", nmax="4"),
    cell("nmax4-f16", kv="f16", nmax="4"),
    cell("nmax4-f16-ub256", kv="f16", nmax="4", ubatch=256),
    cell("nmax4-f16-ub1024", kv="f16", nmax="4", ubatch=1024),
    cell("nospec-f16-ub256", kv="f16", spec=False, ubatch=256),
    cell("nmax3-f16-ub256", kv="f16", nmax="3", ubatch=256),
]

AGENT_SYSTEM = (
    "You are an autonomous operations agent for a personal data platform. "
    "You work from an operator backlog. For each item you must read the item, "
    "decide a disposition, and act only through the provided tools. Never "
    "invent identifiers. When a tool result is ambiguous, gather one more "
    "piece of evidence before acting. Keep a written record of every "
    "decision and its evidence. Prefer the least destructive action that "
    "resolves the item. Escalate anything touching credentials, payments, "
    "or deletions of unique data."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "get_item", "description": "Read one backlog item by id",
        "parameters": {"type": "object",
                       "properties": {"id": {"type": "integer"}},
                       "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "set_disposition", "description": "Record a disposition",
        "parameters": {"type": "object",
                       "properties": {"id": {"type": "integer"},
                                      "action": {"type": "string"},
                                      "evidence": {"type": "string"}},
                       "required": ["id", "action", "evidence"]}}},
    {"type": "function", "function": {
        "name": "search_memory", "description": "Search long-term memory",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
]


def filler_prompt(nonce, lines=640):
    body = "\n".join(
        f"Record {i}: the calibration sensor on line {i % 17} reported a "
        f"nominal reading of {1000 + i} units during shift {(i % 3) + 1}, "
        f"flagged routine by operator {(i % 41)}."
        for i in range(lines))
    return (f"Session nonce {nonce}. Read the following maintenance log "
            f"carefully.\n{body}\nHow many records mention shift 2? Answer "
            f"with a single number.")


def post_chat(payload, timeout=300):
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode())
    out["_wall_s"] = round(time.time() - t0, 2)
    return out


def metrics(resp):
    t = resp.get("timings") or {}
    u = resp.get("usage") or {}
    draft_n = t.get("draft_n") or 0
    acc = t.get("draft_n_accepted") or 0
    return {
        "wall_s": resp.get("_wall_s"),
        "prompt_tokens": u.get("prompt_tokens"),
        "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "prompt_tok_s": t.get("prompt_per_second"),
        "decode_tok_s": t.get("predicted_per_second"),
        "draft_accept_rate": round(acc / draft_n, 3) if draft_n else None,
        "finish": (resp.get("choices") or [{}])[0].get("finish_reason"),
    }


def measure(tag, nonce):
    """Three measures; each returns a metrics dict."""
    out = {}
    r = post_chat({
        "model": "muse-glimmer-30b", "temperature": 0, "max_tokens": 512,
        "messages": [{"role": "user", "content":
                      f"Nonce {nonce}. Write a long, detailed essay about "
                      "the history of lighthouses in New England, covering "
                      "construction, keepers, and famous storms."}]})
    out["decode"] = metrics(r)
    r = post_chat({
        "model": "muse-glimmer-30b", "temperature": 0, "max_tokens": 8,
        "messages": [{"role": "user", "content": filler_prompt(nonce)}]})
    out["prefill"] = metrics(r)
    r = post_chat({
        "model": "muse-glimmer-30b", "temperature": 0, "max_tokens": 400,
        "tools": TOOLS, "tool_choice": "auto",
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM},
            {"role": "user", "content":
             f"Nonce {nonce}. Item 4471 is a report that a nightly backup "
             "job has failed three times with a disk-space error. Work the "
             "item: first read it, then record your disposition."}]})
    m = metrics(r)
    tc = ((r.get("choices") or [{}])[0].get("message") or {}).get("tool_calls")
    m["tool_calls"] = len(tc) if tc else 0
    out["agent"] = m
    return out


def wait_health(proc, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early rc={proc.returncode}")
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
                if r.status == 200:
                    return round(time.time() - t0, 1)
        except Exception:
            time.sleep(2)
    raise RuntimeError("health timeout")


def port_busy():
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def run_cell(c, outdir):
    log_path = os.path.join(outdir, f"server-{c['name']}.log")
    with open(log_path, "w") as log:
        proc = subprocess.Popen([BIN] + c["args"], stdout=log,
                                stderr=subprocess.STDOUT, env=ENV)
        try:
            load_s = wait_health(proc)
            runs = [measure(c["name"], nonce=f"{c['name']}-{i}")
                    for i in range(2)]
            return {"cell": c["name"], "load_s": load_s, "runs": runs,
                    "args": c["args"]}
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=15)
            time.sleep(3)


def render_md(results):
    lines = ["# Glimmer tuning bench results", ""]
    lines.append("| cell | load s | decode tok/s | prefill tok/s | "
                 "agent decode tok/s | agent draft acc | agent tool calls |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        def avg(key, sub):
            vals = [run[key][sub] for run in r["runs"]
                    if run[key].get(sub) is not None]
            return round(sum(vals) / len(vals), 2) if vals else "-"
        lines.append(
            f"| {r['cell']} | {r['load_s']} | {avg('decode', 'decode_tok_s')} "
            f"| {avg('prefill', 'prompt_tok_s')} | "
            f"{avg('agent', 'decode_tok_s')} | "
            f"{avg('agent', 'draft_accept_rate')} | "
            f"{avg('agent', 'tool_calls')} |")
    lines.append("")
    lines.append("Rates are llama.cpp timings (predicted/prompt per-second), "
                 "mean of 2 runs per cell, temperature 0, parallel 1.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="")
    ap.add_argument("--cell-json", default="")
    ap.add_argument("--outdir", default=os.path.expanduser("~/glimmer-tune"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    if port_busy():
        sys.exit(f"ABORT: something already answers on port {PORT}")
    if a.cell_json:
        cells = [json.loads(a.cell_json)]
    elif a.cells:
        want = set(a.cells.split(","))
        cells = [c for c in CELLS if c["name"] in want]
        if not cells:
            sys.exit(f"no cells matched {a.cells}")
    else:
        cells = CELLS
    ts = time.strftime("%Y%m%d-%H%M%S")
    results = []
    for c in cells:
        print(f"== cell {c['name']} ==", flush=True)
        try:
            results.append(run_cell(c, a.outdir))
        except Exception as e:
            results.append({"cell": c["name"], "error": str(e)})
            print(f"cell failed: {e}", flush=True)
    raw = os.path.join(a.outdir, f"results-{ts}.json")
    with open(raw, "w") as f:
        json.dump(results, f, indent=1)
    ok = [r for r in results if "runs" in r]
    if ok:
        md = os.path.join(a.outdir, f"results-{ts}.md")
        with open(md, "w") as f:
            f.write(render_md(ok))
        print(open(md).read())
    print(f"raw: {raw}")


if __name__ == "__main__":
    main()
