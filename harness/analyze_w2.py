import json, os, statistics as st
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'w2', 'results-w2.json')))
S = d['sections']
def ms(vals):
    vals=[v for v in vals if v is not None]
    if not vals: return "n/a"
    m=st.mean(vals); sd=st.pstdev(vals) if len(vals)>1 else 0.0
    return f"{m:.2f} ± {sd:.2f} (n={len(vals)}, vals={[round(v,2) for v in vals]})"

print("=== MATRIX (agg = total pred tokens / max wall; wall-slot = pred_n/wall_s per request; timings-slot = server predicted_per_second) ===")
for c in S['matrix']['cells']:
    walls=[]; aggs=[]; tims=[]; accs=[]
    for rep in c['reps']:
        aggs.append(rep.get('aggregate_tps'))
        for r in rep['requests']:
            if 'error' in r: print("  ERR", r['error']); continue
            walls.append(r['predicted_n']/r['wall_s'])
            tims.append(r.get('predicted_per_second'))
            if r.get('draft_n'): accs.append(r['draft_n_accepted']/r['draft_n'])
    print(f"ctx{c['ctx']} par{c['parallel']}: agg {ms(aggs)} | wall-slot {ms(walls)} | timings-slot {ms(tims)} | draft-acc {ms(accs)}")

print("\n=== KV 131k ===")
kv={}
for c in S['kv131k']['cells']:
    pp=[r.get('prompt_per_second') for r in c['reps'] if 'error' not in r]
    tg=[r.get('predicted_per_second') for r in c['reps'] if 'error' not in r]
    pn=[r.get('prompt_n') for r in c['reps'] if 'error' not in r]
    wt=[r.get('predicted_n')/r['wall_s'] for r in c['reps'] if 'error' not in r and r.get('predicted_n')]
    kv[c['kv']]=(st.mean(pp), st.mean(tg))
    print(f"{c['kv']}: prompt_n {pn} pp {ms(pp)} tg-timings {ms(tg)} tg-wall {ms(wt)}")
f_pp,q_pp=kv['f16'][0],kv['q8_0'][0]; f_tg,q_tg=kv['f16'][1],kv['q8_0'][1]
print(f"q8_0 prefill deficit vs f16: {(f_pp-q_pp)/f_pp*100:.1f}% | decode deficit: {(f_tg-q_tg)/f_tg*100:.1f}%")

print("\n=== PREFILL ===")
for c in S['prefill']['cells']:
    pp=[r.get('prompt_per_second') for r in c['reps'] if 'error' not in r]
    pn=[r.get('prompt_n') for r in c['reps'] if 'error' not in r]
    extra=""
    if 'greedy_nodraft_hashes' in c:
        extra=f" | greedy-nodraft identical={c['greedy_nodraft_identical']} unique={len(set(c['greedy_nodraft_hashes']))}/5"
    print(f"ub{c['ubatch']} b{c['batch']}: prompt_n {pn} pp {ms(pp)}{extra}")

print("\n=== AGENT ===")
A=S['agent']['parts']
tc=A['tool_calls']; print("tool_calls score:", tc['score'])
for case in tc['cases']:
    print(f"  {case['want']}: valid={case['valid']} wall={case.get('wall_s')} got={case.get('got')} err={case.get('error','')}")
j=A['json']; print("json:", j['raw_valid'], j['stripped_valid'], j['ref_match'])
for case in j['cases']:
    print(f"  {case['case']}: raw={case.get('raw_valid')} stripped={case.get('stripped_valid')} ref={case.get('ref_match')} wall={case.get('wall_s')} err={case.get('error','')}")
mt=A['multiturn_cache']; print("multiturn:")
for t in mt['turns']: print("  ", t)
rt=A['reasoning_tax']; print("reasoning tax:")
for r in rt['runs']: print("  ", r)
sm=A['sampling']; print("sampling:")
for name in ('meta_card','temp0'):
    print(f"  {name}: decode {sm[name]['decode_tps']}")
    for run in sm[name]['runs']: print("    ", {k:run.get(k) for k in ('wall_s','completion_tokens','sha256')}, str(run.get('content_head',''))[:60])
g=sm['greedy_repro_draft']; print(f"greedy draft: identical={g['identical']} unique={len(set(g['hashes']))}/5 hashes={[h[:10] for h in g['hashes']]}")
