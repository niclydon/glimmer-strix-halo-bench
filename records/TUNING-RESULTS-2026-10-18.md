# Glimmer tuning bench results, Crucible, October 18, 2026

Muse Glimmer 30B (unsloth UD-Q4_K_XL + DFlash drafter) on a Ryzen AI Max+ 395 (Strix Halo, gfx1151, ROCm 7.2.1, llama.cpp b11719). Direct llama-server instances on a scratch port, one config per cell, llama.cpp `timings` as the metric source, temperature 0, 2 runs per cell. Raw data: Crucible `~/glimmer-tune/results-20261018-171138.json` (matrix) and `results-20261018-173706.json` (validation cell). Harness: `~/workspace/glimmer/tune_bench.py`.

## Measures

- decode: 93-token prompt, 512 tokens of open prose out.
- prefill: ~20.5k-token prompt, 8 tokens out.
- agent: Nexus-style system prompt + 3 tool definitions, one backlog-triage ask, ends in a tool call.

## Results (means of 2 runs)

| cell | decode tok/s | prefill tok/s | agent cold wall | agent decode tok/s | agent draft acc |
|---|---|---|---|---|---|
| deployed (n-max 16, q8_0 KV) | 17.3 | 356 | 4.6 s | 68 (60 / 76) | 0.64 |
| n-max 4, q8_0 | 17.4 | 358 | 6.3 s | 27 | 0.66 |
| n-max 4, f16 | 17.7 | 315 (one outlier run) | 6.1 s | 26 | 0.66 |
| n-max 4, f16, ub 256 | 18.6 | 336 | 6.4 s | 27 | 0.66 |
| n-max 4, f16, ub 1024 | 18.4 | 338 | 6.0 s | 28 | 0.68 |
| no spec, f16, ub 256 | 13.4 | 356 | 10.2 s | 13 | n/a |
| n-max 3, f16, ub 256 | 19.1 | 340 | 6.1 s | 30 | 0.82 |
| validation: n-max 15, f16, ub default | 16.6 | 349 | 4.1 s | 75 (73 / 78) | 0.74 |

## Findings

1. **The published DFlash sweet spot (n-max 3-4) is real for prose and wrong for agent turns.** On open prose, n-max 3 wins decode (19.1 tok/s) and essay draft acceptance collapses at n-max 16 (0.11). On tool-call turns, the picture inverts: the generated span is mostly predictable ATEM tool-call scaffolding, acceptance stays high (0.64-0.74) even at the longest blocks, and n-max 15-16 decodes the turn at 60-78 tok/s against ~27 at n-max 4. Cold agent-turn wall time: 4.1-4.6 s at n-max 15-16 vs ~6 s at n-max 3-4, 10.2 s with speculation off. A seat whose job is agent turns should run the longest in-range draft block.
2. **The deployed n-max 16 exceeds the DFlash block maximum.** The drafter's block is 16 tokens, so the maximum useful n-max is 15. n-max 15 reproduced the n-max 16 agent numbers (75 vs 68 tok/s, same band) at in-range settings.
3. **KV cache type is a wash at 64k on this model.** f16 vs q8_0 at n-max 4: 17.7 vs 17.4 tok/s decode, prefill indistinguishable once an outlier run is set aside. Glimmer's KV is small (2 KV heads, mostly SWA layers, ~2.1 GB at 131k), so f16 costs about 1 GiB; we adopt f16 for the published deep-context behavior (q8_0's deficit grows with depth) rather than for anything measured here.
4. **Ubatch does not transfer from Vulkan reports.** The reported gfx1151 optimum of ub 256 did not reproduce on this ROCm build: ub 256 and ub 1024 both prefilled ~5% slower than the default 512 (~336-338 vs ~356 tok/s), with tight within-cell dispersion. Default stays.
5. **Prefill is ~350 tok/s at 20k depth and no flag moved it.** N-max, KV type, and ubatch all land within noise of ~340-358. This is the hardware number for this model, depth, and backend, and it remains the binding constraint for cold agent turns with large system prompts.
6. **DFlash is worth ~1.4x on prose and ~2.3x on agent-turn wall time** versus speculation off (13.4 prose, 10.2 s agent wall). Tool-call reliability was perfect across every run of every cell: 16 of 16 agent measures ended in exactly one valid tool call.
7. Load time per instance was 8-16 s; the 8 s validation load is the fastest recorded, variance unexplained and not load-bearing.

## Applied configuration (prepared, pending Nic's go-ahead)

Homelab worktree branch `glimmer-tuned-flags` (off origin/main f04300e), one local commit:

- models-manifest.yaml, muse-glimmer-30b entry: `--cache-type-k f16 --cache-type-v f16`; new field `spec_draft_n_max: 15`.
- scripts/gen-llama-swap-config.py: the draft_model branch now honors per-entry `spec_draft_n_max` / `spec_draft_n_min` (defaults unchanged at 16 / 3). Generator tests: 8 passed, 17 subtests.
- Generated Crucible config diffed against the deployed file: exactly one line changes (the Glimmer cmd), exactly the three intended flags. No other stanza moves.

## Caveats

- 2 runs per cell. Between-cell prose-decode differences under ~1.5 tok/s are within the dispersion this bench shows; the agent-turn effect (2-3x) and the prefill ubatch deficit (consistent across two cells) are the results we stand on.
- Greedy decoding on this stack is not bit-reproducible across spec settings (output token counts differed slightly between cells), so agent measures carry output-shape variance; wall time and the timings rates are reported as measured.
- The agent measure's second run in each cell benefits from llama.cpp prompt-cache hits on the shared prompt prefix; cold (first-run) walls are the headline numbers.
- Permissive was hard-off before the bench; Crucible's only resident during the runs was the bench instance itself on the scratch port.
