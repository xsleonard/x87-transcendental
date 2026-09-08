#!/bin/bash
# h411: re-score the hostile FCOS terminal-adder sets with the current
# Round-56 model, results and C1 (C1 = SW bit 9 via directed bounds).
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
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
mkdir -p h411
declare -A SETS=(
  [h363]=capture-kit/inputs/constraint_fcos_terminal_neighbors_h363.txt
  [h372]=capture-kit/inputs/constraint_fcos_scaled_tail_h372.txt
  [h380]=capture-kit/inputs/constraint_fcos_payload_h380.txt
  [h384]=capture-kit/inputs/constraint_fcos_payload_h384.txt
)
for s in h363 h372 h380 h384; do
  IN=${SETS[$s]}
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    src/fsincos_skylake --batch $RC $FCOS < $IN > h411/${s}_m_$mode.txt
  done
  python3 - "$s" "$IN" <<'PYEOF'
import sys
s, infile = sys.argv[1:3]
inp = [l.strip() for l in open(infile) if l.strip()]
res_miss = c1_miss = 0
miss_rows = []
hw = {}; mo = {}
for m in ("rn","rd","ru"):
    hw[m] = [l.split() for l in open(f"captures/skylake-fcos-{s}/fcos_{m}_status.txt")]
    mo[m] = [l.split() for l in open(f"h411/{s}_m_{m}.txt")]
n = len(inp)
def neg(t): return (int(t[0],16) >> 15) & 1
for i in range(n):
    for m in ("rn","rd","ru"):
        h = hw[m][i]; o = mo[m][i]
        if h[0] != "OK": continue
        if h[1:3] != o[1:3]:
            res_miss += 1
            miss_rows.append((i, m, inp[i], h[1], h[2], o[1], o[2]))
    # C1: model increment flag from directed bounds vs hw SW bit 9
    rd_r = mo["rd"][i][1:3]; ru_r = mo["ru"][i][1:3]
    for m in ("rn","rd","ru"):
        h = hw[m][i]
        if h[0] != "OK": continue
        r = mo[m][i][1:3]
        toward = ru_r if neg(r) else rd_r
        inc = 0 if r == toward else 1
        if inc != ((int(h[4],16) >> 9) & 1):
            c1_miss += 1
print(f"{s}: n={n} result_misses={res_miss} C1_misses={c1_miss}")
with open(f"h411/{s}_misses.txt","w") as f:
    for row in miss_rows:
        f.write(" ".join(map(str,row)) + "\n")
PYEOF
done
