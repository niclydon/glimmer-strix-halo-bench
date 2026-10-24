# Muse Glimmer 30B on Strix Halo — bench data

This repository is the public evidence package behind the article
**"Muse Glimmer 30B on Strix Halo: a week of measurements"**: the bench
records, raw result data, harness scripts, and environment manifests for a
week of benchmarking Meta's Muse Spark Glimmer 30B (unsloth GGUF builds)
on two GMKtec EVO-X2 machines (Ryzen AI Max+ 395 / Radeon 8060S, Strix
Halo), run October 18–24, 2026.

Every number in the article traces to a record in `records/` and, where
the run produced machine-readable output, to a file in `data/`. The
records keep their methodology disclosures and caveats; the article's
claims are scoped to what those records support.

## Layout

- `article/` — the article text as published, plus the four chart PNGs
  embedded in it (chart sources: `harness/make_charts.py`).
- `records/` — the bench records: one per bench day/window, written at
  the time of the run, plus the program plan.
- `data/` — raw machine-readable results, grouped by run:
  - `crucible-sweep/` — llama-bench and server-path JSON from the
    Crucible context-depth sweep (Oct 19).
  - `tuning/` — the October 18 tuning run's raw JSON (two result
    files; the prose-workload payloads themselves are withheld, see
    "What's withheld, and why").
  - `w1/` — Furnace window 1 (Oct 20): HIP vs Vulkan llama-bench JSON,
    the DFlash server sweep results, and `forge-smoke.json`, the
    post-restore Forge smoke result.
  - `w2/` — Furnace window 2 / Phase 3 (Oct 22): the full results JSON
    (serving matrix, 131k KV cells, prefill focus, agent suite, greedy
    reproducibility, reasoning tax), and `forge-smoke.json`.
  - `w3/` — Furnace window 3 / Phase 4 (Oct 24): quant ladder
    llama-bench JSON, full results JSON, analysis JSON, 1 Hz power
    samples (`power.csv`), phase boundaries (`phases.csv`), the
    vision test image (`vision-test.png`), and `forge-smoke.json`.
- `harness/` — the bench and analysis scripts that produced the data,
  plus the chart script.
- `environment/` — `MANIFEST.md`: hosts, software builds, and the model
  files (names, sizes, SHA-256) as recorded at bench time; `raw/`
  holds the per-window environment manifests captured on Furnace at
  each window.

## Article section → backing record and data

| Article section | Record | Data / harness |
|---|---|---|
| The setup | all records; `environment/MANIFEST.md` | — |
| Lesson one: the right draft length depends on what the model is doing | `records/TUNING-RESULTS-2026-10-18.md`, `records/BENCH-2026-10-18.md` | `harness/tune_bench.py`, `harness/bench.py` |
| Depth: decode is flat, prefill pays | `records/CRUCIBLE-SWEEP-2026-10-19.md` | `data/crucible-sweep/bench_pp512_tg128.json`, `data/crucible-sweep/bench_pp8192.json`, `data/crucible-sweep/server_tg.json`; `article/chart-depth.png` |
| HIP versus Vulkan, and an honest loose end | `records/FURNACE-BENCH-W1-RESULTS.md` | `data/w1/llamabench-hip-*.json`, `data/w1/llamabench-vulkan-*.json`; `harness/glimmer_llamabench.sh`; `article/chart-hip-vulkan.png` |
| Speculation at depth: what the sweep actually measured; Greedy is not greedy | `records/FURNACE-BENCH-W1-RESULTS.md` (DFlash at depth, plus its 2026-10-24 interpretation note); `records/FURNACE-BENCH-W2-RESULTS.md` (greedy reproducibility) | `data/w1/dflash-server-results.json`; `data/w2/results-w2.json`; `harness/dflash_bench.py`, `harness/bench_w2.py` |
| KV cache at 131k: the deficit lives in decode | `records/FURNACE-BENCH-W2-RESULTS.md` | `data/w2/results-w2.json`; `harness/bench_w2.py`; `article/chart-kv.png` |
| The quant ladder | `records/FURNACE-BENCH-W3-RESULTS.md` | `data/w3/llamabench-UD-Q4_K_XL.json`, `data/w3/llamabench-UD-Q5_K_XL.json`, `data/w3/llamabench-UD-Q6_K_XL.json`, `data/w3/results-w3.json`, `data/w3/analysis-w3.json`; `harness/bench_w3.py`, `harness/analyze_w3.py`; `article/chart-quant.png` |
| Serving shape: slots buy concurrency, not speed | `records/FURNACE-BENCH-W2-RESULTS.md` | `data/w2/results-w2.json` |
| The reasoning tax, and the one real failure | `records/REASONING-CONTROL-VERDICT-2026-10-18.md`, `records/PROSE-WORKLOAD-TEST-2026-10-18.md`, `records/FURNACE-BENCH-W2-RESULTS.md` (tax table), `records/CRUCIBLE-SWEEP-2026-10-19.md` (longtext run) | `harness/budget_probe.py`, `harness/longtext_bench.py`; `data/crucible-sweep/longtext-results.json` |
| Power and thermals: a non-story, measured | `records/FURNACE-BENCH-W3-RESULTS.md` | `data/w3/power.csv`, `data/w3/phases.csv`, `data/w3/results-w3.json`; `harness/w3_power_sampler.py` |
| Vision: a first pass | `records/FURNACE-BENCH-W3-RESULTS.md` | `data/w3/vision-test.png`, `data/w3/results-w3.json` |
| The settings card | synthesis of all records above | — |
| What this article is not claiming | caveats as recorded in each record above | — |

