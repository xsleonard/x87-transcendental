#!/bin/bash
# h404: h377 3-seed triangulation — model-vs-hardware matrix across
# FSIN/FCOS/FSINCOS/FPTAN on the seeds and +-4 ulp neighbors.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
SRC=src/fsincos_skylake
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
FSIN="--fsin-standalone $COMMON"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
PAIR="$COMMON --round40-fsincos-tiny --round53-fcos-operation-classes \
 --round38-p6-cosine-split --round54-fsincos-table-lanes"
IN=h403/h377_neighbors.txt
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  $SRC --batch $RC $FSIN < $IN > h403/m_h377_sin_$mode.txt
  $SRC --batch $RC $FCOS < $IN > h403/m_h377_cos_$mode.txt
  $SRC --batch $RC $PAIR < $IN > h403/m_h377_sincos_$mode.txt
  $SRC --batch $RC --fptan < $IN > h403/m_h377_fptan_seed_$mode.txt
  $SRC --batch $RC --fptan --fptan-exact-n < $IN > h403/m_h377_fptan_exact_$mode.txt
done
python3 - <<'PYEOF'
inp = [l.split() for l in open("h403/h377_neighbors.txt")]
def hw(insn, m):
    return [l.split() for l in open(f"h403/hw_h377_{insn}_{m}.txt")]
def mo(name, m):
    return [l.split() for l in open(f"h403/m_h377_{name}_{m}.txt")]
seeds = {0+4: "s27", 9+4: "s7", 18+4: "s29"}
print("input(offset)  mode  fsin fcos sincos_s sincos_c fptan_seed fptan_exact   (x=miss .=match)")
for i in range(len(inp)):
    group = i // 9; off = i % 9 - 4
    tag = f"g{group}{'%+d' % off}"
    for m in ("rn","rd","ru"):
        hs, hc, hp, ht = hw("sin",m), hw("cos",m), hw("sincos",m), hw("fptan",m)
        ms, mc, mp = mo("sin",m), mo("cos",m), mo("sincos",m)
        mts, mte = mo("fptan_seed",m), mo("fptan_exact",m)
        def cmp2(a, b, sl_a, sl_b):
            return "." if a[sl_a] == b[sl_b] else "x"
        row = [
            cmp2(hs[i], ms[i], slice(1,3), slice(1,3)),
            cmp2(hc[i], mc[i], slice(1,3), slice(1,3)),
            cmp2(hp[i], mp[i], slice(1,3), slice(1,3)),
            cmp2(hp[i], mp[i], slice(3,5), slice(3,5)),
            cmp2(ht[i], mts[i], slice(1,3), slice(1,3)),
            cmp2(ht[i], mte[i], slice(1,3), slice(1,3)),
        ]
        if "x" in row:
            print(f"{tag:8s} {inp[i][0]}:{inp[i][1]} {m}  " + "  ".join(row))
print("done; only rows with at least one miss are printed")
PYEOF
