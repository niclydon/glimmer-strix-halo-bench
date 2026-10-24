#!/usr/bin/env python3
"""Furnace Bench W2 Phase 3: serving shape + agent workload.
Runs ON furnace inside the maintenance window (production stopped).
Scratch llama-server on port 5999 only, production HIP build
/services/llama.cpp/build/bin/llama-server (b11719).
Writes incremental JSON to ~/glimmer-furnace-bench/results-w2/.
Direct server path (no Forge): JSON validity is therefore uncached by
construction; agent prompts additionally carry unique nonces per call.
"""
import hashlib, json, os, re, signal, subprocess, sys, threading, time
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
MODEL = os.path.join(HOME, "glimmer-furnace-bench/models/Muse-Glimmer-30B-UD-Q4_K_XL.gguf")
DRAFT = os.path.join(HOME, "glimmer-furnace-bench/models/dflash-kquant.gguf")
OUTDIR = os.path.join(HOME, "glimmer-furnace-bench/results-w2")
BIN = "/services/llama.cpp/build/bin/llama-server"
PORT = 5999
BASE = f"http://127.0.0.1:{PORT}"
ENV = dict(os.environ,
           LD_LIBRARY_PATH="/services/llama.cpp/build/bin:/opt/rocm-7.2.1/lib",
           ROCBLAS_USE_HIPBLASLT="0", GPU_MAX_ALLOC_PERCENT="100")
RESULTS = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sections": {}}
FILLER_UNIT = "The quick brown fox jumps over the lazy dog near the river bank. "
# measured W1: ~14.01 tok/unit via /completion prompt_n

def save():
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "results-w2.json"), "w") as f:
        json.dump(RESULTS, f, indent=1)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def filler(target_tokens, tail):
    units = max(1, int(target_tokens / 14.01))
    return FILLER_UNIT * units + tail

def nonce():
    return hashlib.sha256(os.urandom(16)).hexdigest()[:12]

class Server:
    def __init__(self, label, extra):
        self.label = label
        logpath = os.path.join(OUTDIR, f"server-{label}.log")
        self.logf = open(logpath, "w")
        cmd = [BIN, "-m", MODEL, "-ngl", "99", "-fit", "off", "-fa", "on",
               "--host", "127.0.0.1", "--port", str(PORT), "--jinja",
               "--alias", "bench"] + extra
        log(f"START {label}: {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd, env=ENV, stdout=self.logf,
                                     stderr=subprocess.STDOUT)
        self.cmd = cmd
    def wait_health(self, timeout=420):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server {self.label} exited rc={self.proc.returncode}")
            try:
                with urllib.request.urlopen(BASE + "/health", timeout=3) as r:
                    if r.status == 200:
                        log(f"  {self.label} healthy after {time.time()-t0:.0f}s")
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

