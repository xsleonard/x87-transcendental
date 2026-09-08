#!/bin/bash
# The standing second-host (VM) regression, successor of r58_vm.sh +
# vm_rz.sh after the h908 deletion.  Home: /root/fsincos-r88 (NOT
# /home/coduoserver — that tree was cleaned by the box's game-server
# tenant; NOT /tmp).  Three corpora survive with re-runnable inputs:
# h347, sweep, dense (h405/h409 were lost with their VM-local
# inputs).  Does three things:
#   1) EPOCH CHECK: fresh-captures rn/rd/ru and diffs BIT-FOR-BIT
#      against the banked 2026-07/08 mirrors (hardware-vs-hardware,
#      cross-time, this silicon).  Any differing line is an epoch
#      event — report loudly, do not proceed silently.
#   2) RZ CAPTURE: re-captures the rz legs lost in h908 into fresh/.
#   3) MODEL SCORE: the current model vs all four modes x three
#      corpora (expect 0 everywhere).
set -e
cd /root/fsincos-r88
date -u +%Y-%m-%dT%H:%M:%SZ
grep -m1 "model name" /proc/cpuinfo || true
epoch_fail=0
for mode in rn rd ru; do
  src/x87_capture $mode sin --status < corpora/h347_inputs.txt > fresh/h347_fsin_${mode}.txt
  src/x87_capture $mode sin --status < corpora/sweep_inputs.txt > fresh/sweep_fsin_${mode}.txt
  src/x87_capture $mode sin --status < corpora/dense_qn.txt > fresh/dense_fsin_${mode}.txt
  for c in h347:fsin_${mode}_status sweep:sweep_fsin_${mode} dense:dense_fsin_${mode}; do
    corp=${c%%:*}; bank=${c#*:}
    fresh="fresh/${corp}_fsin_${mode}.txt"
    [ $corp = sweep ] && fresh="fresh/sweep_fsin_${mode}.txt"
    [ $corp = dense ] && fresh="fresh/dense_fsin_${mode}.txt"
    d=$(diff "banked/${bank}.txt" "$fresh" | grep -c "^<" || true)
    echo "EPOCH $corp $mode: $d differing rows"
    [ "$d" = "0" ] || epoch_fail=1
  done
done
[ $epoch_fail = 0 ] && echo "EPOCH_OK (fresh captures bit-identical to 2026-07/08 banked)" \
                    || echo "EPOCH_EVENT — investigate before trusting anything below"
for corp in h347 sweep dense; do
  inp=corpora/${corp}_inputs.txt
  [ $corp = sweep ] && inp=corpora/sweep_inputs.txt
  [ $corp = dense ] && inp=corpora/dense_qn.txt
  src/x87_capture rz sin --status < $inp > fresh/${corp}_fsin_rz.txt
  echo "RZ CAPTURED $corp: $(wc -l < fresh/${corp}_fsin_rz.txt)"
done
score() {
  local tag=$1 infile=$2 hwfile=$3 RC=$4
  src/fsincos_skylake --batch $RC --fsin-standalone < $infile > /tmp/vmc_mo.txt
  python3 - "$hwfile" <<'PYEOF'
import sys
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
hw = norm(sys.argv[1]); mo = norm("/tmp/vmc_mo.txt")
assert len(hw) == len(mo), (len(hw), len(mo))
print(sum(1 for a, b in zip(hw, mo) if a != b))
PYEOF
}
fail=0
for mode in rn rd ru rz; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  [ $mode = rz ] && RC="--rc=rz"
  for corp in h347 sweep dense; do
    inp=corpora/${corp}_inputs.txt
    [ $corp = sweep ] && inp=corpora/sweep_inputs.txt
    [ $corp = dense ] && inp=corpora/dense_qn.txt
    n=$(score $corp $inp fresh/${corp}_fsin_${mode}.txt $RC)
    echo "MODEL $corp $mode: $n"
    [ "$n" = "0" ] || fail=1
  done
done
[ $fail = 0 ] && echo "VM_CHECK_ZERO_OK" || { echo "VM_CHECK_NONZERO"; exit 1; }
