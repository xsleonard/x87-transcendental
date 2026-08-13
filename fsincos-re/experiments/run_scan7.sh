#!/bin/sh
# comb-5 (W1): family-1 window [0x80,0xA8), 160 segments x 250M at
# 2^54 spacing.  Starts Python-generated.  Capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb5_*.txt ties_comb5.txt scan7.done cap520.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan {} 250000000 > comb5_{}.txt" < starts7.txt
for s in $(cat starts7.txt); do cat "comb5_$s.txt"; done > ties_comb5.txt
wc -l ties_comb5.txt > scan7.done
awk '{print $1}' ties_comb5.txt | sort -u | sed 's/^/3ffc /' > comb5_inputs.txt
n=$(wc -l < comb5_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb5_inputs.txt > "comb5_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb5_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > cap520.done; exit 1; }
done
echo DONE > cap520.done
