#!/usr/bin/env python3
# h737: process h733 miner votes.  Census -> dumps -> stratify by
# (insn, via/branch, active, theta, ce) -> exact bracket quantum per
# row (in corr-lsb and RU where r59 present).  Runs on partial or
# complete h733_votes.txt.
import subprocess, collections
from fractions import Fraction
import h715_forensics as F

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

votes = collections.defaultdict(dict)   # (se,sig,insn) -> mode -> (hw, mo)
for l in open("h733_votes.txt"):
    t = l.split()
    ck, insn, mode, se, sig = t[0], t[1], t[2], t[3], t[4]
    hwv = t[5].split("=")[1]; mov = t[6].split("=")[1]
    votes[(se, sig, insn)][mode] = (hwv, mov)
print("distinct (operand, insn) votes:", len(votes))
strat = collections.Counter()
quanta = collections.Counter()
rows_out = []
for (se, sig, insn), modes in sorted(votes.items()):
    flag = "--fcos-standalone" if insn == "cos" else "--fsin-standalone"
    p = subprocess.run(["./model_h235", "--batch", flag, "--dump-internals"],
                       input="%s %s\n" % (se, sig),
                       capture_output=True, text=True)
    d = {}
    for L in p.stderr.splitlines():
        t = L.split()
        if t and t[0].startswith("DI_") and t[0] != "DI_IN":
            dd = d.setdefault(t[0], {})
            for kv in t[1:]:
                k, v = kv.split("=", 1)
                dd[k] = v
    corr = d.get("DI_CORR", {}); tc = d.get("DI_TC", {})
    poly = d.get("DI_POLY", {}); r59 = d.get("DI_R59", {})
    br = d.get("DI_BR", {})
    via = corr.get("via", "?")
    branch = br.get("br", via)
    active = tc.get("active", "?")
    theta = r59.get("theta", "-")
    ce = r59.get("ce", "-")
    key = (insn, branch, "act=" + str(active), "th=" + str(theta))
    strat[key] += 1
    # full 3-mode hw needed for brackets: mine only stores the
    # missing modes; run model for all modes and use vote hw where
    # present, model output where the model was correct (hw == mo
    # there by definition of a miss line only in its mode).
    hw3 = []
    for mode in ("rn", "rd", "ru"):
        if mode in modes:
            hw3.append(modes[mode][0].split("/"))
        else:
            args = ["./model_h235", "--batch", flag]
            if mode != "rn": args.append("--rc=" + mode)
            r = subprocess.run(args, input="%s %s\n" % (se, sig),
                               capture_output=True, text=True)
            t = r.stdout.split()
            hw3.append([t[1], t[2]] if t[0] == "OK" else ["C2"])
    cw = parse_wv(corr["out"]) if "out" in corr else None
    if cw is None:
        rows_out.append((se, sig, insn, branch, active, theta, "NOCORR", ""))
        continue
    v_pre = 1 + F.wv_val(cw)
    neg = None
    for cand in (0, 1):
        vs = -v_pre if cand else v_pre
        args = ["./model_h235", "--batch", flag]
        # model rn output for sign calibration
        r = subprocess.run(args, input="%s %s\n" % (se, sig),
                           capture_output=True, text=True)
        t = r.stdout.split()
        if F.round80(vs, "rn").split() == t[1:3]:
            neg = cand; break
    if neg is None:
        rows_out.append((se, sig, insn, branch, active, theta, "SIGNFAIL", ""))
        continue
    vs0 = -v_pre if neg else v_pre
    iv = None
    for mi, mode in enumerate(("rn", "rd", "ru")):
        pi = F.preimage(hw3[mi][0], hw3[mi][1], mode)
        iv = pi if iv is None else F.intersect(iv, pi)
    lo, hi, lc, hc = iv
    d_lo = lo - vs0; d_hi = hi - vs0
    if neg: d_lo, d_hi = -d_hi, -d_lo
    CL = Fraction(2)**cw[1]
    ql, qh = float(d_lo / CL), float(d_hi / CL)
    q = ""
    if abs(qh - ql) < 1e-9:
        q = "POINT %+".replace("%+","") + ("%+.2f" % ql)
        quanta[("POINT", insn, branch, round(ql))] += 1
    else:
        for c in (-1, 1):
            if ql <= c <= qh:
                quanta[("contains%+d" % c, insn, branch)] += 1
    rows_out.append((se, sig, insn, branch, active, theta,
                     "[%+.2f..%+.2f]cl" % (ql, qh), q))
for r in rows_out[:40]:
    print(" ".join(str(x) for x in r))
print()
print("STRATIFICATION:")
for k, n in strat.most_common():
    print("  %-40s %d" % (str(k), n))
print()
print("QUANTA:")
for k, n in quanta.most_common(12):
    print("  %-40s %d" % (str(k), n))
