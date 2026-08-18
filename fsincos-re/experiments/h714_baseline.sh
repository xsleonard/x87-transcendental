#!/bin/bash
# h714 (T1/T2 forensics, 2026-08-18): inertness proof + census prep.
# Builds model_di from the --dump-internals/--perturb instrumented
# source, byte-diffs it (flags off) against the incumbent
# model_master over ALL corpora x modes, keeping the master outputs
# for the census.  Aborts on the first non-identical file.
set -e
cd /root/r59
gcc -O2 -o model_di fsincos_skylake_di.c -lm
FCOS="--fcos-standalone"
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    ./model_master --batch $RC $FCOS \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_master.txt
    ./model_di --batch $RC $FCOS \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_di.txt
    cmp mo_${corp}_${mode}_master.txt mo_${corp}_${mode}_di.txt
    echo "IDENTICAL ${corp} ${mode}"
    rm mo_${corp}_${mode}_di.txt
  done
done
echo ALL_IDENTICAL
