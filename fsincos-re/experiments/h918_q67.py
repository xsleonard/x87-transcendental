#!/usr/bin/env python3
# h918: the q67th2 quadrant probe.  The dn-th2-(67,1) quadrant is
# modeled as NEVER-FIRE (h664: 4 lone fires / 1.06M called anomalies);
# the h917 census shows 9 of the 36 ledger keys are exactly hw-fires
# in this quadrant (6 comb ce=-72 + randv1 cos 402b ce=-74 + 2 randv1
# sin ce=-74) — the largest coherent family on the ledger.  The R67/68
# corner law proved fire laws exist in the adjacent cell (dd threshold
# + block-start bits).  This probe computes the full h662b/h662k
# lattice vocabulary for POS (the 9 keys, run live through the
# ledger-off model) and NEG (q67th2-branch rows harvested model-side
# from banked comb corpora — suite-zero makes every non-ledger row a
# labeled no-fire), then tests candidate tap vectors (the missing
# 12th vector) x fire-semantics variants for exact separation.
#
# usage: h918_q67.py NEG1.txt [NEG2.txt ...]
#   NEG files: lines "DI_IN se sig|DI_R59 ..." from the awk harvest.
import subprocess, re, sys, collections

MODEL = "./model_h917_noled"
TWO66 = 1 << 66


def parse_kv(line):
    d = {}
    for m in re.finditer(r"(\w+)=([0-9a-fA-F-]+)", line):
        d[m.group(1)] = m.group(2)
    return d


def s128(h):
    v = int(h, 16)
    return v - (1 << 128) if v >= (1 << 127) else v


def cmod8(ce):
    q = int(ce / 8)  # C truncation
    return ((ce - 8 * q) + 8) % 8


def lattice(rec):
    """rec: DI_R59 kv dict -> lattice object dict"""
    k = int(rec["k"]); ce = int(rec["ce"])
    b1 = int(rec["b1"]); b2 = int(rec["b2"])
    low3 = int(rec["low3"]); dist = int(rec["dist"])
    S = int(rec["S"], 16); B = int(rec["B"], 16)
    umag = int(rec["umag"], 16)
    Mreg = s128(rec["Mreg"])
    pmask = ~(S ^ B) & ((1 << 128) - 1)
    pm = 0; j = k
    while pm < 32 and ((pmask >> j) & 1):
        pm += 1; j += 1
    phw = cmod8(ce)
    crit = ((pm + phw) % 8 == 7) and pm in (7, 8)
    crit9 = ((pm + phw) % 8 == 7) and pm == 9
    bsrel = 8 + ((8 - phw) % 8)
    bit8 = (umag >> (k + 8)) & 1
    bitbs = (umag >> (k + bsrel)) & 1
    lp = low3 & 1
    dd = low3 + b1 + b2
    # quadrant (67,1) params: qa=2 qg1=2 qg2=3 qp=-3 qq=8 qk=2 qpar=1
    wd = -4 - 2 * (dist - 7)
    base = 2 * low3 + 2 * b1 + 3 * b2 - 3 * lp + wd
    md = Mreg >> 66  # floor; in_region(dn) <=> md < uu
    return dict(k=k, ce=ce, b1=b1, b2=b2, low3=low3, dist=dist,
                rsh=int(rec["rsh"]), pay=int(rec.get("payload", "0")),
                pm=pm, phw=phw, crit=int(crit), crit9=int(crit9),
                bit8=bit8, bitbs=bitbs, lp=lp, dd=dd, base=base,
                md=md, theta=int(rec["theta"]))


