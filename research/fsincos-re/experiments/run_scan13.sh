#!/bin/sh
# h632: near-tie scan for the last uncovered zones (W2 dense +
# W1 incl. the (10,1,-73) stratum), off-grid starts.
cd /root/h491
export LC_ALL=C
rm -f h632seg_*.txt ties_h632.txt h632scan.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 200000000 > h632seg_{}.txt" < starts_h632.txt
for s in $(cat starts_h632.txt); do cat "h632seg_$s.txt"; done > ties_h632.txt
wc -l ties_h632.txt > h632scan.done
