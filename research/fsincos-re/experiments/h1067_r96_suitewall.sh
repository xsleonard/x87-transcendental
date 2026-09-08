#!/bin/bash
# h1067: score the ledger-off R96 build over the standing suite without
# replacing or deleting any historical suitewall artifact.
set -e
cd /root/r84

MODEL=${1:-./model_r96_noledger}
OUTPUT=${2:-r96_noledger_misses.tsv}
if [ -e "$OUTPUT" ]; then
  echo "Refusing to overwrite existing output: $OUTPUT" >&2
  exit 1
fi

job() {
  local corpus=$1 instruction=$2 mode=$3 rc="" flag="--fcos-standalone" hw
  [ "$mode" = rd ] && rc="--rc=rd"
  [ "$mode" = ru ] && rc="--rc=ru"
  [ "$mode" = rz ] && rc="--rc=rz"
  [ "$instruction" = sin ] && flag="--fsin-standalone"
  if [ "$corpus" = randv1 ] || [ "$corpus" = hostv1 ]; then
    hw=/root/h491/${corpus}_${instruction}_${mode}_hw_status.txt
  else
    hw=/root/h491/${corpus}_${mode}_status.txt
  fi
  paste <(nice -n 10 "$MODEL" --batch $rc $flag \
              < /root/h491/${corpus}_inputs.txt) \
        "$hw" /root/h491/${corpus}_inputs.txt \
    | awk -F'\t' -v c="$corpus" -v i="$instruction" -v m="$mode" '
        {
          split($1, a, " "); split($2, h, " ");
          as = a[1] " " a[2] " " a[3]; hs = h[1] " " h[2] " " h[3];
          if (as != hs) print c "\t" i "\t" m "\t" NR-1 "\t" $3 "\t" as "\t" hs;
        }' >> "$OUTPUT"
}

for mode in rn rd ru rz; do
  job randv1 cos "$mode" & job randv1 sin "$mode" &
  job hostv1 cos "$mode" & job hostv1 sin "$mode" &
  wait
done
for corpus in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do
    job "$corpus" cos "$mode" &
  done
  wait
  job "$corpus" cos rz
done

echo "SUITE MISSES: $(wc -l < "$OUTPUT")"
sort "$OUTPUT" | awk -F'\t' '{print $1, $2, $3, $5}' \
  | sort | uniq -c | sort -rn | head -50
echo H1067_R96_SUITEWALL_DONE
