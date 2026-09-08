#!/usr/bin/env python3
# h963: FULL-POPULATION band-stratum counts (the h938 lesson: never
# scope an arm on sampled collateral).  Dump every unique (insn,op)
# in h931_labels (coordinates are mode-independent pre-rounding
# frames), map each op to its (act, sum8, cell, g) stratum, then
# count per stratum: band-C legs, visible legs, invisible-AGREE
# legs (the collateral population).  Output: h963_strata.tsv +
# candidate table (C >= 3, zero invisible-AGREE legs in stratum).
import pickle, subprocess, sys
from collections import Counter, defaultdict

# leg classes
band = set(); vis = set()
f = open("h960_band_legs.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 5: band.add((t[0], t[1], t[2]))
f = open("h960_gate_corpus.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 6: vis.add((t[0], t[1], t[2]))

legs_of = defaultdict(list)          # (insn, op) -> [mode...]
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    legs_of[(t[1], t[3])].append(t[2])
print("unique ops:", len(legs_of), file=sys.stderr)

byinsn = defaultdict(list)
for (insn, op) in legs_of: byinsn[insn].append(op)

def stratum_of(insn, ops):
    out = {}
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    CH = 100000
    for ci in range(0, len(ops), CH):
        chunk = ops[ci:ci + CH]
        p = subprocess.run(["./model_r93", "--batch", fl,
                            "--dump-internals"],
                           input="\n".join(chunk) + "\n",
                           capture_output=True, text=True)
        rows, cur = [], None
        for ln in p.stderr.splitlines():
            if ln.startswith("DI_IN"):
                if cur is not None: rows.append(cur)
                cur = {}
                continue
            if cur is None: continue
            if ln.startswith("DI_TC ") and "d" not in cur:
                w = {}
                for tok in ln.split()[1:]:
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        w[k] = v
                cur["act"] = int(w.get("active", -1))
                cur["low3"] = int(w.get("low3", -1))
                cur["d"] = int(w.get("dist", -1))
                m = w.get("mul", "0:0:0").split(":")
                cur["me2"] = int(m[1])
                l = w.get("left", "0:0:0").split(":")
                r = w.get("right", "0:0:0").split(":")
                cur["ls"] = int(l[0]); cur["rs"] = int(r[0])
                cur["rsig"] = int(r[2], 16)
            elif ln.startswith("DI_ACC") and "top8" not in cur:
                h = ln.split("d60=")[1][:32]
                cur["top8"] = (int(h, 16) >> 52) & 0xFF
        if cur is not None: rows.append(cur)
        assert len(rows) == len(chunk), (insn, ci, len(rows), len(chunk))
        for op, r in zip(chunk, rows):
            d = r.get("d", -1); g = -1
            if 0 < d <= 40:
                mask = (1 << d) - 1
                rlow = r["rsig"] & mask
                grl = (rlow if rlow else (1 << d)) if r["ls"] != r["rs"] \
                      else ((1 << d) - rlow)
                g = 64 if grl > 64 else int(grl)
            s = r["top8"] + r["low3"] if r.get("top8", -1) >= 0 \
                and r.get("low3", -1) >= 0 else -1
            out[op] = (r.get("act", -1), s, d, r.get("me2", 0), g)
        print(insn, ci, "done", file=sys.stderr)
    return out

strata = {}
for insn, ops in sorted(byinsn.items()):
    so = stratum_of(insn, ops)
    for op, st in so.items(): strata[(insn, op)] = st
pickle.dump(strata, open("h963_op_strata.pkl", "wb"), protocol=4)

cnt = defaultdict(lambda: [0, 0, 0])   # stratum -> [bandC, vis, invisA]
for (insn, op), modes in legs_of.items():
    st = strata.get((insn, op))
    if st is None: continue
    for mode in modes:
        k = (insn, mode, op)
        i = 0 if k in band else (1 if k in vis else 2)
        cnt[st][i] += 1
out = open("h963_strata.tsv", "w")
out.write("act\tsum8\td\tme2\tg\tbandC\tvis\tinvisA\n")
for st in sorted(cnt, key=str):
    c, v, a = cnt[st]
    out.write("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n" % (*st, c, v, a))
out.close()
cand = [(c, a, v, st) for st, (c, v, a) in cnt.items() if c >= 3]
cand.sort(reverse=True)
print("strata with bandC >= 3:", len(cand))
tot0 = sum(c for c, a, v, st in cand if a == 0)
print("bandC legs in ZERO-invisA strata:", tot0)
print("top 25 (C, invisA, vis, stratum):")
for c, a, v, st in cand[:25]:
    print("  C=%-4d A=%-6d vis=%-4d act=%s sum=%s cell=(%d,%d) g=%d"
          % (c, a, v, st[0], hex(st[1]), st[2], st[3], st[4]))
