#!/bin/bash
# FSIN corpus regression on the Skylake VM.  The validated rounds
# are inlined unconditionally in fsincos_skylake.c (2026-08-15
# master-algorithm fold) — the bare build IS the model; only the
# instruction-path selector and --rc remain.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
make -C src fsincos_skylake 2>&1 | tail -1
FSIN="--fsin-standalone"
# rz captures landed 2026-08-23 (vm_rz.sh); all four modes gated.
score () {
  local name=$1 infile=$2 hwpat=$3
  local tot=0
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"; [ $mode = rz ] && RC="--rc=rz"
    src/fsincos_skylake --batch $RC $FSIN < $infile > h410/tmp_$mode.txt
    tot=$((tot + $(python3 - "$hwpat" "$mode" <<'PYEOF'
import sys
hwpat, mode = sys.argv[1:3]
def norm(p):
    out=[]
    for l in open(p):
        t=l.split()
        out.append(tuple(t[1:3]) if t[0]=="OK" else ("C2",))
    return out
hw = norm(hwpat.replace("MODE",mode))
mo = norm(f"h410/tmp_{mode}.txt")
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
)))
  done
  echo "$name: $tot"
}
score fsin_h347 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsin_MODE_status.txt"
score fsin_sweep capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsin_MODE.txt"
score fsin_dense capture-kit/inputs/dense_qn.txt "fresh/dense_fsin_MODE.txt"
score fsin_h405win h405/window_inputs.txt "h405/hw_sin_MODE.txt"
score fsin_h409sep h409/separators.txt "h409/hw_MODE.txt"
echo R58_VM_DONE
