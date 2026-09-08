#!/usr/bin/env python3
# h743: table-kernel (NOCORR) vote forensics via DI_FIN.  For each
# vote with no DI_CORR: take the terminal DI_FIN (L, R, neg),
# replicate v = L + R and the architectural rounding (validated
# against the model), bracket the chip from hw, and express the
# needed delta in R-lsb units (the table-path correction grid).
import subprocess, collections
from fractions import Fraction
import h715_forensics as F

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

votes = collections.defaultdict(dict)
for l in open("h733_votes.txt"):
    t = l.split()
    votes[(t[3], t[4], t[1])][t[2]] = (t[5].split("=")[1], t[6].split("=")[1])
quanta = collections.Counter()
rows = 0; nofin = 0; replfail = 0
det = []
for (se, sig, insn), mm in sorted(votes.items()):
    flag = "--fcos-standalone" if insn == "cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
                       input="%s %s\n" % (se, sig),
                       capture_output=True, text=True)
    di = {}
    fin = None
    for L in p.stderr.splitlines():
        t = L.split()
        if t and t[0] == "DI_FIN":
            fin = t
        elif t and t[0].startswith("DI_") and t[0] != "DI_IN":
            di.setdefault(t[0], True)
    if "DI_CORR" in di: continue          # polynomial-path row, done elsewhere
    rows += 1
    if fin is None:
        nofin += 1; continue
    kv = dict(x.split("=",1) for x in fin[1:])
    Lw = parse_wv(kv["L"]); Rw = parse_wv(kv["R"]); neg = int(kv["neg"])
    v = F.wv_val(Lw) + F.wv_val(Rw)
    vs = -v if neg else v
    mo_line = p.stdout.split()
    if F.round80(vs, "rn").split() != mo_line[1:3]:
        replfail += 1; continue
    mo3 = []
    for mode in ("rn","rd","ru"):
        args = ["./model_h235","--batch",flag]
        if mode != "rn": args.append("--rc="+mode)
        r = subprocess.run(args, input="%s %s\n" % (se, sig),
                           capture_output=True, text=True)
        mo3.append(r.stdout.split()[1:3])
    hw3 = []
    for mi, mode in enumerate(("rn","rd","ru")):
        hw3.append(mm[mode][0].split("/") if mode in mm else mo3[mi])
    iv = None
    for mi, mode in enumerate(("rn","rd","ru")):
        pi = F.preimage(hw3[mi][0], hw3[mi][1], mode)
        iv = pi if iv is None else F.intersect(iv, pi)
    lo, hi, lc, hc = iv
    d_lo = lo - vs; d_hi = hi - vs
    if neg: d_lo, d_hi = -d_hi, -d_lo
    RL = Fraction(2)**Rw[1]
    ql, qh = float(d_lo/RL), float(d_hi/RL)
    tag = "POINT %+.2f" % ql if abs(qh-ql) < 1e-9 else "[%+.2f..%+.2f]" % (ql, qh)
    # quantum sign in R-lsb units
    if abs(qh-ql) < 1e-9: quanta[("POINT", round(ql))] += 1
    else:
        for c in (-1, 1):
            if ql <= c <= qh: quanta[("contains", c)] += 1
    det.append((se, sig, insn, Rw[1]-Lw[1], tag))
for r in det[:25]:
    print(" ".join(str(x) for x in r))
print()
print("table-path rows:", rows, " nofin:", nofin, " replica-fail:", replfail)
print("QUANTA (R-lsb units):")
for k, n in quanta.most_common(10):
    print("  ", k, n)
