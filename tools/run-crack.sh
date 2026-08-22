#!/bin/bash
# compile + run the lookup3 brute-forcer across both MI50s.
set -e
cd "$(dirname "$0")"
hipcc --offload-arch=gfx906 -O3 -o crack crack.cpp
V=$(grep -c . vocab.txt)
echo "vocab V=$V  targets=$(grep -c . targets.txt)"
: > hits.raw
# k=1 and k=2 are tiny -> GPU0
HIP_VISIBLE_DEVICES=0 ./crack 1 0 $V >> hits.raw
HIP_VISIBLE_DEVICES=0 ./crack 2 0 $((V*V)) >> hits.raw
# k=3 -> split across both GPUs
TOT=$((V*V*V)); HALF=$((TOT/2))
echo "k=3 total=$TOT  split $HALF / $((TOT-HALF))"
HIP_VISIBLE_DEVICES=0 ./crack 3 0 $HALF >> hits.g0 2>err.g0 &
P0=$!
HIP_VISIBLE_DEVICES=1 ./crack 3 $HALF $((TOT-HALF)) >> hits.g1 2>err.g1 &
P1=$!
wait $P0 $P1
cat hits.g0 hits.g1 >> hits.raw
sort -u hits.raw > hits.txt
echo "=== unique hits: $(grep -c . hits.txt) ==="
cat hits.txt
