#!/bin/sh
# comb-8: NEAR-TIES (theta in {-2..+2}) over [0xC8,0xF0) x160
# segs, h491_scan3 — dn-side cross-window validation comb.
cd /root/h491
export LC_ALL=C
rm -f comb8_*.txt ties_comb8.txt comb8.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > comb8_{}.txt" < starts8.txt
for s in $(cat starts8.txt); do cat "comb8_$s.txt"; done > ties_comb8.txt
awk '{print $1}' ties_comb8.txt | sort -u | sed 's/^/3ffc /' > comb8_inputs.txt
n=$(wc -l < comb8_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb8_inputs.txt > "comb8_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb8_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > comb8.done; exit 1; }
done
wc -l ties_comb8.txt > comb8.done
echo DONE >> comb8.done
