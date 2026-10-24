#!/usr/bin/env python3
"""Furnace Bench W3 Phase 4: quant ladder + agent subset + 30-min soak + vision.
Runs ON furnace inside the maintenance window (production stopped).
Scratch llama-server on port 5999 only. HIP bench build b11719.
Power sampler runs externally (w3_power_sampler.py); this script records
phase boundary epochs into phases.csv for perf-per-watt slicing.
Incremental JSON: ~/glimmer-furnace-bench/results-w3/results-w3.json
"""
import base64, hashlib, json, os, signal, struct, subprocess, sys, time, zlib
import urllib.request
import urllib.error

HOME = os.path.expanduser("~")
MODELS = os.path.join(HOME, "glimmer-furnace-bench/models")
OUTDIR = os.path.join(HOME, "glimmer-furnace-bench/results-w3")
DRAFT = os.path.join(MODELS, "dflash-kquant.gguf")
MMPROJ = os.path.join(MODELS, "mmproj-kquant.gguf")
BENCH_BIN = os.path.join(HOME, "llama.cpp-bench/build-hip/bin/llama-bench")
SERVER_CANDS = [os.path.join(HOME, "llama.cpp-bench/build-hip/bin/llama-server"),
                "/services/llama.cpp/build/bin/llama-server"]
SERVER_BIN = next((p for p in SERVER_CANDS if os.path.exists(p)), SERVER_CANDS[-1])
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"
ENV = dict(os.environ,
           LD_LIBRARY_PATH=os.path.join(HOME, "llama.cpp-bench/build-hip/bin:/opt/rocm-7.2.1/lib"),
           ROCBLAS_USE_HIPBLASLT="0", GPU_MAX_ALLOC_PERCENT="100")
QUANTS = [("UD-Q4_K_XL", "Muse-Glimmer-30B-UD-Q4_K_XL.gguf"),
          ("UD-Q5_K_XL", "Muse-Glimmer-30B-UD-Q5_K_XL.gguf"),
          ("UD-Q6_K_XL", "Muse-Glimmer-30B-UD-Q6_K_XL.gguf")]
RESULTS = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "server_bin": SERVER_BIN, "sections": {}}

def save():
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "results-w3.json"), "w") as f:
        json.dump(RESULTS, f, indent=1)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def phase(name, tag, t0, t1):
    with open(os.path.join(OUTDIR, "phases.csv"), "a") as f:
        f.write(f"{name},{tag},{t0:.3f},{t1:.3f}\n")
    log(f"PHASE {name}/{tag}: {t1-t0:.0f}s")

def nonce():
    return hashlib.sha256(os.urandom(16)).hexdigest()[:12]

# ---------------- llama-bench ladder ----------------
def section_ladder():
    sec = {"method": "llama-bench HIP build b11719, -p 512 -n 128 -d 0,32768 "
                     "-ngl 99 -fa 1 -r 3 -o json, default ubatch 512 (W1 core shape).",
           "cells": []}
    for tag, fname in QUANTS:
        path = os.path.join(MODELS, fname)
        cell = {"quant": tag, "file": fname}
        if not os.path.exists(path):
            # wait up to 30 min for download to land
            for _ in range(60):
                if os.path.exists(path) and os.path.exists(os.path.join(OUTDIR, "download.done")):
                    break
                time.sleep(30)
        if not os.path.exists(path):
            cell["error"] = "file missing after wait; quant skipped"
            sec["cells"].append(cell); RESULTS["sections"]["ladder"] = sec; save()
            log(f"ladder {tag}: MISSING, skipped")
            continue
        cell["size_bytes"] = os.path.getsize(path)
        outj = os.path.join(OUTDIR, f"llamabench-{tag}.json")
        errf = os.path.join(OUTDIR, f"llamabench-{tag}.err")
        t0 = time.time()
        with open(outj, "w") as fo, open(errf, "w") as fe:
            rc = subprocess.run([BENCH_BIN, "-m", path, "-p", "512", "-n", "128",
                                 "-d", "0,32768", "-ngl", "99", "-fa", "1", "-r", "3",
                                 "-o", "json"], stdout=fo, stderr=fe, env=ENV).returncode
        t1 = time.time()
        phase("ladder", tag, t0, t1)
        cell["rc"] = rc
        try:
            with open(outj) as f:
                cell["bench"] = json.load(f)
        except Exception as e:
            cell["parse_error"] = str(e)
        sec["cells"].append(cell); RESULTS["sections"]["ladder"] = sec; save()
        log(f"ladder {tag}: rc={rc}")
    RESULTS["sections"]["ladder"] = sec; save()
    log("SECTION ladder done")

