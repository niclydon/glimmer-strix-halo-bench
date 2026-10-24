# Furnace Bench Window 2 — Phase 3 Results

Glimmer benchmark program, Furnace (GMKtec EVO-X2, Ryzen AI Max+ 395 / Radeon 8060S gfx1151).
Phase 3 per `FURNACE-BENCH-PLAN.md`: serving shape (context × parallel slots), KV f16 vs q8_0 at full 131k depth, prefill ubatch/batch focus, and the agent workload suite on the real serving path.
Raw data: Furnace `~/glimmer-furnace-bench/results-w2/` (`results-w2.json`, per-config server logs, `environment-manifest.txt`, window-open and restore logs, pre-window and post-restore `/running` snapshots, Forge smoke response). Harness: `bench_w2.py` in this directory (run on Furnace, detached, incremental JSON writes).
Not published anywhere; the article package waits for Nic's approval.

## Verdicts called out

**131k KV verdict.** At full depth (actual prompt 123,918 tokens, ctx 131072, DFlash n-max 15, HIP), the published claim that q8_0's deficit grows to ~21% at 131k is **directionally confirmed for decode and exceeded, and does not hold for prefill**. q8_0 decode was 10.03 ± 1.01 tok/s against f16's 14.35 ± 0.67 (a 30.2% deficit, non-overlapping dispersions at n=2), while prefill was 260.10 ± 13.53 vs 274.52 ± 7.24 tok/s (a 5.3% deficit, within reach of noise). The deficit at depth lives in decode, not prefill. f16 KV at deep context is the right call on this model and backend, for the decode reason.

**Greedy-reproducibility verdict.** Greedy decoding (temp 0, seed 1234, same prompt, 5 runs, cache_prompt off) is **not bit-reproducible with DFlash on, and is bit-reproducible with it off**. With the production-shaped speculative config (draft-dflash, n-max 15): 3 distinct outputs across 5 runs (two pairs and a singleton). Without any draft model, same everything: 5 of 5 identical hashes. The non-reproducibility cited in the Oct 18 tuning notes is a property of the speculative configuration, not of the base sampler on this stack.

## Window and methodology disclosure

- Serving path: the production HIP build, `/services/llama.cpp/build/bin/llama-server` (llama.cpp b11719, commit 5aeac37a3), as a scratch server on port 5999 only. The installed llama-swap config was never edited. All Phase 3 cells ran DFlash (draft-dflash, n-max 15, the Crucible-winning setting) except the prefill section, which ran draft-off to isolate prefill, as noted there.
- Model: staged GGUFs in `~/glimmer-furnace-bench/models/` (NOT `/services/models`). dflash and mmproj verified against pins on first read. The main GGUF produced an anomaly: one background-delivered sha256 read during preconditions reported a mismatch (`0be3db7…`) while foreground reads before and after reported the pinned `82bece30…`, with identical size and mtime throughout. Per the task instruction for a mismatch, the file was re-copied from Crucible `/services/models/muse-glimmer-30b/` and verified foreground twice (both `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38`) before the window opened. The bench ran on the re-copied, twice-verified file.
- Data-integrity note: two background-delivered progress outputs during this run contained shifted or invented details (timestamps offset by ~1h, a flipped greedy result, invented per-case walls). Every number in this record was recomputed from a foreground read of `results-w2.json` after completion; nothing below derives from a delivered progress summary.
- Co-residency: production was fully stopped (forge-api and forge-mcp stopped; llama-swap masked `--runtime` and stopped; nexus-health-watchdog, llama-swap-metrics, and llama-swap-reaper timers stopped; stop verified held across 70 s with VRAM used at 169,684,992 B and no llama processes). The GPU was exclusive to the bench. CPU co-residency was NOT zero: Furnace's own estate churn (Nexus CI runners running tsc/vitest, codex builder sessions, Postgres) ran throughout, at load 25-33 (32 threads) during the first matrix cell, subsiding to load 6.5-9 for the rest of the window. The ctx-65536/parallel-1 matrix cell ran inside the load peak and is flagged contaminated where it appears; all other cells ran at load ≤ ~15 falling to ~7.
- Window timeline (UTC): first stop 2026-10-22T03:17:39Z; bench 03:20:12Z to 04:44:54Z; restore complete 05:36:05Z. Production remained down between bench end and restore start (~50 min) because the run's progress checks were on ~29-minute cycles; that gap is operator cadence, not a restore failure, and is disclosed as such.
- Repetitions: 2 per cell unless stated; mean ± population stddev. Warmup completions discarded per config. llama.cpp `timings` is the rate source except where a wall-derived rate is named; the two agree closely in the raw data of this window (the timings-vs-wall divergence suspected mid-run did not survive the foreground re-read).
- Agent-suite path: direct llama-server chat completions, no Forge in the path, so no Forge response cache exists to defeat; every agent call additionally carried a unique nonce in the user turn. Server default `chat-template-kwargs {"reasoning_strength":"low"}` (the control proven for this model on Oct 18), per-request overrides for the reasoning-tax cells.

