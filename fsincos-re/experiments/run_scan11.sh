#!/bin/sh
# h603: fresh near-tie scan for blind validation of the h602
# zone fits (W1 + [0xC8,0xF0) + W2, off-grid starts).  Scan
# ONLY — selection is locked before any capture.
cd /root/h491
export LC_ALL=C
rm -f h603seg_*.txt ties_h603.txt h603scan.done
xargs -P 6 -I{} sh -c "nice -n 5 /root/h491_scan3 {} 250000000 > h603seg_{}.txt" < starts_h603.txt
for s in $(cat starts_h603.txt); do cat "h603seg_$s.txt"; done > ties_h603.txt
wc -l ties_h603.txt > h603scan.done
