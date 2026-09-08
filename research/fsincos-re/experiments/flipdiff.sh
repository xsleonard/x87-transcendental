#!/bin/bash
set -e
cd /root/r84
./probe_ledger.sh pre_flipdiff
rm -f flip_*.diff
for insn in cos sin; do
  for mode in rn rd ru; do
    /root/x87_capture_x86_64 $mode $insn < /root/h491/randv1_inputs.txt \
      | python3 flip_diff.py /root/h491/randv1_${insn}_${mode}_hw_status.txt \
          /root/h491/randv1_inputs.txt $insn $mode \
      > flip_${insn}_${mode}.diff 2>> flip_counts.txt
    echo "DIFFED $insn $mode: $(wc -l < flip_${insn}_${mode}.diff) rows changed since 2026-08-18"
  done
done
./probe_ledger.sh post_flipdiff
cat flip_*.diff > flip_all.tsv
echo "TOTAL CHANGED ROWS: $(wc -l < flip_all.tsv) / 48,000,000"
echo FLIPDIFF_DONE
