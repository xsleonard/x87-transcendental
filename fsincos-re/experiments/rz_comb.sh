#!/bin/bash
set -e
cd /root/r84
./probe_ledger.sh pre_rzcomb
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  /root/x87_capture_x86_64 rz cos < /root/h491/${corp}_inputs.txt \
      > /root/h491/${corp}_rz_status.txt
  echo "CAPTURED ${corp} rz: $(wc -l < /root/h491/${corp}_rz_status.txt)"
  df -B1M / | tail -1 | awk '{print "  free_MB:", $4}'
done
./probe_ledger.sh post_rzcomb
rm -f rzc_*.miss rzc_counts.txt
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  nice -n 10 ./model_suite --batch --rc=rz --fcos-standalone < /root/h491/${corp}_inputs.txt \
    | python3 cmp_stream.py /root/h491/${corp}_rz_status.txt \
        /root/h491/${corp}_inputs.txt $corp cos rz \
    > rzc_${corp}.miss 2>> rzc_counts.txt
done
cat rzc_*.miss > rzc_misses.tsv
echo "COMB-RZ misses total: $(wc -l < rzc_misses.tsv)"
sort rzc_counts.txt
echo RZ_COMB_DONE
