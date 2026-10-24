import json, re, statistics, os
base=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "w1")
def load(n):
    with open(os.path.join(base,n)) as f: return json.load(f)
out=[]
out.append("=== LLAMA-BENCH (3 reps, mean +/- stddev tok/s) ===")
for backend in ("hip","vulkan"):
    for name,label in (("pp512-tg128","pp512/tg128 ub512"),("pp8192","pp8192 ub512"),("dflash-off","baseline ub256")):
        d=load(f"llamabench-{backend}-{name}.json")
        for x in d:
            kind="pp"+str(x["n_prompt"]) if x["n_prompt"] else "tg"+str(x["n_gen"])
            out.append(f"{backend} {label} {kind} depth={x['n_depth']} {x['avg_ts']:.2f} +/- {x['stddev_ts']:.2f} (ub={x['n_ubatch']}, bk={x['backends']})")
out.append("")
out.append("=== DFLASH SERVER SWEEP (llama-server port 5999, /completion temp0, 128 tokens, 3 reps) ===")
d=load("dflash-server-results.json")
for cfg in d["configs"]:
    for depth, reps in cfg["cells"].items():
        tgs=[r["predicted_per_second"] for r in reps if r.get("predicted_per_second")]
        pps=[r["prompt_per_second"] for r in reps if r.get("prompt_per_second")]
        accs=[]
        for r in reps:
            lines=(r.get("acceptance_from_log") or {}).get("lines") or []
            for ln in lines:
                m=re.search(r"draft acceptance = ([0-9.]+).*?(\d+) accepted /\s*(\d+) generated.*?mean len =\s*([0-9.]+)", ln)
                if m: accs.append((float(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))))
        mean=statistics.mean(tgs) if tgs else 0
        sd=statistics.pstdev(tgs) if len(tgs)>1 else 0
        acc_s = "; ".join(f"{a[0]:.3f} ({a[1]}/{a[2]}, len {a[3]:.2f})" for a in accs) if accs else "n/a (no draft)"
        pn = reps[0].get("prompt_n") if reps else None
        out.append(f"{cfg['build']} nmax={cfg['n_max']} depth={depth} (prompt_n={pn}) tg mean {mean:.2f} +/- {sd:.2f} reps {[round(t,2) for t in tgs]} | pp mean {statistics.mean(pps):.1f} | acceptance: {acc_s}")
print("\n".join(out))
with open(os.path.join(base,"summary-w1.txt"),"w") as f: f.write("\n".join(out)+"\n")
