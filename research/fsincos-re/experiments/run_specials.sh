#!/bin/bash
# Task 3 (SESSION-GUIDE): special/boundary operand sweep, FSIN + FCOS,
# hardware (i7 Skylake-family capture) vs model_r61, rn/rd/ru/rz.
set -e
cd /root/h491
mkdir -p specials
python3 /root/h638_mirror/gen_specials.py \
    > specials/inputs.txt 2> specials/classes.txt
n=$(wc -l < specials/inputs.txt)
echo "inputs: $n"

for insn in sin cos; do
  for mode in rn rd ru rz; do
    taskset -c 2 /root/x87_capture_x86_64 $insn $mode --status \
        < specials/inputs.txt > specials/hw_${insn}_${mode}.txt
    l=$(wc -l < specials/hw_${insn}_${mode}.txt)
    [ "$l" -eq "$n" ] || { echo "BAD capture $insn $mode $l/$n"; exit 1; }
  done
done

cd /root/r59
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
FSIN="--fsin-standalone $COMMON --round56-fsin-cosine-carrier \
 --round58-fsin-borrow-rule"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes \
 --round60-fcos-tie-gate"
for mode in rn rd ru rz; do
  RC=""; [ $mode = rn ] || RC="--rc=$mode"
  ./model_r61 --batch $RC $FSIN \
      < /root/h491/specials/inputs.txt \
      > /root/h491/specials/mo_sin_${mode}.txt
  ./model_r61 --batch $RC $FCOS \
      < /root/h491/specials/inputs.txt \
      > /root/h491/specials/mo_cos_${mode}.txt
done

python3 - <<'PYEOF'
from collections import Counter, defaultdict
cls = {}
for l in open("/root/h491/specials/classes.txt"):
    t = l.split()
    cls[(t[0], t[1])] = t[2]
inputs = [tuple(l.split()) for l in open("/root/h491/specials/inputs.txt")]

def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out

grand = 0
for insn in ("sin", "cos"):
    for mode in ("rn", "rd", "ru", "rz"):
        hw = norm(f"/root/h491/specials/hw_{insn}_{mode}.txt")
        mo = norm(f"/root/h491/specials/mo_{insn}_{mode}.txt")
        assert len(hw) == len(mo) == len(inputs)
        cen = Counter()
        ex = defaultdict(list)
        for i, (a, b) in enumerate(zip(hw, mo)):
            if a != b:
                c = cls[inputs[i]]
                cen[c] += 1
                if len(ex[c]) < 3:
                    ex[c].append((inputs[i], a, b))
        grand += sum(cen.values())
        print(f"{insn} {mode}: {sum(cen.values())} mismatches / {len(hw)}")
        for c in sorted(cen):
            print(f"  {c}: {cen[c]}")
            for (inp, a, b) in ex[c]:
                print(f"    {inp[0]} {inp[1]}  hw={a} model={b}")
print(f"GRAND TOTAL: {grand}")
PYEOF
