#!/usr/bin/env python3
"""Charts for the Glimmer article. Every value is transcribed from the
foreground-verified bench records (named per chart below); error bars are
the records' reported stddevs. Output: PNGs in this directory."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.grid": True,
    "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False,
})
DEPTHS = [0, 4096, 16384, 32768, 65536]
DLAB = ["0", "4k", "16k", "32k", "65k"]
HIP, VK, Q4C, Q5C, Q6C = "#c0392b", "#2471a3", "#2471a3", "#7d8a99", "#b9770e"

# --- 1. Depth curves, Crucible llama-bench, NO drafter, KV f16 --------------
# Source: CRUCIBLE-SWEEP-2026-10-19.md, "llama-bench depth sweep" table (3 reps).
tg  = [13.84, 13.64, 13.04, 12.15, 13.02]; tg_e  = [0.02, 0.05, 0.66, 1.03, 0.01]
pp5 = [457.10, 389.89, 362.89, 304.44, 292.32]; pp5_e = [2.23, 5.29, 6.64, 59.83, 5.29]
pp8 = [393.63, 383.11, 357.23, 330.63, 278.14]; pp8_e = [2.59, 1.58, 1.55, 1.05, 7.22]
fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.6))
ax[0].errorbar(DLAB, tg, yerr=tg_e, marker="o", color=HIP, capsize=3)
ax[0].set_title("Decode (tg128) is flat with depth")
ax[0].set_ylabel("tok/s"); ax[0].set_xlabel("context depth (tokens; spacing not to scale)")
ax[1].errorbar(DLAB, pp5, yerr=pp5_e, marker="o", label="pp512", capsize=3)
ax[1].errorbar(DLAB, pp8, yerr=pp8_e, marker="s", label="pp8192", capsize=3)
ax[1].set_title("Prefill pays the depth cost")
ax[1].set_ylabel("tok/s"); ax[1].set_xlabel("context depth (tokens; spacing not to scale)"); ax[1].legend()
fig.tight_layout(); fig.savefig("chart-depth.png"); plt.close(fig)

# --- 2. HIP vs Vulkan decode at depth, Furnace W1 canonical (ubatch 512) ----
# Source: FURNACE-BENCH-W1-RESULTS.md, pp512/tg128 ubatch-512 table (3 reps).
hip_tg = [11.43, 10.75, 5.99, 6.43, 4.83]; hip_e = [0.36, 0.75, 0.17, 0.49, 0.37]
vk_tg  = [13.51, 13.35, 13.13, 13.07, 12.71]; vk_e = [0.02, 0.01, 0.04, 0.02, 0.01]
fig, ax = plt.subplots(figsize=(6.4, 3.8))
ax.errorbar(DLAB, vk_tg, yerr=vk_e, marker="s", color=VK, capsize=3, label="Vulkan tg128")
ax.errorbar(DLAB, hip_tg, yerr=hip_e, marker="o", color=HIP, capsize=3, label="HIP tg128 (ubatch 512)")
# ubatch-256 baseline point from the same record's DFlash-settings table.
ax.errorbar(["32k"], [11.12], yerr=[0.94], marker="D", color=HIP, markersize=7,
        capsize=3, label="HIP tg128 at 32k, ubatch 256 (11.12 ± 0.94)")
ax.set_title("Decode at depth: Vulkan flat; HIP varies by window")
ax.set_ylabel("tok/s"); ax.set_xlabel("context depth (tokens; spacing not to scale)"); ax.legend(fontsize=8.5)
fig.tight_layout(); fig.savefig("chart-hip-vulkan.png"); plt.close(fig)

# --- 3. Quant ladder decode ---------------------------------------------------
# Source: FURNACE-BENCH-W3-RESULTS.md, quant ladder table (3 reps).
import numpy as np
quants = ["UD-Q4_K_XL\n15.88 GB", "UD-Q5_K_XL\n21.79 GB", "UD-Q6_K_XL\n26.27 GB"]
d0  = [11.65, 6.70, 7.30];  d0_e  = [0.90, 0.51, 0.06]
d32 = [12.21, 8.29, 6.92];  d32_e = [0.21, 0.70, 0.07]
x = np.arange(3); w = 0.36
fig, ax = plt.subplots(figsize=(6.4, 3.8))
ax.bar(x - w/2, d0, w, yerr=d0_e, capsize=3, color=Q4C, label="tg128, depth 0")
ax.bar(x + w/2, d32, w, yerr=d32_e, capsize=3, color=Q6C, label="tg128, depth 32768")
ax.set_xticks(x); ax.set_xticklabels(quants)
ax.set_ylabel("tok/s"); ax.set_title("Quant ladder: decode cost of more bits")
ax.legend()
fig.tight_layout(); fig.savefig("chart-quant.png"); plt.close(fig)

# --- 4. KV at full 131k depth ----------------------------------------------
# Source: FURNACE-BENCH-W2-RESULTS.md, KV comparison table (n=2 per cell).
fig, ax = plt.subplots(1, 2, figsize=(7.6, 3.4))
ax[0].bar(["f16", "q8_0"], [14.35, 10.03], yerr=[0.67, 1.01], capsize=4,
          color=[VK, HIP])
ax[0].set_title("Decode: q8_0 −30.2%\n(124k filled in 131k ctx)", fontsize=10)
ax[0].set_ylabel("tok/s")
ax[1].bar(["f16", "q8_0"], [274.52, 260.10], yerr=[7.24, 13.53], capsize=4,
          color=[VK, HIP])
ax[1].set_title("Prefill: q8_0 −5.3%\n(124k filled in 131k ctx)", fontsize=10)
ax[1].set_ylabel("tok/s")
fig.tight_layout(); fig.savefig("chart-kv.png"); plt.close(fig)

print("charts written")
