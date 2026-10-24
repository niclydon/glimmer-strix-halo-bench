#!/usr/bin/env python3
"""Furnace W1 Phase 2 DFlash sweep via scratch llama-server on port 5999.
llama-bench b11719 rejects -md/--spec-* (verified 2026-10-20: 'error: invalid parameter for argument: -md'),
so DFlash cells run through llama-server per the task fallback.
Settings: KV f16, ubatch 256, flash-attn on, ngl 99, temp 0, n_predict 128, cache_prompt false.
Depths: 0 (short prompt) and 32768 (long filler prompt; actual prompt_n recorded from timings).
Reps: 3 per cell. Draft acceptance extracted from server log + timings where present.
"""
import json, os, re, signal, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~")
MODEL = os.path.join(HOME, "glimmer-furnace-bench/models/Muse-Glimmer-30B-UD-Q4_K_XL.gguf")
DRAFT = os.path.join(HOME, "glimmer-furnace-bench/models/dflash-kquant.gguf")
OUTDIR = os.path.join(HOME, "glimmer-furnace-bench/results-w1")
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"

BUILDS = {
    "hip": (os.path.join(HOME, "llama.cpp-bench/build-hip/bin"),
            {"LD_LIBRARY_PATH": os.path.join(HOME, "llama.cpp-bench/build-hip/bin") + ":/opt/rocm-7.2.1/lib",
             "ROCBLAS_USE_HIPBLASLT": "0", "GPU_MAX_ALLOC_PERCENT": "100"}),
    "vulkan": (os.path.join(HOME, "llama.cpp-bench/build-vulkan/bin"),
               {"LD_LIBRARY_PATH": os.path.join(HOME, "llama.cpp-bench/build-vulkan/bin")}),
}

FILLER_UNIT = "The quick brown fox jumps over the lazy dog near the river bank. "
# ~14 tokens per unit by llama tokenizer estimate; actual prompt_n is recorded from timings and is authoritative.

def make_prompt(depth, rep):
    if depth == 0:
        return f"Story seed {rep}: Write a short story about a lighthouse keeper who finds a mysterious map."
    reps = 2400  # target ~32768 tokens; authoritative count from timings.prompt_n
    return (FILLER_UNIT * reps) + f"\nVariation {rep}: Now write a short story about a lighthouse keeper who finds a mysterious map."

def healthy(timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False

def completion(prompt, n_predict=128):
    body = {"prompt": prompt, "n_predict": n_predict, "temperature": 0.0,
            "cache_prompt": False, "stream": False}
    req = urllib.request.Request(BASE + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.loads(r.read().decode())
    data["_wall_s"] = round(time.time() - t0, 3)
    return data

def extract_acceptance(logpath, offset):
    try:
        with open(logpath, errors="replace") as f:
            f.seek(offset)
            text = f.read()
            new_offset = f.tell()
    except Exception as e:
        return None, 0
    rates = re.findall(r"draft acceptance rate\s*=\s*([0-9.]+).*?(\d+)\s*accepted.*?(\d+)\s*generated", text, re.S)
    acc_lines = [ln.strip() for ln in text.splitlines() if "accept" in ln.lower()]
    return {"rates": rates, "lines": acc_lines[-5:]}, new_offset

def run_config(build, nmax):
    bindir, extra_env = BUILDS[build]
    env = dict(os.environ, **extra_env)
    label = "off" if nmax is None else f"nmax{nmax}"
    logpath = os.path.join(OUTDIR, f"dflash-server-{build}-{label}.log")
    log = open(logpath, "w")
    cmd = [os.path.join(bindir, "llama-server"), "-m", MODEL, "-ngl", "99", "-fit", "off",
           "-fa", "on", "--host", "127.0.0.1", "--port", str(PORT),
           "--ctx-size", "40960", "--parallel", "1", "-ub", "256", "-b", "2048",
           "--cache-type-k", "f16", "--cache-type-v", "f16", "--alias", "bench"]
    if nmax is not None:
        cmd += ["--spec-type", "draft-dflash", "--model-draft", DRAFT, "--spec-draft-n-max", str(nmax)]
    print(f"=== {build} {label} cmd: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    result = {"build": build, "n_max": nmax, "method": "llama-server scratch port 5999, /completion, temp 0, cache_prompt false",
              "kv": "f16", "ubatch": 256, "ctx_size": 40960, "cells": {}}
    try:
        if not healthy():
            result["error"] = "server never became healthy"
            return result
        # warmup (discarded)
        try:
            completion(make_prompt(0, 99), n_predict=32)
            print(f"  {build} {label} warmup done", flush=True)
        except Exception as e:
            result["warmup_error"] = str(e)
        offset = os.path.getsize(logpath)
        for depth in (0, 32768):
            reps = []
            for rep in range(3):
                try:
                    data = completion(make_prompt(depth, rep))
                    acc, offset = extract_acceptance(logpath, offset)
                    t = data.get("timings", {})
                    rec = {"rep": rep, "wall_s": data.get("_wall_s"),
                           "prompt_n": t.get("prompt_n"), "prompt_ms": t.get("prompt_ms"),
                           "prompt_per_second": t.get("prompt_per_second"),
                           "predicted_n": t.get("predicted_n"), "predicted_ms": t.get("predicted_ms"),
                           "predicted_per_second": t.get("predicted_per_second"),
                           "timings_raw": t, "acceptance_from_log": acc,
                           "content_head": (data.get("content") or "")[:200]}
                    reps.append(rec)
                    print(f"  {build} {label} depth={depth} rep={rep} prompt_n={rec['prompt_n']} pp_tps={rec['prompt_per_second']} tg_tps={rec['predicted_per_second']} acc={acc}", flush=True)
                except Exception as e:
                    reps.append({"rep": rep, "error": str(e)})
                    print(f"  {build} {label} depth={depth} rep={rep} ERROR {e}", flush=True)
            result["cells"][str(depth)] = reps
        return result
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        time.sleep(5)

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    results = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "note": "llama-bench b11719 has no draft/spec parameters (invalid parameter -md verified); DFlash via scratch llama-server port 5999 harness pattern.",
               "configs": []}
    order = [None, 2, 3, 4, 6, 8, 15]
    for build in ("hip", "vulkan"):
        for nmax in order:
            r = run_config(build, nmax)
            results["configs"].append(r)
            with open(os.path.join(OUTDIR, "dflash-server-results.json"), "w") as f:
                json.dump(results, f, indent=1)
            print(f"wrote partial results after {build} {nmax}", flush=True)
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(OUTDIR, "dflash-server-results.json"), "w") as f:
        json.dump(results, f, indent=1)
    print("DFLASH SWEEP COMPLETE", flush=True)

if __name__ == "__main__":
    main()
