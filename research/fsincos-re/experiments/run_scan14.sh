#!/bin/sh
# h633: cluster-targeted near-tie scan + wholesale neighborhood
# captures for the scanner-invisible strata.
cd /root/h491
export LC_ALL=C
rm -f h633seg_*.txt ties_h633.txt h633.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 4194304 > h633seg_{}.txt" < starts_h633.txt
for s in $(cat starts_h633.txt); do cat "h633seg_$s.txt"; done > ties_h633.txt
for mode in rn rd ru; do
    taskset -c 2 /root/x87_capture_x86_64 cos $mode --status \
        < h633_wholesale.txt > h633w_${mode}_status.txt
done
wc -l ties_h633.txt > h633.done
