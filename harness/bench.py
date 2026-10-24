#!/usr/bin/env python3
"""Glimmer benchmark via Forge default-agent. Usage: python3 bench.py [phase]
Phase A: resolve + decode throughput + prefill. Phase B: tools + JSON + concurrency.
Run on Furnace with FORGE_API_KEY in env."""
import json
import os
import sys
import threading
import time
import urllib.request

BASE = os.environ.get("FORGE_BASE", "http://localhost:8642")
MODEL = os.environ.get("BENCH_MODEL", "default-agent")
KEY = os.environ.get("FORGE_API_KEY", "")


def post(payload, timeout=115):
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return body, time.time() - t0


def split_think(content):
    if "</think>" in content:
        think, _, rest = content.partition("</think>")
        return think, rest.strip()
    return "", content.strip()


def chat(prompt, max_tokens=512, **kw):
    p = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
         "max_tokens": max_tokens, "temperature": 0}
    p.update(kw)
    return post(p)


def phase_a():
    print("== A1 resolve + short chat ==")
    d, w = chat("Reply with exactly: BENCH_OK", 200)
    msg = d["choices"][0]["message"]
    think, final = split_think(msg.get("content") or "")
    print(f"resolved_model={d.get('model')} resolution={d.get('model_resolution')}")
    print(f"final={final!r} wall={w:.2f}s usage={d.get('usage')}")

    print("== A2 decode throughput (max 1000 tok) ==")
    d, w = chat("Write a detailed, step-by-step explanation of how DNS resolution "
                "works, from a browser typing a URL to receiving an IP address. "
                "Be thorough and specific.", 1000)
    u = d["usage"]
    ct = u["completion_tokens"]
    think, final = split_think(d["choices"][0]["message"].get("content") or "")
    think_share = len(think) / max(1, len(think) + len(final))
    print(f"completion_tokens={ct} wall={w:.1f}s tok_per_s={ct / w:.1f} "
          f"think_char_share={think_share:.2f} finish={d['choices'][0]['finish_reason']}")

    print("== A3 prefill (~6000 token prompt, short answer) ==")
    filler = "\n".join(f"Log line {i}: service nexus-worker heartbeat ok, "
                       f"queue depth {i % 37}, latency {i % 91}ms, worker w{i % 12}."
                       for i in range(700))
    d, w = chat(filler + "\n\nBased only on the log lines above, reply with "
                "exactly: PREFILL_OK", 300)
    u = d["usage"]
    print(f"prompt_tokens={u['prompt_tokens']} completion={u['completion_tokens']} "
          f"wall={w:.1f}s prompt_tok_per_s_wall={u['prompt_tokens'] / w:.0f}")


TOOLS = [
    {"type": "function", "function": {"name": "get_weather",
     "description": "Get current weather for a city",
     "parameters": {"type": "object", "properties": {"city": {"type": "string"}},
                    "required": ["city"]}}},
    {"type": "function", "function": {"name": "set_timer",
     "description": "Set a countdown timer",
     "parameters": {"type": "object", "properties": {"minutes": {"type": "integer"}},
                    "required": ["minutes"]}}},
    {"type": "function", "function": {"name": "search_contacts",
     "description": "Search the address book for a person",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}},
                    "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_note",
     "description": "Create a note with a title",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}},
                    "required": ["title"]}}},
    {"type": "function", "function": {"name": "convert_currency",
     "description": "Convert an amount between currencies",
     "parameters": {"type": "object", "properties": {
         "amount": {"type": "number"}, "from_currency": {"type": "string"},
         "to_currency": {"type": "string"}},
        "required": ["amount", "from_currency", "to_currency"]}}},
]

TOOL_CASES = [
    ("What's the weather like in Chicago right now?", "get_weather", "city"),
    ("Set a timer for 25 minutes.", "set_timer", "minutes"),
    ("Look up Mary Jones in my contacts.", "search_contacts", "name"),
    ("Create a note titled 'Trip packing list'.", "create_note", "title"),
    ("Convert 250 US dollars to euros.", "convert_currency", "amount"),
]


def phase_b():
    print("== B1 tool-call reliability (5 cases) ==")
    ok = 0
    for prompt, want_fn, want_key in TOOL_CASES:
        try:
            d, w = chat(prompt, 400, tools=TOOLS, tool_choice="auto")
            msg = d["choices"][0]["message"]
            tcs = msg.get("tool_calls") or []
            verdict = "FAIL no tool_calls"
            if tcs:
                fn = tcs[0]["function"]
                try:
                    args = json.loads(fn["arguments"])
                    if fn["name"] == want_fn and want_key in args:
                        verdict = f"OK {fn['name']}({args})"
                        ok += 1
                    else:
                        verdict = f"FAIL wrong call {fn['name']}({args})"
                except Exception as e:
                    verdict = f"FAIL bad args json: {e}"
            print(f"[{want_fn}] {verdict} wall={w:.1f}s")
        except Exception as e:
            print(f"[{want_fn}] ERROR {e}")
    print(f"tool score: {ok}/5")

    print("== B2 JSON output reliability (5 tries) ==")
    raw_ok = strip_ok = 0
    for i in range(5):
        d, w = chat("Invent a fictional person. Return ONLY a JSON object with "
                    "keys: name (string), age (integer), city (string). "
                    "No other text.", 400)
        content = d["choices"][0]["message"].get("content") or ""
        _, final = split_think(content)
        for label, txt in (("raw", content.strip()), ("stripped", final)):
            try:
                obj = json.loads(txt)
                assert isinstance(obj["name"], str) and isinstance(obj["age"], int)
                if label == "raw":
                    raw_ok += 1
                else:
                    strip_ok += 1
            except Exception:
                pass
        print(f"try{i}: wall={w:.1f}s")
    print(f"json score: raw-parse {raw_ok}/5, after-think-strip {strip_ok}/5")

    print("== B3 concurrency (2 parallel x ~300 tok) ==")
    results = {}

    def worker(n):
        d, w = chat(f"Write a short paragraph about the history of the "
                    f"lighthouse at Boston Harbor. Variant {n}.", 300)
        results[n] = (d["usage"]["completion_tokens"], w)

    t0 = time.time()
    ts = [threading.Thread(target=worker, args=(n,)) for n in (1, 2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = time.time() - t0
    for n, (ct, w) in sorted(results.items()):
        print(f"req{n}: tokens={ct} wall={w:.1f}s")
    print(f"both done in {total:.1f}s")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "a"
    (phase_a if phase == "a" else phase_b)()
