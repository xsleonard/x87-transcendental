#!/usr/bin/env python3
# h949c: SEE the llow shape inside the biggest mixed tuples, and
# test exact-arithmetic gate candidates as GLOBAL predicates.
# TRAIN only (seed < 96411).
import pickle, sys
from collections import Counter, defaultdict

table = pickle.load(open("h949_features.pkl", "rb"))
SPLIT = 96411
train = [r for r in table if r["seed"] < SPLIT]

def geo(r):
    d = r["tc_dist"]
    ls, le2, lsig = r["tc_left"]; rs, re2, rsig = r["tc_right"]
    mask = (1 << d) - 1
    rlow = rsig & mask
    grl = (rlow if rlow else (1 << d)) if ls != rs else ((1 << d) - rlow)
    g = 64 if grl > 64 else int(grl)
    llow = lsig & mask
    me2 = r["tc_mul"][1]
    return d, me2, ls, rs, lsig, rsig, mask, rlow, llow, g, r["tc_payload"]

# --- 1. llow tables for the biggest mixed tuples ---
bytup = defaultdict(list)
for r in train:
    d, me2, ls, rs, lsig, rsig, mask, rlow, llow, g, pay = geo(r)
    bytup[((d, me2), g, pay)].append((llow, rlow, ls != rs, r["hwlab"]))
mixed = [(len(v), k) for k, v in bytup.items()
         if len(set(x[3] for x in v)) > 1]
mixed.sort(reverse=True)
for n, k in mixed[:4]:
    v = bytup[k]
    print("=== tuple", k, "n=%d" % n, "sub=%s" % v[0][2])
    tab = defaultdict(Counter)
    for llow, rlow, sub, y in v:
        tab[llow][y] += 1
    ks = sorted(tab)
    line = []
    for llow in ks:
        c = tab[llow]
        tag = "F" if c["FIRE"] and not c["DECL"] else (
              "D" if c["DECL"] and not c["FIRE"] else "X")
        line.append("%d:%s%d" % (llow, tag, sum(c.values())))
    print("  ", " ".join(line))

# --- 2. exact-arithmetic global predicates ---
# base = lsig -/+ (rsig >> d); exact tail vs granule 2^(d+k):
# sub: borrow beyond window k iff ((base & (2^k-1)) << d) - rlow < 0
# add: carry beyond window k iff ((base & (2^k-1)) << d) + rlow >= 2^(d+k)
def evalpred(name, fn):
    err = Counter(); n = 0
    for r in train:
        p = fn(r)
        if p is None: continue
        n += 1
        if (p and r["hwlab"] != "FIRE") or (not p and r["hwlab"] != "DECL"):
            err[r["hwlab"]] += 1
    print("%-28s n=%d err=%d (missFIRE=%d missDECL=%d)"
          % (name, n, sum(err.values()), err["DECL"], err["FIRE"]))

def mk_cross(k):
    def fn(r):
        d, me2, ls, rs, lsig, rsig, mask, rlow, llow, g, pay = geo(r)
        base = lsig - (rsig >> d) if ls != rs else lsig + (rsig >> d)
        w = (base & ((1 << k) - 1)) << d
        if ls != rs: return w - rlow < 0 if rlow else False
        else: return w + rlow >= (1 << (d + k))
    return fn
for k in range(0, 9):
    evalpred("tailcross k=%d" % k, mk_cross(k))

# reference: L_D's own op-level train error (join ldlab from corpus)
ld = {}
f = open("h948_gate_corpus.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 6: ld[(t[0], t[2])] = t[4]
lde = sum(1 for r in train
          if ld.get((r["insn"], r["op"]), "").upper() != r["hwlab"])
print("L_D op-level train errors:", lde, "/", len(train))
