#!/bin/bash
# h929: the standing carry-census densification chain (user
# directive: keep attacking the remaining misses).  Continues the
# h913/h914 tail scan from seed 94640 in 64-seed batches; each
# batch appends to act_tail.tsv.  Target: ~10x the 93-carry census
# (~16k seeds, weeks); at that power the h928 raw-bit sweep and
# the f4.b65 runner-up get retested.  Kill anytime; progress in
# h929_chain.log.
for b in $(seq 0 77); do
  /root/r84/h913_tailscan.sh 64 $((94640 + b*64)) >> /root/r84/h929_chain.log 2>&1
  echo "BATCH $b done $(date -u +%H:%M) rows=$(wc -l < /root/r84/act_tail.tsv) free=$(df -m / | tail -1 | awk "{print \$4}")M" >> /root/r84/h929_progress.log
  # disk guard: stop cleanly below 1G free
  [ $(df -m / | tail -1 | awk "{print \$4}") -lt 1000 ] && { echo H929_DISK_STOP >> /root/r84/h929_progress.log; exit 1; }
done
echo H929_CHAIN_DONE >> /root/r84/h929_progress.log
