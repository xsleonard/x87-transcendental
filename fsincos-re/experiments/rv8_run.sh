#!/bin/bash
# rv7 promotion blind (pre-reg 4a77b8f): seed 0x8729, 4M ops,
# 8 legs; incumbent (default flags) vs candidate (G_PAYGATE=1),
# both ledger ON, scored against fresh hw.
set -e
cd /root/r84
python3 /root/r59/h733_gen.py 0x8729 4000000 rv8_inputs.txt
wc -l rv8_inputs.txt
gcc -O2 -I/root/r59 -o rv8_incumbent /root/r59/fsincos_skylake.c -lm
gcc -O2 -I/root/r59 -o rv8_candidate fsincos_skylake_h914.c -lm
echo RV7_BUILDS_OK
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    ( /root/x87_capture_x86_64 $mode $insn < rv8_inputs.txt > rv8_hw_${insn}_${mode}.txt ) &
  done
  wait
  echo "RV7_CAPTURED $insn"
done
rm -f rv8_report.txt
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    paste <(nice -n 10 ./rv8_incumbent --batch $RC $FL < rv8_inputs.txt) \
          <(nice -n 10 ./rv8_candidate --batch $RC $FL < rv8_inputs.txt) \
          rv8_hw_${insn}_${mode}.txt rv8_inputs.txt \
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
              print "DIFF\t" i "\t" m "\t" NR-1 "\t" $4 "\t" tag "\t" as "\t" bs "\t" hs >> "rv8_report.txt";
            }
          }
          END { printf "LEG %s %s: diffs=%d inc_miss=%d cand_miss=%d\n", i, m, nd, imiss, cmiss }
        '
  done
done
echo RV7_SCORING_DONE
grep -c DIFF rv8_report.txt 2>/dev/null || echo "0 diff rows"
awk -F"\t" "{print \$6}" rv8_report.txt 2>/dev/null | sort | uniq -c
echo RV7_DONE