def fire_of(v_c0, v_cd, sem, L):
    d7 = L["dist"] - 7
    uu = 2 * ((L["base"] - (v_c0 + v_cd * d7)) // 8) + L["lp"]
    in_r = L["md"] < uu
    bits_band = (L["bit8"] & L["bitbs"]) if L["crit"] else 1
    bits_r65 = (L["bitbs"] if L["crit9"]
                else ((L["bit8"] & L["bitbs"]) if L["crit"] else 1))
    if sem == "V0":
        return in_r
    if sem == "V1":
        return in_r and bits_band
    if sem == "V2":
        return in_r and bits_r65
    if sem == "V3":
        return in_r and (L["bit8"] & L["bitbs"])
    raise ValueError(sem)


# ---- POS: the 9 q67th2 ledger keys, live ----
POS_KEYS = []
for ln in open("probe_keys.tsv"):
    f = ln.split()
    if len(f) != 6:
        continue
    POS_KEYS.append(f)

pos = []
for instr, mode, se, sig, hse, hsig in POS_KEYS:
    args = [MODEL, "--batch",
            "--fcos-standalone" if instr == "cos" else "--fsin-standalone",
            "--dump-internals"]
    if mode != "rn":
        args.append("--rc=" + mode)
    p = subprocess.run(args, input="%s %s\n" % (se, sig),
                       capture_output=True, text=True)
    r59 = None; isq = False
    for l in p.stderr.splitlines():
        if l.startswith("DI_R59"):
            r59 = parse_kv(l)
        elif l.startswith("DI_BR br=q67th2"):
            isq = True
    if isq and r59:
        L = lattice(r59)
        L["op"] = "%s/%s/%s%s" % (instr, mode, se, sig[:8])
        pos.append(L)

print("== %d POS (q67th2 ledger keys) ==" % len(pos))
hdr = ("op ce dist rsh low3 b1 b2 lp dd base md pm phw crit crit9 "
       "bit8 bitbs pay theta")
print(" ".join(hdr.split()))
for L in pos:
    print("%-22s %d %d %d  %d %d %d %d  dd=%d base=%d md=%d  pm=%-2d "
          "phw=%d c=%d c9=%d  b8=%d bbs=%d pay=%d th=%d"
          % (L["op"], L["ce"], L["dist"], L["rsh"], L["low3"], L["b1"],
             L["b2"], L["lp"], L["dd"], L["base"], L["md"], L["pm"],
             L["phw"], L["crit"], L["crit9"], L["bit8"], L["bitbs"],
             L["pay"], L["theta"]))

# ---- NEG: harvested q67th2-branch rows from banked corpora ----
negc = collections.Counter()   # collapsed lattice tuple -> count
neg_n = 0
cells = collections.Counter()
dd_neg = collections.Counter()
for fn in sys.argv[1:]:
    for ln in open(fn):
        if "|" not in ln:
            continue
        inpart, rpart = ln.split("|", 1)
        rec = parse_kv(rpart)
        try:
            L = lattice(rec)
        except (KeyError, ValueError):
            continue
        neg_n += 1
        cells[(L["ce"], L["dist"], L["rsh"])] += 1
        dd_neg[L["dd"]] += 1
        key = (L["base"], L["lp"], L["dist"], L["md"], L["crit"],
               L["crit9"], L["bit8"], L["bitbs"])
        negc[key] += 1

print("\n== NEG harvest: %d rows, %d distinct lattice tuples ==" %
      (neg_n, len(negc)))
print("cells (ce,dist,rsh):",
      sorted(cells.items(), key=lambda x: -x[1])[:12])
print("dd NEG histogram:", sorted(dd_neg.items()))
print("dd POS histogram:",
      sorted(collections.Counter(L["dd"] for L in pos).items()))
pcells = collections.Counter((L["ce"], L["dist"], L["rsh"]) for L in pos)
print("POS cells:", sorted(pcells.items()))

# ---- known candidate vectors + grid search ----
def eval_vec(c0, cd, sem):
    npos = sum(1 for L in pos if fire_of(c0, cd, sem, L))
    nneg = 0
    for (base, lp, dist, md, crit, crit9, bit8, bitbs), n in negc.items():
        L = dict(base=base, lp=lp, dist=dist, md=md, crit=crit,
                 crit9=crit9, bit8=bit8, bitbs=bitbs)
        if fire_of(c0, cd, sem, L):
            nneg += n
    return npos, nneg

print("\n== known dn-th2 vectors ==")
for name, c0, cd in (("shared(18,-6)", 18, -6), ("q66lo(12,-3)", 12, -3)):
    for sem in ("V0", "V1", "V2", "V3"):
        npos, nneg = eval_vec(c0, cd, sem)
        print("%-14s %s: POS %d/%d  NEG-fire %d" %
              (name, sem, npos, len(pos), nneg))

print("\n== grid search c0 in [-16,40], cd in [-8,8] ==")
best = []
for sem in ("V1", "V2", "V3"):
    for c0 in range(-16, 41):
        for cd in range(-8, 9):
            npos, nneg = eval_vec(c0, cd, sem)
            if npos == len(pos):
                best.append((nneg, sem, c0, cd, npos))
best.sort()
for nneg, sem, c0, cd, npos in best[:15]:
    print("ALL-POS %s c0=%d cd=%d  NEG-fire %d" % (sem, c0, cd, nneg))
if not best:
    print("no vector captures all POS in the grid")
    # closest: max POS
    top = []
    for sem in ("V1", "V2", "V3"):
        for c0 in range(-16, 41):
            for cd in range(-8, 9):
                npos, nneg = eval_vec(c0, cd, sem)
                top.append((-npos, nneg, sem, c0, cd))
    top.sort()
    for negp, nneg, sem, c0, cd in top[:10]:
        print("best-effort %s c0=%d cd=%d  POS %d/%d NEG-fire %d" %
              (sem, c0, cd, -negp, len(pos), nneg))

# ---- pure block-start (no region) probe ----
print("\n== pure bit probes (no region) ==")
for name, f in (
        ("crit&b8&bbs", lambda L: L["crit"] and L["bit8"] and L["bitbs"]),
        ("crit|crit9 & bbs", lambda L: (L["crit"] or L["crit9"]) and L["bitbs"]),
        ("b8&bbs", lambda L: L["bit8"] and L["bitbs"])):
    npos = sum(1 for L in pos if f(L))
    nneg = sum(n for key, n in negc.items()
               if f(dict(base=key[0], lp=key[1], dist=key[2], md=key[3],
                         crit=key[4], crit9=key[5], bit8=key[6],
                         bitbs=key[7])))
    print("%-18s POS %d/%d  NEG %d" % (name, npos, len(pos), nneg))
