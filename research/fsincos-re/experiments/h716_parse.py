#!/usr/bin/env python3
# h716 parse: score the perturbation matrix.  For each operand and
# each (tgt,delta): does the perturbed model match hardware in ALL
# three modes?  Also reports per-mode match patterns.
def norm(line):
    t = line.split()
    return "C2" if t[0] == "C2" else "%s/%s" % (t[1], t[2])
ops = []
hw3 = []
mo3 = []
for line in open("h714_hw3.txt"):
    left, h3, m3 = line.strip().split(" | ")
    se, sig, corp, lineno = left.split()
    ops.append((se, sig, corp))
    hw3.append(h3.split())
    mo3.append(m3.split())
MODES = ("rn", "rd", "ru")
CFGS = [(t, d) for t in ("odd", "even", "sq", "f4", "mag")
        for d in (-2, -1, 1, 2)]
pt = {}
for t, d in CFGS:
    for mi, m in enumerate(MODES):
        lines = open(f"pt_{t}_{d}_{m}.txt").read().splitlines()
        assert len(lines) == len(ops)
        for oi, l in enumerate(lines):
            pt[(t, d, m, oi)] = norm(l)
print("%-4s %-18s %-6s base | %s" % ("se", "sig", "corp",
      " ".join("%-7s" % ("%s%+d" % (t[:2], d)) for t, d in CFGS)))
full_fix = {c: 0 for c in CFGS}
for oi, (se, sig, corp) in enumerate(ops):
    base = "".join("=" if mo3[oi][mi] == hw3[oi][mi] else "X"
                   for mi in range(3))
    cells = []
    for t, d in CFGS:
        pat = "".join(
            "=" if pt[(t, d, m, oi)] == hw3[oi][mi] else "X"
            for mi, m in enumerate(MODES))
        if pat == "===":
            full_fix[(t, d)] += 1
            pat = "FIX"
        cells.append("%-7s" % pat)
    print("%-4s %-18s %-6s %s  | %s" % (se, sig[-8:], corp, base,
                                        " ".join(cells)))
print()
print("FULL-RECONCILE COUNTS (all 3 modes match hw), n_ops=%d:" % len(ops))
for t, d in CFGS:
    print("  %-5s %+d : %d" % (t, d, full_fix[(t, d)]))
