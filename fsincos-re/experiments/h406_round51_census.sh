#!/bin/bash
# h406: enumerate every input whose standalone-FSIN result depends on the
# Round-51 leaf, across h347/sweep/dense, and trace their FADD states.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
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
 --round49-p6-carrier-interval --round50-fsin-operation-classes"
mkdir -p h406
cat captures/skylake-trig-h347/inputs.txt capture-kit/inputs/sweep_inputs.txt capture-kit/inputs/dense_qn.txt > h406/all_inputs.txt
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  src/fsincos_skylake --batch $RC --fsin-standalone $COMMON < h406/all_inputs.txt > h406/no51_$mode.txt &
  src/fsincos_skylake --batch $RC --fsin-standalone $COMMON --round51-fsin-fadd-signature < h406/all_inputs.txt > h406/with51_$mode.txt &
  wait
done
python3 - <<'PYEOF'
inp = [l.strip() for l in open("h406/all_inputs.txt")]
dep = set()
for m in ("rn","rd","ru"):
    a = open(f"h406/no51_{m}.txt").read().splitlines()
    b = open(f"h406/with51_{m}.txt").read().splitlines()
    for i,(x,y) in enumerate(zip(a,b)):
        if x != y: dep.add(i)
print("round51-dependent inputs:", len(dep))
with open("h406/dependent_inputs.txt","w") as f:
    for i in sorted(dep): f.write(inp[i]+"\n")
for i in sorted(dep): print(" ", inp[i])
PYEOF
