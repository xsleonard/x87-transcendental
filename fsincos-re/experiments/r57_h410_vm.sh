#!/bin/bash
# Round-57 VM validation: stock h410 (flag off) + flag-ON rescore.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
echo "=== h410 stock (flag OFF) ==="
bash experiments/h410_round56_validation.sh 2>&1
echo "=== flag ON rescore ==="
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
FSIN="--fsin-standalone $COMMON --round56-fsin-cosine-carrier --round57-fcos-borrow-rule"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes \
 --round57-fcos-borrow-rule"
PAIR="$COMMON --round40-fsincos-tiny --round53-fcos-operation-classes \
 --round38-p6-cosine-split --round54-fsincos-table-lanes \
 --round57-fcos-borrow-rule"
score () {
  local name=$1 infile=$2 hwpat=$3 kind=$4 flags=$5
  local tot=0
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $flags < $infile > h410/tmp_$mode.txt
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
mo = norm(f"h410/tmp_{mode}.txt", kind=="pair")
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
)))
  done
  echo "$name: $tot"
}
score fsin_h347_ON captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsin_MODE_status.txt" single "$FSIN"
score fsin_h405win_ON h405/window_inputs.txt "h405/hw_sin_MODE.txt" single "$FSIN"
score fsin_h409sep_ON h409/separators.txt "h409/hw_MODE.txt" single "$FSIN"
score fcos_h347_ON captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fcos_MODE_status.txt" single "$FCOS"
score fcos_sweep_ON capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fcos_MODE.txt" single "$FCOS"
score fcos_dense_ON capture-kit/inputs/dense_qn.txt "fresh/dense_fcos_MODE.txt" single "$FCOS"
score pair_h347_ON captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsincos_MODE_status.txt" pair "$PAIR"
score pair_h349_ON captures/skylake-trig-h349/inputs.txt "captures/skylake-trig-h349/fsincos_MODE_status.txt" pair "$PAIR"
score pair_sweep_ON capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsincos_MODE.txt" pair "$PAIR"
score pair_dense_ON capture-kit/inputs/dense_qn.txt "fresh/dense_fsincos_MODE.txt" pair "$PAIR"
echo "=== h377 gate (ported binary) ==="
python3 experiments/h377_fsin_binary64_residual_gate.py src/fsincos_skylake --expect-baseline | grep "residual gate"
echo VM_ALL_DONE