## Serving matrix (DFlash n-max 15, KV f16, ub 512, b 2048, temp 0, 512-token generations, short prompts)

| ctx | slots | aggregate tok/s | per-slot tok/s (wall) | draft acceptance |
|---:|---:|---:|---:|---:|
| 65536 | 1 | 6.32 ± 0.23 | 6.32 ± 0.23 | 0.15 ± 0.03 |
| 65536 | 2 | 17.91 ± 6.41 | 9.98 ± 4.10 | 0.25 ± 0.09 |
| 65536 | 4 | 15.54 ± 0.54 | 5.29 ± 1.82 | 0.08 ± 0.06 |
| 131072 | 1 | 15.41 ± 1.22 | 15.41 ± 1.22 | 0.21 ± 0.01 |
| 131072 | 2 | 16.19 ± 0.10 | 9.75 ± 5.06 | 0.09 ± 0.06 |
| 131072 | 4 | 19.49 ± 0.66 | 6.30 ± 1.52 | 0.10 ± 0.05 |

Read: once the load peak passed, aggregate throughput is roughly conserved at ~15-19 tok/s no matter how the slots are sliced: parallel slots buy concurrency, not speed, replicating the Oct 18 Forge-path finding (~17 tok/s total across 2 slots) on the direct serving path and extending it to 4 slots and both context sizes. The ctx-65536/1 cell (6.32) is the load-contaminated outlier and should not be read as a context effect; the same shape at 131072 under quiet load gives 15.41. Draft acceptance on this open-prose workload is low (0.08-0.25) at n-max 15, consistent with the Oct 18 tuning finding that prose acceptance collapses at long draft blocks while agent-turn acceptance stays high.

## KV comparison at full 131k depth (prompt 123,918 tokens, 256-token generation, DFlash n-max 15)

| KV | prefill tok/s | decode tok/s (timings) |
|---|---:|---:|
| f16 | 274.52 ± 7.24 | 14.35 ± 0.67 |
| q8_0 | 260.10 ± 13.53 | 10.03 ± 1.01 |
| q8_0 deficit | 5.3% | 30.2% |

Verdict as called out above: the ~21%-at-131k claim understates the decode deficit on HIP (30.2%) and overstates the prefill one (5.3%). n=2 per cell; the decode gap is ~4x the larger stddev, the prefill gap is inside 1 stddev of the q8_0 cell.

## Prefill focus (20,491-token prompt, 8-token generation, draft off, KV f16, ctx 65536)

| ubatch | batch | prefill tok/s |
|---:|---:|---:|
| 256 | 2048 | 314.34 ± 1.50 |
| 512 | 2048 | 329.29 ± 8.37 |
| 1024 | 2048 | 326.69 ± 15.61 |
| 256 | 8192 | 261.47 ± 5.20 |
| 512 | 8192 | 334.44 ± 13.41 |
| 1024 | 8192 | 357.28 ± 2.99 |

Read: at batch 2048, ubatch is a wash (314-329, overlapping dispersions), replicating the Crucible result that the Vulkan-reported ub-256 optimum does not transfer to HIP. Batch 8192 interacts: it is the best cell at ub 1024 (357.28 ± 2.99, ~8% over the ub512/b2048 production default) and the worst at ub 256 (261.47). One pair of settings does not make a tuning law at n=2; the defensible claim is that the default (ub 512, b 2048, ~329) is within ~8% of the best cell found, and ub 256 + b 8192 is a combination to avoid.

## Agent suite (ctx 65536, parallel 2, KV f16, DFlash n-max 15, reasoning_strength low default)

- Tool calls: **20/20 valid** across the 20-prompt set (5 tools × 4 phrasings, the Oct 18 tool set extended), each with a unique nonce, temp 0. Every call named the expected function with parseable JSON args containing the required key. Walls 1.87-4.82 s.
- JSON validity, uncached: **5/5 raw-parse, 5/5 after think-strip, 5/5 nonce-ref echoes**. This differs from Oct 18 (0/5 raw through Forge) in the raw column: on this direct path with the server-default reasoning_strength=low, no response carried a think prefix that broke raw parsing. The measurement is genuinely uncached (direct server, unique nonce per call, ref value required in the object and matched). The Oct 18 raw failures and tonight's raw passes differ in path and reasoning control together; the record states the outcomes, not a single-cause claim.
- Multi-turn prompt cache: 4-turn conversation over a ~6.1k-token shared prefix. Cache hit rate (cache_n / (cache_n + prompt_n) from server timings, corroborated by usage.prompt_tokens_details.cached_tokens): turn 0 (cold) 0.0%, turns 1-3: 99.7%, 99.6%, 99.7%. After the first turn, effectively the entire prefix is served from cache every turn.
- Reasoning token tax (same incident-summary prompt, max_tokens 2000, finish=stop everywhere, final answer ~370-411 chars at every level):

