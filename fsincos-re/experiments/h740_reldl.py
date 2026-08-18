#!/usr/bin/env python3
# h740: is the B_low cutoff RELATIVE (B_low/2^dl) or absolute?
# Histogram normalized B_low for the |corr|+1 class by dl, plus the
# -1 class's fracL (left-side mirror candidate).
import subprocess, collections, math
def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))
def dump_rows(pairs, flag):
    inp = "\n".join("%s %s" % p for p in pairs) + "\n"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input=inp, capture_output=True, text=True)
    out = []; d = None
    for L in p.stderr.splitlines():
        t = L.split()
        if not t: continue
        if t[0] == "DI_IN":
            if d is not None: out.append(d)
            d = {"IN": (t[1], t[2])}
        elif d is not None and t[0].startswith("DI_"):
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                dd[k] = v
    if d is not None: out.append(d)
    return out
import re
votes = collections.defaultdict(dict)
for l in open("h733_votes.txt"):
    t = l.split()
    votes[(t[3], t[4], t[1])][t[2]] = (t[5].split("=")[1], t[6].split("=")[1])
# needed direction per vote: hw vs mo in the failing mode: compare sigs
rows = []
for insn in ("cos","sin"):
    flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
    pairs = [(k[0],k[1]) for k in votes if k[2]==insn]
    ds = dump_rows(pairs, flag)
    for d, pr in zip(ds, pairs):
        tc = d.get("DI_TC"); corr = d.get("DI_CORR", {})
        if not tc or corr.get("via") != "default": continue
        left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
        dl = left[1] - right[1]
        B_low = right[2] & ((1 << dl) - 1)
        mul = parse_wv(tc["mul"]); lf = parse_wv(tc["lf"])
        lfull = mul[2]*lf[2]; shL = lfull.bit_length()-67
        fracL = (lfull & ((1<<shL)-1)) / float(1<<shL)
        # direction from the vote: hw vs mo sig compare in a miss mode
        mm = votes[(pr[0],pr[1],insn)]
        mode, (hwv, mov) = next(iter(mm.items()))
        hsig = int(hwv.split("/")[1], 16); msig = int(mov.split("/")[1], 16)
        hse = int(hwv.split("/")[0], 16)
        # v smaller in magnitude-of-output terms: compare as values
        neg = (hse >> 15) & 1
        d_out = (hsig - msig) * (-1 if neg else 1)   # +1 => hw value larger
        # v_pre = value/sign... chip corr larger  <=> hw value SMALLER
        # (cos side, i0=0).  d_out=-1 => corrP1 class.
        cls = "corrP1" if d_out < 0 else "corrM1"
        rows.append((cls, dl, B_low, fracL))
c1 = [r for r in rows if r[0]=="corrP1"]
c2 = [r for r in rows if r[0]=="corrM1"]
print("corrP1 (chip |corr| larger):", len(c1), " corrM1:", len(c2))
print("corrP1 by dl: relative B_low = B_low/2^dl as -log2:")
bydl = collections.defaultdict(list)
for _, dl, B, fL in c1:
    bydl[dl].append(B)
for dl in sorted(bydl):
    vals = ["%d(2^-%.1f)" % (B, dl - math.log2(B) if B else 99)
            for B in sorted(bydl[dl])]
    print("  dl=%-3d n=%-3d B_low: %s" % (dl, len(bydl[dl]),
          " ".join(vals[:14])))
print("corrM1 fracL:", " ".join("%.3f" % r[3] for r in sorted(c2, key=lambda r:r[3])))
print("corrM1 (dl,B_low):", [(r[1], r[2]) for r in c2])
