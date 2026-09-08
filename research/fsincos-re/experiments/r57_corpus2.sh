#!/bin/bash
# Round-57 corpus2 regression: model vs recorded i7 hardware,
# flag off vs on, all three rounding modes.
set -e
cd /root/corpus2
gcc -O2 -ffp-contract=off -o model_r57 /root/src/fsincos_skylake.c -lm
FCOS="--fcos-standalone --round18-poly --round21-table-bias \
 --round23-narrow-coefficient --round24-table-delta-rn67 \
 --round29-p5-fmul-route --round30-fsin-cosine-square \
 --round31-fsin-cosine-tail --round32-fsin-cosine-horner \
 --round33-fsin-cosine-product --round34-table-lookup-firc \
 --round35-table-p-terminal --round36-table-fadd-microcontrol \
 --round37-p6-four-term --round41-fsin-cosine-split \
 --round42-p6-sine-split --round43-p6-sine-bias --round44-p6-sine-bias \
 --round45-p6-sine-fraction --round46-p6-narrow-sine-fraction \
 --round47-p6-narrow-sine-fraction --round48-p6-narrow-sine-fraction \
 --round49-p6-carrier-interval --round50-fsin-operation-classes \
 --round51-fsin-fadd-signature --round38-p6-cosine-split \
 --round39-fcos-tiny --round52-fcos-low3-carrier \
 --round53-fcos-operation-classes"
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  ./model_r57 --batch $RC $FCOS < selected_inputs.txt > r57_off_$mode.txt
  ./model_r57 --batch $RC $FCOS --round57-fcos-borrow-rule \
      < selected_inputs.txt > r57_on_$mode.txt
done
python3 - <<'PYEOF'
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
for mode in ("rn", "rd", "ru"):
    hw = norm(f"hw_{mode}.txt")
    off = norm(f"r57_off_{mode}.txt")
    on = norm(f"r57_on_{mode}.txt")
    moff = sum(1 for a, b in zip(hw, off) if a != b)
    mon = sum(1 for a, b in zip(hw, on) if a != b)
    fixed = sum(1 for a, b, c in zip(hw, off, on)
                if a != b and a == c)
    broke = sum(1 for a, b, c in zip(hw, off, on)
                if a == b and a != c)
    print(f"{mode}: n={len(hw)} off_mismatch={moff} "
          f"on_mismatch={mon} fixed={fixed} broke={broke}")
PYEOF
