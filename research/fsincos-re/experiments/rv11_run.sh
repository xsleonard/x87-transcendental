#!/bin/bash
# rv11 promotion blind: seed 0x872C, 4M ops, 8 legs; incumbent =
# R93 source with -DG_R93OVR=0 (verified output-identical to R92 on
# 34,460 ops x 4 modes) vs candidate = R93 default; both ledger ON,
# scored against fresh hw.  Epoch probes (33/33) bracket the
# capture.  PRE-REGISTERED (before capture): expect 0-3 diff rows;
# PASS iff (a) no CAND-wrong diff row outside the h956b mixed
# tuples, (b) CAND_WINS >= INC_WINS, (c) cand_miss <= inc_miss per
# leg, (d) probes 33/33 pre+post.
set -e
cd /root/r84
/root/r84/probe_ledger.sh rv11-pre
python3 /root/r59/h733_gen.py 0x872C 4000000 rv11_inputs.txt
wc -l rv11_inputs.txt
gcc -O2 -ffp-contract=off -DG_R93OVR=0 -o rv11_incumbent /root/r59/fsincos_skylake.c -lm
gcc -O2 -ffp-contract=off -o rv11_candidate /root/r59/fsincos_skylake.c -lm
echo RV11_BUILDS_OK
for insn in cos sin; do
  for mode in rn rd ru rz; do
    ( /root/x87_capture_x86_64 $mode $insn < rv11_inputs.txt \
        > rv11_hw_${insn}_${mode}.txt ) &
  done
  wait
  echo "RV11_CAPTURED $insn"
done
/root/r84/probe_ledger.sh rv11-post
rm -f rv11_report.txt
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    paste <(nice -n 10 ./rv11_incumbent --batch $RC $FL < rv11_inputs.txt) \
          <(nice -n 10 ./rv11_candidate --batch $RC $FL < rv11_inputs.txt) \
          rv11_hw_${insn}_${mode}.txt rv11_inputs.txt \
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
              print "DIFF\t" i "\t" m "\t" NR-1 "\t" $4 "\t" tag "\t" as "\t" bs "\t" hs >> "rv11_report.txt";
            }
          }
          END { printf "LEG %s %s: diffs=%d inc_miss=%d cand_miss=%d\n", i, m, nd, imiss, cmiss }
        '
  done
done
echo RV11_SCORING_DONE
[ -f rv11_report.txt ] && awk -F"\t" "{print \$6}" rv11_report.txt | sort | uniq -c || echo "0 diff rows"
echo RV11_DONE
