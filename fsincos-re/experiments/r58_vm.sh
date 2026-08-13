#!/bin/bash
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
make -C src fsincos_skylake 2>&1 | tail -1
COMMON="--round18-poly --round21-table-bias --round23-narrow-coefficient \
 --round24-table-delta-rn67 --round29-p5-fmul-route \
 --round30-fsin-cosine-square --round31-fsin-cosine-tail \
 --round32-fsin-cosine-horner --round33-fsin-cosine-product \
 --round34-table-lookup-firc --round35-table-p-terminal \
 --round36-table-fadd-microcontrol --round37-p6-four-term \
 --round41-fsin-cosine-split --round42-p6-sine-split \
 --round43-p6-sine-bias --round44-p6-sine-bias \
 --round45-p6-sine-fraction --round46-p6-narrow-sine-fraction \
 --round47-p6-narrow-sine-fraction --round48-p6-narrow-sine-fraction \
 --round49-p6-carrier-interval --round50-fsin-operation-classes \
 --round51-fsin-fadd-signature"
FSIN58="--fsin-standalone $COMMON --round56-fsin-cosine-carrier --round58-fsin-borrow-rule"
score () {
  local name=$1 infile=$2 hwpat=$3 flags=$4
  local tot=0
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $flags < $infile > h410/tmp_$mode.txt
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
score fsin_h347_R58 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsin_MODE_status.txt" "$FSIN58"
score fsin_sweep_R58 capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsin_MODE.txt" "$FSIN58"
score fsin_dense_R58 capture-kit/inputs/dense_qn.txt "fresh/dense_fsin_MODE.txt" "$FSIN58"
score fsin_h405win_R58 h405/window_inputs.txt "h405/hw_sin_MODE.txt" "$FSIN58"
score fsin_h409sep_R58 h409/separators.txt "h409/hw_MODE.txt" "$FSIN58"
echo R58_VM_DONE
