#!/bin/bash
# Round-57 h410-equivalent on the i7 oracle: fresh sweep+dense
# captures (sin/cos/sincos x rn/rd/ru), then model flag-off vs
# flag-on scoring for FSIN/FCOS/PAIR.
set -e
cd /root/r57val
RUNNER=/root/x87_capture_x86_64
for ins in sin cos sincos; do
  for mode in rn rd ru; do
    for corp in sweep dense; do
      f=hw_${corp}_${ins}_${mode}.txt
      [ -s $f ] || taskset -c 2 $RUNNER $ins $mode --status \
          < ${corp}_inputs.txt > $f
    done
  done
done
echo CAPTURES_DONE
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
FSIN="--fsin-standalone $COMMON --round56-fsin-cosine-carrier"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
PAIR="$COMMON --round40-fsincos-tiny --round53-fcos-operation-classes \
 --round38-p6-cosine-split --round54-fsincos-table-lanes"
MODEL=/root/corpus2/model_r57
for corp in sweep dense; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    $MODEL --batch $RC $FSIN < ${corp}_inputs.txt > mo_${corp}_fsin_${mode}_off.txt
    $MODEL --batch $RC $FSIN --round57-fcos-borrow-rule < ${corp}_inputs.txt > mo_${corp}_fsin_${mode}_on.txt
    $MODEL --batch $RC $FCOS < ${corp}_inputs.txt > mo_${corp}_fcos_${mode}_off.txt
    $MODEL --batch $RC $FCOS --round57-fcos-borrow-rule < ${corp}_inputs.txt > mo_${corp}_fcos_${mode}_on.txt
    $MODEL --batch $RC $PAIR < ${corp}_inputs.txt > mo_${corp}_pair_${mode}_off.txt
    $MODEL --batch $RC $PAIR --round57-fcos-borrow-rule < ${corp}_inputs.txt > mo_${corp}_pair_${mode}_on.txt
  done
done
echo MODEL_DONE
python3 - <<'PYEOF'
def norm(p, paired):
    out = []
    for l in open(p):
        t = l.split()
        if t[0] != "OK":
            out.append(("C2",))
        else:
            out.append(tuple(t[1:5]) if paired else tuple(t[1:3]))
    return out
hwmap = {"fsin": "sin", "fcos": "cos", "pair": "sincos"}
for corp in ("sweep", "dense"):
    for kind in ("fsin", "fcos", "pair"):
        paired = kind == "pair"
        off = on = 0
        for mode in ("rn", "rd", "ru"):
            hw = norm(f"hw_{corp}_{hwmap[kind]}_{mode}.txt", paired)
            mo = norm(f"mo_{corp}_{kind}_{mode}_off.txt", paired)
            mn = norm(f"mo_{corp}_{kind}_{mode}_on.txt", paired)
            assert len(hw) == len(mo) == len(mn)
            off += sum(1 for a, b in zip(hw, mo) if a != b)
            on += sum(1 for a, b in zip(hw, mn) if a != b)
        print(f"{kind}_{corp}: n={len(hw)}x3 off={off} on={on}")
PYEOF
echo ALL_DONE
