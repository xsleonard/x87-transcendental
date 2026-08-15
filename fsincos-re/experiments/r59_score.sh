#!/bin/bash
set -e
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
for corp in comb7 comb9; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    ./model_r59 --batch $RC $FCOS --round57-fcos-borrow-rule \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_r57.txt
    ./model_r59 --batch $RC $FCOS --round59-fcos-theta-band \
        < /root/h491/${corp}_inputs.txt > mo_${corp}_${mode}_r59.txt
  done
done
python3 - <<PYEOF
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
for corp in ("comb7", "comb9"):
    for tag in ("r57", "r59"):
        tot = 0
        for mode in ("rn", "rd", "ru"):
            hw = norm(f"/root/h491/{corp}_{mode}_status.txt")
            mo = norm(f"mo_{corp}_{mode}_{tag}.txt")
            assert len(hw) == len(mo), (corp, mode, len(hw), len(mo))
            tot += sum(1 for a, b in zip(hw, mo) if a != b)
        print(f"{corp} {tag}: {tot} mismatches / {3*len(hw)}")
PYEOF
