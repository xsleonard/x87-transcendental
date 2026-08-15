#!/bin/bash
# Standalone-FCOS corpus regression on the i7.  The validated rounds
# are inlined unconditionally in fsincos_skylake.c (2026-08-15
# master-algorithm fold) — build the bare model as model_master in
# /root/r59 (gcc -O2 -o model_master fsincos_skylake.c -lm) before
# running.  Expected: comb7 1, comb9 12, comb11 0, comb12 0,
# comb13 8, comb14 0 (every nonzero row enumerated in
# notes/algorithm-description.md, blind-spot register).
set -e
cd /root/r59
FCOS="--fcos-standalone"
for corp in comb7 comb9 comb11 comb12 comb13 comb14; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    ./model_master --batch $RC $FCOS \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_master.txt
  done
done
python3 - <<PYEOF
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
for corp in ("comb7", "comb9", "comb11", "comb12", "comb13", "comb14"):
    tot = 0
    for mode in ("rn", "rd", "ru"):
        hw = norm(f"/root/h491/{corp}_{mode}_status.txt")
        mo = norm(f"mo_{corp}_{mode}_master.txt")
        assert len(hw) == len(mo)
        tot += sum(1 for a, b in zip(hw, mo) if a != b)
    print(f"{corp}: {tot} mismatches / {3*len(hw)}")
PYEOF
