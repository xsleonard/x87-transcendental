#!/bin/bash
# R90-candidate suite wall, then overnight fringe densification.
/root/r84/h913_suitewall.sh ./model_r90 > /root/r84/h914_suitewall.log 2>&1
# 10 more tail-scan batches for the adder-boundary fringe (seeds 94000+)
for b in 0 1 2 3 4 5 6 7 8 9; do
  /root/r84/h913_tailscan.sh 64 $((94000 + b*64)) >> /root/r84/h914_fringe.log 2>&1
done
echo H914_CHAIN_DONE >> /root/r84/h914_fringe.log
