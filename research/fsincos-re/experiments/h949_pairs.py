#!/usr/bin/env python3
# h949d: matched-coordinate collision pairs.  TRAIN ops sharing
# (cell, g, pay, llow, rlow, subflag, low3, ud, rsh) with OPPOSITE
# hw labels.  For each pair, diff every dumped field; aggregate
# which fields differ and, for wide words, which BIT positions
# differ most (relative to the window).  The discriminating state
# must live in what differs.
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
SPLIT = 96411
train = [r for r in table if r["seed"] < SPLIT]

LOOSE = len(sys.argv) > 1 and sys.argv[1] == "loose"
def key(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    k = (d, r["tc_mul"][1], ls != rs, lsig & mask, rsig & mask,
         r["tc_payload"])
    if not LOOSE:
        k += (r["tc_low3"], r["tc_ud"], r["tc_rsh"])
    return k

groups = defaultdict(list)
for r in train: groups[key(r)].append(r)
pairs = []
for k, v in groups.items():
    fires = [r for r in v if r["hwlab"] == "FIRE"]
    decls = [r for r in v if r["hwlab"] == "DECL"]
    if fires and decls: pairs.append((k, fires, decls))
print("collision groups:", len(pairs), "ops involved:",
      sum(len(f) + len(d) for _, f, d in pairs))

allk = set()
for r in train[:2000]: allk.update(r)
WIDE = sorted(k for k in allk if any(
    isinstance(r.get(k), tuple) for r in train[:2000]))
SCAL = sorted(k for k in allk if k != "seed" and any(
    isinstance(r.get(k), int) for r in train[:2000]))
Z = (0, 0, 0)

# aggregate: for each scalar field, how often F/D pair differs; for
# wide words, which bit positions differ (position relative to LSB)
sc_diff = Counter()
bit_diff = defaultdict(Counter)
npair = 0
for k, fires, decls in pairs:
    for rf in fires[:2]:
        for rd in decls[:2]:
            npair += 1
            for f_ in SCAL:
                if rf.get(f_) != rd.get(f_): sc_diff[f_] += 1
            for w in WIDE:
                a = rf.get(w, Z)[2]; b = rd.get(w, Z)[2]
                x = a ^ b
                for bit in range(128):
                    if (x >> bit) & 1: bit_diff[w][bit] += 1
print("compared pairs:", npair)
print("\n--- scalar fields differing (count/%d) ---" % npair)
for f_, c in sc_diff.most_common(25):
    print("  %-14s %d" % (f_, c))
print("\n--- wide-word LOWEST differing bit (histogram) ---")
for w in WIDE:
    lo = Counter()
    for k, fires, decls in pairs:
        for rf in fires[:2]:
            for rd in decls[:2]:
                x = rf.get(w, Z)[2] ^ rd.get(w, Z)[2]
                if x: lo[(x & -x).bit_length() - 1] += 1
    if lo:
        print("  %-10s %s" % (w, sorted(lo.items())[:10]))

# print two full example pairs
import json
def show(r):
    out = {}
    for k2 in sorted(r):
        v = r[k2]
        if isinstance(v, tuple): out[k2] = "%d:%d:%032x" % v
        elif isinstance(v, int) and v > 1 << 20: out[k2] = "%x" % v
        else: out[k2] = v
    return out
for k, fires, decls in pairs[:2]:
    print("\n=== PAIR at key", k)
    a, b = show(fires[0]), show(decls[0])
    for k2 in sorted(set(a) | set(b)):
        av, bv = a.get(k2), b.get(k2)
        mark = "   " if av == bv else ">>>"
        print(" %s %-12s F=%s  D=%s" % (mark, k2, av, bv))
