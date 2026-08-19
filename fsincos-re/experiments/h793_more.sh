#!/bin/bash
set -e
cd /root/r59
for SEED in 0x789002 0x789003; do
  CK=ck15; [ $SEED = 0x789003 ] && CK=ck16
  python3 h733_gen.py $SEED 8000000 ${CK}_inputs.txt
  for insn in cos sin; do
    for mode in rn rd ru; do
      RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
      FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
      /root/x87_capture $insn $mode < ${CK}_inputs.txt > ${CK}hw_${insn}_${mode}.txt
      ./model_h780 --batch $RC $FL < ${CK}_inputs.txt > ${CK}b_${insn}_${mode}.txt
      ./model_r72  --batch $RC $FL < ${CK}_inputs.txt > ${CK}g_${insn}_${mode}.txt
    done
  done
  CK=$CK python3 - <<PYEOF
import os
CK = os.environ["CK"]
def norm(l):
    t = l.split()
    return ("C2",) if t[0]=="C2" else tuple(t[1:3])
inp = open(CK+"_inputs.txt").read().splitlines()
base = set(); new = set(); m = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open("%shw_%s_%s.txt"%(CK,insn,mode)).read().splitlines()
        b  = open("%sb_%s_%s.txt"%(CK,insn,mode)).read().splitlines()
        g  = open("%sg_%s_%s.txt"%(CK,insn,mode)).read().splitlines()
        for i,(a,x,y) in enumerate(zip(hw,b,g)):
            na = norm(a)
            if norm(x)!=na: base.add((insn,mode,i)); m[(insn,mode,i)]=(inp[i],"/".join(na))
            if norm(y)!=na: new.add((insn,mode,i)); m[(insn,mode,i)]=(inp[i],"/".join(na))
print("BLIND %s: R71 %d R72 %d FIXED %d BROKEN %d" % (CK, len(base), len(new), len(base-new), len(new-base)))
f = open(CK+"_fixed.txt","w")
for k in sorted(base-new): f.write("%s %s %s  %s hw=%s\n" % (k[0],k[1],k[2],m[k][0],m[k][1]))
f.close()
f = open(CK+"_broken.txt","w")
for k in sorted(new-base): f.write("%s %s %s  %s hw=%s\n" % (k[0],k[1],k[2],m[k][0],m[k][1]))
f.close()
PYEOF
  rm -f ${CK}b_*.txt ${CK}g_*.txt ${CK}hw_*.txt ${CK}_inputs.txt
done
echo H793_DONE
