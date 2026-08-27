#!/bin/bash
# h912 activation census: over every banked suite corpus, find all
# rows where payload-on (A) differs from payload-off (B).  Each hit
# is an activation-VISIBLE row; banked hw labels it PAYLOAD (==A),
# NOPAYLOAD (==B), or OTHER.  Streaming; only hits stored.
set -e
cd /root/r84
rm -f avhit_*.part act_census.tsv
job() {
  local corp=$1 insn=$2 mode=$3 RC="" FL="--fcos-standalone" hw
  [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"; [ $mode = rz ] && RC="--rc=rz"
  [ $insn = sin ] && FL="--fsin-standalone"
  if [ $corp = randv1 ] || [ $corp = hostv1 ]; then
    hw=/root/h491/${corp}_${insn}_${mode}_hw_status.txt
  else
    hw=/root/h491/${corp}_${mode}_status.txt
  fi
  paste <(nice -n 10 ./model_payA --batch $RC $FL < /root/h491/${corp}_inputs.txt) \
        <(nice -n 10 ./model_payB --batch $RC $FL < /root/h491/${corp}_inputs.txt) \
        $hw /root/h491/${corp}_inputs.txt \
    | awk -F"\t" -v c=$corp -v i=$insn -v m=$mode '
        {
          if ($1 == $2) next;
          split($1, a, " "); split($2, b, " "); split($3, h, " ");
          as = a[1] " " a[2] " " a[3]; bs = b[1] " " b[2] " " b[3];
          hs = h[1] " " h[2] " " h[3];
          if (a[1] != "OK" || b[1] != "OK") { lab = "WEIRD"; }
          else { lab = (hs == as) ? "PAYLOAD" : ((hs == bs) ? "NOPAYLOAD" : "OTHER"); }
          print lab "\t" c "\t" i "\t" m "\t" NR-1 "\t" $4 "\t" as "\t" bs "\t" hs;
        }' > avhit_${corp}_${insn}_${mode}.part
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
cat avhit_*.part > act_census.tsv && rm -f avhit_*.part
echo "ACT CENSUS HITS: $(wc -l < act_census.tsv)"
cut -f1 act_census.tsv | sort | uniq -c
echo H912_CENSUS_DONE
