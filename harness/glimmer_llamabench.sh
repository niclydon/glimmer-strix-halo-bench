#!/bin/bash
# Glimmer canonical llama-bench set on Furnace, HIP vs Vulkan at b11719.
# pp512 / tg128 at depth 0 and 32768; tg with DFlash n-max 3 and without.
set -u
MODEL=/services/models/muse-glimmer-30b/Muse-Glimmer-30B-UD-Q4_K_XL.gguf
DRAFT=/services/models/muse-glimmer-30b/dflash-kquant.gguf
OUT=~/glimmer-furnace-bench
mkdir -p "$OUT"

run() {
  local build=$1; shift
  local bin=~/llama.cpp-bench/build-$build/bin
  export LD_LIBRARY_PATH=$bin:/opt/rocm-7.2.1/lib
  echo "--- llamabench $build plain $(date -Is)"
  "$bin/llama-bench" -m "$MODEL" -p 512 -n 128 -d 0,32768 -ngl 99 -fa 1 \
    -o json > "$OUT/llamabench-glimmer-$build-plain.json" 2> "$OUT/llamabench-glimmer-$build-plain.err"
  echo "--- llamabench $build dflash $(date -Is)"
  "$bin/llama-bench" -m "$MODEL" -md "$DRAFT" -p 512 -n 128 -d 0,32768 -ngl 99 -fa 1 \
    --spec-type draft-dflash --spec-draft-n-max 3 \
    -o json > "$OUT/llamabench-glimmer-$build-dflash.json" 2> "$OUT/llamabench-glimmer-$build-dflash.err"
}

run hip
run vulkan
echo "=== LLAMABENCH COMPLETE $(date -Is) ==="
