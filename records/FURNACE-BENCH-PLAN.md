# Furnace Glimmer benchmark program — plan

Commissioned by Nic, Oct 18, 2026: full, comprehensive, extensive benchmarking of Muse Glimmer 30B on the Furnace hardware, to be published together with the Crucible results. Premise: nobody is publishing Glimmer numbers on Strix Halo; we will.

Furnace is the same silicon as Crucible (Ryzen AI Max+ 395, Radeon 8060S gfx1151, ROCm 7.2.1) in a different serving role: it carries production default-chat (gemma-4-chat-12b) through its own llama-swap and Forge. That difference is the point. Crucible gives the tuned single-model picture; Furnace gives cross-validation on a second machine, the production-serving picture, and the one comparison the public record completely lacks: ROCm/HIP vs Vulkan on identical Strix Halo hardware (every public Strix Halo number, including AMD's 24 tok/s, is Vulkan on Windows).

## Phase 0 — discovery (no changes)

Verify and record, foreground: Furnace llama.cpp build and backend(s) (expected b9496, which predates the muse-glimmer arch at b10362+, so an upgrade is a hard prerequisite), llama-swap version and residents, UMA/GTT carve-out size, free disk for a second model tree, kernel and firmware versions, power profile tooling. Output: an environment manifest seed file in the bench repo. No production touch.

## Phase 1 — builds (side trees only)

- HIP/ROCm build of llama.cpp at the same commit as Crucible's b11719 (5aeac37a3), in a side tree (llama.cpp-next pattern), ROCm path and HIP compiler pinned exactly as on Crucible. Production build untouched.
- Vulkan build of the same commit (RADV), same tree discipline. This is the head-to-head backend.
- Stage the three GGUFs from Crucible, sha256-verified against the Crucible copies (main UD-Q4_K_XL 82bece30..., dflash 27d9a805..., mmproj f48b4523...).
- Optional tier: UD-Q5_K_XL and Q6_K quants from the same Unsloth repo, for the quant ladder (Phase 4).

## Phase 2 — canonical + DFlash (maintenance window 1)

llama-bench, the community-canonical shape, on both backends:
- pp512 / tg128 at depths 0, 4096, 16384, 32768, 65536 (-d sweep), 3+ repetitions, mean and standard deviation reported.
- pp8192 for the agent-context regime.
- DFlash sweep at the Crucible-winning KV/ubatch settings: n-max off / 2 / 3 / 4 / 6 / 8 / 15, at depth 0 and depth 32768, recording draft acceptance alongside tg. The depth-32k DFlash2 behavior on ROCm is unpublished anywhere; this is a headline result either way.
- Furnace's production gemma stays down or co-resident per the window decision made in Phase 0; whichever it is gets disclosed in the published methodology.

## Phase 3 — serving shape + agent workload (maintenance window 2)

llama-server (the real serving path, Forge in front for one pass):
- Context 65536 and 131072; parallel slots 1 / 2 / 4; aggregate vs per-slot throughput.
- KV f16 vs q8_0 at full 131k depth (direct test of the published claim that q8_0's deficit grows to ~21% at 131k, on a model whose KV is small enough that the answer is genuinely uncertain).
- Ubatch 256 / 512 / 1024 and batch 2048 / 8192, prefill-focused.
- The agent suite from the Crucible bench, extended: tool-call validity across 20 prompts, JSON validity measured uncached (Forge response cache explicitly defeated, per the Oct 18 bench caveat), multi-turn runs reporting prompt-cache hit rates, reasoning-level token tax at low / medium / high.
- Sampling at Meta's card settings (temp 1.0, top-p 0.95, top-k 64) and at temp 0, both reported; the greedy non-reproducibility note gets tested, not just cited (same prompt, same seed, 5 runs).

## Phase 4 — quant ladder, power, stretch (maintenance window 3)

- Quant ladder: UD-Q4_K_XL vs UD-Q5_K_XL vs Q6_K — decode/prefill deltas plus the agent suite as a coarse quality check. Question being answered: is the quality worth roughly 25% slower decode on this bandwidth ceiling?
- Power and thermal: rocm-smi sampled at 1 Hz through the tg runs and a 30-minute decode soak; report watts, tokens per joule, and any clock decay. Perf-per-watt is the Strix Halo story and nobody publishes it for this model.
- Stretch: mmproj wired for one vision pass (image understanding smoke + timings). No published Glimmer vision numbers on Strix Halo exist either.

## Methodology (the academic angle, applies to both machines)

- Every run emits an environment manifest: kernel, ROCm, BIOS/firmware, llama.cpp commit and build flags, GGUF sha256, tool versions, power profile, ambient notes.
- Warmup runs discarded; repetitions with dispersion, never single-run headlines.
- Raw JSON/CSV and the exact harness scripts published in a public GitHub repo alongside the article; negative and null results included.
- Co-residency and background load during every run disclosed by name.
- Telemetry scope per Nic's Oct 18 decision: no Langfuse, no dbt in the bench path. Serving-path numbers come from Forge requests.db where Forge is in the loop; everything else is files in the repo. Revisit only if the runs become a longitudinal dataset.

## Publication package

- The article: Crucible tuning story + Furnace comprehensive results as one piece (dev.to primary, cross-posted to Nic's own blog; final text and venue get Nic's approval before anything posts).
- The bench repo: harness, manifests, raw data, results tables.
- Pointers where the audience is: a Hugging Face model-page discussion linking the results, and a llama.cpp discussion post if the backend comparison shows a material HIP-vs-Vulkan delta.

## Sequencing and gates

Phase 0-1 need no window and no production touch. Phases 2-4 each need a Furnace window where displacing or sharing the GPU with production gemma is acceptable; windows are scheduled with Nic, not taken. The Crucible tuning results (in progress Oct 18) land first and set the Furnace matrix's starting settings.
