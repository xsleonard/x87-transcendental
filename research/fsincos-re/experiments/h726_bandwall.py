#!/usr/bin/env python3
# h726: band-family doppelganger test.  For each band miss, count
# clean same-cell rows whose margin lies BETWEEN the miss's margin
# and the region boundary with the OPPOSITE behavior — each one is
# a direct order-contradiction for any monotone (cell, Mreg) law.
import collections
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
def cellof(r59, th):
    sgn = 0 if th == 0 else (1 if th > 0 else -1)
    return (sgn, abs(th), r59["s4"], r59["side"], r59["low3"],
            r59["b1"], r59["b2"], r59["dist"], r59["rsh"])
MISS = set(l.split()[1] for l in open("h714_ops.txt"))
clean = collections.defaultdict(list)
for (se, sig), d in blocks("h720_sample.dump"):
    if sig in MISS: continue
    br = d.get("DI_BR", {})
    if br.get("br") != "band": continue
    r59 = d["DI_R59"]
    m = (r59["Mreg"] - (br["uu"] << 66)) / float(1 << 66)
    clean[cellof(r59, r59["theta"])].append((m, br["in_region"], br["fire"]))
# misses: 9 missed fires (in_region=0, chip fired), 3 over-fires
for (se, sig), d in blocks("h714_dump.txt"):
    br = d.get("DI_BR", {})
    if br.get("br") != "band": continue
    r59 = d["DI_R59"]; th = r59["theta"]
    m = (r59["Mreg"] - (br["uu"] << 66)) / float(1 << 66)
    cell = cellof(r59, th)
    cl = clean.get(cell, [])
    if br["in_region"] == 0:
        # missed fire: chip fired at |m| outside.  doppelganger =
        # clean out-of-region row with |margin| <= |m| (closer to or
        # equal the boundary) that did NOT fire (hardware clean).
        dop = [x for x in cl if x[1] == 0 and abs(x[0]) <= abs(m)]
        kind = "missfire"
    else:
        # over-fire: chip suppressed inside at |m|.  doppelganger =
        # clean in-region row deeper inside (|margin| >= |m|) that
        # DID fire correctly.
        dop = [x for x in cl if x[1] == 1 and x[2] == 1 and abs(x[0]) >= abs(m)]
        kind = "overfire"
    print("%-8s %-8s th=%+d m=%+7.3f cell-n=%-4d doppelgangers=%d %s"
          % (sig[-8:], kind, th, m, len(cl), len(dop),
             "CONTRADICTION" if dop else "(none in sample)"))
