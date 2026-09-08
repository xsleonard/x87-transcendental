#!/bin/bash
# rv10 promotion blind: seed 0x872B, 4M ops, 8 legs; incumbent
# (/root/r59 R91 record, default flags) vs candidate (R92 source +
# -DG_B74SCOPE=1), both ledger ON, scored against fresh hw.  Epoch
# probes (34/34) bracket the capture.
set -e
cd /root/r84
/root/r84/probe_ledger.sh rv10-pre
python3 /root/r59/h733_gen.py 0x872B 4000000 rv10_inputs.txt
wc -l rv10_inputs.txt
gcc -O2 -I/root/r59 -o rv10_incumbent /root/r59/fsincos_skylake.c -lm
gcc -O2 -o rv10_candidate r92_src2.c -lm -DG_B74SCOPE=1
echo RV10_BUILDS_OK
for insn in cos sin; do
  for mode in rn rd ru rz; do
    ( /root/x87_capture_x86_64 $mode $insn < rv10_inputs.txt \
        > rv10_hw_${insn}_${mode}.txt ) &
  done
  wait
  echo "RV10_CAPTURED $insn"
done
/root/r84/probe_ledger.sh rv10-post
rm -f rv10_report.txt
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    paste <(nice -n 10 ./rv10_incumbent --batch $RC $FL < rv10_inputs.txt) \
          <(nice -n 10 ./rv10_candidate --batch $RC $FL < rv10_inputs.txt) \
          rv10_hw_${insn}_${mode}.txt rv10_inputs.txt \
      | awk -F"\t" -v i=$insn -v m=$mode '
          {
            split($1,a," "); split($2,b," "); split($3,h," ");
            as=a[1]" "a[2]" "a[3]; bs=b[1]" "b[2]" "b[3]; hs=h[1]" "h[2]" "h[3];
            im = (as==hs); cm = (bs==hs);
            if (!im) imiss++;
            if (!cm) cmiss++;
            if (as!=bs) {
              nd++;
              tag = cm ? (im ? "BOTH?" : "CAND_WINS") : (im ? "INC_WINS" : "NEITHER");
              print "DIFF\t" i "\t" m "\t" NR-1 "\t" $4 "\t" tag "\t" as "\t" bs "\t" hs >> "rv10_report.txt";
            }
          }
          END { printf "LEG %s %s: diffs=%d inc_miss=%d cand_miss=%d\n", i, m, nd, imiss, cmiss }
        '
  done
done
echo RV10_SCORING_DONE
[ -f rv10_report.txt ] && awk -F"\t" "{print \$6}" rv10_report.txt | sort | uniq -c || echo "0 diff rows"
echo RV10_DONE