# ---------------- server helper ----------------
class Server:
    def __init__(self, label, model, extra):
        self.label = label
        self.load_s = None
        logpath = os.path.join(OUTDIR, f"server-{label}.log")
        self.logf = open(logpath, "w")
        cmd = [SERVER_BIN, "-m", model, "-ngl", "99", "-fit", "off", "-fa", "on",
               "--host", "127.0.0.1", "--port", str(PORT), "--jinja",
               "--alias", "bench"] + extra
        log(f"START {label}: {' '.join(cmd)}")
        self.t0 = time.time()
        self.proc = subprocess.Popen(cmd, env=ENV, stdout=self.logf,
                                     stderr=subprocess.STDOUT)
        self.cmd = cmd
    def wait_health(self, timeout=600):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server {self.label} exited rc={self.proc.returncode}")
            try:
                with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
                    if r.status == 200:
                        self.load_s = round(time.time() - self.t0, 1)
                        log(f"  {self.label} healthy after {self.load_s}s")
                        return True
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError(f"server {self.label} never healthy")
    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait(timeout=10)
        self.logf.close()
        log(f"  {self.label} stopped")
        time.sleep(4)

def draft_args(nmax=15):
    return ["--spec-type", "draft-dflash", "--model-draft", DRAFT,
            "--spec-draft-n-max", str(nmax)]

def post(path, payload, timeout=1800):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    return data, time.time() - t0

def completion(prompt, n_predict=512, temp=0.0, cache_prompt=False, seed=None):
    p = {"prompt": prompt, "n_predict": n_predict, "temperature": temp,
         "cache_prompt": cache_prompt, "stream": False}
    if seed is not None:
        p["seed"] = seed
    return post("/completion", p)

def chat(messages, max_tokens=1024, temp=0.0, tools=None, kwargs=None, extra=None):
    p = {"model": "bench", "messages": messages, "max_tokens": max_tokens,
         "temperature": temp, "stream": False}
    if tools:
        p["tools"] = tools; p["tool_choice"] = "auto"
    if kwargs:
        p["chat_template_kwargs"] = {"reasoning_strength": kwargs}
    if extra:
        p.update(extra)
    return post("/v1/chat/completions", p)

def split_reasoning(msg):
    rc = msg.get("reasoning_content") or ""
    content = msg.get("content") or ""
    if "</think>" in content:
        think, _, rest = content.partition("</think>")
        return (rc + think), rest.strip()
    return rc, content.strip()

