#!/bin/bash
set -e
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
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
for corp in comb7 comb9 comb11; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    ./model_r61 --batch $RC $FCOS --round60-fcos-tie-gate \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_r61.txt
  done
done
python3 - <<PYEOF
from collections import Counter
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
for corp in ("comb7", "comb9", "comb11"):
    theta = {}
    seen = set()
    for l in open(f"/root/h491/ties_{corp}.txt"):
        f = l.split()
        if f[0] in seen: continue
        seen.add(f[0])
        theta[f[0]] = int(f[9])
    inputs = [l.split()[1] for l in open(f"/root/h491/{corp}_inputs.txt")]
    tot = 0
    cen = Counter()
    for mode in ("rn", "rd", "ru"):
        hw = norm(f"/root/h491/{corp}_{mode}_status.txt")
        mo = norm(f"mo_{corp}_{mode}_r61.txt")
        assert len(hw) == len(mo)
        for i, (a, b) in enumerate(zip(hw, mo)):
            if a != b:
                tot += 1
                cen[theta.get(inputs[i], "?")] += 1
    print(f"{corp} r61: {tot} mismatches / {3*len(hw)}  by theta: "
          f"{dict(sorted(cen.items(), key=str))}")
PYEOF
