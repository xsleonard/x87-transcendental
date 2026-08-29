#!/usr/bin/env python3
# h962: the band frame at 1,619-leg power (13.5x the h916 TAILVIS
# count).  For every h960 band leg + a 60k random invisible-AGREE
# sample: dump (act, top8, low3 -> sum8, dist, me2, g, ud, rud,
# pay, via) per (insn,mode); LF-equality on the C legs.  Output:
# the carry-rate ladder C/(C+AGREE) by (act, sum8), stratum purity
# at (act, sum8, cell, g-bucket), the sub-band tail's own strata,
# and delta direction.  Question: do >=95%-pure strata exist for a
# scoped exact-tail (LF) arm = the R94 candidate?
import random, re, subprocess, sys
from collections import Counter, defaultdict

cband = []
f = open("h960_band_legs.tsv"); f.readline()
for ln in f:
    t = ln.rstrip("\n").split("\t")
    if len(t) == 5: cband.append((t[0], t[1], t[2], t[3], t[4]))
print("band C legs:", len(cband), file=sys.stderr)

agree = []
for ln in open("h931_labels.tsv"):
    t = ln.rstrip("\n").split("\t")
    if len(t) == 9 and t[8] == "AGREE":
        agree.append((t[1], t[2], t[3]))
random.seed(962)
bg = random.sample(agree, 60000)
del agree
print("AGREE sample:", len(bg), file=sys.stderr)

def dump(keys):
    out = {}
    grp = defaultdict(list)
    for k in keys: grp[(k[0], k[1])].append(k[2])
    for (insn, mode), opsl in sorted(grp.items()):
        fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
        args = ["./model_r93", "--batch", fl, "--dump-internals"]
        if mode != "rn": args.insert(2, "--rc=" + mode)
        p = subprocess.run(args, input="\n".join(opsl) + "\n",
                           capture_output=True, text=True)
        rows, cur = [], None
        for ln in p.stderr.splitlines():
            tag = ln.split(" ", 1)[0]
            if tag == "DI_IN":
                if cur is not None: rows.append(cur)
                cur = {"_t": set()}
                continue
            if cur is None or tag in cur["_t"]: continue
            cur["_t"].add(tag)
            if tag == "DI_TC":
                for f_ in ("active", "low3", "dist", "ud", "rud",
                           "payload"):
                    m = re.search(f_ + r"=(-?\d+)", ln)
                    if m: cur[f_] = int(m.group(1))
                m = re.search(r"mul=\d+:(-?\d+):", ln)
                if m: cur["me2"] = int(m.group(1))
                m = re.search(r"left=(\d+):-?\d+:", ln)
                if m: cur["ls"] = int(m.group(1))
                m = re.search(r"right=(\d+):(-?\d+):([0-9a-f]{32})", ln)
                if m:
                    cur["rs"] = int(m.group(1))
                    cur["rsig"] = int(m.group(3), 16)
            elif tag == "DI_ACC":
                m = re.search(r"d60=([0-9a-f]{32})", ln)
                if m: cur["top8"] = (int(m.group(1), 16) >> 52) & 0xFF
            elif tag == "DI_CORR":
                m = re.search(r"via=(\w+)", ln)
                if m: cur["via"] = m.group(1)
        if cur is not None: rows.append(cur)
        assert len(rows) == len(opsl), (insn, mode, len(rows), len(opsl))
        for op, r in zip(opsl, rows):
            d = r.get("dist", -1)
            g = -1
            if 0 < d <= 40 and "rsig" in r:
                mask = (1 << d) - 1
                rlow = r["rsig"] & mask
                grl = (rlow if rlow else (1 << d)) if r.get("ls", 0) != r.get("rs", 0) \
                      else ((1 << d) - rlow)
                g = 64 if grl > 64 else int(grl)
            s = r.get("top8", -1) + r.get("low3", -1) \
                if r.get("top8", -1) >= 0 and r.get("low3", -1) >= 0 else -1
            out[(insn, mode, op)] = dict(
                act=r.get("active", -1), sum8=s, d=d, me2=r.get("me2", 0),
                g=g, ud=r.get("ud", -1), rud=r.get("rud", -1),
                pay=r.get("payload", -99), via=r.get("via", "?"))
    return out

cd = dump([(a, b, c) for a, b, c, _, _ in cband])
bd = dump(bg)

def runlf(keys):
    out = {}
    grp = defaultdict(list)
    for k in keys: grp[(k[0], k[1])].append(k[2])
    for (insn, mode), opsl in sorted(grp.items()):
        fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
        args = ["./model_h951_lf", "--batch", fl]
        if mode != "rn": args.insert(2, "--rc=" + mode)
        p = subprocess.run(args, input="\n".join(opsl) + "\n",
                           capture_output=True, text=True)
        o = [tuple(x.lower() for x in l.split()[1:3])
             for l in p.stdout.splitlines()]
        assert len(o) == len(opsl)
        for op, v in zip(opsl, o): out[(insn, mode, op)] = v
    return out

lf = runlf([(a, b, c) for a, b, c, _, _ in cband])

# --- report ---
def sgn(hw, mo):
    a = int(hw.split(":")[1], 16); b = int(mo.split(":")[1], 16)
    d = a - b
    return d if abs(d) <= 2 else 99

lad = defaultdict(lambda: [0, 0])      # (act, sum8) -> [C, AGREE]
strat = defaultdict(lambda: [0, 0])    # (act, sum8, cell, gbucket)
sub = Counter(); dirs = Counter(); lfeq = Counter()
def gb(g): return g if 0 <= g <= 8 else (16 if g <= 16 else 99)
for (insn, mode, op, hw, r3) in cband:
    r = cd[(insn, mode, op)]
    k = (r["act"], r["sum8"])
    lad[k][0] += 1
    strat[(r["act"], r["sum8"], (r["d"], r["me2"]), gb(r["g"]))][0] += 1
    if r["sum8"] < 0xFD:
        sub[(r["act"], r["sum8"], (r["d"], r["me2"]))] += 1
    dirs[sgn(hw, r3)] += 1
    lfeq["eq" if lf[(insn, mode, op)] == tuple(hw.split(":")) else "ne"] += 1
for k3 in bg:
    r = bd[k3]
    lad[(r["act"], r["sum8"])][1] += 1
    strat[(r["act"], r["sum8"], (r["d"], r["me2"]), gb(r["g"]))][1] += 1
print("delta(hw - r93):", dict(dirs))
print("LF==hw on C legs:", dict(lfeq))
print("\n--- carry ladder (act, sum8): C / AGREE-sample ---")
for k in sorted(lad, key=str):
    c, a = lad[k]
    if c or (0xF8 <= (k[1] if k[1] else 0) <= 0x10A):
        print("  act=%s sum=%s: C=%d agree=%d" % (k[0], hex(k[1]) if k[1] >= 0 else "?", c, a))
print("\n--- strata with C>=5 and purity >=80%% (C/(C+A)) ---")
rows = []
for k, (c, a) in strat.items():
    if c >= 5 and c / (c + a) >= 0.8: rows.append((c, a, k))
rows.sort(reverse=True)
for c, a, k in rows[:30]:
    print("  C=%d A=%d  act=%s sum=%s cell=%s g=%s" %
          (c, a, k[0], hex(k[1]), k[2], k[3]))
print("pure-strata C total:", sum(c for c, a, k in rows))
print("\n--- sub-band tail (sum < 0xFD) top strata ---")
for k, c in sub.most_common(12): print("  ", k, c)
import pickle
pickle.dump((cband, cd, bd, dict(lf)), open("h962_band.pkl", "wb"), protocol=4)
