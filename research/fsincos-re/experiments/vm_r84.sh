#!/bin/bash
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
cp -n src/fsincos_skylake.c src/fsincos_skylake.c.preR84 || true
cp /tmp/fsincos_skylake_r84.c src/fsincos_skylake.c
(cd src && gcc -O2 -DG_ROUND84=1 -o fsincos_skylake_r84 fsincos_skylake.c -lm)
echo VM_BUILD_OK
for op in bffccba984e26b9f b1dbc588a7057f83 f93a965b8e95df8a fffffffffffed1bb ed0c54bb6592cc09 dbd08dc1357cf85a deb64efdf184a873 c6922e431f576000 fb109f8a9d6453dd; do
  n=$(cat captures/skylake-trig-h347/inputs.txt capture-kit/inputs/sweep_inputs.txt capture-kit/inputs/dense_qn.txt h405/window_inputs.txt h409/separators.txt | grep -c "$op" || true)
  echo "OVERLAP $op: $n"
done
score () {
  local name=$1 infile=$2 hwpat=$3
  local tot=0
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake_r84 --batch $RC --fsin-standalone < $infile > h410/tmp_$mode.txt
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
assert len(hw)==len(mo)
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
)))
  done
  echo "R84VM $name: $tot"
}
score fsin_h347 captures/skylake-trig-h347/inputs.txt "captures/skylake-trig-h347/fsin_MODE_status.txt"
score fsin_sweep capture-kit/inputs/sweep_inputs.txt "fresh/sweep_fsin_MODE.txt"
score fsin_dense capture-kit/inputs/dense_qn.txt "fresh/dense_fsin_MODE.txt"
score fsin_h405win h405/window_inputs.txt "h405/hw_sin_MODE.txt"
score fsin_h409sep h409/separators.txt "h409/hw_MODE.txt"
echo R84_VM_DONE
