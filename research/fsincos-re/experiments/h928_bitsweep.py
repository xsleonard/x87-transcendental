#!/usr/bin/env python3
# h928: THE RAW-BIT INFORMATION SWEEP over the parked act1 adder
# boundary band.  Every prior hunt tested STRUCTURED coordinates
# (frames, sums, lanes, lattices).  This sweep tests EVERY RAW BIT
# of EVERY dumped intermediate against the carry labels, with the
# h916 seed-split holdout (train < 94064, holdout >= 94064) and
# Bonferroni control.  Outcomes: (a) a bit/conjunction survives the
# holdout -> a NEW vocabulary the manual hunts missed; (b) nothing
# survives -> the park acquires an information-theoretic raw-bit
# proof at this dataset's power.
# Labels: fringe3.pkl (10,845 R90-declined in-window rows, 120 C).
import pickle, subprocess, re, sys
import numpy as np

MODEL = "./model_h928"
rows = pickle.load(open("fringe3.pkl", "rb"))
print("rows", len(rows), "C:", sum(1 for r in rows if r["cls"] == "C"))

# one dump run per (insn, operand); mode irrelevant to the frames
ops = []
seen = {}
for r in rows:
    insn, mode, se, sig = r["k"]
    key = (insn, se, sig)
    if key in seen:
        # keep C label if any mode shows carry
        i = seen[key]
        if r["cls"] == "C":
            ops[i]["cls"] = "C"
        continue
    seen[key] = len(ops)
    ops.append(dict(insn=insn, se=se, sig=sig, cls=r["cls"],
                    seed=r["seed"]))
print("distinct operands:", len(ops),
      "C:", sum(1 for o in ops if o["cls"] == "C"))

# hex fields to harvest per row: name -> width in bits
HEXF = [("umag", 128), ("S", 128), ("B", 128), ("Mreg", 128),
        ("t4", 128), ("sqlow", 128), ("rd3", 128), ("disc", 128),
        ("d60", 128)]
WIDEF = ["L", "R", "tc", "mag", "sq", "odd", "even", "f4", "m"]

def harvest(insn, batch):
    inp = "".join("%s %s\n" % (o["se"], o["sig"]) for o in batch)
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    p = subprocess.run([MODEL, "--batch", fl, "--dump-internals"],
                       input=inp, capture_output=True, text=True)
    out, cur = [], None
    for ln in p.stderr.splitlines():
        if ln.startswith("DI_IN"):
            if cur is not None:
                out.append(cur)
            cur = {}
        elif cur is None:
            continue
        else:
            for m in re.finditer(r"(\w+)=([0-9a-f]{16,32})\b", ln):
                k, v = m.group(1), m.group(2)
                if k not in cur and len(v) in (16, 32):
                    cur[k] = int(v, 16)
            m = re.search(r"(\w+)=-?\d+:-?\d+:([0-9a-f]{32})", ln)
            for m in re.finditer(r"(\w+)=-?\d+:-?\d+:([0-9a-f]{32})", ln):
                k = m.group(1)
                if k not in cur:
                    cur[k] = int(m.group(2), 16)
    if cur is not None:
        out.append(cur)
    return out

# harvest all, build the bit matrix
names = None
vecs, labels, seeds = [], [], []
for insn in ("cos", "sin"):
    batch = [o for o in ops if o["insn"] == insn]
    for i in range(0, len(batch), 4000):
        chunk = batch[i:i + 4000]
        hs = harvest(insn, chunk)
        assert len(hs) == len(chunk), (len(hs), len(chunk))
        for o, h in zip(chunk, hs):
            if names is None:
                names = sorted(h)
                print("fields:", names)
            vec = []
            for n in names:
                v = h.get(n, 0)
                vec.append(v)
            vecs.append(vec)
            labels.append(1 if o["cls"] == "C" else 0)
            seeds.append(o["seed"])
        print("harvested", insn, i + len(chunk), "/", len(batch),
              file=sys.stderr)

nfield = len(names)
N = len(vecs)
y = np.array(labels, dtype=np.int8)
sd = np.array(seeds)
train = sd < 94064
hold = ~train
print("N=%d fields=%d  train C/N %d/%d  hold C/N %d/%d"
      % (N, nfield, y[train].sum(), (~y[train].astype(bool)).sum(),
         y[hold].sum(), (~y[hold].astype(bool)).sum()))

# bits matrix: nfield x 128 bits
B = np.zeros((N, nfield * 128), dtype=np.int8)
for i, vec in enumerate(vecs):
    for j, v in enumerate(vec):
        for b in range(128):
            if (v >> b) & 1:
                B[i, j * 128 + b] = 1

# drop constant bits
var = B.var(axis=0) > 0
idx = np.where(var)[0]
print("informative bit positions:", len(idx))

# per-bit train contrast
ytr = y[train].astype(np.float64)
Btr = B[train][:, idx].astype(np.float64)
pC = Btr[ytr == 1].mean(axis=0)
pN = Btr[ytr == 0].mean(axis=0)
delta = pC - pN
# z-score under binomial null
nC = int(ytr.sum()); nN = int((1 - ytr).sum())
p0 = Btr.mean(axis=0)
se = np.sqrt(p0 * (1 - p0) * (1 / nC + 1 / nN)) + 1e-12
z = delta / se
order = np.argsort(-np.abs(z))
print("\ntop 20 train bits (field.bit  pC pN z):")
for r_ in order[:20]:
    gi = idx[r_]
    print("  %s.b%-3d  %.3f %.3f  z=%+.2f"
          % (names[gi // 128], gi % 128, pC[r_], pN[r_], z[r_]))

# holdout evaluation of top-K with Bonferroni over the tested count
K = 40
yh = y[hold].astype(np.float64)
Bh = B[hold][:, idx].astype(np.float64)
nCh = int(yh.sum()); nNh = int((1 - yh).sum())
print("\nholdout check (top %d train bits; Bonferroni x%d):"
      % (K, len(idx)))
import math
best = []
for r_ in order[:K]:
    gi = idx[r_]
    qC = Bh[yh == 1, r_].mean(); qN = Bh[yh == 0, r_].mean()
    q0 = Bh[:, r_].mean()
    seh = math.sqrt(max(q0 * (1 - q0), 1e-12) * (1 / nCh + 1 / nNh))
    zh = (qC - qN) / (seh + 1e-12)
    same_sign = np.sign(zh) == np.sign(z[r_])
    best.append((abs(zh) if same_sign else 0, names[gi // 128],
                 gi % 128, z[r_], zh))
best.sort(reverse=True)
for absz, nm, b, ztr, zh in best[:12]:
    # two-sided normal tail, Bonferroni over all tested bits
    ptail = math.erfc(abs(zh) / math.sqrt(2))
    print("  %s.b%-3d train z=%+.2f  HOLD z=%+.2f  p_bonf=%.2g"
          % (nm, b, ztr, zh, min(1.0, ptail * len(idx))))
sig = [x for x in best if x[0] > 0 and
       math.erfc(x[0] / math.sqrt(2)) * len(idx) < 0.05]
print("\nVERDICT: %d bits survive the seed-split holdout at"
      " Bonferroni 0.05 over %d tested positions"
      % (len(sig), len(idx)))
np.save("h928_bits.npy", B); np.save("h928_y.npy", y)
np.save("h928_seed.npy", sd)
open("h928_names.txt", "w").write("\n".join(names))
