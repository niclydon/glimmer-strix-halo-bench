# Furnace Bench Window 3 — Phase 4 Results

## Interpretation note - added 2026-10-24, after independent review

Four corrections. (1) The quant quality language below overstates the
suite: the tool-call score is a signature check (expected function
plus one required argument key), this run did not retain full
arguments, and equal scores do not establish quality equivalence.
(2) The soak's two per-request rate clusters (9.1-16.4 and 55-84
tok/s) have no recorded outputs or acceptance counters; their cause
is unverified and they should not be attributed to window 1's
acceptance patterns. (3) Counts: the power CSV holds 6,757
measurement rows plus its header; the soak slice is 1,826 rows.
(4) One stored field was wrong in the original capture: stddev_ns
for the UD-Q5_K_XL depth-0 tg128 row read 3,345,753,631 ns against
its own samples ([20100486487, 17570304335, 19889302226] ns; sample
stdev 1,403,814,549.29 ns). The publication copies of the data
correct the derived field from the samples; token/s figures were
always consistent and unaffected. Thermal language below is scoped
to the single 30-minute soak described. The original text below is
unchanged.


Glimmer benchmark program, Furnace (GMKtec EVO-X2, Ryzen AI Max+ 395 / Radeon 8060S gfx1151).
Phase 4 per `FURNACE-BENCH-PLAN.md`: quant ladder (UD-Q4_K_XL vs UD-Q5_K_XL vs UD-Q6_K_XL), power and thermal (1 Hz rocm-smi through the runs plus a 30-minute sustained decode soak), and the mmproj vision stretch.
Raw data: Furnace `~/glimmer-furnace-bench/results-w3/` (`results-w3.json`, per-quant `llamabench-*.json`, `power.csv` 1 Hz samples, `phases.csv` phase boundaries, per-config server logs, `environment-manifest.txt`, window-open / download / restore logs, `forge-smoke.json`, `vision-test.png`). Harness: `bench_w3.py` + `w3_power_sampler.py` + `analyze_w3.py` in this directory (copies on Furnace in `~/glimmer-furnace-bench/`).
Not published anywhere; the article package waits for Nic's approval.

**With this window, the bench data for the publication package is complete** (Phases 2, 3, and 4 all run on Furnace; Crucible tuning landed Oct 18). What remains is article text and venue, which need Nic's approval.

## Verdicts called out

**Quant ladder verdict.** The higher quants cost far more decode than the plan's ~25% premise, and the coarse quality check shows nothing bought with it. At depth 0, tg128 decode: UD-Q4_K_XL 11.65 tok/s vs UD-Q5_K_XL 6.70 (−42%) vs UD-Q6_K_XL 7.30 (−37%). At depth 32768: 12.21 vs 8.29 (−32%) vs 6.92 (−43%). On the agent-suite subset (20 tool calls + 5 JSON prompts, the W2 set), **all three quants scored identically: 20/20 valid tool calls and 5/5 JSON (raw, think-stripped, and nonce-ref) at every quant**. That suite has a ceiling effect and cannot rule out subtler quality differences (reasoning depth, long-form prose), but on the only quality evidence this program collects, the extra bits buy nothing measurable on this bandwidth ceiling while costing a third to two-fifths of decode speed. UD-Q4_K_XL stays the right quant for this hardware. One anomaly, as measured: at depth 0, Q5 decode (6.70 ± 0.51) landed *below* Q6 (7.30 ± 0.06) with non-overlapping dispersion; at depth 32768 the expected order restored (Q5 8.29 > Q6 6.92). No explanation is claimed for the depth-0 inversion.

**Soak verdict: no clock decay, no thermal wall.** Across the full 30-minute sustained decode soak on UD-Q4_K_XL, mean sclk was 1969 MHz in the first 5 minutes and 2209 MHz in the last 5; mean socket power rose 74.9 W → 81.8 W and mean edge temperature 51.5 °C → 58.0 °C (peak 66 °C) as the chassis heat-soaked, with clocks *rising*, not decaying. Perf-per-watt for the soak's serving shape: **0.203 tokens/joule** at a mean 80.0 W (29,696 tokens, 146.2 kJ over 1827 s).

