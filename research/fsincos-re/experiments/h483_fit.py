#!/usr/bin/env python3
"""h483: exact fits over (t4, rf, rdisc) on all 1,310 labeled rows.

h482 causal set: f4 tail (>=3 bits, value-like), rdisc_b14 (pooled
z=+3.1), rf_b0 negative (possibly rdisc-mediated).  Candidate exact
forms of the rs-increment gate, all functions of the right product's
generation arithmetic:
  R1: RN of the true product:  fire <=> rdisc*2^s4 + t4*rf >= half
  R1s: strict >
  Rg: gridded threshold: fire <=> D_ext >= 2^(WR-1) * (1 +- 2^-a)
  Rw: fire <=> top-w bits of D_ext all ones / any set (window forms)
Also: pooled full-vector discordance and holdout gauge with the new
bits over all labeled rows.
"""
import json
from collections import Counter, defaultdict
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
import random
MODES = ("rn", "rd", "ru")
E2M = -66

def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"

rows = {}
def load(lockfile, prefix):
    d = json.load(open(lockfile))
    st = {m: open(f"{prefix}cos_{m}_status.txt").read().splitlines()
          for m in MODES}
    if "inputs" in d:
        order = d["inputs"]
    else:
        order = []
        for p in d["pairs"]:
            order += [p["g0"], p["g1"]]
        order += d["controls"]
    for i, e in enumerate(order):
        hw = [sig(st[m][i]) for m in MODES]
        rows[e["m"]] = 1 if hw == e["fired"] else \
            (0 if hw == e["clean"] else 2)

load("h479_locked.json", "h479_")
# note: h480's status files were the plain cos_* until h482 overwrote
# them; h480 outcomes come from its TSV instead
for line in open("h480_outcomes.tsv").read().splitlines()[1:]:
    f = line.split("\t")
    rows[f[0]] = {"CLEAN": 0, "FIRE": 1}.get(f[6], 2)
load("h482_locked.json", "")
print(f"labeled rows: {len(rows)}, fires: "
      f"{sum(1 for v in rows.values() if v==1)}, bad: "
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
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    t4 = f4_full & ((1 << s4) - 1)
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale:
        scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) \
        - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    cell = (dist, low3, k, rdisc >> (sR-1))
    D = (rdisc << s4) + t4 * positive[2]
    W = sR + s4
    bits = (f4_full >> (s4-1) & 1, f4_full >> (s4-2) & 1,
            f4_full >> (s4-3) & 1, rdisc >> (sR-2) & 1,
            positive[2] & 1)
    return cell, D, W, bits, payload

data = []
for mhex, o in sorted(rows.items()):
    if o == 2:
        continue
    cell, D, W, bits, payload = state(mhex)
    data.append((o, cell, D, W, bits, payload))
n = len(data)
print(f"scored: {n}")

def rep(name, fn):
    exc = sum(1 for d in data if fn(d) != d[0])
    fp = sum(1 for d in data if fn(d) == 1 and d[0] == 0)
    print(f"  {name:34s} exceptions={exc:4d} (fp {fp}, "
          f"fn {exc-fp})")

print("\n=== exact fits ===")
rep("R1: D_ext >= half (RN true prod)",
    lambda d: 1 if d[2] >= 1 << (d[3]-1) else 0)
rep("R1s: strict", lambda d: 1 if d[2] > 1 << (d[3]-1) else 0)
for a in (2, 3, 4):
    rep(f"D >= half*(1-2^-{a})",
        lambda d, a=a: 1 if d[2] >= (1 << (d[3]-1)) - (1 << (d[3]-1-a))
        else 0)
    rep(f"D >= half*(1+2^-{a})",
        lambda d, a=a: 1 if d[2] >= (1 << (d[3]-1)) + (1 << (d[3]-1-a))
        else 0)
for w in (2, 3, 4, 6):
    rep(f"top-{w} bits of D all ones",
        lambda d, w=w: 1 if (d[2] >> (d[3]-w)) == (1 << w) - 1 else 0)

print("\n=== pooled full-vector discordance (all rows) ===")
groups = defaultdict(Counter)
for o, cell, D, W, bits, payload in data:
    if payload in (0, 8):
        continue
    groups[(cell, bits)][o] += 1
mixed = {k: c for k, c in groups.items() if c[0] and c[1]}
mrows = sum(sum(c.values()) for c in mixed.values())
trows = sum(sum(c.values()) for c in groups.values())
print(f"  groups: {len(groups)}, mixed: {len(mixed)}, rows in "
      f"mixed: {mrows}/{trows}")

print("\n=== holdout gauge with new bits ===")
rnd = random.Random(483)
accs = []
for trial in range(20):
    idx = list(range(n))
    rnd.shuffle(idx)
    train = [data[i] for i in idx[:n//2]]
    test = [data[i] for i in idx[n//2:]]
    rule = defaultdict(lambda: [0, 0])
    for o, cell, D, W, bits, payload in train:
        rule[(cell, bits)][o] += 1
    hit = tot = 0
    for o, cell, D, W, bits, payload in test:
        kk = (cell, bits)
        if kk in rule:
            pred = 1 if rule[kk][1] > rule[kk][0] else 0
            hit += pred == o
            tot += 1
    accs.append(hit / tot if tot else 0)
print(f"  cell+5bits holdout acc {sum(accs)/len(accs):.3f}")