The three Furnace windows follow `records/FURNACE-BENCH-PLAN.md`
(Phases 2, 3, and 4; Phase 1 was the Crucible tuning and sweep work).

## Reproduction: what is exact, what is historical

The harness scripts are the programs as run, with the exceptions and
gaps named here. Treat this package as a successful-result export
with full data, not a complete attempt ledger.

- llama-bench cells: `harness/glimmer_llamabench.sh` is a historical
  partial script. It covers depths 0 and 32,768 only, does not pin
  the 3-repetition counts, passes draft flags the pinned llama-bench
  build rejects, and can report COMPLETE after a failed command. The
  published cells' parameters are in the records and the JSON.
- DFlash server sweep (window 1): `harness/dflash_bench.py` is the
  run script.
- Crucible sweep: the run scripts named in
  `records/CRUCIBLE-SWEEP-2026-10-19.md` were session scripts and are
  not in this package; the sweep's data and record are complete.
- Longtext: the run used a patched single-cell variant (n-max 15, no
  ubatch 256). `harness/longtext_bench.py` (n-max 3, ubatch 256,
  four cells) is a related experiment, not the run script.
- Windows 2 and 3: `harness/bench_w2.py` and `harness/bench_w3.py`
  are the run scripts. Window 3 overwrote its result files across
  attempts rather than versioning them; earlier partial attempts are
  described in the record, not preserved as separate raw versions.
- Analysis scripts (`analyze_w1/w2/w3.py`) carry hard-coded paths from
  the bench hosts; they are provenance for the derived tables, not
  portable entry points. The chart script (`make_charts.py`) plots
  values transcribed in it from the records.

## Notes

- Server logs from the bench windows are not included; everything the
  article cites from them is carried in the records and the JSON data.
- `FINAL-PASS.md` (repo root) documents the pre-publication privacy and
  sensitivity review of this package: what was scanned, what was
  withheld or changed, and why.
- `CORRECTIONS.md` (repo root) documents the post-review correction
  pass of 2026-10-24: the claim corrections, one corrected derived
  data field, and the open publication decisions.

## What's withheld, and why

A small number of files from the bench program are not in this repo,
by design:

- The October 18 prose-workload payloads and their result files. The
  prose tests used private personal and third-party material.
  Payloads and generated prose are excluded; the public records
  retain workload shapes, token counts, methods, and aggregate
  results. The records (`PROSE-WORKLOAD-TEST-2026-10-18.md`,
  `REASONING-CONTROL-VERDICT-2026-10-18.md`) document the workloads;
  the tuning run's own raw JSON (`data/tuning/`) is included.
- The window state snapshots (llama-swap `/running` captures taken
  before and after each window). They are operational artifacts
  containing full production command lines, and no article number
  depends on them; the records document each window's verified
  restore in prose.
- The longtext payload behind the Crucible longtext run. It is a real
  weekly-synthesis payload, withheld on the same basis as the prose
  payloads above. Its result file ships in `data/crucible-sweep/`
  (the run returned no content; the file carries metrics only).

Two mechanical changes were made to the public copies, and nothing
else was altered: the four contact names used in the agent-suite test
prompts were replaced with generic placeholder names (the names are
inputs to a `search_contacts` call; no measurement depends on them),
and one private interconnect address in the window 1 record was
removed. Originals are retained privately.