**Vision verdict: one clean pass, one noted miss.** The mmproj wired up on the first attempt and the model described the synthetic ground-truth image substantially correctly (shapes, colors, and positions), with one framing error on the red rectangle (below). Load 21.0 s, prefill 214.9 tok/s (303 prompt tokens including image tokens), decode 11.14 tok/s.

## Window and methodology disclosure

- **Pre-window production state was NOT the W1-era state, and the restore targeted the actual state.** This window ran inside Nic's 12-hour backlog sprint (ordered 2026-10-23 21:16 ET, Ledger chat): at the pre-window check (2026-10-24T03:07Z) llama-swap and the llama-swap-metrics / llama-swap-reaper / nexus-health-watchdog timers were already **inactive** (stopped for the sprint, with an explicit "do not restart them during the sprint" directive), forge-api and forge-mcp were active, and VRAM was already free (169,684,992 B used). The bench task text's restore spec (start llama-swap, trio ready, qwen3-30b smoke) was stale on two counts — the sprint posture, and the W2 finding that the resident trio and default-chat seat had already changed. Following the W2 precedent, the window stopped only what was running (forge-api; forge-mcp followed as a dependent), runtime-masked llama-swap as a guard, and restored to the verified pre-window state. The divergence is recorded here loudly rather than silently resolved. Answering the open question later recorded against OB-68208: **the Oct 23 23:10 ET stop of forge-api/forge-mcp was this scheduled bench window** (window-open log, 2026-10-24T03:10:37Z), not a pane overreaching.
- Window timeline (UTC): window open 2026-10-24T03:10:37Z (forge-api stop) through restore complete 05:06:31Z. Phases: Q4 ladder first pass 03:12–03:16Z; soak 03:19:39–03:49:46Z; vision 03:50Z; agent Q4/Q5 04:05–04:14Z; Q6 download completed 04:45Z (see download note); supplemental ladder (all three quants, one coherent run) 04:47–04:58Z; supplemental agent (all three quants) 04:58–05:04Z. The ladder and agent tables below are from the supplemental runs; the first-pass Q4 cells agreed with them (Q4 tg128 depth 0: 9.93 first pass vs 11.65 supplemental; the ladder was run three times for Q4 across the night with consistent ordering).
- Builds: llama.cpp b11719, commit 5aeac37a3, HIP bench build (`~/llama.cpp-bench/build-hip`), for both llama-bench and the scratch llama-server. Kernel 6.19.10-061910-generic, ROCm 7.2.1, BIOS EVO-X2 1.12. No ACPI platform_profile on this host and powerprofilesctl absent (same manifest gap as W1/W2, disclosed).
- GGUF sha256, all verified foreground on Furnace: main UD-Q4_K_XL `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38`, dflash `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc`, mmproj `f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6` (all match the program pins). Ladder files downloaded this window from `unsloth/Muse-Glimmer-30B-GGUF` and verified against the repo's LFS hashes: UD-Q5_K_XL (21,789,618,976 B) `97a66c4b41d9e778af7cdfa43508e08dbf765fb5049b740c69ad815e5191c637`; UD-Q6_K_XL (26,265,362,976 B) `fb5f80d110c4fa932cc652e70873c0bd12c0954009038aa675e65086104c2739`. Naming note: the repo carries no plain `Q6_K` file; the Q6 rung is its `UD-Q6_K_XL`, and it is named that way throughout this record.
- Download note (affects scheduling, not data): the Q5/Q6 downloads were the night's long pole. Unauthenticated HF transfers stalled repeatedly (one ~5-minute Q5 stall self-recovered), the first Q6 hf attempt wedged at 5.09 GB and was restarted, and the first aria2c attempt died at ~14 GB when the CDN signed URL expired (HTTP 403); a resumed aria2c run with a fresh URL completed it. An early partial Q6 file was visible to the harness before completion; the ladder driver was killed before it could bench the partial file, and the one cell that did touch it (agent Q6, server load error rc=1) was discarded and re-run clean in the supplemental pass. All reported Q6 numbers come from the sha256-verified file.
- Co-residency: GPU exclusive to the bench for every reported cell (production stopped or already down; runtime mask held llama-swap down; VRAM verified free at window open and at restore). CPU co-residency was NOT zero: the backlog sprint's estate churn (builder panes, CI, Postgres) ran throughout, load ~4 at window open rising to ~13 by restore. Prefill cells show the noise this causes (see the Q5 pp512 depth-0 dispersion); decode cells, the ladder's headline, show tight dispersions (±0.06–0.90) and are unaffected in ordering.
- Power method: `rocm-smi --showpower --showtemp --showclocks` sampled at 1 Hz (6,758 samples, `power.csv`) from before the first bench phase to after the last; phases sliced by the epoch boundaries in `phases.csv`. Socket graphics package power, sensor-edge temperature, sclk. Tokens-per-joule is computed only where token counts and energy cover the same interval (the soak); ladder-phase energies include model load and both pp and tg work, so no per-cell tok/J is claimed for the ladder.
- Watchdog note: `nexus-health-watchdog.timer` reactivated on its own twice during the window (journal shows starts at 03:10:59Z and 03:19:00Z after stops) — some estate mechanism restarts it; it was active again at restore. It could not disturb the bench (llama-swap runtime-masked throughout) and is left as found.

