#!/bin/bash
set -e
cd /root/r59
python3 h733_gen.py 0x789001 8000000 ck14_inputs.txt
wc -l ck14_inputs.txt
for insn in cos sin; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    /root/x87_capture $insn $mode < ck14_inputs.txt > ck14hw_${insn}_${mode}.txt
    ./model_h780 --batch $RC $FL < ck14_inputs.txt > ck14b_${insn}_${mode}.txt
    ./model_r72  --batch $RC $FL < ck14_inputs.txt > ck14g_${insn}_${mode}.txt
    echo "lane done $insn $mode $(date +%H:%M:%S)"
  done
done
python3 ck14_score.py
rm -f ck14b_*.txt ck14g_*.txt
echo H789_DONE
