#!/bin/bash
# h627b: table-path zone scan + capture on the i7.
# usage: h627b_scan.sh <NMILLION>
set -e
cd /root/r57val
N=${1:-30}
python3 - "$N" <<'PYEOF'
import random
import sys
n = int(sys.argv[1]) * 1000000
rng = random.Random(0x627627)
PI4 = 0xC90FDAA22168C234  # pi/4 sig at 3ffe
with open("h627_cand.txt", "w") as f:
    for _ in range(n):
        if rng.random() < 0.5:
            se, lo, hi = 0x3FFD, 1 << 63, (1 << 64) - 1
        else:
            se, lo, hi = 0x3FFE, 1 << 63, PI4 - 1
        f.write(f"{se:04x} {rng.randrange(lo, hi):016x}\n")
PYEOF
echo generated
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
/root/corpus2/model_r58 --batch $FCOS --debug-cosine-carrier \
    < h627_cand.txt > /dev/null 2> h627_traces.txt
echo traced $(wc -l < h627_traces.txt) of $(wc -l < h627_cand.txt)
python3 - <<'PYEOF'
inp = open("h627_cand.txt")
out = open("h627_zone.tsv", "w")
kept = 0
total = 0
for line in open("h627_traces.txt"):
    x = inp.readline().strip()
    if not line.startswith("COS_CARRIER"):
        continue
    total += 1
    f = {}
    for tok in line.split()[1:]:
        k, v = tok.split("=")
        f[k] = v
    if f["active"] != "1" or f["lsign"] != "1" or \
            f["rsign"] != "0":
        continue
    le2, re2 = int(f["le2"]), int(f["re2"])
    ls, rs = int(f["ls"], 16), int(f["rs"], 16)
    dist, low3 = int(f["dist"]), int(f["low3"])
    prepay = low3 + 8 - dist
    scale = min(le2, re2, le2 - 8)
    M = (ls << (le2 - scale)) - (rs << (re2 - scale)) \
        + (prepay << (le2 - 8 - scale))
    if M <= 0:
        continue
    k2 = M.bit_length() - 67
    if k2 < 3:
        continue
    disc = M & ((1 << k2) - 1)
    if disc > 2 and disc < (1 << k2) - 2:
        continue
    out.write(x + "\t" + line.strip() + "\n")
    kept += 1
print(f"aligned {total}, in-zone {kept}")
out.close()
PYEOF
cut -f1 h627_zone.tsv > h627_inputs.txt
NN=$(wc -l < h627_inputs.txt)
echo capturing $NN inputs
for mode in rn rd ru; do
    taskset -c 2 /root/x87_capture_x86_64 cos $mode --status \
        < h627_inputs.txt > h627_${mode}_status.txt
    lines=$(wc -l < h627_${mode}_status.txt)
    [ "$lines" -eq "$NN" ] || { echo "BAD count $mode"; exit 1; }
done
echo H627_DONE
