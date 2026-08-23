#!/bin/bash
set -e
cd /tmp/vmepoch
for insn in cos sin; do
  for mode in rn rd ru rz; do
    /home/coduoserver/fsincos-residual-20260807-1/src/x87_capture $mode $insn \
      < ledger_ops.txt > vmcap_${insn}_${mode}.txt
    /home/coduoserver/fsincos-residual-20260807-1/src/fsincos_skylake --batch \
      $( [ $mode = rd ] && echo --rc=rd; [ $mode = ru ] && echo --rc=ru; [ $mode = rz ] && echo --rc=rz ) \
      $( [ $insn = sin ] && echo --fsin-standalone || echo --fcos-standalone ) \
      < ledger_ops.txt > vmmo_${insn}_${mode}.txt
  done
done
python3 vm_threeway.py
echo VM_EPOCH_DONE
