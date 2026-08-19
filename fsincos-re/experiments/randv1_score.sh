#!/bin/bash
# Standing "reasonable corpus" regression (goal 2026-08-18): randv1 =
# 8M blind random operands (h727_gen.py, seed 0x662662: 60% broad
# normals 2^-65..2^62, 20% binary64-aligned, 10% near-k*pi/2, 5%
# tiny/denormal, 5% C2/specials), captured on the i7 for FCOS+FSIN
# x rn/rd/ru.  Expected (2026-08-19, post-R71): TOTAL 21/48,000,000, all +-1 ulp (register B9: 4
# rows, B10 reduced-route tail: 17 rows).
set -e
cd /root/r59
for mode in rn rd ru; do
  RC=""; [ $mode = rd ] && RC="--rc=rd"; [ $mode = ru ] && RC="--rc=ru"
  ./model_master --batch $RC --fcos-standalone \
      < /root/h491/randv1_inputs.txt > rv_cos_${mode}.txt
  ./model_master --batch $RC --fsin-standalone \
      < /root/h491/randv1_inputs.txt > rv_sin_${mode}.txt
done
python3 - <<'PYEOF'
def norm(l):
    t = l.split()
    return ("C2",) if t[0] == "C2" else tuple(t[1:3])
tot = 0
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw = open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt").read().splitlines()
        mo = open(f"rv_{insn}_{mode}.txt").read().splitlines()
        assert len(hw) == len(mo) == 8000000
        bad = sum(1 for a,b in zip(hw,mo) if norm(a) != norm(b))
        print(f"{insn} {mode}: {bad} / 8000000")
        tot += bad
print("TOTAL:", tot, "/ 48000000  (baseline 21, post-R71)")
PYEOF
rm -f rv_cos_*.txt rv_sin_*.txt
