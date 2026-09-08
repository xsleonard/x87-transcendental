#!/bin/bash
# h407: complete validation of the retired-Round-51 source with the
# standard shipping flag sets (round51 passed and inert).
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
make -C src fsincos_skylake 2>&1 | tail -1
src/fsincos_skylake --selftest > /dev/null && echo SELFTEST_PASS
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
FCOS_EXTRA="--round38-p6-cosine-split --round39-fcos-tiny --round52-fcos-low3-carrier --round53-fcos-operation-classes"
PAIR_EXTRA="--round40-fsincos-tiny --round53-fcos-operation-classes --round38-p6-cosine-split --round54-fsincos-table-lanes"
mkdir -p h407
score () {
  local name=$1 infile=$2 hwpat=$3 kind=$4 flags=$5
  local tot=0
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $flags < $infile > h407/tmp_$mode.txt
    tot=$((tot + $(python3 - "$hwpat" "$mode" "$kind" <<'PYEOF'
import sys
hwpat, mode, kind = sys.argv[1:4]
def norm(p, paired):
    out=[]
    for l in open(p):
        t=l.split()
        if t[0]!="OK": out.append(("C2",)); continue
        out.append(tuple(t[1:5]) if paired else tuple(t[1:3]))
    return out
hw = norm(hwpat.replace("MODE",mode), kind=="pair")
mo = norm(f"h407/tmp_{mode}.txt", kind=="pair")
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
)))
  done
  echo "$name: $tot"
}
score fsin_h347 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsin_MODE_status.txt" single "--fsin-standalone $COMMON"
score fsin_sweep capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsin_MODE.txt" single "--fsin-standalone $COMMON"
score fsin_dense capture-kit/inputs/dense_qn.txt "fresh/dense_fsin_MODE.txt" single "--fsin-standalone $COMMON"
score fsin_h405win h405/window_inputs.txt "h405/hw_sin_MODE.txt" single "--fsin-standalone $COMMON"
score fcos_h347 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fcos_MODE_status.txt" single "--fcos-standalone $COMMON $FCOS_EXTRA"
score fcos_sweep capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fcos_MODE.txt" single "--fcos-standalone $COMMON $FCOS_EXTRA"
score fcos_dense capture-kit/inputs/dense_qn.txt "fresh/dense_fcos_MODE.txt" single "--fcos-standalone $COMMON $FCOS_EXTRA"
score pair_h347 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsincos_MODE_status.txt" pair "$COMMON $PAIR_EXTRA"
score pair_h349 captures/skylake-trig-h349/inputs.txt "captures/skylake-trig-h349/fsincos_MODE_status.txt" pair "$COMMON $PAIR_EXTRA"
score pair_sweep capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsincos_MODE.txt" pair "$COMMON $PAIR_EXTRA"
score pair_dense capture-kit/inputs/dense_qn.txt "fresh/dense_fsincos_MODE.txt" pair "$COMMON $PAIR_EXTRA"
score pair_h405win h405/window_inputs.txt "h405/hw_sincos_MODE.txt" pair "$COMMON $PAIR_EXTRA"
echo "--- h377 gate:"
python3 experiments/h377_fsin_binary64_residual_gate.py src/fsincos_skylake --show-misses=8 | tail -4
