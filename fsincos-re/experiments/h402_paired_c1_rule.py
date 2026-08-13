#!/usr/bin/env python3
"""Paired FSINCOS C1 derivation test.

Hypotheses, per input/mode (using Round-54 model lane outputs as exact
result values, valid because results have zero misses on these corpora):
  H_cos: C1 = [cos result != cos toward-zero bound]
  H_sin: C1 = [sin result != sin toward-zero bound]
  H_or / H_and / H_xor of the two lane flags.
Toward-zero bound of a lane = RD output if the result is positive else RU
output.  Hardware C1 = SW bit 9 of the paired capture.
"""
import sys

def load_hw(path):
    out = []
    for l in open(path):
        t = l.split()
        if t[0] != "OK":
            out.append(None)
        else:
            out.append((t[1], t[2], t[3], t[4], int(t[6], 16)))
    return out

def load_model(path):
    out = []
    for l in open(path):
        t = l.split()
        out.append(None if t[0] != "OK" else (t[1], t[2], t[3], t[4]))
    return out

def val_neg(se):
    return (int(se, 16) >> 15) & 1

def inc_flag(res, rd, ru):
    """1 if res is the magnitude-incremented endpoint of [toward, away]."""
    toward = ru if val_neg(res[0]) else rd
    return 0 if res == toward else 1

corpora = [
    ("h347", "captures/skylake-trig-h347/fsincos_{m}_status.txt", "out54/pair54_h347_{m}.txt"),
    ("h349", "captures/skylake-trig-h349/fsincos_{m}_status.txt", "out54/pair54_h349_{m}.txt"),
    ("sweep", "fresh/sweep_fsincos_{m}.txt", "out54/pair54_sweep_{m}.txt"),
    ("dense", "fresh/dense_fsincos_{m}.txt", "out54/pair54_dense_{m}.txt"),
]
grand = {}
for name, hwpat, mpat in corpora:
    hw = {m: load_hw(hwpat.format(m=m)) for m in ("rn", "rd", "ru")}
    mo = {m: load_model(mpat.format(m=m)) for m in ("rn", "rd", "ru")}
    n = len(hw["rn"])
    miss = {h: 0 for h in ("H_cos", "H_sin", "H_or", "H_and", "H_xor")}
    checked = 0
    examples = []
    for i in range(n):
        if any(hw[m][i] is None or mo[m][i] is None for m in ("rn", "rd", "ru")):
            continue
        sin_rd, sin_ru = mo["rd"][i][0:2], mo["ru"][i][0:2]
        cos_rd, cos_ru = mo["rd"][i][2:4], mo["ru"][i][2:4]
        for m in ("rn", "rd", "ru"):
            hw_c1 = (hw[m][i][4] >> 9) & 1
            s = inc_flag(mo[m][i][0:2], sin_rd, sin_ru)
            c = inc_flag(mo[m][i][2:4], cos_rd, cos_ru)
            preds = {"H_cos": c, "H_sin": s, "H_or": s | c,
                     "H_and": s & c, "H_xor": s ^ c}
            checked += 1
            for h, p in preds.items():
                if p != hw_c1:
                    miss[h] += 1
                    if h == "H_cos" and len(examples) < 8:
                        examples.append((i, m, "hwC1", hw_c1, "sin_inc", s, "cos_inc", c))
    print(name, "checked", checked, {h: miss[h] for h in miss})
    for e in examples:
        print("   H_cos miss:", e)
    for h in miss:
        grand[h] = grand.get(h, 0) + miss[h]
print("GRAND:", grand)
