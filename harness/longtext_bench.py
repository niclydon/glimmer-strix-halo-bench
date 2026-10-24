#!/usr/bin/env python3
"""Long-form bench for the Glimmer prose stanza shape (Crucible).

Waits for reasoning_bench.py to finish, then runs the longtext payload
(~5k tokens in, weekly-synthesis shape) at a 4096 budget under four knob
cells, plus a 2048-budget run under budget1024. Same scratch-port
discipline as reasoning_bench.py: port 5999 only, waits out the prose
seat's idle expiry, never touches llama-swap.
Writes ~/glimmer-tune/longtext-results.json.
"""
import json, os, signal, subprocess, sys, time, urllib.request

BIN = "/home/niclydon/llama.cpp/build/bin/llama-server"
MODEL = "/services/models/muse-glimmer-30b/Muse-Glimmer-30B-UD-Q4_K_XL.gguf"
DRAFT = "/services/models/muse-glimmer-30b/dflash-kquant.gguf"
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"
OUT = os.path.expanduser("~/glimmer-tune/longtext-results.json")

ENV = dict(os.environ)
ENV.update({
    "ROCBLAS_USE_HIPBLASLT": "0",
    "GPU_MAX_ALLOC_PERCENT": "100",
    "LD_LIBRARY_PATH": "/home/niclydon/llama.cpp/build/bin:/opt/rocm-7.2.1/lib",
})

COMMON = [
    BIN, "-ngl", "99", "-fit", "off", "-fa", "on",
    "--host", "127.0.0.1", "--port", str(PORT),
    "--ctx-size", "65536", "--parallel", "1", "--jinja",
    "--cache-type-k", "f16", "--cache-type-v", "f16",
    "--ubatch-size", "256",
    "--spec-type", "draft-dflash", "--model-draft", DRAFT,
    "--spec-draft-n-max", "3", "--spec-draft-n-min", "3",
    "--alias", "muse-glimmer-30b-prose", "-m", MODEL,
]

CELLS = [
    ("control-default", [], [4096]),
    ("budget1024", ["--reasoning-budget", "1024"], [4096, 2048]),
    ("effort-low", ["--reasoning-effort", "low"], [4096]),
    ("reasoning-off", ["--reasoning", "off"], [4096]),
]

def port_answers():
    try:
        urllib.request.urlopen(BASE + "/health", timeout=2)
        return True
    except Exception:
        return False

def prose_resident():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8099/running", timeout=3) as r:
            d = json.load(r)
        names = [m.get("model") or m.get("alias") or "" for m in d.get("running", [])]
        return any("prose" in n for n in names)
    except Exception:
        return False

def wait_health(proc, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False

def call(payload, max_tokens):
    body = {"model": "muse-glimmer-30b-prose", "messages": payload["messages"],
            "temperature": payload.get("temperature", 0.7),
            "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}}
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    content, reasoning, usage, finish = "", "", None, None
    with urllib.request.urlopen(req, timeout=1500) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
            except json.JSONDecodeError:
                continue
            if d.get("usage"):
                usage = d["usage"]
            for ch in d.get("choices", []):
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    content += delta["content"]
                if delta.get("reasoning_content"):
                    reasoning += delta["reasoning_content"]
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    return {"wall_s": round(time.time() - t0, 1), "finish": finish,
            "usage": usage, "content": content,
            "reasoning_chars": len(reasoning), "content_chars": len(content)}

def main():
    # Wait for the knob bench to finish first (same scratch port).
    while subprocess.run(["pgrep", "-f", "reasoning_bench.py"],
                         capture_output=True).returncode == 0:
        print("waiting for reasoning_bench to finish...", flush=True)
        time.sleep(20)
    waited = 0
    while prose_resident() and waited < 900:
        print("waiting for prose seat to idle-expire...", flush=True)
        time.sleep(20)
        waited += 20
    if port_answers():
        print("ABORT: scratch port answers", flush=True)
        sys.exit(1)
    payload = json.load(open(os.path.expanduser("~/glimmer-tune/test-longtext.json")))
    results = {}
    for name, extra, budgets in CELLS:
        print(f"== cell {name}: starting server", flush=True)
        srvlog = open(os.path.expanduser(f"~/glimmer-tune/longtext-{name}.server.log"), "w")
        proc = subprocess.Popen(COMMON + extra, env=ENV,
                                stdout=srvlog, stderr=subprocess.STDOUT,
                                preexec_fn=os.setsid)
        try:
            if not wait_health(proc):
                results[name] = {"error": "server failed to become healthy",
                                 "exit": proc.poll()}
                print(f"   FAILED to start (exit {proc.poll()})", flush=True)
                continue
            results[name] = {}
            for b in budgets:
                r = call(payload, b)
                results[name][f"longtext@{b}"] = r
                print(f"   longtext@{b}: wall={r['wall_s']} finish={r['finish']} "
                      f"reasoning_chars={r['reasoning_chars']} content_chars={r['content_chars']}",
                      flush=True)
            json.dump(results, open(OUT, "w"), indent=1)
        finally:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=20)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        time.sleep(3)
    print("done", flush=True)

if __name__ == "__main__":
    main()
