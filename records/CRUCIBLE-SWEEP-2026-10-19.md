# Crucible context-depth sweep — Glimmer publication package — 2026-10-19

## Status note - added 2026-10-24

Status lines in this record ("nothing from this sweep has been published") describe the moment of writing; the package was published later. The exact run scripts named below were session scripts on Crucible and are not in the package; the sweep's data and this record are complete.


Run window: scheduled Mon 2026-10-19 23:07 EDT (America/New_York); executed on Crucible only.
Furnace production untouched. Declared maintenance window approved by Nic in the Glimmer build chat, Oct 19, 2026.

## Environment manifest

- Host: crucible (GMKtec NucBox_EVO-X2, product version 1.0)
- OS: Ubuntu 24.04.5 LTS (Noble Numbat)
- Kernel: 6.19.10-061910-generic (x86_64, SMP PREEMPT_DYNAMIC, 2026-03-25)
- BIOS: American Megatrends International, LLC., version EVO-X2 1.12, release date 12/09/2025, firmware revision 1.10
- GPU: AMD Radeon Graphics, gfx1151, Wave Size 32, VRAM 49152 MiB (UMA, Strix Halo / Ryzen AI Max+ 395)
- ROCm: 7.2.1 (/opt/rocm-7.2.1)
- llama.cpp: build 11719 (b11719), commit 5aeac37a35b44fde4bdffaec9159f2fcb253b622, built with GNU 13.3.0 for Linux x86_64
  - Build flags (from build/CMakeCache.txt): CMAKE_BUILD_TYPE=Release, GGML_HIP=ON, GGML_HIP_GRAPHS=ON, GGML_HIP_MMQ_MFMA=ON, GGML_HIP_NO_VMM=ON, ROCM_PATH=/opt/rocm-7.2.1, HIP compiler /opt/rocm-7.2.1/lib/llvm/bin/clang++
  - Binaries: ~/llama.cpp/build/bin/llama-bench, ~/llama.cpp/build/bin/llama-server (thin launchers, require LD_LIBRARY_PATH below)
- Runtime env for all llama binaries in this sweep:
  - ROCBLAS_USE_HIPBLASLT=0
  - GPU_MAX_ALLOC_PERCENT=100
  - LD_LIBRARY_PATH=/home/niclydon/llama.cpp/build/bin:/opt/rocm-7.2.1/lib
- GGUF files in /services/models/muse-glimmer-30b/ — sha256 verified 2026-10-19 pre-flight, all three MATCH expected:
  - Muse-Glimmer-30B-UD-Q4_K_XL.gguf (main, 15G): 82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38
  - dflash-kquant.gguf (drafter, 1.6G): 27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc
  - mmproj-kquant.gguf (1.4G): f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6
- Production agent-seat shape (from Crucible llama-swap config, verified pre-flight):
  llama-server -ngl 99 -fit off -fa on --ctx-size 65536 --parallel 2 --jinja --cache-type-k f16 --cache-type-v f16 --spec-type draft-dflash --model-draft dflash-kquant.gguf --spec-draft-n-max 15 --spec-draft-n-min 3 -m Muse-Glimmer-30B-UD-Q4_K_XL.gguf
  Prose seat is the same GGUFs with --parallel 1, --ubatch-size 256, --spec-draft-n-max 3.
- Co-residency disclosure: Crucible llama-swap was STOPPED for the sweep (see below), so both Glimmer seats (agent + prose) and the qwen3-embed-8b-crucible embed mirror were down for the duration. No other GPU resident during bench cells. Warmup runs discarded per llama-bench default behaviour (warmup enabled; --no-warmup NOT passed). Repetitions: 3 per cell, mean and stddev reported from llama-bench JSON.
- Raw data on Crucible: ~/glimmer-tune/sweep-2026-10-19/ (llama-bench JSON, server-path JSON, longtext results, server logs).

## Pre-flight

