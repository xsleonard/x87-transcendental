#!/bin/bash
set -e
cd /root/r57val
gcc -O2 -ffp-contract=off -o model_r58 /root/src/fsincos_skylake.c -lm
FSIN="--fsin-standalone --round18-poly --round21-table-bias \
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
 --round51-fsin-fadd-signature --round56-fsin-cosine-carrier"
for corp in sweep dense; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    ./model_r58 --batch $RC $FSIN --round58-fsin-borrow-rule \
        < ${corp}_inputs.txt > mo_${corp}_fsin_${mode}_r58.txt
  done
done
python3 - <<'PYEOF'
def norm(p):
    out = []
    for l in open(p):
        t = l.split()
        out.append(tuple(t[1:3]) if t[0] == "OK" else ("C2",))
    return out
for corp in ("sweep", "dense"):
    tot = 0
    for mode in ("rn", "rd", "ru"):
        hw = norm(f"hw_{corp}_sin_{mode}.txt")
        mo = norm(f"mo_{corp}_fsin_{mode}_r58.txt")
        tot += sum(1 for a, b in zip(hw, mo) if a != b)
    print(f"fsin_{corp}_R58: {tot}")
PYEOF
# h616 rescore with the promoted flag
N=$(wc -l < h616_inputs.txt)
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  ./model_r58 --batch $RC $FSIN --round58-fsin-borrow-rule \
      < h616_inputs.txt > mo_h616_${mode}_r58.txt
done
python3 - <<'PYEOF'
def norm(p):
    return [tuple(l.split()[1:3]) if l.split()[0] == "OK"
            else ("C2",) for l in open(p)]
tot = ok = 0
for mode in ("rn", "rd", "ru"):
    hw = norm(f"h616_{mode}_status.txt")
    mo = norm(f"mo_h616_{mode}_r58.txt")
    tot += len(hw)
    ok += sum(1 for a, b in zip(hw, mo) if a == b)
print(f"h616_R58_vs_hw: {ok}/{tot} = {ok/tot:.4f}")
PYEOF
echo R58_I7_DONE
