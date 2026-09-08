#!/bin/sh
# comb-3: [0xC8, 0xF0), 160 segments x 250M at 2^54 spacing.
# Starts pre-generated in Python (starts5.txt) — shell $(( )) overflows
# above 2^63, on record.  Scan -> ties -> capture cos x rn/rd/ru.
cd /root/h491
export LC_ALL=C
rm -f comb3_*.txt ties_comb3.txt scan5.done cap505.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan {} 250000000 > comb3_{}.txt" < starts5.txt
for s in $(cat starts5.txt); do cat "comb3_$s.txt"; done > ties_comb3.txt
wc -l ties_comb3.txt > scan5.done
awk '{print $1}' ties_comb3.txt | sort -u | sed 's/^/3ffc /' > comb3_inputs.txt
n=$(wc -l < comb3_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < comb3_inputs.txt > "comb3_${mode}_status.txt" || exit 1
    l=$(wc -l < "comb3_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > cap505.done; exit 1; }
done
echo DONE > cap505.done
