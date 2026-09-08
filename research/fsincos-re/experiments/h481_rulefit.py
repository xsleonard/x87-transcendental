#!/usr/bin/env python3
"""h481: fit the extended-tail subtract rule on constructed outcomes.

Mechanism under test: the terminal subtract consumes the two
reconstruction products with extra precision below their chopped ulps.
Right tail beta_R lowers the magnitude (down-fires near all-zeros);
left tail beta_L raises it (up-fires near all-ones).  At an exact tie:
  hardware = R-1  <=>  beta_R > beta_L        (parameter-free form)
Extended tails, exactly computable per input:
  D_extR = rdisc * 2^s4 + t4 * rf   (width WR = sR + s4)
  D_extL = ldisc * 2^s2 + t2 * lf   (width WL = sL + s2)
where t4 = fourth power's below-chop tail (source of the causal
f4_g/f4_b2 bits), t2 = square's below-chop tail (from m^2).
Grids: full-precision compare; window-truncated compares; right-only
windows/thresholds; rdisc-only controls.

Data: all h479+h480 constructed inputs with hardware outcomes
(deduplicated).  Any near-exact rule must be validated on a FRESH
batch before being believed.
"""
import json
from collections import Counter, defaultdict
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
MODES = ("rn", "rd", "ru")
E2M = -66

def hw_results(prefix):
    return {m: open(f"{prefix}cos_{m}_status.txt").read().splitlines()
            for m in MODES}

def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"

rows = {}
l479 = json.load(open("h479_locked.json"))
order479 = []
for p in l479["pairs"]:
    order479 += [p["g0"], p["g1"]]
order479 += l479["controls"]
s479 = hw_results("h479_")
for i, e in enumerate(order479):
    hw = tuple(sig(s479[m][i]) for m in MODES)
    if list(hw) == e["clean"]:
        o = 0
    elif list(hw) == e["fired"]:
        o = 1
    else:
        o = 2
    rows[e["m"]] = o
l480 = json.load(open("h480_locked.json"))
s480 = hw_results("")
for i, e in enumerate(l480["inputs"]):
    hw = tuple(sig(s480[m][i]) for m in MODES)
    if list(hw) == e["clean"]:
        o = 0
    elif list(hw) == e["fired"]:
        o = 1
    else:
        o = 2
    rows[e["m"]] = o
print(f"labeled inputs: {len(rows)}, fires: "
      f"{sum(1 for v in rows.values() if v==1)}, other: "
      f"{sum(1 for v in rows.values() if v==2)}")

def state(mhex):
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn",
                           False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn",
                           False, False, False)
    sq_full = m * m
    s2 = max(sq_full.bit_length() - 67, 0)
    t2 = sq_full & ((1 << s2) - 1)
    f4_full = square[2] * square[2]
    s4 = max(f4_full.bit_length() - 67, 0)
    t4 = f4_full & ((1 << s4) - 1)
    lprod = square[2] * negative[2]
    sL = max(lprod.bit_length() - 67, 0)
    ldisc = lprod & ((1 << sL) - 1)
    rprod = fourth[2] * positive[2]
    sR = max(rprod.bit_length() - 67, 0)
    rdisc = rprod & ((1 << sR) - 1)
    D_R = (rdisc << s4) + t4 * positive[2]
    W_R = sR + s4
    D_L = (ldisc << s2) + t2 * negative[2]
    W_L = sL + s2
    return D_R, W_R, D_L, W_L, rdisc, sR

data = []
for mhex, o in sorted(rows.items()):
    if o == 2:
        continue
    data.append((o, *state(mhex)))
print(f"scored rows: {len(data)}")

def report(name, fn):
    exc = sum(1 for d in data if fn(d) != d[0])
    fp = sum(1 for d in data if fn(d) and not d[0])
    fn_ = sum(1 for d in data if not fn(d) and d[0])
    print(f"  {name:34s} exceptions={exc:4d}  (fp {fp}, fn {fn_})")
    return exc

print("\n=== parameter-free and gridded rules ===")
report("beta_R > beta_L (full precision)",
       lambda d: 1 if d[1] << d[4] > d[3] << d[2] else 0)
report("beta_R > 0 (control)", lambda d: 1 if d[1] else 0)
report("rdisc-only: rud", lambda d: 1 if d[5] >= (1 << (d[6]-1)) else 0)
for wr in (1, 2, 3, 4, 6, 8, 12):
    report(f"right window {wr} nonzero",
           lambda d, wr=wr: 1 if (d[1] >> max(d[2]-wr, 0)) else 0)
for wr in (2, 4, 6, 8, 12, 16, 24):
    report(f"win{wr}(beta_R) > win{wr}(beta_L)",
           lambda d, wr=wr: 1 if (d[1] >> max(d[2]-wr, 0))
           > (d[3] >> max(d[4]-wr, 0)) else 0)
for a in (1, 2, 3, 4):
    report(f"beta_R > beta_L*2^{a}",
           lambda d, a=a: 1 if (d[1] << d[4]) > (d[3] << d[2]) << a
           else 0)
    report(f"beta_R*2^{a} > beta_L",
           lambda d, a=a: 1 if (d[1] << d[4]) << a > (d[3] << d[2])
           else 0)
