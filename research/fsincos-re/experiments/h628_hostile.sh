#!/bin/bash
# h628: current-model score on the four hostile FCOS sets +
# h422, flag off and on — are the R52-frame "7 misses" already
# fixed by the round53-era machinery?
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
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
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
score () {
  local name=$1 infile=$2 hwdir=$3 flags=$4
  local tot=0
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $flags < $infile > h410/t_$mode.txt
    tot=$((tot + $(python3 - "$hwdir" "$mode" <<'PYEOF'
import sys
d, mode = sys.argv[1:3]
def norm(p):
    out=[]
    for l in open(p):
        t=l.split()
        out.append(tuple(t[1:3]) if t[0]=="OK" else ("C2",))
    return out
import os
hp = f"{d}/fcos_{mode}_status.txt"
if not os.path.exists(hp): hp = f"{d}/hw_{mode}.txt"
hw = norm(hp)
mo = norm(f"h410/t_{mode}.txt")
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
)))
  done
  echo "$name: $tot"
}
for s in h363 h372 h380 h384; do
  score fcos_${s}_off shuffle/${s}_orig.txt captures/skylake-fcos-$s "$FCOS"
  score fcos_${s}_ON  shuffle/${s}_orig.txt captures/skylake-fcos-$s "$FCOS --round57-fcos-borrow-rule"
done
score fcos_h422_off h422/selected_inputs.txt h422 "$FCOS"
score fcos_h422_ON  h422/selected_inputs.txt h422 "$FCOS --round57-fcos-borrow-rule"
echo H628_DONE
