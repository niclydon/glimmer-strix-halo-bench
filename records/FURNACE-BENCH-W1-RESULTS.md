# Furnace Bench Window 1 — Phase 2 Results

## Interpretation note - added 2026-10-24, after independent review

This record's DFlash-at-depth interpretation (a bimodal acceptance
distribution, with a high branch near 89 tok/s at n-max 15) does not
survive inspection of the saved outputs. The three runs per cell were
three different prompt variants; in every configuration the first two
variants continue the filler's own list of story instructions
(acceptance 0.76-1.00) and only the third writes the story (acceptance
0.09-0.47). The high rates are synthetic prompt-continuation
throughput, not story-generation performance, and no branch
probability can be estimated from one run each of three different
prompts. The same construction affects the shallow story-sweep means
cited elsewhere as a cross-check. Task-valid residue: the
story-variant observations (n=1 per cell), e.g. HIP n-max 15 at
15.34 tok/s vs 11.62 undrafted; Vulkan n-max 15 at 9.74 vs 11.66
undrafted. The llama-bench backend cells are unaffected. The original
text below is unchanged.

Status note (2026-10-24): status lines in this record ("not published anywhere") describe the moment of writing; the package was published later.


Glimmer benchmark program, Furnace (GMKtec EVO-X2, Ryzen AI Max+ 395 / Radeon 8060S gfx1151).
Phase 2 per `FURNACE-BENCH-PLAN.md`: canonical llama-bench (HIP vs Vulkan) + DFlash sweep.
Raw data: Furnace `~/glimmer-furnace-bench/results-w1/` (llama-bench JSON per cell, `dflash-server-results.json`, `summary-w1.txt`, `environment-manifest.txt`, server logs, restore log).
Not published anywhere; article package waits for Nic's approval.

## Window and methodology disclosure

