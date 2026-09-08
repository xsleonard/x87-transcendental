#!/bin/bash
# h422: construct a dense boundary-sensitive near-collision corpus for the
# terminal carrier, capture it, and store traces. Selection is model-only
# (hardware-blind); hardware is used solely to label the selected set.
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
mkdir -p h422
python3 - <<'PYEOF'
import random
rng = random.Random(0x422422)
with open("h422/candidates.txt","w") as f:
    for _ in range(4000000):
        sig = rng.getrandbits(64) | (1 << 63)
        sign = rng.getrandbits(1)
        se = (sign << 15) | (-3 + 16383)
        f.write(f"{se:04x} {sig:016x}\n")
PYEOF
src/fsincos_skylake --batch $FCOS --debug-cosine-carrier < h422/candidates.txt > /dev/null 2> h422/trace_all.txt
wc -l h422/trace_all.txt
python3 - <<'PYEOF'
def parse_trace(line):
    d = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        d[k] = v
    return d
def correction(d, payload):
    le2 = int(d["le2"]); re2 = int(d["re2"])
    ls = int(d["ls"], 16); rs = int(d["rs"], 16)
    lsign = int(d["lsign"]); rsign = int(d["rsign"])
    scale = min(le2, re2)
    if payload: scale = min(scale, le2 - 8)
    acc = (-1 if lsign else 1) * (ls << (le2 - scale)) \
        + (-1 if rsign else 1) * (rs << (re2 - scale))
    if payload:
        acc += (-1 if lsign else 1) * (payload << (le2 - 8 - scale))
    neg = acc < 0
    mag = -acc if neg else acc
    w = mag.bit_length()
    sh = max(w - 67, 0)
    mag >>= sh
    return (-mag if neg else mag), scale + sh
def final_cos(corr, ce2, mode):
    num = (1 << -ce2) + corr
    w = num.bit_length()
    sh = w - 64
    if sh <= 0: return num << -sh
    kept = num >> sh
    rem = num & ((1 << sh) - 1)
    half = 1 << (sh - 1)
    inc = 0
    if mode == "rn":
        if rem > half or (rem == half and (kept & 1)): inc = 1
    elif mode == "ru":
        if rem: inc = 1
    kept += inc
    if kept >> 64: kept >>= 1
    return kept
inp = open("h422/candidates.txt")
keep = []
with open("h422/trace_all.txt") as tf:
    for i, line in enumerate(tf):
        x = inp.readline()
        d = parse_trace(line)
        if d.get("active") != "1": continue
        p = int(d["payload"])
        le2 = int(d["le2"]); re2 = int(d["re2"])
        rs = int(d["rs"], 16)
        lane_shift = (le2 - 8) - re2
        lane = (rs >> lane_shift if lane_shift >= 0 else rs << -lane_shift) & 0xFF
        diff = (lane - p) & 0xFF
        if diff >= 128: diff -= 256
        if abs(diff) > 2: continue
        base = {m: final_cos(*correction(d, p), m) for m in ("rn","rd","ru")}
        sens = False
        for k in (-3,-2,-1,1,2,3):
            c, e = correction(d, p + k)
            if any(final_cos(c, e, m) != base[m] for m in ("rn","rd","ru")):
                sens = True; break
        if sens:
            keep.append((x.strip(), line.strip()))
print("boundary-sensitive near-collision rows:", len(keep))
with open("h422/selected_inputs.txt","w") as f:
    for x, _ in keep: f.write(x + "\n")
with open("h422/selected_traces.txt","w") as f:
    for _, t in keep: f.write(t + "\n")
PYEOF
for mode in rn rd ru; do
  src/x87_capture $mode cos --status < h422/selected_inputs.txt > h422/hw_$mode.txt
done
wc -l h422/selected_inputs.txt
rm -f h422/candidates.txt h422/trace_all.txt
