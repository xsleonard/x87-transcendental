#!/usr/bin/env python3
# h964: the R94 band-arm fit + blind holdout, R93-method.
# Table = strata (act, sum8, cell, g) with C_train >= 3, ZERO
# invisible-AGREE legs in the FULL population (h963), and zero
# visible legs (no gate interference).  Direction = train majority
# delta.  PRE-REGISTERED BAR (set before this script ran): holdout
# band legs in table strata fixed >= 90%; predicted collateral 0 by
# construction; net >= +100 legs.
import pickle, sys
from collections import Counter, defaultdict

strata = pickle.load(open("h963_op_strata.pkl", "rb"))

# stratum population counts
band = {}
f = open("h960_band_legs.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 5: band[(t[0], t[1], t[2])] = (t[3], t[4])
vis = {}
f = open("h960_gate_corpus.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 6: vis[(t[0], t[1], t[2])] = t[5]   # r93lab

seed_of = {}
cnt = defaultdict(lambda: [0, 0, 0, 0])   # [bandC, visD, invisA, visF]
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    k = (t[1], t[2], t[3])
    st = strata.get((t[1], t[3]))
    if st is None: continue
    if k in band:
        cnt[st][0] += 1
        seed_of[k] = int(t[0])
    elif k in vis:
        cnt[st][3 if vis[k] == "F" else 1] += 1
    else:
        cnt[st][2] += 1

# split band legs by seed (60% quantile, deterministic)
seeds = sorted(seed_of.values())
cut = seeds[int(0.6 * len(seeds))]
print("band legs:", len(seed_of), "seed cut:", cut,
      "train:", sum(1 for s in seed_of.values() if s < cut),
      "holdout:", sum(1 for s in seed_of.values() if s >= cut))

def delta(hw, mo):
    d = int(hw.split(":")[1], 16) - int(mo.split(":")[1], 16)
    return d if abs(d) <= 2 else 99

tr_c = defaultdict(Counter)
for k, (hw, r3) in band.items():
    if seed_of[k] < cut:
        tr_c[strata[(k[0], k[2])]][delta(hw, r3)] += 1

table = {}
for st, dc in tr_c.items():
    c_tr = sum(dc.values())
    btot, vD, atot, vF = cnt[st]
    # zero invisible-AGREE population AND no DECLINE-side visible
    # legs (a decline-path arm never touches fired legs)
    if c_tr >= 3 and atot == 0 and vD == 0:
        table[st] = dc.most_common(1)[0][0]
print("table strata:", len(table))
for st in sorted(table, key=str):
    btot, vD, atot, vF = cnt[st]
    print("  act=%d sum=%s cell=(%d,%d) g=%d -> %+d  "
          "[pop C=%d visD=%d invisA=%d visF=%d]"
          % (st[0], hex(st[1]), st[2], st[3], st[4], table[st],
             btot, vD, atot, vF))

# holdout evaluation
ho = [(k, v) for k, v in band.items() if seed_of[k] >= cut]
in_tab = fixed = wrongdir = 0
for k, (hw, r3) in ho:
    st = strata[(k[0], k[2])]
    if st not in table: continue
    in_tab += 1
    if delta(hw, r3) == table[st]: fixed += 1
    else: wrongdir += 1
print("HOLDOUT: band legs %d; in-table %d; fixed %d (%.1f%%); wrong-dir %d"
      % (len(ho), in_tab, fixed, 100.0 * fixed / max(1, in_tab), wrongdir))
print("BAR: fix-rate >= 90%%: %s; net >= +100 (train+holdout in-table fixed): %s"
      % (fixed >= 0.9 * in_tab,
         sum(1 for k, (hw, r3) in band.items()
             if strata[(k[0], k[2])] in table
             and delta(hw, r3) == table[strata[(k[0], k[2])]]) >= 100))
pickle.dump(table, open("h964_table.pkl", "wb"), protocol=4)
