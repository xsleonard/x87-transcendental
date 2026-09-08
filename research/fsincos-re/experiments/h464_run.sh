#!/bin/sh
# h464 driver (runs on the i7): generate 8x12M random positive e=-3
# FCOS inputs, stream each shard through the reconstruction model's
# COS_CARRIER tracer into the zone filter (near-boundary rows only),
# then capture every selected input under RN/RD/RU.  Shards run in
# parallel on the 8 hardware threads; traces are never stored.
# Launch:  cd /root/h464 && setsid nohup sh h464_run.sh > run.log 2>&1 &
set -e
cd /root/h464
MODEL=/root/corpus2/model
RUNNER=/root/x87_capture_x86_64
FLAGS="--fcos-standalone --round18-poly --round21-table-bias \
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
 --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"

for shard in 0 1 2 3 4 5 6 7; do
    python3 - "$shard" << 'PYEOF' &
import random, sys
shard = int(sys.argv[1])
rng = random.Random(0x464000 + shard)
with open(f"cand_{shard}.txt", "w") as f:
    for _ in range(12000000):
        significand = rng.getrandbits(64) | (1 << 63)
        f.write(f"3ffc {significand:016x}\n")
PYEOF
done
wait
echo "candidates generated: $(date)"

for shard in 0 1 2 3 4 5 6 7; do
    ( "$MODEL" --batch $FLAGS --debug-cosine-carrier < cand_$shard.txt \
        2>&1 >/dev/null | \
      python3 h464_zone_filter.py cand_$shard.txt \
        > sel_$shard.tsv 2> filt_$shard.log ) &
done
wait
echo "filtering complete: $(date)"
cat filt_*.log

cat sel_*.tsv > selected.tsv
cut -f1,2 selected.tsv | tr '\t' ' ' > captured_inputs.txt
N=$(wc -l < captured_inputs.txt)
echo "selected rows: $N"
for mode in rn rd ru; do
    taskset -c 2 "$RUNNER" cos "$mode" --status \
        < captured_inputs.txt > "hw_${mode}.txt"
    lines=$(wc -l < "hw_${mode}.txt")
    [ "$lines" -eq "$N" ] || { echo "BAD count $mode: $lines"; exit 1; }
done
rm -f cand_*.txt
echo DONE > h464.done
