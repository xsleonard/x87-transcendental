#!/usr/bin/env python3
# h976: THE BORROW-DEPTH QUESTION.  h975 reduced the band to: hw
# sometimes takes the exact-tail borrow/carry (nhw == nexact) and
# sometimes ignores it (nhw == ncar), at the same coordinates.  If
# hw's tail adder is width-limited, taking should correlate with
# how DEEP the true value crosses the grid line.  For every pinned
# borrow-opportunity op (nexact != ncar), compute the exact
# crossing depth and tabulate took/ignored against it (and the
# usual coordinates).
import sys
from collections import Counter, defaultdict

MODES = ("rn", "rd", "ru", "rz")

feat = {}
for ln in open("h970_features.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        ix = {c: i for i, c in enumerate(t)}
        continue
    feat[(t[0], t[1])] = t
nhw = {}
for ln in open("h975_nhw.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "insn":
        jx = {c: i for i, c in enumerate(t)}
        continue
    if t[jx["pinned"]] == "1":
        nhw[(t[0], t[1])] = int(t[jx["nset"]])
corr = {}
for ln in open("h972_corr.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] != "insn":
        corr[(t[0], t[1])] = t

hist = defaultdict(Counter)
coord = defaultdict(Counter)
rows = []
for k, n in sorted(nhw.items()):
    t = feat[k]
    c = corr[k]
    g = lambda col: t[ix[col]]
    mulsig, lfsig = int(g("mulsig"), 16), int(g("lfsig"), 16)
    rfsig, f4sig = int(g("rfsig"), 16), int(g("f4sig"), 16)
    ls, rs = int(g("leftsign")), int(g("rightsign"))
    le2, re2 = int(g("lefte2")), int(g("righte2"))
    PL, PR = mulsig * lfsig, f4sig * rfsig
    shL, shR = PL.bit_length() - 67, PR.bit_length() - 67
    dL, dR = PL & ((1 << shL) - 1), PR & ((1 << shR) - 1)
    pay = int(g("pay2")) if g("pay2") not in ("-",) else 0
    b2 = min(le2 - shL, re2 - shR, le2 - 8) - 6
    A = (-1) ** ls * (int(g("leftsig"), 16) << (le2 - b2)) \
        + (-1) ** rs * (int(g("rightsig"), 16) << (re2 - b2))
    if pay:
        A += (-1) ** (ls ^ (pay < 0)) * (abs(pay) << (le2 - 8 - b2))
    TL = (-1) ** ls * (dL << (le2 - shL - b2))
    TR = (-1) ** rs * (dR << (re2 - shR - b2))
    def chop(x):
        m = -x if x < 0 else x
        w = m.bit_length()
        ch = (m >> (w - 67)) << (w - 67)
        return (-ch if x < 0 else ch), 1 << (w - 67)
    chval, ulp67 = chop(A)
    ex, uex = chop(A + TL + TR)
    nexact = round((ex - chval) / ulp67)
    cs, ce2, csig = int(c[5]), int(c[6]), int(c[7], 16)
    corrval = (-1) ** cs * (csig << (ce2 - b2))
    ncar = (corrval - chval) // ulp67
    if nexact == ncar:
        continue                    # no opportunity: nothing to decide
    took = (n == nexact)
    ignored = (n == ncar)
    lab = "TOOK" if took else ("IGN" if ignored else "OTHERN")
    # depth: distance (in ulp67) from the TRUE value to the chop-
    # lattice boundary separating the nexact outcome from the ncar
    # outcome.  t_true always lies in the nexact region; small
    # depth = the decision was close.  Frame-proof: value-side
    # chop regions are [chval+j*u, chval+(j+1)*u) for positive
    # values and (chval+(j-1)*u, chval+j*u] for negative.
    t_true = A + TL + TR
    step = 1 if ncar > nexact else -1
    if t_true > 0:
        B = chval + (nexact + (1 if step > 0 else 0)) * ulp67
    else:
        B = chval + (nexact + (0 if step > 0 else -1)) * ulp67
    depth = abs(t_true - B) / ulp67
    side = "%+d->%+d" % (ncar, nexact)
    bin_ = "%.1f" % (int(depth * 10) / 10)
    if depth < 0.001:
        bin_ = "<.001"
    elif depth < 0.01:
        bin_ = "<.01"
    elif depth < 0.1:
        bin_ = "<.1"
    hist[(side, lab)][bin_] += 1
    coord[(side, lab)][("act" + g("act"),
                        "rud" + g("rud"), "rsh" + g("rsh"),
                        "ls%d" % ls)] += 1
    rows.append((side, lab, round(depth, 6), g("act"), g("sum8"),
                 g("d"), g("me2"), g("g"), g("low3"), ls, rs,
                 g("rsh"), g("rud")))

print("== depth histogram by (side, verdict) ==")
for kk in sorted(hist):
    print(kk, dict(sorted(hist[kk].items())))
print("\n== coordinates by (side, verdict) (top) ==")
for kk in sorted(coord):
    print(kk)
    for cc, n in coord[kk].most_common(8):
        print("   ", cc, n)
w = open("h976_rows.tsv", "w")
w.write("side\tverdict\tdepth\tact\tsum8\td\tme2\tg\tlow3\tls\trs\t"
        "rsh\trud\n")
for r in rows:
    w.write("\t".join(map(str, r)) + "\n")
w.close()
print("\nrows written:", len(rows))