- All three GGUF sha256 hashes matched the expected values exactly.
- llama-swap was active before the sweep, with muse-glimmer-30b (agent, port 5801) ready and qwen3-embed-8b-crucible ready; GET http://localhost:8099/running returned both.
- llama-bench drafter support check: `llama-bench --help` on b11719 lists NO speculative / draft parameters at all (no --spec-type, no --model-draft, no spec-draft-n-max/min). Therefore, per the sweep instructions, the llama-bench depth sweep was run WITHOUT the DFlash drafter, and the tg cells were ALSO run through a scratch llama-server with the drafter attached (agent-seat flags, n-max 15) — see "Server-path tg (DFlash attached)" below.

## Window discipline and the llama-swap watchdog (methodology note, read before citing)

- Stopping llama-swap was not one-and-done. First stop (03:10:54 UTC) took 31 s to drain its servers and the service was restarted within the same second it deactivated (03:11:25); a second stop (03:12:25) was likewise restarted at 03:12:26. Root cause found live: `llama-swap-metrics.service` declares `Wants=llama-swap.service` and is fired every 30 s by `llama-swap-metrics.timer`, so every metrics run pulled llama-swap back up.
- Fix applied inside the window: stop `llama-swap-metrics.timer` first, then llama-swap (03:22:05 UTC). Verified inactive at +10/+20/+30/+40/+50 s (two full timer periods) and at every later check. The timer was restarted during restore; both units are `active` at the end of this record.
- Contamination audit for the interval before the fix (Stage A, 03:16:04–03:22:05 UTC, swap parent up but empty): the llama-swap journal for that instance shows NO model load and NO health-check events at all between its start (03:12:26) and its stop (03:22:05); direct process checks at launch and during the stage showed zero llama-server processes; the only load in the whole pre-sweep hour was the embed mirror health check at 03:12:22, before any bench started. Verdict: no GPU co-residency during any measured cell; for Stage A's first ~6 minutes the (empty, 10 MB) llama-swap parent process was present on CPU only. All Stage B/C/D cells ran with llama-swap fully down.
- A one-rep pilot (pp512/tg128 at depth 0, 03:11 UTC) ran while the first stop was still draining and is DISCARDED; it is not in any table below (kept as pilot.json in the raw dir for provenance only). Its numbers (pp 405.6, tg 13.56) are superseded by the clean Stage A cells.
- No partial-offload (-ngl 16) Glimmer instance was run at any point. All bench/server instances used -ngl 99.

## Results — llama-bench depth sweep (NO drafter; -ngl 99, -fa on, KV f16, 3 reps)

Command shape: `llama-bench -m Muse-Glimmer-30B-UD-Q4_K_XL.gguf -ngl 99 -fa on -ctk f16 -ctv f16 -p 512 -n 128 -d <depths> -r 3 -o json` (one invocation produces the pp512 and tg128 entries per depth), and `-p 8192 -n 0` for the pp8192 cells. Raw: bench_pp512_tg128.json, bench_pp8192.json in the raw dir. Times are UTC test_time stamps from the JSON.

| test | depth | mean tok/s | stddev | samples tok/s |
|---|---|---|---|---|
| pp512 | 0 | 457.10 | 2.23 | 455.10, 459.51, 456.68 |
| pp512 | 4096 | 389.89 | 5.29 | 395.15, 384.56, 389.96 |
| pp512 | 16384 | 362.89 | 6.64 | 370.56, 359.21, 358.91 |
| pp512 | 32768 | 304.44 | 59.83 | 365.74, 246.19, 301.39 |
| pp512 | 65536 | 292.32 | 5.29 | 298.42, 288.89, 289.65 |
| tg128 | 0 | 13.84 | 0.02 | 13.84, 13.86, 13.81 |
| tg128 | 4096 | 13.64 | 0.05 | 13.67, 13.66, 13.58 |
| tg128 | 16384 | 13.04 | 0.66 | 12.28, 13.45, 13.39 |
| tg128 | 32768 | 12.15 | 1.03 | 11.10, 12.20, 13.16 |
| tg128 | 65536 | 13.02 | 0.01 | 13.01, 13.03, 13.03 |
| pp8192 | 0 | 393.63 | 2.59 | 395.82, 394.31, 390.76 |
| pp8192 | 4096 | 383.11 | 1.58 | 384.52, 383.39, 381.41 |
| pp8192 | 16384 | 357.23 | 1.55 | 358.88, 356.98, 355.81 |
| pp8192 | 32768 | 330.63 | 1.05 | 331.70, 330.58, 329.60 |
| pp8192 | 65536 | 278.14 | 7.22 | 285.35, 278.17, 270.91 |

