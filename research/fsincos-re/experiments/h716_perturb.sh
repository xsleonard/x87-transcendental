#!/bin/bash
# h716 (T2): perturbation matrix over the census operands.
# For each target x delta x mode, run model_di --perturb and save
# outputs; h716_parse.py scores them against hardware.
set -e
cd /root/r59
FCOS="--fcos-standalone"
for tgt in odd even sq f4 mag; do
  for dl in -2 -1 1 2; do
    for mode in rn rd ru; do
      RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
      ./model_di --batch $RC $FCOS --perturb=${tgt}:${dl} \
          < h714_ops.txt > pt_${tgt}_${dl}_${mode}.txt
    done
  done
done
echo H716_DONE
