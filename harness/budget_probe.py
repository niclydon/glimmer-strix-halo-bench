#!/usr/bin/env python3
"""Probe --reasoning-budget / --reasoning-effort on Muse Glimmer (scratch, partial offload).

Runs one llama-server per cell on port 5999 with -ngl 99 (full offload,
the production shape; partial offload was implicated in the Oct 18 host
wedge via the amdgpu userptr path). Run only while the prose seat is
unloaded so the instance fits beside the resident agent seat.
the two resident production instances, no draft model (mechanism check, not
a speed test). Cells: budget0, budget256, effort-low. Calls per cell: brief
at production budget 600 (temp 0.7), PIE judge at 400 (temp 0). Streams and
records reasoning vs content chars, finish reason, wall time.
"""
import json, os, signal, subprocess, sys, time, urllib.request

LLAMA = "/home/niclydon/llama.cpp/build/bin/llama-server"
MODEL = "/services/models/muse-glimmer-30b/Muse-Glimmer-30B-UD-Q4_K_XL.gguf"
HERE = os.path.expanduser("~/glimmer-tune")
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"
ENV = dict(os.environ, ROCBLAS_USE_HIPBLASLT="0", GPU_MAX_ALLOC_PERCENT="100",
           LD_LIBRARY_PATH="/home/niclydon/llama.cpp/build/bin:/opt/rocm-7.2.1/lib")

CELLS = [
    ("budget0", ["--reasoning-budget", "0"]),
    ("budget256", ["--reasoning-budget", "256"]),
    ("effort-low", ["--reasoning-effort", "low"]),
]

def healthy(timeout=420):
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

def port_free():
    try:
        urllib.request.urlopen(BASE + "/health", timeout=2)
        return False
    except Exception:
        return True

def call(payload_file, max_tokens, temp):
    payload = json.load(open(os.path.join(HERE, payload_file)))
    body = {"model": "probe", "messages": payload["messages"],
            "max_tokens": max_tokens, "temperature": temp, "stream": True}
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    content, reasoning, finish = [], [], None
    with urllib.request.urlopen(req, timeout=900) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            for ch in chunk.get("choices", []):
                d = ch.get("delta", {})
                if d.get("content"):
                    content.append(d["content"])
                if d.get("reasoning_content"):
                    reasoning.append(d["reasoning_content"])
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    return {"payload": payload_file, "max_tokens": max_tokens,
            "wall_s": round(time.time() - t0, 1), "finish": finish,
            "reasoning_chars": len("".join(reasoning)),
            "content_chars": len("".join(content)),
            "content": "".join(content)}

def main():
    results = {}
    for name, extra in CELLS:
        print(f"=== cell {name}: {extra}", flush=True)
        if not port_free():
            results[name] = {"error": "port 5999 busy"}
            continue
        log = open(os.path.join(HERE, f"probe-{name}.server.log"), "w")
        cmd = [LLAMA, "-m", MODEL, "-ngl", "99", "-fit", "off", "-fa", "on",
               "--host", "127.0.0.1", "--port", str(PORT), "--ctx-size", "8192",
               "--parallel", "1", "--jinja", "--cache-type-k", "f16",
               "--cache-type-v", "f16", "--alias", "probe"] + extra
        proc = subprocess.Popen(cmd, env=ENV, stdout=log, stderr=subprocess.STDOUT)
        try:
            if not healthy():
                results[name] = {"error": "server never became healthy"}
                continue
            cell = {}
            cell["brief"] = call("test-brief.json", 600, 0.7)
            print(f"  brief: finish={cell['brief']['finish']} "
                  f"reasoning={cell['brief']['reasoning_chars']} "
                  f"content={cell['brief']['content_chars']} "
                  f"wall={cell['brief']['wall_s']}", flush=True)
            cell["pie"] = call("test-pie.json", 400, 0.0)
            print(f"  pie: finish={cell['pie']['finish']} "
                  f"reasoning={cell['pie']['reasoning_chars']} "
                  f"content={cell['pie']['content_chars']} "
                  f"wall={cell['pie']['wall_s']}", flush=True)
            results[name] = cell
        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
            time.sleep(5)
    out = os.path.join(HERE, "budget-probe-results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print(f"wrote {out}", flush=True)

if __name__ == "__main__":
    main()
