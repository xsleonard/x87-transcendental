#!/bin/bash
set -e
cd /root/r59
for insn in cos sin; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    nice -n 10 ./model_h780 --batch $RC $FL < /root/h491/randv1_inputs.txt > h785mo_${insn}_${mode}.txt
  done
done
echo CAPTURES_DONE
python3 h785_census.py
rm -f h785mo_*.txt
echo H785_DONE
