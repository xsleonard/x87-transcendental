#!/usr/bin/env python3
# h949: full-feature harvest for the gate predicate hunt.
# For every op in h948_gate_ops.tsv (34,460 mode-consistent visible
# ops, hwlab FIRE/DECL), run model_r92 --dump-internals and harvest
# EVERY DI field (scalars + full 128-bit words), join the seed from
# h931_labels.tsv, and pickle the table for the contrast/holdout
# analyses.  Run on i7 in /root/r84.
import pickle, subprocess, sys
from collections import defaultdict

# --- seed join: (insn, op) -> min seed ---
seed_of = {}
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) != 9: continue
    k = (t[1], t[3])
    s = int(t[0])
    if k not in seed_of or s < seed_of[k]: seed_of[k] = s

# --- ops to harvest ---
ops = []          # (insn, op, hwlab)
f = open("h948_gate_ops.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    ops.append((t[0], t[1], t[2]))
print("ops:", len(ops), file=sys.stderr)

HEXBYTE = {"laneb", "lane2", "lane3"}
HEXWORD = {"d60", "rdisc", "ra"}
TAGS = {"DI_RC2": "rc2", "DI_RED": "red", "DI_POLY": "poly",
        "DI_TC": "tc", "DI_TC2": "tc2", "DI_ACC": "acc",
        "DI_B81": "b81", "DI_CORR": "corr", "DI_FIN": "fin"}

def parse_di(text, n_expect):
    rows, cur = [], None
    for ln in text.splitlines():
        w = ln.split()
        if not w: continue
        tag = w[0]
        if tag == "DI_IN":
            if cur is not None: rows.append(cur)
            cur = {}
            continue
        if cur is None or tag not in TAGS: continue
        pre = TAGS[tag]
        for tok in w[1:]:
            if "=" not in tok: continue
            k, v = tok.split("=", 1)
            key = pre + "_" + k
            if key in cur: continue
            if ":" in v:                       # wide s:e2:sighex
                s2, e2, sig = v.split(":")
                cur[key] = (int(s2), int(e2), int(sig, 16))
            elif k in HEXBYTE or k in HEXWORD or v.startswith("0x"):
                cur[key] = int(v, 16)
            else:
                try: cur[key] = int(v)
                except ValueError: cur[key] = v
    if cur is not None: rows.append(cur)
    assert len(rows) == n_expect, (len(rows), n_expect)
    return rows

byinsn = defaultdict(list)
for i, (insn, op, hwlab) in enumerate(ops):
    byinsn[insn].append(i)

table = [None] * len(ops)
for insn, idxs in sorted(byinsn.items()):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    CH = 100000
    for ci in range(0, len(idxs), CH):
        chunk = idxs[ci:ci + CH]
        inp = "\n".join(ops[i][1] for i in chunk) + "\n"
        p = subprocess.run(["./model_r92", "--batch", fl, "--dump-internals"],
                           input=inp, capture_output=True, text=True)
        rows = parse_di(p.stderr, len(chunk))
        for i, r in zip(chunk, rows):
            insn_i, op_i, hwlab_i = ops[i]
            r["insn"] = insn_i; r["op"] = op_i; r["hwlab"] = hwlab_i
            r["seed"] = seed_of.get((insn_i, op_i), -1)
            table[i] = r
        print(insn, ci, "done", file=sys.stderr)

missing = sum(1 for r in table if r is None)
noseed = sum(1 for r in table if r is not None and r["seed"] < 0)
print("harvested:", len(table) - missing, "missing:", missing,
      "no-seed:", noseed)
pickle.dump(table, open("h949_features.pkl", "wb"), protocol=4)
# seed distribution for the pre-registered split
seeds = sorted(r["seed"] for r in table if r is not None)
q60 = seeds[int(0.6 * len(seeds))]
print("seed min/med/q60/max:", seeds[0], seeds[len(seeds)//2], q60,
      seeds[-1])
print("TRAIN = seed <", q60, "->",
      sum(1 for s in seeds if s < q60), "ops; HOLDOUT >=", q60, "->",
      sum(1 for s in seeds if s >= q60), "ops")
