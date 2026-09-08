#!/usr/bin/env python3
# h968: THE VALUE-LAW CENSUS (run on i7 /root/r84).  h967 dissolved
# the mode-blind R94 arm: the band deficit is VALUE-level (hw acts
# as round_rc(v - delta), delta an infinitesimal magnitude deficit)
# and leg visibility is pure rounding arithmetic:
#   - v exactly on the 64-bit output grid  -> magnitude-down modes
#     drop one grid unit ({rz, rd} for +, {rz, ru} for -), the rest
#     absorb;
#   - v at an rn tie that rounded up       -> rn drops to m93(rz);
#   - v anywhere else                      -> invisible.
# This census tests the law EXHAUSTIVELY: every op of every stratum
# with any corpus band-C leg (172 strata, 8,315 ops), model_r93_ref
# x 4 modes + fresh silicon x 4 modes.
#
# PRE-REGISTERED PROTOCOL (before first run):
#   split ops by md5(insn:op) low-bit -> FIT / HOLDOUT halves.
#   Stratum ACCEPTED on the fit half iff: zero OTHER ops, zero
#   CLEAN-EXPOSED ops (on-grid ops the law says must change but
#   didn't), >= 2 exposed (deficit or tie) fit ops, all law-perfect.
#   HOLDOUT BAR (all must hold, else the law/table is refuted):
#     across accepted strata: 100% law-match on holdout exposed
#     ops, zero CLEAN-EXPOSED, zero OTHER, and >= 100 aggregate
#     holdout deficit legs.
import hashlib, pickle, subprocess, sys
from collections import Counter, defaultdict

band = set()
for ln in open("h963_strata.tsv"):
    t = ln.rstrip("\n").split("\t")
    if t[0] == "act":
        continue
    if int(t[5]) >= 1:
        band.add(tuple(int(x) for x in t[:5]))
print("band strata:", len(band))

strata = pickle.load(open("h963_op_strata.pkl", "rb"))
sel = sorted((insn, op) for (insn, op), st in strata.items()
             if st in band)
stmap = {k: strata[k] for k in sel}
del strata
print("ops:", len(sel))

byinsn = defaultdict(list)
for insn, op in sel:
    byinsn[insn].append(op)

MODES = ("rn", "rd", "ru", "rz")

def runm(model, insn, mode, ops):
    fl = "--fsin-standalone" if insn == "sin" else "--fcos-standalone"
    args = [model, "--batch", fl]
    if mode != "rn":
        args.insert(2, "--rc=" + mode)
    p = subprocess.run(args, input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    out = [tuple(l.split()[1:3]) for l in p.stdout.splitlines()]
    assert len(out) == len(ops)
    return out

def runhw(insn, mode, ops):
    p = subprocess.run(["/root/x87_capture_x86_64", mode, insn],
                       input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    rows = []
    for l in p.stdout.splitlines():
        t = l.split()
        rows.append(tuple(t[1:3]) if t and t[0] == "OK"
                    else ("WEIRD", l))
    assert len(rows) == len(ops)
    return rows

def dec1(v):
    se, sig = int(v[0], 16), int(v[1], 16)
    if sig == 0x8000000000000000:
        return ("%04x" % ((se & 0x8000) | (((se & 0x7FFF) - 1) & 0x7FFF)),
                "ffffffffffffffff")
    return ("%04x" % se, "%016x" % (sig - 1))

M = {}   # (insn, mode) -> list
H = {}
for insn, ops in sorted(byinsn.items()):
    for mode in MODES:
        M[(insn, mode)] = runm("./model_r93_ref", insn, mode, ops)
        H[(insn, mode)] = runhw(insn, mode, ops)
        print("ran", insn, mode, file=sys.stderr)

out = open("h968_ops.tsv", "w")
out.write("insn\top\tact\tsum8\td\tme2\tg\thalf\tcls\tongrid\tsign\t"
          "chg\t" + "\t".join("m_%s\th_%s" % (m, m) for m in MODES)
          + "\n")
scnt = defaultdict(Counter)
othersample = []
for insn, ops in sorted(byinsn.items()):
    for i, op in enumerate(ops):
        st = stmap[(insn, op)]
        m4 = {md: tuple(x.lower() for x in M[(insn, md)][i])
              for md in MODES}
        h4 = {md: tuple(x.lower() for x in H[(insn, md)][i])
              for md in MODES}
        half = ("FIT" if hashlib.md5(("%s:%s" % (insn, op)).encode())
                .digest()[0] & 1 == 0 else "HOL")
        if any(h4[md][0] == "weird" for md in MODES):
            cls = "WEIRD"
            ongrid = sign = -1
            chg = ""
        else:
            ongrid = int(len(set(m4.values())) == 1)
            sign = (int(m4["rn"][0], 16) >> 15) & 1
            down = ("rz", "ru" if sign else "rd")
            chgset = frozenset(md for md in MODES if h4[md] != m4[md])
            chg = ",".join(sorted(chgset))
            valok = all(h4[md] == dec1(m4[md]) for md in chgset)
            if not chgset:
                cls = "CLEANEXP" if ongrid else "CLEAN"
            elif (ongrid and chgset == frozenset(down) and valok):
                cls = "DEFICIT"
            elif (not ongrid and chgset == frozenset(("rn",))
                  and h4["rn"] == m4["rz"]):
                cls = "TIE"
            else:
                cls = "OTHER"
                if len(othersample) < 60:
                    othersample.append((insn, op, st, sign, ongrid,
                                        chg, m4, h4))
        scnt[st][(half, cls)] += 1
        out.write("\t".join(map(str, (
            insn, op, st[0], st[1], st[2], st[3], st[4], half, cls,
            ongrid, sign, chg,
            *(x for md in MODES for x in
              (m4[md][0] + ":" + m4[md][1],
               h4[md][0] + ":" + h4[md][1]))))) + "\n")
out.close()

# fit-half acceptance
accepted = []
for st in sorted(scnt):
    c = scnt[st]
    fother = c[("FIT", "OTHER")]
    fclean = c[("FIT", "CLEANEXP")]
    fexp = c[("FIT", "DEFICIT")] + c[("FIT", "TIE")]
    if fother == 0 and fclean == 0 and fexp >= 2:
        accepted.append(st)

# holdout bar on accepted strata
hexp = hdef = hclean = hother = 0
for st in accepted:
    c = scnt[st]
    hdef += c[("HOL", "DEFICIT")]
    hexp += c[("HOL", "DEFICIT")] + c[("HOL", "TIE")]
    hclean += c[("HOL", "CLEANEXP")]
    hother += c[("HOL", "OTHER")]
# deficit legs = 2 per deficit op (two down modes), 1 per tie op
hdeflegs = 2 * hdef + (hexp - hdef)

print("\n== per-stratum (half, cls) counts ==")
for st in sorted(scnt):
    tag = " ACC" if st in accepted else ""
    print(st, dict(scnt[st]), tag)
print("\n== OTHER sample (first 60) ==")
for r in othersample:
    print(r[:6])
    for md in MODES:
        print("   ", md, "m=", r[6][md], "h=", r[7][md])
print("\naccepted strata (fit-half):", len(accepted))
print("HOLDOUT: exposed=%d deficit_ops=%d cleanexp=%d other=%d "
      "deficit_legs=%d" % (hexp, hdef, hclean, hother, hdeflegs))
verdict = (hclean == 0 and hother == 0 and hdeflegs >= 100)
print("HOLDOUT BAR:", "PASS" if verdict else "FAIL")
pickle.dump({st: dict(scnt[st]) for st in accepted},
            open("h968_table_v2.pkl", "wb"))
