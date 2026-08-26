#!/bin/bash
# R88 reassembled cross-machine FSIN check: the promoted model
# (built from /root/r59 by r84_suite_zero.sh as ./model_suite)
# against the SURVIVING banked VM-captured truth (h347 + sweep +
# dense, rn/rd/ru).  The VM working tree was deleted ~2026-08-26;
# h405/h409 and all VM-side RZ captures are lost (inputs were
# VM-local).  Comparison host: i7; truth: VM silicon captures
# (skylake-trig-h347 2026-07-22, skylake-perinsn-20260807).
set -e
cd /root/r84
cat > /tmp/vmf_cmp.py <<'PYEOF'
import sys
hwf, tag = sys.argv[1:3]
def norm(t): return ("C2",) if t[0] == "C2" else tuple(t[1:3])
n = bad = 0
with open(hwf) as hw:
    for mline, hline in zip(sys.stdin, hw):
        if norm(mline.split()) != norm(hline.split()): bad += 1
        n += 1
    if next(hw, None) is not None:
        print(f"LENGTH-MISMATCH {tag}"); sys.exit(1)
print(f"{tag}: {bad} / {n}")
sys.exit(0 if bad == 0 else 1)
PYEOF
fail=0
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  ./model_suite --batch $RC --fsin-standalone < vmfsin/h347_inputs.txt \
    | python3 /tmp/vmf_cmp.py vmfsin/fsin_${mode}_status.txt vm_h347_$mode || fail=1
  ./model_suite --batch $RC --fsin-standalone < vmfsin/sweep_inputs.txt \
    | python3 /tmp/vmf_cmp.py vmfsin/sweep_fsin_${mode}.txt vm_sweep_$mode || fail=1
  ./model_suite --batch $RC --fsin-standalone < vmfsin/dense_qn.txt \
    | python3 /tmp/vmf_cmp.py vmfsin/dense_fsin_${mode}.txt vm_dense_$mode || fail=1
done
[ $fail = 0 ] && echo "VMFSIN_ZERO_OK" || { echo "VMFSIN_NONZERO"; exit 1; }
