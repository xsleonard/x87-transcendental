#!/bin/sh
# comb-4 (validation): both windows [0xA8,0xF0), 288 segments x 250M,
# 2^54 spacing, offset +2^53 from combs 1/3.  Starts from Python.
# Capture: cos x rn/rd/ru on everything; sincos x rn/rd/ru on the
# dist=9 window subset (mhex < 0xC8...) for E2.
cd /root/h491
export LC_ALL=C
rm -f comb4_*.txt ties_comb4.txt scan6.done cap515.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan {} 250000000 > comb4_{}.txt" < starts6.txt
for s in $(cat starts6.txt); do cat "comb4_$s.txt"; done > ties_comb4.txt
wc -l ties_comb4.txt > scan6.done
awk '{print $1}' ties_comb4.txt | sort -u | sed 's/^/3ffc /' > comb4_inputs.txt
awk '$2 < "c8"' comb4_inputs.txt > comb4_sincos_inputs.txt
n=$(wc -l < comb4_inputs.txt)
ns=$(wc -l < comb4_sincos_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb4_inputs.txt > "comb4_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb4_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD cos $mode $l/$n" > cap515.done; exit 1; }
done
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < comb4_sincos_inputs.txt > "comb4_sc_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb4_sc_${mode}_status.txt")
    [ "$l" -eq "$ns" ] || { echo "BAD sincos $mode $l/$ns" > cap515.done; exit 1; }
done
echo DONE > cap515.done