Reading: decode (tg128) without speculation is essentially flat with depth (13.84 at 0 → 13.02 at 65536, -6%), consistent with Glimmer's small KV. Prefill falls with depth: pp512 -36% (457 → 292), pp8192 -29% (394 → 278) from depth 0 to 65536. Failed cells: none; all 15 cells completed. Named dispersion: pp512 at depth 32768 carries one outlier rep (246.19 vs 365.74/301.39 in the same cell); its mean/stddev are reported as measured, not cleaned. tg128 at 32768 shows the widest tg dispersion (±1.03) for the same reason family; no co-residency explains it (see audit above) and the neighbouring depths are tight.

## Results — server-path tg128 (DFlash attached, agent-seat flags)

Scratch llama-server on port 5999 (killed and verified gone after the stage): -ngl 99 -fit off -fa on, KV f16, --spec-type draft-dflash --model-draft dflash-kquant.gguf --spec-draft-n-max 15 --spec-draft-n-min 3, --parallel 1 (single-stream measure). One disclosed deviation from the production seat: --ctx-size 131072 instead of 65536, because a depth-65536 measurement plus 128 generated tokens cannot fit a 65536 context; all other agent flags identical. Depth was established with a repeated filler passage tokenized via the server /tokenize endpoint to the exact depth, followed by a short story instruction; generation measured from server `timings` (predicted_per_second), temperature 0, cache_prompt on, 3 reps per depth, one discarded warmup at depth 0. Raw: server_tg.json / server_tg.log / server_tg.server.log.

| depth | mean decode tok/s | stddev | reps tok/s | draft accepted/drafted per rep |
|---|---|---|---|---|
| 0 | 16.39 | 1.10 | 15.38, 17.56, 16.24 | 67/857; 75/775; 70/821 |
| 4096 | 21.68 | 4.16 | 26.49, 19.23, 19.33 | 94/476; 81/637; 81/637 |
| 16384 | 22.39 | 2.26 | 19.77, 23.67, 23.71 | 83/611; 91/491; 91/491 |
| 32768 | 18.18 | 2.73 | 17.25, 16.04, 21.25 | 85/592; 92/511; 92/511 |
| 65536 | 19.52 | 0.03 | 19.49, 19.56, 19.50 | 88/548; 87/543; 87/545 |