# ---------------- agent subset (from W2) ----------------
TOOLS = [
    {"type": "function", "function": {"name": "get_weather", "description": "Get current weather for a city",
     "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "set_timer", "description": "Set a countdown timer",
     "parameters": {"type": "object", "properties": {"minutes": {"type": "integer"}}, "required": ["minutes"]}}},
    {"type": "function", "function": {"name": "search_contacts", "description": "Search the address book for a person",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_note", "description": "Create a note with a title",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "convert_currency", "description": "Convert an amount between currencies",
     "parameters": {"type": "object", "properties": {"amount": {"type": "number"},
        "from_currency": {"type": "string"}, "to_currency": {"type": "string"}},
        "required": ["amount", "from_currency", "to_currency"]}}},
]
TOOL_CASES = [
    ("What's the weather like in Chicago right now?", "get_weather", "city"),
    ("What is the weather in Denver today?", "get_weather", "city"),
    ("Tell me the current weather for Seattle.", "get_weather", "city"),
    ("How is the weather in Miami right now?", "get_weather", "city"),
    ("Set a timer for 25 minutes.", "set_timer", "minutes"),
    ("Set a timer for 10 minutes.", "set_timer", "minutes"),
    ("Start a 45 minute countdown timer.", "set_timer", "minutes"),
    ("Set a countdown of 5 minutes.", "set_timer", "minutes"),
    ("Look up Mary Jones in my contacts.", "search_contacts", "name"),
    ("Find John Smith in my contacts.", "search_contacts", "name"),
    ("Look up the contact for Robert Brown.", "search_contacts", "name"),
    ("Search my contacts for Patricia Davis.", "search_contacts", "name"),
    ("Create a note titled 'Trip packing list'.", "create_note", "title"),
    ("Create a note titled 'Grocery list'.", "create_note", "title"),
    ("Make a note called 'Meeting notes Oct 21'.", "create_note", "title"),
    ("Create a note with the title 'Bench ideas'.", "create_note", "title"),
    ("Convert 250 US dollars to euros.", "convert_currency", "amount"),
    ("Convert 100 euros to US dollars.", "convert_currency", "amount"),
    ("Convert 75 British pounds to Japanese yen.", "convert_currency", "amount"),
    ("Convert 500 Canadian dollars to US dollars.", "convert_currency", "amount"),
]

