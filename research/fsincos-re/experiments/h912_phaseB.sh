#!/bin/bash
# h912 phase B: fresh-random densification of the activation boundary.
# Per chunk: generate 2M operands (mix matched to the labeled-set tz
# profile), A/B-diff (payload-on vs payload-off) on cos+sin x 4 modes,
# capture hw for the hit rows immediately, label PAYLOAD/NOPAYLOAD/
# OTHER, append to act_fresh.tsv, delete the chunk.
# Usage: h912_phaseB.sh <nchunks> <seedbase>
set -e
cd /root/r84
NCH=${1:-8}
SEEDBASE=${2:-91200}
gen() { # seed
  python3 - "$1" <<'PYEOF'
import sys, random
random.seed(int(sys.argv[1]))
w = sys.stdout.write
for _ in range(2000000):
    se = random.randint(0x3fbe, 0x403d) | (random.randint(0, 1) << 15)
    sig = random.getrandbits(64) | (1 << 63)
    r = random.random()
    if r < 0.25:
        tz = random.randint(4, 11)
        sig &= ~((1 << tz) - 1)
    elif r < 0.40:
        tz = random.randint(12, 23)
        sig &= ~((1 << tz) - 1)
    w("%04x %016x\n" % (se, sig))
PYEOF
}
for ((c=0; c<NCH; c++)); do
  seed=$((SEEDBASE + c))
  gen $seed > chunkB.txt
  for insn in cos sin; do
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    for mode in rn rd ru rz; do
      RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
      [ $mode = rz ] && RC="--rc=rz"
      paste <(nice -n 10 ./model_payA --batch $RC $FL < chunkB.txt) \
            <(nice -n 10 ./model_payB --batch $RC $FL < chunkB.txt) \
            chunkB.txt \
        | awk -F'\t' -v i=$insn -v m=$mode -v s=$seed '
            $1 != $2 { print s "\t" i "\t" m "\t" NR-1 "\t" $3 "\t" $1 "\t" $2 }' \
        > fbh_${insn}_${mode}.part &
    done
    wait
  done
  # capture hw for this chunk's hits, leg by leg (tiny inputs)
  for insn in cos sin; do
    for mode in rn rd ru rz; do
      f=fbh_${insn}_${mode}.part
      [ -s $f ] || { rm -f $f; continue; }
      cut -f5 $f > fbh_ops.txt
      /root/x87_capture_x86_64 $mode $insn < fbh_ops.txt > fbh_hw.txt
      paste $f fbh_hw.txt | awk -F'\t' '
        {
          split($6, a, " "); split($7, b, " "); split($8, h, " ");
          as = a[1] " " a[2] " " a[3]; bs = b[1] " " b[2] " " b[3];
          hs = h[1] " " h[2] " " h[3];
          if (a[1] != "OK" || b[1] != "OK") lab = "WEIRD";
          else lab = (hs == as) ? "PAYLOAD" : ((hs == bs) ? "NOPAYLOAD" : "OTHER");
          print lab "\t" $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" as "\t" bs "\t" hs;
        }' >> act_fresh.tsv
      rm -f $f fbh_ops.txt fbh_hw.txt
    done
  done
  echo "CHUNK $c (seed $seed): cumulative $(wc -l < act_fresh.tsv 2>/dev/null || echo 0)"
done
rm -f chunkB.txt
echo "PHASEB HITS: $(wc -l < act_fresh.tsv)"
cut -f1 act_fresh.tsv | sort | uniq -c
echo H912_PHASEB_DONE
