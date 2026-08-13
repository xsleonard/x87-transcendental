#!/bin/sh
# h571: paired-lane (sincos) capture of the full comb-7 near-tie
# input set, 3 rounding modes — for the cross-schedule side-split
# contingency analysis (2026-08-10 handoff work item 3).
cd /root/h491
export LC_ALL=C
n=$(wc -l < comb7_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < comb7_inputs.txt > "comb7_sc_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb7_sc_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > cap571.done; exit 1; }
done
echo DONE > cap571.done