def agent_subset(tag, model_path):
    res = {"quant": tag}
    srv = Server(f"agent-{tag}", model_path,
                 ["--ctx-size", "65536", "--parallel", "1", "-ub", "512", "-b", "2048",
                  "--cache-type-k", "f16", "--cache-type-v", "f16",
                  "--chat-template-kwargs", '{"reasoning_strength":"low"}']
                 + draft_args(15))
    t0 = time.time()
    try:
        srv.wait_health()
        res["load_s"] = srv.load_s
        chat([{"role": "user", "content": "Warmup: say hello."}], max_tokens=64)
        d1 = []; ok = 0
        for prompt, want_fn, want_key in TOOL_CASES:
            rec = {"prompt": prompt, "want": want_fn}
            try:
                d, w = chat([{"role": "user", "content": f"{prompt} [ref {nonce()}]"}],
                            max_tokens=1024, tools=TOOLS)
                msg = d["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                rec["wall_s"] = round(w, 2)
                if tcs:
                    fn = tcs[0]["function"]
                    rec["got"] = fn.get("name")
                    try:
                        args = json.loads(fn["arguments"])
                        rec["valid"] = bool(fn["name"] == want_fn and want_key in args)
                    except Exception as e:
                        rec["valid"] = False; rec["args_error"] = str(e)
                else:
                    rec["valid"] = False; rec["got"] = None
                ok += 1 if rec["valid"] else 0
            except Exception as e:
                rec["valid"] = False; rec["error"] = str(e)
            d1.append(rec)
        res["tool_calls"] = {"score": f"{ok}/20", "cases": d1}
        schemas = [
            ("person", {"name": "string", "age": "integer", "city": "string"}),
            ("book", {"title": "string", "author": "string", "year": "integer"}),
            ("product", {"product": "string", "price": "number", "in_stock": "boolean"}),
            ("event", {"event": "string", "date": "string", "location": "string"}),
            ("recipe", {"dish": "string", "servings": "integer", "minutes": "integer"}),
        ]
        d2 = []; raw_ok = strip_ok = ref_ok = 0
        for name, fields in schemas:
            n = nonce()
            keys = ", ".join(f"{k} ({v})" for k, v in fields.items())
            prompt = (f"Invent a fictional {name}. Return ONLY a JSON object with keys: "
                      f"{keys}, and ref (string) with value \"{n}\". No other text.")
            rec = {"case": name, "nonce": n}
            try:
                d, w = chat([{"role": "user", "content": prompt}], max_tokens=1024)
                msg = d["choices"][0]["message"]
                content = msg.get("content") or ""
                _, final = split_reasoning(msg)
                rec["wall_s"] = round(w, 2)
                rec["raw_valid"] = False; rec["stripped_valid"] = False; rec["ref_match"] = False
                try:
                    json.loads(content.strip()); rec["raw_valid"] = True; raw_ok += 1
                except Exception:
                    pass
                try:
                    obj = json.loads(final); rec["stripped_valid"] = True; strip_ok += 1
                    if obj.get("ref") == n:
                        rec["ref_match"] = True; ref_ok += 1
                except Exception:
                    pass
                rec["content_head"] = content[:160]
            except Exception as e:
                rec["error"] = str(e)
            d2.append(rec)
        res["json"] = {"raw_valid": f"{raw_ok}/5", "stripped_valid": f"{strip_ok}/5",
                       "ref_match": f"{ref_ok}/5", "cases": d2}
    except Exception as e:
        res["error"] = str(e); log(f"agent {tag} ERROR {e}")
    finally:
        srv.stop()
    phase("agent", tag, t0, time.time())
    return res

def section_agent():
    sec = {"method": "W2 agent-suite subset: 20 tool-call prompts + 5 JSON-validity "
                     "prompts, direct llama-server, ctx 65536, parallel 1, KV f16, "
                     "DFlash n-max 15, reasoning_strength low, temp 0, unique nonce per call.",
           "cells": []}
    for tag, fname in QUANTS:
        path = os.path.join(MODELS, fname)
        if not os.path.exists(path):
            sec["cells"].append({"quant": tag, "error": "file missing; skipped"})
            continue
        sec["cells"].append(agent_subset(tag, path))
        RESULTS["sections"]["agent"] = sec; save()
    RESULTS["sections"]["agent"] = sec; save()
    log("SECTION agent done")

# ---------------- soak ----------------
def section_soak():
    sec = {"method": "UD-Q4_K_XL (production quant), ctx 32768, parallel 1, KV f16, "
                     "DFlash n-max 15, temp 0, repeated /completion n_predict 1024 "
                     "prose generations back-to-back for 1800 s. Power sampled "
                     "externally at 1 Hz (power.csv); slice by phases.csv soak row.",
           "target_s": 1800}
    path = os.path.join(MODELS, QUANTS[0][1])
    srv = Server("soak-q4", path,
                 ["--ctx-size", "32768", "--parallel", "1", "-ub", "512", "-b", "2048",
                  "--cache-type-k", "f16", "--cache-type-v", "f16"] + draft_args(15))
    reqs = []
    total_tok = 0
    t_start = None
    try:
        srv.wait_health()
        completion("Warmup: say hello.", n_predict=64)
        t_start = time.time()
        i = 0
        while time.time() - t_start < 1800:
            prompt = (f"[{nonce()}] Write a long, detailed essay about the history of "
                      f"lighthouses and maritime navigation, covering construction, "
                      f"keepers, storms, and famous lights around the world.")
            try:
                d, w = completion(prompt, n_predict=1024, seed=1000 + i)
                t = d.get("timings", {}) or {}
                pn = t.get("predicted_n") or 0
                total_tok += pn
                reqs.append({"i": i, "wall_s": round(w, 2), "predicted_n": pn,
                             "tg_tps": t.get("predicted_per_second"),
                             "pp_tps": t.get("prompt_per_second")})
                log(f"  soak req{i}: tok={pn} tg={t.get('predicted_per_second')} total={total_tok}")
            except Exception as e:
                reqs.append({"i": i, "error": str(e)}); log(f"  soak req{i} ERROR {e}")
            i += 1
        t_end = time.time()
        phase("soak", "UD-Q4_K_XL", t_start, t_end)
        sec["elapsed_s"] = round(t_end - t_start, 1)
        sec["requests"] = reqs
        sec["total_predicted_tokens"] = total_tok
        sec["mean_tg_tps"] = round(total_tok / (t_end - t_start), 2) if t_end > t_start else None
    except Exception as e:
        sec["error"] = str(e); log(f"soak ERROR {e}")
        if t_start:
            phase("soak", "UD-Q4_K_XL", t_start, time.time())
    finally:
        srv.stop()
    RESULTS["sections"]["soak"] = sec; save()
    log("SECTION soak done")

# ---------------- vision ----------------
def make_test_png(path):
    """Synthetic ground-truth image, stdlib PNG: white bg, red rectangle
    top-left, blue circle center, green square bottom-right, black bar bottom."""
    W, H = 480, 360
    px = bytearray()
    for y in range(H):
        px.append(0)
        for x in range(W):
            r, g, b = 255, 255, 255
            if x < 160 and y < 120:
                r, g, b = 220, 30, 30
            dx, dy = x - 240, y - 150
            if dx * dx + dy * dy < 55 * 55:
                r, g, b = 30, 60, 220
            if x >= 340 and x < 440 and y >= 220 and y < 320:
                r, g, b = 30, 180, 60
            if y >= 335:
                r, g, b = 0, 0, 0
            px += bytes((r, g, b))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(px), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

def section_vision():
    sec = {"method": "llama-server --mmproj mmproj-kquant.gguf, UD-Q4_K_XL, "
                     "ctx 8192, parallel 1. Synthetic 480x360 PNG with known "
                     "ground truth: red rectangle top-left, blue circle center, "
                     "green square bottom-right, black horizontal bar at bottom, "
                     "white background. One chat completion with image_url data URI.",
           "attempts": []}
    img = os.path.join(OUTDIR, "vision-test.png")
    size = make_test_png(img)
    sec["image_bytes"] = size
    path = os.path.join(MODELS, QUANTS[0][1])
    for attempt in (1, 2):
        att = {"attempt": attempt}
        srv = Server(f"vision{attempt}", path,
                     ["--ctx-size", "8192", "--parallel", "1",
                      "--mmproj", MMPROJ])
        t0 = time.time()
        try:
            srv.wait_health(timeout=600)
            att["load_s"] = srv.load_s
            with open(img, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            payload_msgs = [{"role": "user", "content": [
                {"type": "text", "text": "Describe this image in detail: list every shape you see, its color, and where it is located in the image."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]
            d, w = chat(payload_msgs, max_tokens=512, temp=0.0)
            msg = d["choices"][0]["message"]
            _, final = split_reasoning(msg)
            tm = d.get("timings", {}) or {}
            att["wall_s"] = round(w, 2)
            att["response"] = final or (msg.get("content") or "")
            att["usage"] = d.get("usage")
            att["timings"] = {"prompt_n": tm.get("prompt_n"),
                              "prompt_per_second": tm.get("prompt_per_second"),
                              "predicted_n": tm.get("predicted_n"),
                              "predicted_per_second": tm.get("predicted_per_second")}
            sec["attempts"].append(att)
            phase("vision", f"attempt{attempt}", t0, time.time())
            log(f"vision attempt{attempt}: wall={att['wall_s']} resp_head={att['response'][:100]!r}")
            break
        except Exception as e:
            att["error"] = str(e)
            sec["attempts"].append(att)
            log(f"vision attempt{attempt} ERROR {e}")
        finally:
            srv.stop()
    RESULTS["sections"]["vision"] = sec; save()
    log("SECTION vision done")

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if os.path.exists(os.path.join(OUTDIR, "results-w3.json")) and which != "all":
        with open(os.path.join(OUTDIR, "results-w3.json")) as f:
            RESULTS.update(json.load(f))
    if which in ("all", "ladder"): section_ladder()
    if which in ("all", "agent"): section_agent()
    if which in ("all", "soak"): section_soak()
    if which in ("all", "vision"): section_vision()
    RESULTS["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
    log("BENCH W3 COMPLETE")

if __name__ == "__main__":
    main()
