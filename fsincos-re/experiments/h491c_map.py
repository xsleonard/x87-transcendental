#!/usr/bin/env python3
"""h491c: build the dense dual-schedule fire maps.

Reads h491_ties.tsv + the six capture status files.  Per tie, per
instruction: outcome CLEAN / FIRE / OTHER (cos lane for sincos).
Outputs:
  - overall census per instruction per cell;
  - for each of the biggest mixed cells: 32x32 fire-rate grids over
    (t4hi12 top 5 bits x rdhi12 top 5 bits) for FCOS, FSINCOS, and
    the flip map (P(different outcome));
  - h491_mapdata.tsv (every tie with both outcomes) for deeper
    analysis and visualization.
Run from /tmp/stageA with the status files fetched.
"""
from collections import defaultdict, Counter

MODES = ("rn", "rd", "ru")

ties = []
with open("h491_ties.tsv") as fh:
    header = fh.readline()
    for line in fh:
        f = line.rstrip("\n").split("\t")
        ties.append(f)
n = len(ties)
status = {}
for insn, tok in (("cos", 2), ("sincos", 4)):
    for md in MODES:
        lines = open(f"{insn}_{md}_status.txt").read().splitlines()
        assert len(lines) == n, (insn, md, len(lines), n)
        status[(insn, md)] = lines


def outcome(insn, tok, i, clean, fired):
    vals = []
    for md in MODES:
        t = status[(insn, md)][i].split()
        if t[0] != "OK":
            return "BAD"
        vals.append(f"{int(t[tok], 16):016x}")
    if vals == clean:
        return "CLEAN"
    if vals == fired:
        return "FIRE"
    return "OTHER"


rows = []
for i, f in enumerate(ties):
    clean = f[7].split(",")
    fired = f[8].split(",")
    oc = outcome("cos", 2, i, clean, fired)
    osc = outcome("sincos", 4, i, clean, fired)
    rows.append((f, oc, osc))

print("=== census ===")
print(f"ties: {n}")
print(f"FCOS   : {Counter(r[1] for r in rows)}")
print(f"FSINCOS: {Counter(r[2] for r in rows)}")

cells = defaultdict(list)
for f, oc, osc in rows:
    cells[(f[1], f[2], f[3], f[4])].append((f, oc, osc))

with open("h491_mapdata.tsv", "w") as fh:
    fh.write("m\tdist\tlow3\tk\trud\tt4hi12\trdhi12\tfcos\tsincos\n")
    for f, oc, osc in rows:
        fh.write("\t".join(f[:7]) + f"\t{oc}\t{osc}\n")

def grid(sub, which):
    g = defaultdict(lambda: [0, 0])
    for f, oc, osc in sub:
        o = oc if which == "fcos" else osc
        if o not in ("CLEAN", "FIRE"):
            continue
        t5 = int(f[5], 16) >> 7          # top 5 of t4hi12
        d5 = int(f[6], 16) >> 7
        c = g[(t5, d5)]
        c[0] += 1
        c[1] += o == "FIRE"
    return g

def render(g, label):
    print(f"\n--- {label} (rows T 0..31 top-down, cols D 0..31) ---")
    for t in range(32):
        line = []
        for d in range(32):
            tot, fi = g[(t, d)]
            if not tot:
                line.append(".")
            else:
                r = fi / tot
                line.append("#" if r > 0.8 else
                            "+" if r > 0.55 else
                            "o" if r > 0.3 else
                            "-" if r > 0.1 else "0")
        print("".join(line))

big = sorted(cells, key=lambda c: -len(cells[c]))[:4]
for cell in big:
    sub = cells[cell]
    nf = sum(1 for _, oc, _ in sub if oc == "FIRE")
    ns = sum(1 for _, _, osc in sub if osc == "FIRE")
    print(f"\n================ cell (dist,low3,k,rud)={cell} "
          f"n={len(sub)} fcos-fires={nf} sincos-fires={ns}")
    render(grid(sub, "fcos"), "FCOS")
    render(grid(sub, "sincos"), "FSINCOS")
    # flip map
    g = defaultdict(lambda: [0, 0])
    for f, oc, osc in sub:
        if oc in ("CLEAN", "FIRE") and osc in ("CLEAN", "FIRE"):
            t5 = int(f[5], 16) >> 7
            d5 = int(f[6], 16) >> 7
            c = g[(t5, d5)]
            c[0] += 1
            c[1] += oc != osc
    render(g, "FLIP (schedule-sensitive region)")
print("\nwrote h491_mapdata.tsv")