## Quant ladder (llama-bench, HIP, pp512 / tg128, 3 reps, mean ± stddev)

| Quant | File size | pp512 d0 | tg128 d0 | pp512 d32768 | tg128 d32768 |
|---|---:|---:|---:|---:|---:|
| UD-Q4_K_XL | 15.88 GB | 441.84 ± 18.89 | 11.65 ± 0.90 | 345.09 ± 4.23 | 12.21 ± 0.21 |
| UD-Q5_K_XL | 21.79 GB | 290.69 ± 59.58 | 6.70 ± 0.51 | 318.50 ± 4.75 | 8.29 ± 0.70 |
| UD-Q6_K_XL | 26.27 GB | 413.43 ± 4.93 | 7.30 ± 0.06 | 311.12 ± 19.62 | 6.92 ± 0.07 |

Read: decode is the ladder's story (table above and verdict). Prefill at depth 32768 is within ~10% across quants (311–345); the depth-0 prefill column is noisy under sprint CPU contention (Q5's ±59.58 dispersion is the tell) and no prefill ordering is claimed at depth 0. W1 comparison for the Q4 rung at the same cells (HIP, ubatch 512): pp512 d0 448.47 / tg128 d0 11.43 / pp512 d32768 273.06 / tg128 d32768 6.43 — tonight's Q4 depth-32768 tg (12.21) is well above W1's ubatch-512 reading and close to W1's ubatch-256 baseline (11.12); cross-window variance at depth on HIP remains a caveat for any single depth-32768 decode figure, Q4 included.

## Agent-suite subset by quant (W2 subset: 20 tool calls + 5 JSON, ctx 65536, KV f16, DFlash n-max 15, reasoning low, temp 0)

| Quant | Tool calls valid | JSON raw | JSON stripped | JSON ref-match | Server load |
|---|---:|---:|---:|---:|---:|
| UD-Q4_K_XL | 20/20 | 5/5 | 5/5 | 5/5 | 18.2 s |
| UD-Q5_K_XL | 20/20 | 5/5 | 5/5 | 5/5 | 24.1 s |
| UD-Q6_K_XL | 20/20 | 5/5 | 5/5 | 5/5 | 42.1 s |

No quality separation at this coarseness, at any quant. (Agent-phase mean socket power: Q4 69.1 W, Q5 68.8 W, Q6 62.3 W — the slower quants draw slightly less mean power while doing the same work more slowly.)

## Power and thermal

Ladder-phase socket power (mean / peak, 1 Hz samples over each llama-bench phase, load included): Q4 79.2 / 116.0 W, Q5 78.9 / 104.0 W, Q6 77.5 / 118.0 W. Edge temperatures during ladder phases peaked at 69 °C.

