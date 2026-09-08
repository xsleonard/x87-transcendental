#!/bin/bash
set -e
cd /root/r59
# GATE 1: randv1 with same-run baseline classification
for insn in cos sin; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    nice -n 10 ./model_h780 --batch $RC $FL < /root/h491/randv1_inputs.txt > cb_${insn}_${mode}.txt
    nice -n 10 ./model_r72 --batch $RC $FL < /root/h491/randv1_inputs.txt > cg_${insn}_${mode}.txt
  done
done
python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
known = set(); new = set()
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt").read().splitlines()
        b = open(f"cb_{insn}_{mode}.txt").read().splitlines()
        g = open(f"cg_{insn}_{mode}.txt").read().splitlines()
        assert len(hw) == len(b) == len(g) == 8000000
        for i,(a,x,y) in enumerate(zip(hw,b,g)):
            na = norm(a)
            if norm(x) != na: known.add((insn,mode,i))
            if norm(y) != na: new.add((insn,mode,i))
print("GATE1 randv1: r71-baseline", len(known), "r72", len(new),
      "FIXED", len(known-new), "BROKEN", len(new-known))
for k in sorted(new-known): print("  BROKEN", k)
for k in sorted(known-new): print("  FIXED", k)
PYEOF
rm -f cb_*.txt cg_*.txt
# GATE 2: comb regression (must equal shipped exactly)
for corp in comb7 comb9 comb11 comb12 comb13 comb14 comb15 comb16 comb17 comb18; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    nice -n 10 ./model_r72 --batch $RC --fcos-standalone < /root/h491/${corp}_inputs.txt > cc_${corp}_${mode}.txt
  done
done
python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
exp = dict(comb7=1,comb9=11,comb11=0,comb12=0,comb13=7,comb14=0,comb15=5,comb16=3,comb17=1,comb18=2)
tot = 0
for corp in exp:
    c = 0
    for mode in ("rn","rd","ru"):
        hw = open(f"/root/h491/{corp}_{mode}_status.txt").read().splitlines()
        mo = open(f"cc_{corp}_{mode}.txt").read().splitlines()
        assert len(hw) == len(mo)
        c += sum(1 for a,b in zip(hw,mo) if norm(a) != norm(b))
    flag = "OK" if c == exp[corp] else ("BETTER" if c < exp[corp] else "REGRESS")
    print(f"GATE2 {corp}: {c} (shipped {exp[corp]}) {flag}")
    tot += c
print("GATE2 comb TOTAL:", tot, "(shipped 30)")
PYEOF
rm -f cc_*.txt
# GATE 3: hostv1
for insn in cos sin; do
  for mode in rn rd ru; do
    RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
    FL="--fcos-standalone"; [ $insn = sin ] && FL="--fsin-standalone"
    nice -n 10 ./model_r72 --batch $RC $FL < /root/h491/hostv1_inputs.txt > ch_${insn}_${mode}.txt
  done
done
python3 - <<PYEOF
def norm(l):
    t = l.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
tot = 0
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open(f"/root/h491/hostv1_{insn}_{mode}_hw_status.txt").read().splitlines()
        mo = open(f"ch_{insn}_{mode}.txt").read().splitlines()
        assert len(hw) == len(mo)
        tot += sum(1 for a,b in zip(hw,mo) if norm(a) != norm(b))
print("GATE3 hostv1 TOTAL:", tot, "(shipped 4)")
PYEOF
rm -f ch_*.txt
echo R72_GATES_DONE
