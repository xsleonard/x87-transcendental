#!/usr/bin/env python3
# h722: test the "wider region obeys h662k" fragment at scale.
# Among CLEAN band rows with in_region=0 and margin inside the
# missed-fire zone, how many WOULD fire under h662k (non-crit =>
# unconditional; crit => bs bits)?  Every one is a counterexample
# (hardware did not fire there).  Also: clean tie rows in the razor
# band vs the 3 razor misses.
import sys
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
MISS = set(l.split()[1] for l in open("h714_ops.txt"))
n_band_out = 0; zone = 0; would = 0; crit_would = 0; noncrit = 0
tie_razor = 0; tie_all = 0
margins = []
for (se, sig), d in blocks("h720_sample.dump"):
    if sig in MISS: continue
    r59 = d.get("DI_R59"); br = d.get("DI_BR")
    if not r59 or not br: continue
    b = br.get("br")
    Mreg = r59["Mreg"]
    if b == "tie":
        tie_all += 1
        u0 = br.get("u0")
        m = (Mreg - (u0 << 66)) / float(1 << 66)
        if abs(m) <= 0.5: tie_razor += 1
        continue
    if b != "band" or br.get("in_region") != 0: 
        continue
    n_band_out += 1
    uu = br.get("uu"); th = r59["theta"]
    m = (Mreg - (uu << 66)) / float(1 << 66)
    sgn_dn = th > 0
    # outside means: dn: m >= 0 ; up: m < 0.  extension zone |m|<=4
    if abs(m) > 4: continue
    zone += 1
    margins.append(m)
    S = r59["S"]; B = r59["B"]; umag = r59["umag"]
    k = r59["k"]; ce = r59["ce"]
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and (pmask >> j) & 1:
        pm += 1; j += 1
    phw = ((ce % 8) + 8) % 8
    crit = (pm + phw) % 8 == 7 and pm in (7, 8)
    if not crit:
        would += 1; noncrit += 1
    else:
        bsrel = 8 + ((8 - phw) % 8)
        bit8 = (umag >> (k + 8)) & 1
        bitbs = (umag >> (k + bsrel)) & 1
        f = (bit8 & bitbs) if sgn_dn else bitbs
        if f: would += 1; crit_would += 1
print("clean band rows out-of-region:", n_band_out)
print("  in extension zone |margin|<=4:", zone)
print("  WOULD fire under naive h662k extension:", would,
      " (noncrit:", noncrit, " crit+bits:", crit_would, ")")
print("  => counterexample rate:", "%.4f" % (would/zone if zone else 0))
if margins:
    import statistics
    print("  zone margin mean %.2f sd %.2f" %
          (statistics.mean(margins), statistics.pstdev(margins)))
print("clean tie rows:", tie_all, " razor |m|<=0.5:", tie_razor)
