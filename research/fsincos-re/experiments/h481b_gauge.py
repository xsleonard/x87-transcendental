#!/usr/bin/env python3
"""h481b: how much do the known causal bits + cell explain?
2-fold holdout purity of fire ~ (cell, f4_g, f4_b2, rud, +rdisc_b14)
on the 1,086 labeled constructed inputs."""
import json, random
from collections import defaultdict
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5, C6_6,
                                 build_chain, mul_round)
MODES = ("rn", "rd", "ru")
E2M = -66

def sig(line):
    t = line.split()
    return f"{int(t[2],16):016x}" if t[0] == "OK" else "BAD"

rows = {}
l479 = json.load(open("h479_locked.json"))
order479 = []
for p in l479["pairs"]: order479 += [p["g0"], p["g1"]]
order479 += l479["controls"]
s479 = {m: open(f"h479_cos_{m}_status.txt").read().splitlines() for m in MODES}
for i, e in enumerate(order479):
    hw = [sig(s479[m][i]) for m in MODES]
    rows[e["m"]] = 1 if hw == e["fired"] else 0
l480 = json.load(open("h480_locked.json"))
s480 = {m: open(f"cos_{m}_status.txt").read().splitlines() for m in MODES}
feats480 = {}
for i, e in enumerate(l480["inputs"]):
    hw = [sig(s480[m][i]) for m in MODES]
    rows[e["m"]] = 1 if hw == e["fired"] else 0
    feats480[e["m"]] = (tuple(e["cell"]), e["feats"])

def featurize(mhex):
    if mhex in feats480:
        cell, f = feats480[mhex]
        return cell, f["f4_g"], f["f4_b2"], (f["rdisc16"] >> 14) & 1
    m = int(mhex, 16)
    mag = (0, E2M, m)
    square = mul_round(mag, mag, 67, "chop")
    fourth = mul_round(square, square, 67, "chop")
    negative = build_chain(fourth, C6_5, C6_3, C6_1, 67, 64, "rn", False, False, False)
    positive = build_chain(fourth, C6_6, C6_4, C6_2, 67, 64, "rn", False, False, False)
    left = mul_round(square, negative, 67, "chop")
    right = mul_round(fourth, positive, 67, "chop")
    f4_full = square[2] * square[2]
    s4 = f4_full.bit_length() - 67
    rprod = fourth[2] * positive[2]
    sR = rprod.bit_length() - 67
    rdisc = rprod & ((1 << sR) - 1)
    rud = rdisc >> (sR - 1)
    b14 = (rdisc >> (sR - 2)) & 1
    lprod = square[2] * negative[2]
    low3 = square[2] & 7
    dist = abs(left[1] - right[1])
    M = 0  # cell k: recompute quickly
    payload = low3 + 8 - dist
    scale = min(left[1], right[1])
    if payload and left[1] - 8 < scale: scale = left[1] - 8
    M = (left[2] << (left[1]-scale)) + (payload << (left[1]-8-scale)) - (right[2] << (right[1]-scale))
    k = M.bit_length() - 67
    return (dist, low3, k, rud), (f4_full >> (s4-1)) & 1, (f4_full >> (s4-2)) & 1, b14

data = [(rows[m], featurize(m)) for m in sorted(rows)]
rnd = random.Random(4812)
for keyname, keyfn in (
    ("cell only", lambda c,g,b2,b14: c),
    ("cell+f4_g", lambda c,g,b2,b14: (c,g)),
    ("cell+f4_g+f4_b2", lambda c,g,b2,b14: (c,g,b2)),
    ("cell+f4_g+f4_b2+rdisc_b14", lambda c,g,b2,b14: (c,g,b2,b14)),
):
    accs = []
    for trial in range(20):
        idx = list(range(len(data)))
        rnd.shuffle(idx)
        half = len(idx)//2
        train = [data[i] for i in idx[:half]]
        test = [data[i] for i in idx[half:]]
        rule = defaultdict(lambda: [0,0])
        for o, f in train: rule[keyfn(*f)][o] += 1
        hit = tot = 0
        for o, f in test:
            kk = keyfn(*f)
            if kk in rule:
                pred = 1 if rule[kk][1] > rule[kk][0] else 0
                hit += pred == o; tot += 1
        accs.append(hit/tot if tot else 0)
    print(f"{keyname:28s} holdout acc {sum(accs)/len(accs):.3f} "
          f"(n test buckets seen only)")
