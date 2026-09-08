#!/bin/bash
# rv9 promotion blind (pre-reg 44df5e8): seed 0x872A, 4M ops,
# 8 legs; incumbent (/root/r59 R90 record, default flags) vs
# candidate (repo 269fc3a source + -DG_Q67SCOPE=1), both ledger
# ON, scored against fresh hw.  Epoch probes (36/36) bracket the
# capture; the h914 chain is complete and the capture host free.
set -e
cd /root/r84
/root/r84/probe_ledger.sh rv9-pre
python3 /root/r59/h733_gen.py 0x872A 4000000 rv9_inputs.txt
wc -l rv9_inputs.txt
gcc -O2 -I/root/r59 -o rv9_incumbent /root/r59/fsincos_skylake.c -lm
gcc -O2 -o rv9_candidate h924_src2.c -lm -DG_Q67SCOPE=1
echo RV9_BUILDS_OK
for insn in cos sin; do
  for mode in rn rd ru rz; do
    ( /root/x87_capture_x86_64 $mode $insn < rv9_inputs.txt \
        > rv9_hw_${insn}_${mode}.txt ) &
  done
  wait
  echo "RV9_CAPTURED $insn"
done
/root/r84/probe_ledger.sh rv9-post
rm -f rv9_report.txt
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    paste <(nice -n 10 ./rv9_incumbent --batch $RC $FL < rv9_inputs.txt) \
          <(nice -n 10 ./rv9_candidate --batch $RC $FL < rv9_inputs.txt) \
          rv9_hw_${insn}_${mode}.txt rv9_inputs.txt \
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
              print "DIFF\t" i "\t" m "\t" NR-1 "\t" $4 "\t" tag "\t" as "\t" bs "\t" hs >> "rv9_report.txt";
            }
          }
          END { printf "LEG %s %s: diffs=%d inc_miss=%d cand_miss=%d\n", i, m, nd, imiss, cmiss }
        '
  done
done
echo RV9_SCORING_DONE
grep -c DIFF rv9_report.txt 2>/dev/null || echo "0 diff rows"
awk -F"\t" "{print \$6}" rv9_report.txt 2>/dev/null | sort | uniq -c
echo RV9_DONE
