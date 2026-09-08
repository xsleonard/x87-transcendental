#!/bin/bash
# Preserved verbatim from the 2026-08-07 Round-54 pass; ran in
# /home/coduoserver/fsincos-residual-20260807-1 on the Skylake capture host.
# See notes/skylake-comparison.md (Round 54) and notes/residual-ideas.md.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1/src
make fsincos_skylake 2>&1 | tail -1
./fsincos_skylake --selftest > /dev/null && echo SELFTEST_PASS
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
PAIRBASE="$COMMON --round40-fsincos-tiny"
PAIR54="$PAIRBASE --round53-fcos-operation-classes --round38-p6-cosine-split --round54-fsincos-table-lanes"
mkdir -p out54
# 1. flag-off byte identity: old paired flags, new binary vs previous outputs
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  $SRC --batch $RC $PAIRBASE < captures/skylake-trig-h347/inputs.txt > out54/pairbase_h347_$mode.txt &
done
wait
for mode in rn rd ru; do
  cmp -s out54/pairbase_h347_$mode.txt out347/pair_$mode.txt && echo "FLAGOFF_IDENTICAL_h347_$mode" || echo "FLAGOFF_DIFFERS_h347_$mode"
done
# 2. standalone byte identity with round54 present (must be inert)
$SRC --batch --fsin-standalone $COMMON --round54-fsincos-table-lanes < capture-kit/inputs/sweep_inputs.txt > out54/fsin_sweep_rn54.txt
cmp -s out54/fsin_sweep_rn54.txt outsw/fsin_sweep_rn.txt && echo "STANDALONE_INERT_OK" || echo "STANDALONE_INERT_FAIL"
# 3. round54 paired vs all paired hardware corpora
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  $SRC --batch $RC $PAIR54 < captures/skylake-trig-h347/inputs.txt > out54/pair54_h347_$mode.txt &
  $SRC --batch $RC $PAIR54 < captures/skylake-trig-h349/inputs.txt > out54/pair54_h349_$mode.txt &
  $SRC --batch $RC $PAIR54 < capture-kit/inputs/sweep_inputs.txt > out54/pair54_sweep_$mode.txt &
  $SRC --batch $RC $PAIR54 < capture-kit/inputs/dense_qn.txt > out54/pair54_dense_$mode.txt &
  $SRC --batch $RC $PAIRBASE < capture-kit/inputs/sweep_inputs.txt > out54/pairbase_sweep_$mode.txt &
  $SRC --batch $RC $PAIRBASE < capture-kit/inputs/dense_qn.txt > out54/pairbase_dense_$mode.txt &
  wait
done
python3 - <<'PYEOF'
def pair_model(p): return [tuple(l.split()[1:5]) for l in open(p)]
def pair_hw(p): return [tuple(l.split()[1:5]) for l in open(p)]
def score(mp, hp):
    s = sum(1 for x,y in zip(mp,hp) if x[0:2]!=y[0:2])
    c = sum(1 for x,y in zip(mp,hp) if x[2:4]!=y[2:4])
    return s, c
for corpus, hwpat, inn in (
    ("h347", "captures/skylake-trig-h347/fsincos_{m}_status.txt", None),
    ("h349", "captures/skylake-trig-h349/fsincos_{m}_status.txt", None),
    ("sweep", "fresh/sweep_fsincos_{m}.txt", None),
    ("dense", "fresh/dense_fsincos_{m}.txt", None),
):
    for m in ("rn","rd","ru"):
        hp = pair_hw(hwpat.format(m=m))
        new = pair_model(f"out54/pair54_{corpus}_{m}.txt")
        s, c = score(new, hp)
        line = f"{corpus} {m} round54 sin/cos misses: {s} {c}"
        try:
            base = pair_model(f"out54/pairbase_{corpus}_{m}.txt")
            bs, bc = score(base, hp)
            line += f"   baseline: {bs} {bc}"
        except FileNotFoundError:
            pass
        print(line)
PYEOF
