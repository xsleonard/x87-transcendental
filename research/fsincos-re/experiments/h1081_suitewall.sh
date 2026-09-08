#!/bin/bash
# h1081 suite wall: score a ledger-disabled candidate over every banked
# hardware corpus without deleting or overwriting a historical artifact.
# Usage: h1081_suitewall.sh <model-binary> <new-output-path>
set -e
cd /root/r84
M=${1:?model binary required}
OUT=${2:?new output path required}
[ ! -e "$OUT" ] || { echo "refusing to overwrite $OUT" >&2; exit 2; }
touch "$OUT"

job() {
  local corp=$1 insn=$2 mode=$3 RC="" FL="--fcos-standalone" hw
  [ "$mode" = rd ] && RC="--rc=rd"
  [ "$mode" = ru ] && RC="--rc=ru"
  [ "$mode" = rz ] && RC="--rc=rz"
  [ "$insn" = sin ] && FL="--fsin-standalone"
  if [ "$corp" = randv1 ] || [ "$corp" = hostv1 ]; then
    hw=/root/h491/${corp}_${insn}_${mode}_hw_status.txt
  else
    hw=/root/h491/${corp}_${mode}_status.txt
  fi
  paste <(nice -n 10 "$M" --batch $RC $FL < /root/h491/${corp}_inputs.txt) \
        "$hw" /root/h491/${corp}_inputs.txt \
    | awk -F'\t' -v c="$corp" -v i="$insn" -v m="$mode" '
        {
          split($1, a, " "); split($2, h, " ");
          as = a[1] " " a[2] " " a[3]; hs = h[1] " " h[2] " " h[3];
          if (as != hs) print c "\t" i "\t" m "\t" NR-1 "\t" $3 "\t" as "\t" hs;
        }' >> "$OUT"
}

for mode in rn rd ru rz; do
  job randv1 cos "$mode" & job randv1 sin "$mode" &
  job hostv1 cos "$mode" & job hostv1 sin "$mode" &
  wait
done
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do job "$corp" cos "$mode" & done
  wait
  job "$corp" cos rz
done
echo "SUITE MISSES: $(wc -l < "$OUT")"
sort "$OUT" | awk -F'\t' '{print $1, $2, $3, $5}' | sort | uniq -c | sort -rn | head -50
echo H1081_SUITEWALL_DONE