def tstats(recs, key):
    vals = [r[key] for r in recs if r.get(key) is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5 if len(vals) > 1 else 0.0
    return {"mean": round(m, 2), "stddev": round(sd, 2), "vals": [round(v, 2) for v in vals]}

def timings_rec(data, wall):
    t = data.get("timings", {}) or {}
    return {"wall_s": round(wall, 2), "prompt_n": t.get("prompt_n"),
            "cache_n": t.get("cache_n"), "prompt_ms": t.get("prompt_ms"),
            "prompt_per_second": t.get("prompt_per_second"),
            "predicted_n": t.get("predicted_n"), "predicted_ms": t.get("predicted_ms"),
            "predicted_per_second": t.get("predicted_per_second"),
            "draft_n": t.get("draft_n"), "draft_n_accepted": t.get("draft_n_accepted")}

# ---------------- Section A: serving matrix ----------------
def section_matrix():
    sec = {"method": "llama-server /completion, temp 0, cache_prompt false, seed 7, "
                     "n_predict 512, DFlash n-max 15, KV f16, ub 512, b 2048, "
                     "reasoning kwargs n/a (raw completion). 2 reps. "
                     "Aggregate = total predicted tokens / max request wall.",
           "cells": []}
    gen_prompt = ("Write a detailed explanation of how photosynthesis converts "
                  "sunlight into chemical energy, covering the light-dependent "
                  "reactions and the Calvin cycle in depth, step by step.")
    for ctx, par in [(65536, 1), (65536, 2), (65536, 4),
                     (131072, 1), (131072, 2), (131072, 4)]:
        label = f"matrix-ctx{ctx}-par{par}"
        srv = Server(label, ["--ctx-size", str(ctx), "--parallel", str(par),
                             "-ub", "512", "-b", "2048",
                             "--cache-type-k", "f16", "--cache-type-v", "f16"]
                            + draft_args(15))
        cell = {"ctx": ctx, "parallel": par, "reps": []}
        try:
            srv.wait_health()
            completion("Warmup: say hello.", n_predict=64)  # discarded
            for rep in range(2):
                barrier = threading.Barrier(par)
                recs = [None] * par
                def work(i):
                    barrier.wait()
                    try:
                        d, w = completion(f"[{nonce()}] {gen_prompt}", n_predict=512, seed=7)
                        recs[i] = timings_rec(d, w)
                    except Exception as e:
                        recs[i] = {"error": str(e)}
                with ThreadPoolExecutor(max_workers=par) as ex:
                    list(ex.map(work, range(par)))
                ok = [r for r in recs if r and "error" not in r]
                tot_tok = sum(r["predicted_n"] or 0 for r in ok)
                max_wall = max((r["wall_s"] for r in ok), default=None)
                agg = round(tot_tok / max_wall, 2) if max_wall else None
                cell["reps"].append({"rep": rep, "requests": recs,
                                     "aggregate_tps": agg})
                log(f"  {label} rep{rep}: agg={agg} per-slot={[r.get('predicted_per_second') for r in recs]}")
        except Exception as e:
            cell["error"] = str(e); log(f"  {label} ERROR {e}")
        finally:
            srv.stop()
        cell["per_slot_tps"] = tstats([r for rep in cell["reps"] for r in rep["requests"]
                                      if "error" not in r], "predicted_per_second")
        cell["aggregate_tps"] = tstats(cell["reps"], "aggregate_tps")
        sec["cells"].append(cell); RESULTS["sections"]["matrix"] = sec; save()
    log("SECTION matrix done")

# ---------------- Section B: KV at full 131k ----------------
def section_kv():
    sec = {"method": "ctx 131072, parallel 1, DFlash n-max 15, ub 512, b 2048, temp 0, "
                     "cache_prompt false. Filler prompt target ~124k tokens "
                     "(actual prompt_n recorded). n_predict 256. 2 reps per KV type.",
           "cells": []}
    prompt = filler(124000, "\nNow write a detailed summary of the story above about the fox and the dog.")
    for kv in ("f16", "q8_0"):
        label = f"kv131k-{kv}"
        srv = Server(label, ["--ctx-size", "131072", "--parallel", "1",
                             "-ub", "512", "-b", "2048",
                             "--cache-type-k", kv, "--cache-type-v", kv]
                            + draft_args(15))
        cell = {"kv": kv, "reps": []}
        try:
            srv.wait_health()
            completion("Warmup: say hello.", n_predict=32)
            for rep in range(2):
                try:
                    d, w = completion(prompt, n_predict=256)
                    rec = timings_rec(d, w)
                    cell["reps"].append(rec)
                    log(f"  {label} rep{rep}: prompt_n={rec['prompt_n']} pp={rec['prompt_per_second']} tg={rec['predicted_per_second']} wall={rec['wall_s']}")
                except Exception as e:
                    cell["reps"].append({"error": str(e)}); log(f"  {label} rep{rep} ERROR {e}")
        except Exception as e:
            cell["error"] = str(e); log(f"  {label} ERROR {e}")
        finally:
            srv.stop()
        cell["prompt_tps"] = tstats(cell["reps"], "prompt_per_second")
        cell["decode_tps"] = tstats(cell["reps"], "predicted_per_second")
        sec["cells"].append(cell); RESULTS["sections"]["kv131k"] = sec; save()
    # verdict computed in analysis; raw stored here
    log("SECTION kv131k done")

# ---------------- Section C: prefill focus ----------------
def section_prefill():
    sec = {"method": "ctx 65536, parallel 1, KV f16, NO draft (prefill isolation), "
                     "temp 0, cache_prompt false. Filler prompt target ~20.5k tokens, "
                     "n_predict 8. 2 reps per (ubatch,batch) cell.",
           "cells": []}
    prompt = filler(20500, "\nReply with exactly: PREFILL_OK")
    for ub, b in [(256, 2048), (512, 2048), (1024, 2048),
                  (256, 8192), (512, 8192), (1024, 8192)]:
        label = f"prefill-ub{ub}-b{b}"
        srv = Server(label, ["--ctx-size", "65536", "--parallel", "1",
                             "-ub", str(ub), "-b", str(b),
                             "--cache-type-k", "f16", "--cache-type-v", "f16"])
        cell = {"ubatch": ub, "batch": b, "reps": []}
        try:
            srv.wait_health()
            completion("Warmup: say hello.", n_predict=16)
            for rep in range(2):
                try:
                    d, w = completion(prompt, n_predict=8)
                    rec = timings_rec(d, w)
                    cell["reps"].append(rec)
                    log(f"  {label} rep{rep}: prompt_n={rec['prompt_n']} pp={rec['prompt_per_second']}")
                except Exception as e:
                    cell["reps"].append({"error": str(e)}); log(f"  {label} rep{rep} ERROR {e}")
            if (ub, b) == (512, 2048):
                # greedy reproducibility WITHOUT draft (companion to agent-server run)
                hashes = []
                for i in range(5):
                    d, w = completion("Explain in detail why the sky is blue, covering Rayleigh scattering.",
                                      n_predict=256, seed=1234)
                    hashes.append(hashlib.sha256((d.get("content") or "").encode()).hexdigest())
                cell["greedy_nodraft_hashes"] = hashes
                cell["greedy_nodraft_identical"] = len(set(hashes)) == 1
                log(f"  greedy nodraft identical={cell['greedy_nodraft_identical']}")
        except Exception as e:
            cell["error"] = str(e); log(f"  {label} ERROR {e}")
        finally:
            srv.stop()
        cell["prompt_tps"] = tstats(cell["reps"], "prompt_per_second")
        sec["cells"].append(cell); RESULTS["sections"]["prefill"] = sec; save()
    log("SECTION prefill done")

# ---------------- Section D/E: agent suite + sampling ----------------
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

def chat(messages, max_tokens=1024, temp=0.0, tools=None, kwargs=None, seed=None, extra=None):
    p = {"model": "bench", "messages": messages, "max_tokens": max_tokens,
         "temperature": temp, "stream": False}
    if tools:
        p["tools"] = tools; p["tool_choice"] = "auto"
    if kwargs:
        p["chat_template_kwargs"] = {"reasoning_strength": kwargs}
    if seed is not None:
        p["seed"] = seed
    if extra:
        p.update(extra)
    return post("/v1/chat/completions", p)

def split_reasoning(msg):
    """Return (reasoning_text, final_text) from a chat message."""
    rc = msg.get("reasoning_content") or ""
    content = msg.get("content") or ""
    if "</think>" in content:
        think, _, rest = content.partition("</think>")
        return (rc + think), rest.strip()
    return rc, content.strip()

def section_agent():
    sec = {"method": "ctx 65536, parallel 2, KV f16, ub 512, b 2048, DFlash n-max 15, "
                     "server-default chat-template-kwargs reasoning_strength=low. "
                     "Direct llama-server chat completions (no Forge in path, so no "
                     "Forge response cache); every agent call also carries a unique "
                     "nonce in the user turn.", "parts": {}}
    srv = Server("agent", ["--ctx-size", "65536", "--parallel", "2",
                           "-ub", "512", "-b", "2048",
                           "--cache-type-k", "f16", "--cache-type-v", "f16",
                           "--chat-template-kwargs", '{"reasoning_strength":"low"}']
                          + draft_args(15))
    try:
        srv.wait_health()
        chat([{"role": "user", "content": "Warmup: say hello."}], max_tokens=64)

        # D1 tool calls (20)
        d1 = []
        ok = 0
        for prompt, want_fn, want_key in TOOL_CASES:
            rec = {"prompt": prompt, "want": want_fn}
            try:
                d, w = chat([{"role": "user", "content": f"{prompt} [ref {nonce()}]"}],
                            max_tokens=1024, tools=TOOLS)
                msg = d["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                rec["wall_s"] = round(w, 2)
                rec["usage"] = d.get("usage")
                rec["finish"] = d["choices"][0].get("finish_reason")
                if tcs:
                    fn = tcs[0]["function"]
                    rec["got"] = fn.get("name"); rec["args_raw"] = fn.get("arguments")
                    try:
                        args = json.loads(fn["arguments"])
                        rec["valid"] = bool(fn["name"] == want_fn and want_key in args)
                    except Exception as e:
                        rec["valid"] = False; rec["args_error"] = str(e)
                else:
                    rec["valid"] = False; rec["got"] = None
                    rec["content_head"] = (msg.get("content") or "")[:160]
                ok += 1 if rec["valid"] else 0
            except Exception as e:
                rec["valid"] = False; rec["error"] = str(e)
            d1.append(rec); log(f"  D1 {want_fn}: valid={rec.get('valid')} wall={rec.get('wall_s')}")
        sec["parts"]["tool_calls"] = {"score": f"{ok}/20", "cases": d1}

        # D2 JSON validity, uncached (unique nonce + required ref echo)
        schemas = [
            ("person", {"name": "string", "age": "integer", "city": "string"}),
            ("book", {"title": "string", "author": "string", "year": "integer"}),
            ("product", {"product": "string", "price": "number", "in_stock": "boolean"}),
            ("event", {"event": "string", "date": "string", "location": "string"}),
            ("recipe", {"dish": "string", "servings": "integer", "minutes": "integer"}),
        ]
        d2 = []
        raw_ok = strip_ok = ref_ok = 0
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
                rec["wall_s"] = round(w, 2); rec["usage"] = d.get("usage")
                for label, txt in (("raw", content.strip()), ("stripped", final)):
                    try:
                        obj = json.loads(txt)
                        if label == "raw": raw_ok += 1; rec["raw_valid"] = True
                        else:
                            strip_ok += 1; rec["stripped_valid"] = True
                            if obj.get("ref") == n: ref_ok += 1; rec["ref_match"] = True
                    except Exception:
                        rec[label + "_valid"] = rec.get(label + "_valid", False)
                rec.setdefault("raw_valid", False); rec.setdefault("stripped_valid", False)
                rec.setdefault("ref_match", False)
                rec["content_head"] = content[:200]
            except Exception as e:
                rec["error"] = str(e)
            d2.append(rec); log(f"  D2 {name}: raw={rec.get('raw_valid')} stripped={rec.get('stripped_valid')} ref={rec.get('ref_match')}")
        sec["parts"]["json"] = {"raw_valid": f"{raw_ok}/5", "stripped_valid": f"{strip_ok}/5",
                                "ref_match": f"{ref_ok}/5", "cases": d2}

        # D3 multi-turn prompt-cache: 4 turns sharing a long prefix
        prefix = filler(6000, "\nEND OF OPERATIONS LOG.\n")
        system = ("You are an operations assistant. The following is the operations "
                  "log for the week. Answer questions about it briefly.\n" + prefix)
        turns = ["How many log lines mention the river bank?",
                 "What animals appear in the log?",
                 "Summarize the log in one sentence.",
                 "Reply with exactly: TURNS_DONE"]
        msgs = [{"role": "system", "content": system}]
        d3 = []
        for i, t in enumerate(turns):
            msgs.append({"role": "user", "content": t})
            try:
                d, w = chat(msgs, max_tokens=400)
                tm = d.get("timings", {}) or {}
                u = d.get("usage", {}) or {}
                rec = {"turn": i, "wall_s": round(w, 2),
                       "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
                       "prompt_per_second": tm.get("prompt_per_second"),
                       "usage_prompt_tokens": u.get("prompt_tokens"),
                       "usage_details": u.get("prompt_tokens_details")}
                if rec["prompt_n"]:
                    rec["cache_hit_rate"] = round((rec["cache_n"] or 0) / rec["prompt_n"], 3)
                d3.append(rec)
                msgs.append({"role": "assistant",
                             "content": d["choices"][0]["message"].get("content") or ""})
                log(f"  D3 turn{i}: prompt_n={rec['prompt_n']} cache_n={rec['cache_n']} hit={rec.get('cache_hit_rate')}")
            except Exception as e:
                d3.append({"turn": i, "error": str(e)}); log(f"  D3 turn{i} ERROR {e}")
        sec["parts"]["multiturn_cache"] = {"turns": d3}

        # D4 reasoning token tax: low / medium / high via per-request kwargs
        report = ("Incident report: At 02:14 the ingest worker on node furnace began "
                  "retrying a failed S3 upload. Retries continued for 41 minutes, "
                  "duplicating 312 objects before an operator paused the queue. "
                  "Root cause was an expired credential in the rotation pool. No "
                  "customer data was exposed; duplicates were reconciled by 05:00. "
                  "Follow-ups: alert on retry storms, shorten credential TTL checks.")
        d4 = []
        for level in ("low", "medium", "high"):
            for rep in range(2):
                rec = {"level": level, "rep": rep}
                try:
                    d, w = chat([{"role": "user", "content":
                                  f"Summarize this incident report in exactly three bullet points. [ref {nonce()}]\n\n{report}"}],
                                max_tokens=2000, kwargs=level)
                    msg = d["choices"][0]["message"]
                    reasoning, final = split_reasoning(msg)
                    u = d.get("usage", {}) or {}
                    rec.update({"wall_s": round(w, 2), "completion_tokens": u.get("completion_tokens"),
                                "completion_details": u.get("completion_tokens_details"),
                                "reasoning_chars": len(reasoning), "final_chars": len(final),
                                "finish": d["choices"][0].get("finish_reason")})
                except Exception as e:
                    rec["error"] = str(e)
                d4.append(rec); log(f"  D4 {level} rep{rep}: ct={rec.get('completion_tokens')} rchars={rec.get('reasoning_chars')} wall={rec.get('wall_s')}")
        sec["parts"]["reasoning_tax"] = {"runs": d4}

        # E sampling + greedy reproducibility (same server, DFlash on)
        prose = "Write a short story opening about a cartographer who maps a city that changes every night."
        e = {}
        for name, extra in (("meta_card", {"temperature": 1.0, "top_p": 0.95, "top_k": 64}),
                            ("temp0", {"temperature": 0.0})):
            runs = []
            for i in range(3):
                try:
                    d, w = chat([{"role": "user", "content": prose}], max_tokens=256, extra=extra)
                    content = d["choices"][0]["message"].get("content") or ""
                    tm = d.get("timings", {}) or {}
                    runs.append({"wall_s": round(w, 2),
                                 "predicted_per_second": tm.get("predicted_per_second"),
                                 "completion_tokens": (d.get("usage") or {}).get("completion_tokens"),
                                 "sha256": hashlib.sha256(content.encode()).hexdigest(),
                                 "content_head": content[:120]})
                except Exception as ex:
                    runs.append({"error": str(ex)})
            e[name] = {"runs": runs, "decode_tps": tstats(runs, "predicted_per_second")}
            log(f"  E {name}: done")
        hashes = []
        for i in range(5):
            d, w = completion("Explain in detail why the sky is blue, covering Rayleigh scattering.",
                              n_predict=256, temp=0.0, seed=1234)
            hashes.append(hashlib.sha256((d.get("content") or "").encode()).hexdigest())
        e["greedy_repro_draft"] = {"seed": 1234, "temp": 0.0, "n_predict": 256,
                                   "hashes": hashes, "identical": len(set(hashes)) == 1}
        log(f"  E greedy draft identical={e['greedy_repro_draft']['identical']}")
        sec["parts"]["sampling"] = e
    except Exception as e:
        sec["error"] = str(e); log(f"  agent SECTION ERROR {e}")
    finally:
        srv.stop()
    RESULTS["sections"]["agent"] = sec; save()
    log("SECTION agent done")

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if os.path.exists(os.path.join(OUTDIR, "results-w2.json")) and which != "all":
        with open(os.path.join(OUTDIR, "results-w2.json")) as f:
            RESULTS.update(json.load(f))
    if which in ("all", "matrix"): section_matrix()
    if which in ("all", "kv"): section_kv()
    if which in ("all", "prefill"): section_prefill()
    if which in ("all", "agent"): section_agent()
    RESULTS["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
    log("BENCH W2 COMPLETE")

if __name__ == "__main__":
    main()
