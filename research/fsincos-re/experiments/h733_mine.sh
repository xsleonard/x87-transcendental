#!/bin/bash
# h733: B10 densification miner.  5 chunks x 8M large-|x| operands,
# capture FCOS+FSIN x rn/rd/ru, score vs model_di (bare = shipped),
# append votes to h733_votes.txt, delete bulk.  ~230 votes expected.
set -e
cd /root/r59
: > h733_votes.txt
for ck in 1 2 3 4 5; do
  python3 h733_gen.py $((0x733000 + ck)) 8000000 ck_inputs.txt
  for insn in cos sin; do
    for mode in rn rd ru; do
      /root/x87_capture $insn $mode < ck_inputs.txt > ck_${insn}_${mode}_hw.txt
      RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
      FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
      ./model_di --batch $RC $FL < ck_inputs.txt > ck_${insn}_${mode}_mo.txt
    done
  done
  python3 - "$ck" <<'PYEOF'
import sys
ck = sys.argv[1]
def norm(l):
    t = l.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
inp = open("ck_inputs.txt").read().splitlines()
votes = 0
with open("h733_votes.txt", "a") as f:
    for insn in ("cos","sin"):
        for mode in ("rn","rd","ru"):
            hw = open(f"ck_{insn}_{mode}_hw.txt").read().splitlines()
            mo = open(f"ck_{insn}_{mode}_mo.txt").read().splitlines()
            assert len(hw) == len(mo) == len(inp), (insn, mode)
            for i,(a,b) in enumerate(zip(hw,mo)):
                if norm(a) != norm(b):
                    votes += 1
                    f.write("ck%s %s %s %s hw=%s mo=%s\n" %
                            (ck, insn, mode, inp[i],
                             "/".join(norm(a)), "/".join(norm(b))))
print("chunk", ck, "votes", votes)
PYEOF
  rm -f ck_inputs.txt ck_cos_* ck_sin_*
  echo "CHUNK_${ck}_DONE"
done
wc -l h733_votes.txt
echo H733_ALLDONE
