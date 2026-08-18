#!/usr/bin/env python3
# h725: clean-wall interval feasibility for the tie family.
# Threshold refinement thr = u0<<66 + f(cell)*2^66: per cell the
# clean rows sandwich f in (max margin of fired, min margin of
# unfired]; a required flip demands f beyond one end.  Feasible iff
# the demand lies inside the clean gap.
import sys, collections
HEX128 = {"umag","S","B","Mreg","t4","sqlow","rd3","disc"}
def blocks(path):
    cur = None; d = None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "DI_IN":
            if cur is not None: yield cur, d
            cur = (t[1], t[2]); d = {}
        elif d is None: continue
        else:
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                if t[0] == "DI_R59" and k in HEX128:
                    x = int(v, 16)
                    if x >= 1 << 127: x -= 1 << 128
                    dd[k] = x
                elif ":" in v and v.count(":") == 2: dd[k] = v
                elif "," in v: dd[k] = v
                elif v.lstrip("-").isdigit(): dd[k] = int(v)
                else: dd[k] = v
    if cur is not None: yield cur, d

def cellof(r59):
    return (r59["s4"], r59["side"], r59["low3"], r59["b1"],
            r59["b2"], r59["dist"], r59["rsh"])

MISS = set(l.split()[1] for l in open("h714_ops.txt"))
# clean wall: per cell, margins of fired / unfired
wall = collections.defaultdict(lambda: dict(fired=[], unfired=[]))
for (se, sig), d in blocks("h720_sample.dump"):
    if sig in MISS: continue
    br = d.get("DI_BR", {})
    if br.get("br") != "tie": continue
    r59 = d["DI_R59"]
    m = (r59["Mreg"] - (br["u0"] << 66)) / float(1 << 66)
    wall[cellof(r59)]["fired" if br["tfire"] == 1 else "unfired"].append(m)
# requirements from the tie misses
REQ = {  # sig-suffix: (need, demand_direction)
  "9242f0c": "suppress",   # cca  model fired, chip not  => f < margin
  "7503a2f": "suppress",   # fa5
  "b69285f": "fire",       # e22  model unfired, chip fired => f > margin
  "4ff121c": "fire",       # e1d
  "0688f849": "special",   # be6 (needs -2, not a tie flip)
  "30c1fc9": "special",    # fb90
}
for (se, sig), d in blocks("h714_dump.txt"):
    br = d.get("DI_BR", {})
    if br.get("br") != "tie": continue
    r59 = d["DI_R59"]
    cell = cellof(r59)
    m = (r59["Mreg"] - (br["u0"] << 66)) / float(1 << 66)
    need = None
    for suf, n in REQ.items():
        if sig.endswith(suf): need = n
    w = wall.get(cell, dict(fired=[], unfired=[]))
    lo = max(w["fired"]) if w["fired"] else float("-inf")
    hi = min(w["unfired"]) if w["unfired"] else float("+inf")
    n_f, n_u = len(w["fired"]), len(w["unfired"])
    # clean gap for f in this cell: (lo, hi]
    if need == "suppress":
        ok = m > lo   # f can sit in (lo, m) to suppress this row
        verdict = "FEASIBLE f in (%.3f, %.3f)" % (lo, m) if ok else \
                  "INFEASIBLE (clean fired at %.3f >= miss %.3f)" % (lo, m)
    elif need == "fire":
        ok = m < hi   # f can sit in (m, hi] to fire this row
        verdict = "FEASIBLE f in (%.3f, %.3f]" % (m, hi) if ok else \
                  "INFEASIBLE (clean unfired at %.3f <= miss %.3f)" % (hi, m)
    else:
        verdict = "(special row, not a single tie flip)"
    print("%s %-8s m=%+7.3f cell=%s wall n=(%d fired,%d unfired) gap=(%.3f,%.3f] %s"
          % (sig[-8:], need, m, cell, n_f, n_u, lo, hi, verdict))
