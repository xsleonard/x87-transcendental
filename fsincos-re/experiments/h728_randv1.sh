#!/bin/bash
# h728: capture + score the randv1 reasonable corpus (FCOS + FSIN,
# rn/rd/ru) against the bare closed-form model.
set -e
cd /root/r59
for insn in cos sin; do
  for mode in rn rd ru; do
    /root/x87_capture $insn $mode < randv1_inputs.txt \
        > randv1_${insn}_${mode}_hw.txt
    echo "captured $insn $mode"
  done
done
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  ./model_master --batch $RC --fcos-standalone \
      < randv1_inputs.txt > randv1_cos_${mode}_mo.txt
  echo "model cos $mode"
  ./model_master --batch $RC --fsin-standalone \
      < randv1_inputs.txt > randv1_sin_${mode}_mo.txt
  echo "model sin $mode"
done
python3 - <<'PYEOF'
def norm(line):
    t = line.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
tot_all = 0
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open(f"randv1_{insn}_{mode}_hw.txt").read().splitlines()
        mo = open(f"randv1_{insn}_{mode}_mo.txt").read().splitlines()
        assert len(hw) == len(mo) == 8000000, (insn, mode, len(hw), len(mo))
        bad = 0
        for i,(a,b) in enumerate(zip(hw,mo)):
            if norm(a) != norm(b):
                bad += 1
                if bad <= 5:
                    inp = None
                    print("MISMATCH", insn, mode, "line", i, "hw:", a.strip(), "mo:", b.strip())
        print(f"{insn} {mode}: {bad} mismatches / 8000000")
        tot_all += bad
print("TOTAL:", tot_all, "/ 48000000")
PYEOF
echo H728_DONE
