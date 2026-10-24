# Environment manifest

Compiled only from facts stated in the bench records in `records/` and
the per-window environment manifests captured on Furnace at bench time.
Where a fact was not captured, this manifest says so rather than filling
the gap.

## Hosts

Both bench machines are GMKtec EVO-X2 units: AMD Ryzen AI Max+ 395 with
Radeon 8060S graphics (gfx1151).

| Host | Role in this program | GPU budget |
|---|---|---|
| Crucible | Oct 18 tuning pass, first bench, prose workload test, Oct 19 context-depth sweep, longtext run | 48 GiB |
| Furnace | Windows 1–3 (Phases 2–4): backend comparison, serving/KV, quant ladder, power, vision | 64 GiB (65,536 MiB total VRAM per the HIP init log) |

- BIOS: EVO-X2 1.12 (Furnace windows 1 and 3 records).
- Kernel (both hosts, per the sweep and window records):
  6.19.10-061910-generic.
- Power posture gap, as disclosed in the window records: neither host
  exposes an ACPI platform_profile and powerprofilesctl is absent;
  Furnace's CPU scaling governor was `powersave`.

## Software

- llama.cpp **b11719**, commit `5aeac37a3` (llama-server version string
  `0.7.0-dev (build 11719, commit 5aeac37a3)`, built with GNU 13.3.0 for
  Linux x86_64, per the Furnace window manifests).
- ROCm **7.2.1** (`/opt/rocm-7.2.1`).
- Build trees used, per the records: Crucible's deployed llama.cpp tree;
  on Furnace, the HIP and Vulkan side trees (`build-hip`, `build-vulkan`)
  for window 1, the production HIP build
  (`/services/llama.cpp/build/bin/llama-server`) for window 2, and the
  bench HIP build (`~/llama.cpp-bench/build-hip`) for window 3.
- llama-swap (production serving only; stopped during every bench
  window): **v265 on Crucible** (BENCH-2026-10-18). The Furnace
  llama-swap version is **not stated in the bench records**.
- **Vulkan driver: the RADV/Mesa version was not captured.** The window
  1 record and manifest identify the Vulkan device only as
  "RADV GFX1151"; no Mesa version was recorded for the Vulkan cells.

## Model files

From `unsloth/Muse-Glimmer-30B-GGUF`. Sizes and SHA-256 as tabled in the
article's setup section; the hashes were verified on the bench hosts
during the runs (per-window hash lists are in the records).

| file | size | SHA-256 |
|---|---|---|
| Muse-Glimmer-30B-UD-Q4_K_XL.gguf | 15.88 GB | `82bece304887a313ece08400bc030f6066c7bff5b906b0cd40308ec8a409fd38` |
| dflash-kquant.gguf (DFlash drafter) | 1.63 GB | `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc` |
| mmproj-kquant.gguf (vision projector) | 1.40 GB | `f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6` |
| Muse-Glimmer-30B-UD-Q5_K_XL.gguf (ladder) | 21.79 GB (21,789,618,976 B) | `97a66c4b41d9e778af7cdfa43508e08dbf765fb5049b740c69ad815e5191c637` |
| Muse-Glimmer-30B-UD-Q6_K_XL.gguf (ladder) | 26.27 GB (26,265,362,976 B) | `fb5f80d110c4fa932cc652e70873c0bd12c0954009038aa675e65086104c2739` |

The ladder files were downloaded from Hugging Face during window 3 and
verified against the repo's LFS hashes (FURNACE-BENCH-W3-RESULTS). The
Hugging Face repo revision was not pinned in the records; the file
hashes above are the identity pin.
