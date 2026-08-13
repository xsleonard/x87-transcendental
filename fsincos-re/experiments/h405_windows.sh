#!/bin/bash
# h405: dense windows around the three h377 seeds; FSIN + FSINCOS capture
# plus standalone-FSIN model scoring for a family census.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
mkdir -p h405
python3 - <<'PYEOF'
seeds = [("401a","ed5c03467a232800"),("c006","8a7da33ed97f1000"),("c01c","ccb8a935dddf4000")]
W = 3000
with open("h405/window_inputs.txt","w") as f:
    for se, sig in seeds:
        s = int(sig,16)
        for d in range(-W, W+1):
            f.write(f"{se} {s+d:016x}\n")
print("inputs:", 3*(2*W+1))
PYEOF
for mode in rn rd ru; do
  src/x87_capture $mode sin --status < h405/window_inputs.txt > h405/hw_sin_$mode.txt
  src/x87_capture $mode sincos --status < h405/window_inputs.txt > h405/hw_sincos_$mode.txt
done
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
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  src/fsincos_skylake --batch $RC --fsin-standalone $COMMON < h405/window_inputs.txt > h405/m_sin_$mode.txt &
done
wait
python3 - <<'PYEOF'
W = 3000; N = 2*W+1
names = ["g0(exp27)","g1(exp7)","g2(exp29)"]
for gi in range(3):
    lo, hi = gi*N, (gi+1)*N
    total = {"model_miss":0, "pair_vs_alone":0}
    miss_offsets = []
    for m in ("rn","rd","ru"):
        hs = [l.split() for l in open(f"h405/hw_sin_{m}.txt")][lo:hi]
        hp = [l.split() for l in open(f"h405/hw_sincos_{m}.txt")][lo:hi]
        ms = [l.split() for l in open(f"h405/m_sin_{m}.txt")][lo:hi]
        for i in range(N):
            if hs[i][0] != "OK": continue
            if hs[i][1:3] != ms[i][1:3]:
                total["model_miss"] += 1
                miss_offsets.append((i-W, m))
            if hs[i][1:3] != hp[i][1:3]:
                total["pair_vs_alone"] += 1
    print(names[gi], total, "miss offsets:", miss_offsets[:20])
PYEOF
