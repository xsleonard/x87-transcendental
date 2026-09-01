#!/bin/bash
# rv12 promotion blind: seed 0x872D, 4M ops, 8 legs; incumbent =
# R95 source with -DG_R95XSUP=0 (proven output-identical to R93 on
# the 5.09M-op scope corpus, 8 legs, three independent builds) vs
# candidate = R95 default; both ledger ON, scored against fresh hw.
# Epoch probes (33/33) bracket the capture.  PRE-REGISTERED (locked
# 2026-09-01 BEFORE capture, h988/h989 zero-break scorecard):
#   (a) ZERO INC_WINS rows (no leg where incumbent right and
#       candidate wrong) — the hard gate;
#   (b) cand_miss <= inc_miss on every leg;
#   (c) diff rows expected 0-40 (band fresh rate ~4e-7 x fix
#       fraction); CAND_WINS + NEITHER only;
#   (d) probes 33/33 pre+post.
set -e
cd /root/r84
/root/r84/probe_ledger.sh rv12-pre
python3 /root/r59/h733_gen.py 0x872D 4000000 rv12_inputs.txt
wc -l rv12_inputs.txt
gcc -O2 -ffp-contract=off -DG_R95XSUP=0 -o rv12_incumbent /root/r59/fsincos_skylake.c -lm
gcc -O2 -ffp-contract=off -o rv12_candidate /root/r59/fsincos_skylake.c -lm
echo RV12_BUILDS_OK
for insn in cos sin; do
  for mode in rn rd ru rz; do
    ( /root/x87_capture_x86_64 $mode $insn < rv12_inputs.txt \
        > rv12_hw_${insn}_${mode}.txt ) &
  done
  wait
  echo "RV12_CAPTURED $insn"
done
/root/r84/probe_ledger.sh rv12-post
rm -f rv12_report.txt
for insn in cos sin; do
  FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
  for mode in rn rd ru rz; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    [ $mode = rz ] && RC="--rc=rz"
    paste <(nice -n 10 ./rv12_incumbent --batch $RC $FL < rv12_inputs.txt) \
          <(nice -n 10 ./rv12_candidate --batch $RC $FL < rv12_inputs.txt) \
          rv12_hw_${insn}_${mode}.txt rv12_inputs.txt \
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
              print "DIFF\t" i "\t" m "\t" NR-1 "\t" $4 "\t" tag "\t" as "\t" bs "\t" hs >> "rv12_report.txt";
            }
          }
          END { printf "LEG %s %s: diffs=%d inc_miss=%d cand_miss=%d\n", i, m, nd, imiss, cmiss }
        '
  done
done
echo RV12_SCORING_DONE
[ -f rv12_report.txt ] && awk -F"\t" "{print \$6}" rv12_report.txt | sort | uniq -c || echo "0 diff rows"
echo RV12_DONE
