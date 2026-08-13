#!/bin/sh
# h604: W1 densifying near-tie scan (160 positions, +9*2^52)
# + capture ALL near-ties cos x3.
cd /root/h491
export LC_ALL=C
rm -f h604seg_*.txt ties_h604.txt h604.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 150000000 > h604seg_{}.txt" < starts_h604.txt
for s in $(cat starts_h604.txt); do cat "h604seg_$s.txt"; done > ties_h604.txt
awk '{print $1}' ties_h604.txt | sort -u | sed 's/^/3ffc /' > h604_inputs.txt
n=$(wc -l < h604_inputs.txt)
RUNNER=/root/x87_capture_x86_64
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < h604_inputs.txt > "h604_${mode}_status.txt" || exit 1
    l=$(wc -l < "h604_${mode}_status.txt")
    [ "$l" -eq "$n" ] || { echo "BAD $mode $l/$n" > h604.done; exit 1; }
done
wc -l ties_h604.txt > h604.done
echo DONE >> h604.done
