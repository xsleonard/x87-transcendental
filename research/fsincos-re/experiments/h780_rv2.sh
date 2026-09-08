#!/bin/bash
set -e
cd /root/r59
test -s rv2_inputs.txt
wc -l rv2_inputs.txt
for insn in cos sin; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    /root/x87_capture $insn $mode < rv2_inputs.txt > rv2hw_${insn}_${mode}.txt
    ./model_h780 --batch $RC $FL < rv2_inputs.txt > rv2mo_${insn}_${mode}.txt
    echo "done $insn $mode $(date +%H:%M:%S)"
  done
done
python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t[0]=="C2" else tuple(t[1:3])
inp = open("rv2_inputs.txt").read().splitlines()
nv = 0
with open("h780_votes.txt","w") as f:
    for insn in ("cos","sin"):
        for mode in ("rn","rd","ru"):
            hw = open("rv2hw_%s_%s.txt"%(insn,mode)).read().splitlines()
            mo = open("rv2mo_%s_%s.txt"%(insn,mode)).read().splitlines()
            assert len(hw)==len(mo)==len(inp), (insn,mode)
            for i,(a,b) in enumerate(zip(hw,mo)):
                if norm(a)!=norm(b):
                    nv += 1
                    f.write("rv2 %s %s %s hw=%s mo=%s\n" % (insn, mode, inp[i], "/".join(norm(a)), "/".join(norm(b))))
print("h780 rv2 total miss lines:", nv)
PYEOF
echo H780_DONE