| level | completion tokens (2 reps) | reasoning chars | wall s |
|---|---|---:|---:|
| low | 160, 164 | 287, 287 | 7.82, 6.16 |
| medium | 360, 387 | 1286, 1399 | 10.96, 12.23 |
| high | 589, 587 | 2376, 2379 | 19.47, 29.83 |

The chat-template-kwargs control is clean and monotonic for this prose shape: medium costs ~2.3x low's tokens, high ~3.6x, for an identical-length visible answer. Within-level dispersion is small (the high-level wall spread, 19.5 vs 29.8 s at near-identical token counts, is the one loose thread and is within the night's CPU-contention noise).

## Sampling and greedy reproducibility (agent server, 256-token generations)

| setting | decode tok/s (timings) | outputs |
|---|---:|---|
| Meta card (temp 1.0, top-p 0.95, top-k 64) | 12.31 ± 0.55 | 3 runs, 3 distinct |
| temp 0 (chat path, no fixed seed) | 11.50 ± 2.38 | 3 runs, 2 distinct (runs 1 and 3 identical) |
| greedy test, DFlash on (temp 0, seed 1234, /completion) | — | 5 runs, **3 distinct** |
| greedy test, draft off (temp 0, seed 1234, /completion) | — | 5 runs, **5 identical** |

Verdict as called out above. Secondary variables on the record: the draft-on greedy run served from the parallel-2 agent server, the draft-off run from the parallel-1 prefill server; the speculative configuration is the named difference, with slot parallelism as a recorded covariate. Temp-0 through the chat path without a fixed seed landed on the same output in 2 of 3 runs, which is consistent with the draft-path picture: usually converged, not guaranteed.

## Environment manifest (summary; full text in results-w2/environment-manifest.txt)

GMKtec EVO-X2, Ryzen AI Max+ 395 (Radeon 8060S, gfx1151), kernel 6.19.10-061910-generic, ROCm 7.2.1, BIOS 1.12 (Phase 0). Serving build: production HIP llama.cpp b11719 (5aeac37a3) at `/services/llama.cpp/build/bin/llama-server`. GGUF sha256 (post-recopy, verified): main `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38`, dflash `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc`, mmproj `f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6` (mmproj staged and pinned; Phase 3 runs no vision pass, that is Phase 4). No ACPI platform_profile on this host and powerprofilesctl absent (same manifest gap as W1, disclosed). VRAM: 48,239,415,296 B used pre-window, 169,684,992 B in-window free state, 47,729,635,328 B after restore.

## Restore verification (2026-10-22, UTC)

Restore ran in the prescribed order and every step was verified live. One divergence from the task text, on the record: the task's restore spec named the W1-era trio (qwen3-30b-a3b-instruct-2507, qwen3-8b, qwen3-embed-8b) and a qwen3-30b smoke, but production had changed since the task was written. Verified live before the window (03:07Z `/running`) and in the pre-window snapshot, the resident trio was gemma-4-chat-12b, qwen3-8b, qwen3-embed-8b, per the Oct 21 operator decision that restored Gemma as the resident generation seat and retired the Qwen seat. Restore targeted the actual pre-window state, not the stale spec:

1. Scratch sweep: port 5999 free, no scratch llama-server processes.
2. `systemctl unmask --runtime llama-swap` — runtime mask symlink removed.
3. `systemctl start llama-swap` — active; preload complete ~90 s after start: GET http://localhost:8099/running showed gemma-4-chat-12b, qwen3-8b, qwen3-embed-8b all ready. Saved as `results-w2/restore-running-final.json`.
4. Timers restarted and active: nexus-health-watchdog.timer, llama-swap-metrics.timer, llama-swap-reaper.timer.
5. `forge-api` started — active; `forge-mcp` active.
6. Forge smoke: POST http://localhost:8642/v1/chat/completions, model `default-chat`, HTTP 200 on the second attempt (first raced startup), content `SMOKE_OK`, model_resolution canonical `gemma-4-chat-12b`. Saved as `results-w2/forge-smoke.json`.

Production was down only inside the window above (03:17:39Z to 05:36:05Z, including the disclosed post-bench cadence gap) and is fully restored and smoke-verified. The optional Forge-in-front-of-scratch pass was not run: after restore, Forge's default-chat resolves to Gemma, and re-pointing production routing at the scratch Glimmer server was outside this window's authority; Forge-path Glimmer numbers exist from Oct 18. Nothing was published.