Reading: with the drafter attached, prose-continuation decode at depth is 16.4 tok/s at depth 0 and 19.5 tok/s at depth 65536 (mid-depths 18–22, wide dispersion), versus 13.8 / 13.0 without speculation in llama-bench — DFlash at n-max 15 is worth roughly 1.2–1.6x on this prose shape at depth, with low draft acceptance (8–18% of drafted tokens accepted) exactly as the Oct 18 tuning bench predicted for long blocks on prose. (The n-max 15 payoff case remains agent tool-call turns at 60–78 tok/s from Oct 18; this sweep's prose shape is the weak case for long blocks, now measured at depth.) Identical accepted/drafted counts on reps 2–3 at depths ≥4096 are the expected artefact of temperature 0 + prompt caching producing the same continuation; the decode rates are live measurements against the full KV depth in each rep.

## Results — longtext bench (first run of this payload shape)

Harness: staged ~/glimmer-tune/longtext_bench.py, adapted for this sweep only in flags and scope (patch_longtext.py in the raw dir): DFlash n-max 3 → 15 and ubatch 256 dropped, to match the agent-seat flags named in the sweep instructions (ctx 65536, parallel 1, KV f16); the four-knob cell matrix was reduced to the single agent-seat cell at the payload's 4096-token budget (the knob matrix belongs to the reasoning bench, not this sweep). Payload: ~/glimmer-tune/test-longtext.json (weekly-synthesis shape). Scratch server on port 5999, killed and verified gone after the run. Raw: longtext-results.json, longtext_sweep.log, longtext-agent-nmax15.server.log.

- Prompt: 2,507 tokens (server usage count; the harness docstring's "~5k tokens in" is stale — the staged payload tokenizes to 2,507).
- Prefill: 395.26 tok/s (prompt eval 6.34 s, server timings).
- Total wall: 158.6 s. Generation: 4,096 tokens in 152.28 s = 26.89 tok/s decode (server timings). Draft acceptance 0.194 (3,046 accepted / 15,727 generated), mean accepted length 3.90.
- Completion: finish_reason = "length". Content: 0 characters. Reasoning content: 18,445 characters.
- VERDICT: INCOMPLETE / TRUNCATED. At agent-seat flags (no reasoning control of any kind), the model spent the entire 4,096-token budget on reasoning and produced no answer at all for the weekly-synthesis payload. This is the longtext counterpart of the Oct 18 prose-seat finding (uncontrolled reasoning eats whole budgets); on the agent seat there is not even the prose seat's reasoning_strength-low template kwarg. A long-form prose workload does not complete on the agent-seat shape at a 4k budget — it needs a reasoning-controlled seat or a far larger budget. The decode rate itself (26.89 tok/s sustained over 4,096 tokens at ~2.5k depth) is healthy; the failure is budget allocation to reasoning, not throughput.

## Cleanup verification

- Runner's own post-stage sweeps: "no 5999 server after stage C", "no 5999 server after stage D", "no 5998 server after stage D" (STATUS file in raw dir).
- Independent check after the runner finished: `ps aux | grep llama-server` shows no scratch processes; ports 5999 and 5998 have no listeners. No llama-server was left on any scratch port.
- Stage return codes: A rc=0, B rc=0, C rc=0, D rc=0; runner finished 2026-10-20T03:46:56Z.

## Restore verification

- `llama-swap-metrics.timer` restarted first, then llama-swap: both `active` (systemctl is-active).
- The agent seat does NOT auto-preload on swap start (verified: /running stayed [] for 4 minutes after start; "persistent" in its group means never evicted, not preloaded). It was loaded via one tiny chat completion through llama-swap: HTTP 200 from model muse-glimmer-30b (the reply spent its 64-token budget on reasoning_content and finished "length" — the known Glimmer reasoning behaviour, not a seat fault; timings predicted 28.59 tok/s).
- Prose seat on-demand load verified with one tiny chat completion through llama-swap: HTTP 200 from muse-glimmer-30b-prose, finish_reason "stop", content "Hello!", predicted 26.79 tok/s.
- Final GET http://localhost:8099/running: [('muse-glimmer-30b', 'ready'), ('muse-glimmer-30b-prose', 'ready')], with both llama-server processes live. The embed mirror (qwen3-embed-8b-crucible) is on-demand (ttl 600) and was not requested during restore, so it is not resident at the end of the window — the same state it cycles through in normal operation (it loaded on request at 03:12 pre-sweep and unloads on TTL).
- Restore status: PASS. No seat was left down.

## Raw data

All raw JSON/CSV/logs and the exact scripts used are on Crucible under ~/glimmer-tune/sweep-2026-10-19/ : bench_pp512_tg128.json, bench_pp8192.json, server_tg.json (+ .log, .server.log), longtext-results.json, longtext_sweep.log, longtext-agent-nmax15.server.log, sweep_runner.sh, server_tg.py, longtext_bench_sweep.py, patch_longtext.py, STATUS, pilot.json/pilot.err (discarded pilot, provenance only). Local copies of the four result JSONs and server_tg.log are also in ~/workspace/glimmer/sweep-raw/ on this VM. Nothing from this sweep has been published anywhere.