### 30-minute soak (UD-Q4_K_XL, ctx 32768, KV f16, DFlash n-max 15, back-to-back 1024-token prose generations, temp 0)

- Duration 1827 s, 29 requests, 29,696 predicted tokens, wall-mean decode 16.25 tok/s. Per-request timings rates were bimodal (10.6–16.4 tok/s on the low branch, 55–85 tok/s on the high branch), the same DFlash acceptance bimodality documented in W1; the wall mean is the honest sustained figure for this serving shape.
- Power: mean 80.0 W, peak 107.1 W. Energy 146.2 kJ. **Tokens per joule: 0.203** (equivalently ~4.92 J/token, ~80 W at 16.25 tok/s sustained).
- Temperature: mean edge 56.2 °C, peak 66 °C.
- Clock/thermal verdict (first 5 min vs last 5 min): sclk mean 1969 → 2209 MHz, power 74.9 → 81.8 W, temp 51.5 → 58.0 °C mean. No decay anywhere; the part heat-soaks ~6.5 °C over the half hour and clocks slightly *up*. At these power levels (~80 W mean, ~118 W worst peak all night) the EVO-X2's cooling is nowhere near a limit for this model.

## Vision stretch (mmproj)

- Wiring: scratch llama-server `--mmproj mmproj-kquant.gguf` with UD-Q4_K_XL, ctx 8192, first attempt. Server load to healthy 21.0 s.
- Test image: synthetic 480×360 PNG generated for this run (`vision-test.png` in the raw data) with exact ground truth: white background; red rectangle (160×120) flush with the top-left corner; blue circle (r=55) at center (240,150); green square (100×100) bottom-right area (x 340–440, y 220–320); black horizontal bar across the bottom 25 px.
- Timings: prompt 303 tokens (image tokens included) prefilled at 214.9 tok/s; 512 tokens decoded at 11.14 tok/s; wall 47.29 s.
- Correctness, qualitatively: background, black bar (position, span), blue circle (color, shape, center-right placement), and green square (color, shape) all described correctly, and the red rectangle's location and extents were given approximately right ("right edge about one-third in" = 160/480 exactly; "bottom edge about one-quarter down" vs the true one-third). Two misses: the red rectangle was described as "cropped at the top and left edges… only the lower-right portion visible" when it is in fact fully in frame and flush with the corner, and the response hit the 512-token output cap mid-way through the green square's entry, so its location sentence never landed. Net: a clean first pass on wiring and basic scene description, with extent/framing judgment as the visible weakness. One image is a smoke, not a vision benchmark; it is reported as such.

## Restore verification (2026-10-24, UTC)

Restore targeted the verified pre-window (sprint) state, per the disclosure above, and every step was verified live:

1. Scratch sweep: port 5999 free, no scratch llama-server processes; power sampler stopped (6,758 samples written).
2. `systemctl unmask --runtime llama-swap` — runtime mask symlink removed. llama-swap deliberately **left inactive**: it was inactive before the window under the sprint directive, which runs to ~09:16 ET Oct 24.
3. `forge-api` started — active. `forge-mcp` — active.
4. Timers: llama-swap-metrics.timer and llama-swap-reaper.timer inactive (as found); nexus-health-watchdog.timer active (it self-reactivated during the window; see the watchdog note).
5. Forge smoke: POST http://localhost:8642/v1/chat/completions, model `default-chat`, returned **HTTP 200** with content `SMOKE_OK`, served by `muse-glimmer-30b-prose` — the Oct 23 promotion made the Crucible Glimmer prose seat the default-chat primary, so the smoke passes with Furnace's local GPU empty (the Furnace-resident fallback leg stays down with llama-swap until the sprint posture ends). Saved as `results-w3/forge-smoke.json`.
6. VRAM after restore: 169,684,992 B used — identical to the pre-window reading.

The bench displaced nothing that was running except forge-api/forge-mcp (03:10:37Z–05:06:31Z), both restored and verified, with the default-chat smoke passing via the Crucible primary. When the sprint ends, llama-swap and its timers come back under the sprint's own restore, not this window's. Nothing was published.
