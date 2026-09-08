#!/bin/bash
# Band census phase 1 (v2, tab-parsed): over every banked suite
# corpus, find all rows where the maximal-band build (B) differs
# from the classic-core build (A).  Each such row is an
# architecturally VISIBLE band row; banked hw labels it carry
# (==B), nocarry (==A), or other.  C2 rows can never be hits (A
# and B are byte-identical outside fire71).  Streaming; only the
# rare hit rows are stored.
set -e
cd /root/r84
gcc -O2 -I/root/r59 -DG_ROUND84=0 -DG70_SUMRULE=0 -DG70_GUARD=8 -o model_bandA fsincos_skylake_sum.c -lm
gcc -O2 -I/root/r59 -DG_ROUND84=0 -DG70_SUMRULE=9 -o model_bandB fsincos_skylake_sum.c -lm
echo CENSUS_BUILDS_OK
rm -f bhit_*.part band_hits.tsv
job() {
  local corp=$1 insn=$2 mode=$3 RC="" FL="--fcos-standalone" hw
  [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"; [ $mode = rz ] && RC="--rc=rz"
  [ $insn = sin ] && FL="--fsin-standalone"
  if [ $corp = randv1 ] || [ $corp = hostv1 ]; then
    hw=/root/h491/${corp}_${insn}_${mode}_hw_status.txt
  else
    hw=/root/h491/${corp}_${mode}_status.txt
  fi
  paste <(nice -n 10 ./model_bandA --batch $RC $FL < /root/h491/${corp}_inputs.txt) \
        <(nice -n 10 ./model_bandB --batch $RC $FL < /root/h491/${corp}_inputs.txt) \
        $hw /root/h491/${corp}_inputs.txt \
    | awk -F'\t' -v c=$corp -v i=$insn -v m=$mode '
        {
          if ($1 == $2) next;
          split($1, a, " "); split($2, b, " "); split($3, h, " ");
          as = a[1] " " a[2] " " a[3]; bs = b[1] " " b[2] " " b[3];
          hs = h[1] " " h[2] " " h[3];
          if (a[1] != "OK" || b[1] != "OK") { lab = "WEIRD"; }
          else { lab = (hs == bs) ? "CARRY" : ((hs == as) ? "NOCARRY" : "OTHER"); }
          print lab "\t" c "\t" i "\t" m "\t" NR-1 "\t" $4 "\t" as "\t" bs "\t" hs;
        }' > bhit_${corp}_${insn}_${mode}.part
}
for mode in rn rd ru rz; do
  job randv1 cos $mode & job randv1 sin $mode &
  job hostv1 cos $mode & job hostv1 sin $mode &
  wait
done
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do job $corp cos $mode & done
  wait
  job $corp cos rz
done
cat bhit_*.part > band_hits.tsv && rm -f bhit_*.part
echo "BAND HITS: $(wc -l < band_hits.tsv)"
cut -f1 band_hits.tsv | sort | uniq -c
echo CENSUS_PHASE1_DONE
