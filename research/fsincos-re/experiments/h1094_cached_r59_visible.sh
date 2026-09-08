#!/bin/bash
# Harvest a deterministic sample of R59 endpoint-visible controls from
# already-captured comb corpora.  No hardware instruction is executed.
# Usage: h1094_cached_r59_visible.sh OUTPUT_TSV
set -e
cd /root/r84
OUT=${1:?new output path required}
[ ! -e "$OUT" ] || { echo "refusing to overwrite $OUT" >&2; exit 2; }
printf 'insn\tmode\top\thw\tbase\tfminus2\tfplus1\tcorpus\tindex\n' > "$OUT"

job() {
  local corpus=$1 mode=$2 stride=$3 rc="" hw
  [ "$mode" = rd ] && rc="--rc=rd"
  [ "$mode" = ru ] && rc="--rc=ru"
  [ "$mode" = rz ] && rc="--rc=rz"
  hw=/root/h491/${corpus}_${mode}_status.txt
  paste <(./h1094_force1 --batch $rc --fcos-standalone \
              < /root/h491/${corpus}_inputs.txt) \
        <(./h1094_force4 --batch $rc --fcos-standalone \
              < /root/h491/${corpus}_inputs.txt) \
        <(./h1089_candidate --batch $rc --fcos-standalone \
              < /root/h491/${corpus}_inputs.txt) \
        "$hw" /root/h491/${corpus}_inputs.txt \
    | awk -F'\t' -v c="$corpus" -v m="$mode" -v stride="$stride" '
        {
          split($1, a, " "); split($2, b, " ");
          split($3, d, " "); split($4, h, " ");
          av=a[1] ":" a[2] ":" a[3]; bv=b[1] ":" b[2] ":" b[3];
          dv=d[1] ":" d[2] ":" d[3]; hv=h[1] ":" h[2] ":" h[3];
          if (av != bv) {
            visible++;
            if (dv == hv && visible % stride == 0) {
              row = "cos\t" m "\t" $5 "\t" h[2] ":" h[3];
              row = row "\t" d[2] ":" d[3] "\t" a[2] ":" a[3];
              row = row "\t" b[2] ":" b[3] "\t" c "\t" NR-1;
              print row;
            }
          }
        }' >> "$OUT"
}

job comb9 rn 200
job comb9 ru 200
job comb16 ru 100
echo "rows $(( $(wc -l < "$OUT") - 1 ))"
sha256sum "$OUT"
