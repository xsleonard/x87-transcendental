#!/bin/bash
set -e
cd /root/r84
df -B1M / | tail -1
./probe_ledger.sh pre_rz
for spec in "randv1 cos" "randv1 sin" "hostv1 cos" "hostv1 sin"; do
  set -- $spec; corp=$1; insn=$2
  /root/x87_capture_x86_64 rz $insn < /root/h491/${corp}_inputs.txt \
      > /root/h491/${corp}_${insn}_rz_hw_status.txt
  echo "CAPTURED ${corp} ${insn} rz: $(wc -l < /root/h491/${corp}_${insn}_rz_hw_status.txt)"
done
./probe_ledger.sh post_rz
rm -f rz_*.miss rz_counts.txt
for spec in "randv1 cos" "randv1 sin" "hostv1 cos" "hostv1 sin"; do
  set -- $spec; corp=$1; insn=$2
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  nice -n 10 ./model_suite --batch --rc=rz $FL < /root/h491/${corp}_inputs.txt \
    | python3 cmp_stream.py /root/h491/${corp}_${insn}_rz_hw_status.txt \
        /root/h491/${corp}_inputs.txt $corp $insn rz \
    > rz_${corp}_${insn}.miss 2>> rz_counts.txt
done
cat rz_*.miss > rz_misses.tsv
echo "RZ misses total: $(wc -l < rz_misses.tsv)"
sort rz_counts.txt
echo RZ_CAMPAIGN_DONE
