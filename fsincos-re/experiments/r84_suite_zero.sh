#!/bin/bash
# THE STANDING FULL-SUITE REGRESSION (post-Round-84): asserts the
# bare build is at ZERO on every banked i7 suite corpus — randv1
# (FCOS+FSIN x rn/rd/ru), hostv1 (same), comb7-18 (FCOS x 3 modes).
# Streaming (model output piped straight into the comparator;
# nothing stored — the box runs near disk capacity).  Companion:
# r58_vm.sh (VM FSIN five corpora).  Any nonzero line here is a NEW
# OPEN PROBLEM: census it and decide (derive / isolate / ledger
# WITH a suite gate) — never silently append to r84_ledger[].
set -e
mkdir -p /root/r84 && cd /root/r84
cp -f /root/r59/fsincos_skylake.c fsincos_skylake_suite.c
gcc -O2 -I/root/r59 -o model_suite fsincos_skylake_suite.c -lm
cat > /tmp/r84_cmp.py <<'PYEOF'
import sys
hwf, corp, insn, mode = sys.argv[1:5]
def norm(t): return ("C2",) if t[0] == "C2" else tuple(t[1:3])
n = bad = 0
with open(hwf) as hw:
    for mline, hline in zip(sys.stdin, hw):
        if norm(mline.split()) != norm(hline.split()): bad += 1
        n += 1
    if next(hw, None) is not None:
        print(f"LENGTH-MISMATCH {corp} {insn} {mode}"); sys.exit(1)
print(f"{corp} {insn} {mode}: {bad} / {n}")
sys.exit(0 if bad == 0 else 1)
PYEOF
fail=0
job() { # corpus insn mode
  local corp=$1 insn=$2 mode=$3 RC="" FL="--fcos-standalone" hw
  [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  [ $insn = sin ] && FL="--fsin-standalone"
  if [ $corp = randv1 ] || [ $corp = hostv1 ]; then
    hw=/root/h491/${corp}_${insn}_${mode}_hw_status.txt
  else
    hw=/root/h491/${corp}_${mode}_status.txt
  fi
  nice -n 10 ./model_suite --batch $RC $FL < /root/h491/${corp}_inputs.txt \
    | python3 /tmp/r84_cmp.py $hw $corp $insn $mode
}
for corp in randv1 hostv1; do
  for insn in cos sin; do
    for mode in rn rd ru; do job $corp $insn $mode || fail=1; done
  done
done
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do job $corp cos $mode || fail=1; done
done
[ $fail = 0 ] && echo "SUITE_ZERO_OK" || { echo "SUITE_NONZERO"; exit 1; }
