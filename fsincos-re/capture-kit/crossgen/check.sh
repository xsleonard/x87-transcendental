#!/bin/sh
# Cross-generation borrow-gate probe.  Run on ANY x86 machine
# with x87 (Intel or AMD, any generation).  Builds the capture
# runner, captures FCOS on the 56k adversarial operands in all
# three rounding modes, and diffs against the Skylake
# reference.  Verdict:
#   IDENTICAL  -> this silicon's terminal borrow behavior is
#                 bit-identical to Skylake (heritage holds to
#                 this generation);
#   DIFFERS    -> the gate is generation-local; the per-
#                 category breakdown shows WHERE (rule rows =
#                 the modeled gate, chop/other = its residual).
set -e
cd "$(dirname "$0")"
CC=${CC:-cc}
[ -x ./x87_capture ] || $CC -O2 -o x87_capture ../x87_capture.c
total=0
for mode in rn rd ru; do
    ./x87_capture cos $mode --status < inputs.txt > got_$mode.txt
    n=$(paste got_$mode.txt skylake_$mode.txt | awk \
        '$1=="OK" && $4=="OK" && ($2!=$5 || $3!=$6)' | wc -l)
    echo "$mode: $n differing rows"
    total=$((total + n))
done
if [ "$total" -eq 0 ]; then
    echo "VERDICT: IDENTICAL to Skylake (all modes)"
else
    echo "VERDICT: DIFFERS ($total mode-rows)"
    echo "per-category breakdown (rn):"
    paste got_rn.txt skylake_rn.txt inputs.txt | awk \
        '$1=="OK" && $4=="OK" && ($2!=$5 || $3!=$6) {print $8}' \
        > diff_ms.txt
    awk 'NR==FNR{d[$1]=1; next} d[$1]{c[$2]++}
         END{for (k in c) print k, c[k]}' \
        diff_ms.txt categories.tsv
fi
