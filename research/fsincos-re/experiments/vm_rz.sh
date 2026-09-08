#!/bin/bash
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
cap() { src/x87_capture rz sin < $1 > $2; echo "CAPTURED $2: $(wc -l < $2)"; }
cap captures/skylake-trig-h347/inputs.txt captures/skylake-trig-h347/fsin_rz_status.txt
cap capture-kit/inputs/sweep_inputs.txt fresh/sweep_fsin_rz.txt
cap capture-kit/inputs/dense_qn.txt fresh/dense_fsin_rz.txt
cap h405/window_inputs.txt h405/hw_sin_rz.txt
cap h409/separators.txt h409/hw_rz.txt
score() {
  local name=$1 infile=$2 hwfile=$3
  src/fsincos_skylake --batch --rc=rz --fsin-standalone < $infile > h410/tmp_rz.txt
  python3 - "$hwfile" <<'PYEOF'
import sys
def norm(p):
    out=[]
    for l in open(p):
        t=l.split()
        out.append(tuple(t[1:3]) if t[0]=="OK" else ("C2",))
    return out
hw = norm(sys.argv[1]); mo = norm("h410/tmp_rz.txt")
assert len(hw)==len(mo)
print(sum(1 for a,b in zip(hw,mo) if a!=b))
PYEOF
}
for spec in "fsin_h347 captures/skylake-trig-h347/inputs.txt captures/skylake-trig-h347/fsin_rz_status.txt" \
            "fsin_sweep capture-kit/inputs/sweep_inputs.txt fresh/sweep_fsin_rz.txt" \
            "fsin_dense capture-kit/inputs/dense_qn.txt fresh/dense_fsin_rz.txt" \
            "fsin_h405win h405/window_inputs.txt h405/hw_sin_rz.txt" \
            "fsin_h409sep h409/separators.txt h409/hw_rz.txt"; do
  set -- $spec
  echo "RZVM $1: $(score $1 $2 $3)"
done
echo VM_RZ_DONE