- Model staged from Crucible `/services/models/muse-glimmer-30b/` over the Thunderbolt link into `~/glimmer-furnace-bench/models/` on Furnace (NOT `/services/models`). SHA-256 verified on Furnace before the window: main `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38`, dflash `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc`, mmproj `f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6`. All three match the Crucible pins.
- Builds: llama.cpp b11719, commit 5aeac37a3, HIP build (`build-hip`, backend reported as ROCm) and Vulkan build (`build-vulkan`, RADV GFX1151), both pre-existing side trees. Kernel 6.19.10-061910-generic, ROCm 7.2.1, BIOS EVO-X2 1.12.
- Co-residency during every reported bench run: NONE. Production was fully stopped (forge-api stopped; llama-swap masked `--runtime` and stopped; nexus-health-watchdog.timer stopped). Warmup runs were the tool's defaults and are discarded by llama-bench; the server sweep ran one discarded warmup completion per configuration.
- Power profile: no ACPI platform_profile file exists on this host and powerprofilesctl is not installed; CPU scaling governor recorded in the on-host manifest. This is a gap in the manifest, disclosed rather than filled in.
- Window timeline (UTC): first stop 2026-10-20T04:17:06Z. That stop did NOT hold: at 04:17:25Z `llama-swap-metrics.service` (`Wants=llama-swap.service`, 30 s timer) restarted llama-swap despite the runtime mask. A one-rep HIP probe cell run at 04:18 during that partial resurrection is DISCARDED and is not in any table below. The window was re-opened at 2026-10-20T04:27:31Z by additionally stopping `llama-swap-metrics.timer` and `llama-swap-reaper.timer` (the reaper also has `Wants=llama-swap.service`), then stopping llama-swap again and verifying it stayed inactive for 70 s (two metrics periods) with VRAM used at 169,684,992 B and no llama processes. All reported cells ran after 04:29Z. Window end (restore complete) 2026-10-20T07:14:36Z.
- llama-bench cells: 3 repetitions each, mean ± stddev (the tool's own statistics). Default ubatch 512 except the DFlash-baseline rows, which use the Crucible-winning ubatch 256 / KV f16 settings.
- DFlash method change (required): llama-bench b11719 has no draft-model parameters at all — `-md` returns `error: invalid parameter for argument: -md`, verified live. The DFlash sweep therefore ran through a scratch llama-server on port 5999 (the bench harness pattern from `furnace_bench.py`), one server per backend × n-max, KV f16, ubatch 256, ctx 40960, temp 0, cache_prompt false, 128 predicted tokens, 3 reps per cell. Depth 32768 cells used a filler prompt of 33,621 actual prompt tokens (recorded from server timings; the label is the target depth). Depth 0 cells used a 20-token prompt. The filler is a repeated sentence, and the generation prompt is a short story instruction; acceptance is measured on the generated story tokens. The repetitive context is a real caveat for the depth-32768 acceptance numbers (see the finding).
- Scratch hygiene: scratch servers only ever on port 5999, each terminated by the harness at the end of its configuration; final sweep found port 5999 free and no scratch llama-server processes.

## Canonical llama-bench: HIP vs Vulkan (tok/s, mean ± stddev, 3 reps)

### pp512 / tg128, ubatch 512

| Depth | HIP pp512 | HIP tg128 | Vulkan pp512 | Vulkan tg128 |
|---:|---:|---:|---:|---:|
| 0 | 448.47 ± 6.05 | 11.43 ± 0.36 | 363.90 ± 13.28 | 13.51 ± 0.02 |
| 4096 | 387.16 ± 4.33 | 10.75 ± 0.75 | 318.75 ± 2.30 | 13.35 ± 0.01 |
| 16384 | 323.95 ± 59.87 | 5.99 ± 0.17 | 294.43 ± 2.88 | 13.13 ± 0.04 |
| 32768 | 273.06 ± 17.91 | 6.43 ± 0.49 | 266.41 ± 1.28 | 13.07 ± 0.02 |
| 65536 | 271.37 ± 8.65 | 4.83 ± 0.37 | 220.06 ± 3.06 | 12.71 ± 0.01 |

### pp8192, ubatch 512

| Depth | HIP pp8192 | Vulkan pp8192 |
|---:|---:|---:|
| 0 | 336.75 ± 4.73 | 325.83 ± 0.47 |
| 4096 | 331.63 ± 9.76 | 313.81 ± 0.35 |
| 16384 | 265.31 ± 7.97 | 287.54 ± 0.24 |
| 32768 | 257.22 ± 1.10 | 259.17 ± 0.34 |
| 65536 | 278.63 ± 7.40 | 216.94 ± 0.59 |

### Baseline at the DFlash settings (ubatch 256, KV f16), pp512 / tg128

| Depth | HIP pp512 | HIP tg128 | Vulkan pp512 | Vulkan tg128 |
|---:|---:|---:|---:|---:|
| 0 | 397.34 ± 10.78 | 11.32 ± 0.78 | 360.39 ± 13.66 | 13.55 ± 0.01 |
| 32768 | 308.43 ± 14.01 | 11.12 ± 0.94 | 258.92 ± 0.31 | 13.03 ± 0.04 |

Read of the backend comparison:

- Prefill: HIP is faster at pp512 at every depth (by 3–23%), and at pp8192 for shallow depths; Vulkan pp8192 overtakes HIP at depth 16384 (287.54 vs 265.31) and matches at 32768, then falls behind again at 65536. HIP pp8192 at depth 65536 (278.63) is non-monotonic against its own 32768 value; stddev there is ±7.40, so treat the 65536 HIP pp8192 point as noisy.
- Decode is the split that matters: Vulkan tg128 is essentially flat with depth (13.51 → 12.71, −6% across 0→65536) with near-zero dispersion (±0.01–0.04). HIP tg128 at ubatch 512 falls off a cliff between depth 4096 and 16384 (10.75 → 5.99) and keeps falling to 4.83 at 65536 (−58%). At depth 65536 Vulkan decode is 2.6× HIP decode at the canonical settings.
- The HIP decode cliff is ubatch-sensitive, not a pure backend constant: at ubatch 256 (the DFlash settings), HIP tg128 at depth 32768 is 11.12 instead of 6.43, and its pp512 at that depth is also higher (308.43 vs 273.06). Anyone reproducing the HIP cliff should check ubatch first. Vulkan shows no such sensitivity (13.07 at ub512 vs 13.03 at ub256, depth 32768).

## DFlash sweep (llama-server, KV f16, ubatch 256; tg tok/s, 3 reps)

Acceptance is the server-reported draft acceptance for that rep (accepted/generated, mean accepted length). Per-rep values are shown because the distribution is bimodal: in nearly every cell, two reps take a high-acceptance generation path and one rep takes a low-acceptance path, on both backends, with identical accepted/generated counts across backends on the shared paths. A mean alone would misrepresent these cells.

### Depth 0 (20-token prompt)

| n-max | HIP tg mean ± sd (reps) | HIP acceptance (reps) | Vulkan tg mean ± sd (reps) | Vulkan acceptance (reps) |
|---:|---|---|---|---|
| off | 12.28 ± 0.25 (12.35, 11.94, 12.55) | — | 13.27 ± 0.09 (13.15, 13.33, 13.32) | — |
| 2 | 25.70 ± 3.07 (27.66, 28.08, 21.37) | 0.921, 0.965, 0.563 | 27.45 ± 3.67 (29.79, 30.30, 22.26) | 0.921, 0.977, 0.586 |
| 3 | 29.64 ± 6.09 (35.08, 32.69, 21.14) | 0.850, 0.902, 0.456 | 28.04 ± 4.40 (30.37, 31.87, 21.88) | 0.788, 0.902, 0.503 |
| 4 | 19.78 ± 6.74 (12.35, 28.66, 18.32) | 0.766, 0.766, 0.416 | 27.60 ± 5.48 (32.71, 30.08, 20.00) | 0.748, 0.766, 0.416 |
| 6 | 25.10 ± 6.14 (31.63, 26.79, 16.88) | 0.664, 0.615, 0.308 | 24.66 ± 5.45 (30.57, 26.00, 17.42) | 0.664, 0.615, 0.341 |
| 8 | 31.93 ± 7.41 (38.19, 36.08, 21.52) | 0.560, 0.495, 0.249 | 21.44 ± 5.27 (26.29, 23.91, 14.11) | 0.565, 0.515, 0.249 |
| 15 | 39.13 ± 12.38 (50.50, 44.98, 21.92) | 0.380, 0.388, 0.155 | 23.70 ± 6.81 (29.64, 27.30, 14.17) | 0.360, 0.342, 0.141 |

### Depth 32768 (actual prompt 33,621 tokens) — the headline cells

| n-max | HIP tg mean ± sd (reps) | HIP acceptance (reps) | Vulkan tg mean ± sd (reps) | Vulkan acceptance (reps) |
|---:|---|---|---|---|
| off | 10.00 ± 1.28 (9.90, 8.48, 11.62) | — | 10.52 ± 0.98 (10.64, 9.27, 11.66) | — |
| 2 | 22.91 ± 4.66 (25.41, 26.94, 16.39) | 0.988, 1.000, 0.397 | 24.39 ± 4.01 (28.31, 25.98, 18.89) | 0.988, 1.000, 0.469 |
| 3 | 18.95 ± 6.05 (27.50, 14.35, 15.01) | 0.949, 0.930, 0.264 | 25.46 ± 7.04 (30.45, 30.43, 15.50) | 0.930, 0.930, 0.292 |
| 4 | 21.84 ± 6.03 (28.95, 22.38, 14.20) | 0.867, 0.867, 0.241 | 25.18 ± 7.18 (30.64, 29.88, 15.04) | 0.867, 0.836, 0.285 |
| 6 | 22.48 ± 8.49 (29.70, 27.19, 10.56) | 0.802, 0.802, 0.184 | 24.16 ± 7.92 (28.82, 30.65, 13.01) | 0.759, 0.802, 0.235 |
| 8 | 30.71 ± 13.29 (31.55, 46.55, 14.04) | 0.840, 0.801, 0.143 | 24.05 ± 9.36 (31.65, 29.64, 10.86) | 0.840, 0.784, 0.192 |
| 15 | 64.68 ± 34.89 (88.97, 89.74, 15.34) | 0.922, 0.887, 0.107 | 40.63 ± 21.85 (55.94, 56.21, 9.74) | 0.922, 0.922, 0.091 |

## The depth-32768 DFlash finding

DFlash does not collapse at depth 32768 on Strix Halo, on either backend. That is the result, called out either way as the plan required: at the Crucible-winning settings, every n-max ≥ 2 beats the no-draft baseline at depth on both backends (baseline ~10.0 HIP / ~10.5 Vulkan server tg), and acceptance on the high branch is as high at depth as at depth 0 (0.93–1.00 for n-max 2–4). Two qualifications, both in the data:

1. It is acceptance-gated and bimodal. Roughly one rep in three (always the rep whose generation path diverged) falls to acceptance 0.09–0.47 and tg 10–19, near or barely above baseline. The mean is a mix of two regimes, not a typical run; the tables above keep the reps separate for exactly this reason.
2. n-max 15 at depth is the extreme case: HIP reps of 88.97 and 89.74 tok/s (acceptance 0.92/0.89, mean accepted length 14.11 — nearly the whole draft, every round) against a third rep at 15.34 (acceptance 0.107). Vulkan shows the same branch structure lower (55.94, 56.21, 9.74). The 33.6k-token context here is a repeated-sentence filler, which likely makes the following story generation more predictable than natural 32k context would; the honest claim is "on this depth construction, the high branch exists and is large", with a natural-text depth replication still owed before the article treats 89 tok/s as a general depth-32768 number.

Backend read for DFlash: at depth 0, HIP wins the larger drafts (n-max 8 and 15 means clearly ahead); at depth 32768, Vulkan is the steadier mid-range (n-max 3–6 means ahead, tighter high branch), while HIP owns the n-max 15 ceiling. Neither backend breaks DFlash at depth.

## Restore verification (all 2026-10-20, UTC)

Restore ran in the prescribed order and every step was verified live:

1. `systemctl unmask --runtime llama-swap` — runtime mask symlink removed.
2. `systemctl start llama-swap` — active.
3. Always-on preload: GET http://localhost:8099/running showed all three residents ready at 07:13:17Z (~165 s after start, sequential preload): `qwen3-30b-a3b-instruct-2507` ready, `qwen3-8b` ready, `qwen3-embed-8b` ready. Full response saved as `results-w1/restore-running.json`.
4. `nexus-health-watchdog.timer` started — active. The two extra timers stopped for the window, `llama-swap-metrics.timer` and `llama-swap-reaper.timer`, were also restarted — both active.
5. `forge-api` started — active. Forge smoke: POST http://localhost:8642/v1/chat/completions, model `default-chat`, returned HTTP 200 on the second attempt (first attempt raced the startup), served by `qwen3-30b-a3b-instruct-2507` with content "Hello!" — saved as `results-w1/forge-smoke.json`.
6. `forge-mcp`, which had stopped as a dependent of forge-api, was restarted — active.
7. VRAM after restore: 61,768,871,936 B used (production residents), matching the pre-window posture. Port 5999 free, no scratch servers remain.

Production was down only inside the window above and is fully restored and smoke-verified. Nothing was published.
