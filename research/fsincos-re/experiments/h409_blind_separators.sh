#!/bin/bash
# h409: hardware-blind separator validation of the h408 carrier transfer.
# Separators are inputs where the with/without-h408 models disagree,
# selected purely from model output; hardware is consulted only to score.
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
 --round49-p6-carrier-interval --round50-fsin-operation-classes \
 --round52-fcos-low3-carrier"
mkdir -p h409
# deterministic candidate generation across exponents (no hardware access)
python3 - <<'PYEOF'
import random
rng = random.Random(0x408409)
with open("h409/candidates.txt","w") as f:
    for _ in range(400000):
        e = rng.randint(2, 62)
        sig = rng.getrandbits(64) | (1 << 63)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (e + 16383)
        f.write(f"{se:04x} {sig:016x}\n")
PYEOF
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  src/fsincos_skylake --batch $RC --fsin-standalone $COMMON < h409/candidates.txt > h409/base_$mode.txt &
  src/fsincos_skylake --batch $RC --fsin-standalone $COMMON --h408-fsin-cosine-carrier < h409/candidates.txt > h409/h408_$mode.txt &
  wait
done
python3 - <<'PYEOF'
inp = [l.strip() for l in open("h409/candidates.txt")]
sep = set()
for m in ("rn","rd","ru"):
    a = open(f"h409/base_{m}.txt").read().splitlines()
    b = open(f"h409/h408_{m}.txt").read().splitlines()
    for i,(x,y) in enumerate(zip(a,b)):
        if x != y: sep.add(i)
print("separator inputs:", len(sep))
with open("h409/separators.txt","w") as f:
    for i in sorted(sep): f.write(inp[i]+"\n")
PYEOF
if [ -s h409/separators.txt ]; then
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/x87_capture $mode sin --status < h409/separators.txt > h409/hw_$mode.txt
    src/fsincos_skylake --batch $RC --fsin-standalone $COMMON < h409/separators.txt > h409/sep_base_$mode.txt
    src/fsincos_skylake --batch $RC --fsin-standalone $COMMON --h408-fsin-cosine-carrier < h409/separators.txt > h409/sep_h408_$mode.txt
  done
  python3 - <<'PYEOF'
tot = {"base":0, "h408":0}
n = 0
for m in ("rn","rd","ru"):
    hw = [tuple(l.split()[1:3]) for l in open(f"h409/hw_{m}.txt")]
    ba = [tuple(l.split()[1:3]) for l in open(f"h409/sep_base_{m}.txt")]
    h4 = [tuple(l.split()[1:3]) for l in open(f"h409/sep_h408_{m}.txt")]
    n += len(hw)
    tot["base"] += sum(1 for a,b in zip(hw,ba) if a!=b)
    tot["h408"] += sum(1 for a,b in zip(hw,h4) if a!=b)
print(f"separator observations: {n}")
print(f"baseline (no carrier) misses: {tot['base']}")
print(f"h408 (carrier transfer) misses: {tot['h408']}")
PYEOF
fi
