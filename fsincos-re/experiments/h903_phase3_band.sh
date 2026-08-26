#!/bin/bash
# Band census phase 3: fresh-random densification, chunked.
# Generates 2M-operand chunks (h727 broad-normal core, non-blind
# seeds), A/B-diffs each chunk per (insn, mode), banks hit operands
# with their A/B outputs, deletes the chunk.  hw for the hits is
# captured afterward (band3_capture.sh) and merged into the cell map.
# Usage: phase3_band.sh <nchunks> <seedbase-int>
set -e
cd /root/r84
NCH=${1:-4}
SEEDBASE=${2:-49374}
gen() { # seed
  python3 - "$1" <<'PYEOF'
import sys, random
random.seed(int(sys.argv[1]))
for _ in range(2000000):
    se = random.randint(0x3fbe, 0x403d) | (random.randint(0, 1) << 15)
    sig = random.getrandbits(64) | (1 << 63)
    r = random.random()
    if r < 0.30:
        sig &= ~((1 << 11) - 1)          # binary64-aligned
    elif r < 0.50:
        tz = random.randint(8, 40)       # random truncation
        sig &= ~((1 << tz) - 1)
    elif r < 0.65:
        tz = random.randint(24, 48)      # heavy trailing zeros
        sig &= ~((1 << tz) - 1)
    sys.stdout.write("%04x %016x\n" % (se, sig))
PYEOF
}
rm -f band3_hits.tsv
for ((c=0; c<NCH; c++)); do
  seed=$((SEEDBASE + c))
  gen $seed > /root/r84/band3_chunk.txt
  for insn in cos sin; do
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    for mode in rn rd ru rz; do
      RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
      [ $mode = rz ] && RC="--rc=rz"
      paste <(nice -n 10 ./model_bandA --batch $RC $FL < band3_chunk.txt) \
            <(nice -n 10 ./model_bandB --batch $RC $FL < band3_chunk.txt) \
            band3_chunk.txt \
        | awk -F'\t' -v i=$insn -v m=$mode -v s=$seed '
            $1 != $2 { print "UNLAB\tband3-" s "\t" i "\t" m "\t" NR-1 "\t" $3 "\t" $1 "\t" $2 "\t?" }' \
        > band3_${insn}_${mode}_${seed}.part &
    done
    wait
  done
  cat band3_*_${seed}.part >> band3_hits.tsv && rm -f band3_*_${seed}.part
  echo "CHUNK $c (seed $seed): cumulative hits $(wc -l < band3_hits.tsv)"
done
rm -f band3_chunk.txt
echo "PHASE3 HITS: $(wc -l < band3_hits.tsv)"
echo PHASE3_DONE
