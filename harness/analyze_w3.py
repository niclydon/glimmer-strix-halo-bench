#!/usr/bin/env python3
"""Furnace Bench W3 analysis: ladder table + perf-per-watt from phases/power.
Run ON furnace after bench completes. Prints markdown-ready summary and
writes analysis-w3.json into results-w3/.
"""
import csv, json, os, statistics, sys

OUT = os.path.expanduser("~/glimmer-furnace-bench/results-w3")

with open(os.path.join(OUT, "results-w3.json")) as f:
    R = json.load(f)

phases = []
with open(os.path.join(OUT, "phases.csv")) as f:
    for row in csv.reader(f):
        if len(row) == 4:
            phases.append({"name": row[0], "tag": row[1],
                           "t0": float(row[2]), "t1": float(row[3])})

power = []
with open(os.path.join(OUT, "power.csv")) as f:
    for row in csv.DictReader(f):
        try:
            power.append({"t": float(row["epoch"]),
                          "w": float(row["power_w"]) if row["power_w"] else None,
                          "temp": float(row["temp_edge_c"]) if row["temp_edge_c"] else None,
                          "sclk": float(row["sclk_mhz"]) if row["sclk_mhz"] else None})
        except Exception:
            pass

def slice_stats(t0, t1):
    s = [p for p in power if t0 <= p["t"] <= t1 and p["w"] is not None]
    if not s:
        return {"n": 0}
    ws = [p["w"] for p in s]
    ts = [p["temp"] for p in s if p["temp"] is not None]
    ck = [p["sclk"] for p in s if p["sclk"] is not None]
    return {"n": len(s),
            "w_mean": round(statistics.mean(ws), 1),
            "w_peak": max(ws),
            "temp_mean": round(statistics.mean(ts), 1) if ts else None,
            "temp_peak": max(ts) if ts else None,
            "sclk_mean": round(statistics.mean(ck), 0) if ck else None,
            "energy_j": round(sum(ws) * ((t1 - t0) / len(s)), 0) if s else None}

def window_stats(t0, t1, frac0, frac1):
    a = t0 + (t1 - t0) * frac0
    b = t0 + (t1 - t0) * frac1
    return slice_stats(a, b)

out = {"ladder": [], "phases_power": {}, "soak": {}}

# Ladder from llama-bench JSON (keys: build_commit etc.; entries under 'results' or list)
for cell in R["sections"].get("ladder", {}).get("cells", []):
    entry = {"quant": cell["quant"], "size_bytes": cell.get("size_bytes")}
    bench = cell.get("bench")
    rows = []
    if isinstance(bench, list):
        rows = bench
    elif isinstance(bench, dict):
        rows = bench.get("results", [])
    for r in rows:
        rows_key = (r.get("n_prompt"), r.get("n_gen"), r.get("n_depth"))
        entry.setdefault("runs", []).append({
            "n_prompt": r.get("n_prompt"), "n_gen": r.get("n_gen"),
            "n_depth": r.get("n_depth"),
            "avg_ts": r.get("avg_ts"), "stddev_ts": r.get("stddev_ts")})
    out["ladder"].append(entry)

for p in phases:
    key = f"{p['name']}/{p['tag']}"
    st = slice_stats(p["t0"], p["t1"])
    out["phases_power"][key] = st

soak = R["sections"].get("soak", {})
for p in phases:
    if p["name"] == "soak":
        st = slice_stats(p["t0"], p["t1"])
        first = window_stats(p["t0"], p["t1"], 0.0, 5 * 60 / max(p["t1"] - p["t0"], 1))
        last = window_stats(p["t0"], p["t1"], 1 - 5 * 60 / max(p["t1"] - p["t0"], 1), 1.0)
        tok = soak.get("total_predicted_tokens") or 0
        dur = p["t1"] - p["t0"]
        out["soak"] = {"duration_s": round(dur, 1), "tokens": tok,
                       "power": st, "first5min": first, "last5min": last,
                       "tok_per_joule": round(tok / st["energy_j"], 4) if st.get("energy_j") else None,
                       "mean_tg_tps_wall": round(tok / dur, 2) if dur else None}

with open(os.path.join(OUT, "analysis-w3.json"), "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))
