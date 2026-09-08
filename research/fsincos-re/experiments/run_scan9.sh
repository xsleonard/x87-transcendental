#!/bin/sh
# comb-7: NEAR-TIES (theta in {-2..+2}) over [0xA8,0xC8) x128 segs,
# h491_scan3 (validated 64/64 vs Python).  Capture cos x rn/rd/ru.
# Also: sincos reproducibility recheck — every 18th line of the
# comb-4 sincos input list recaptured x3 modes.
cd /root/h491
export LC_ALL=C
rm -f comb7_*.txt ties_comb7.txt scan9.done cap525.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb7_{}.txt" < starts9.txt
for s in $(cat starts9.txt); do cat "comb7_$s.txt"; done > ties_comb7.txt
wc -l ties_comb7.txt > scan9.done
awk '{print $1}' ties_comb7.txt | sort -u | sed 's/^/3ffc /' > comb7_inputs.txt
n=$(wc -l < comb7_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb7_inputs.txt > "comb7_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb7_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > cap525.done; exit 1; }
done
awk 'NR % 18 == 0' comb4_sincos_inputs.txt > sc_recheck_inputs.txt
ns=$(wc -l < sc_recheck_inputs.txt)
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" sincos "$mode" --status \
        < sc_recheck_inputs.txt > "sc_recheck_${mode}.txt" || exit 1
done
echo DONE > cap525.done
