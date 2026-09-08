#!/usr/bin/env python3
# h735: h715-style exact forensics on the randv1 miss rows.
# Per row (missing insn): replica-validate the model output from the
# dumped correction, bracket the chip value from the 3-mode hw
# outputs, express the needed delta in units of the correction lsb
# (2^corr.e2), the right-product lsb (UL=2^right.e2), and the
# left-product lsb (2^left.e2) — then test the NEAR-FULL-DISCARD
# CARRY hypothesis: delta == +left_lsb iff left discard top bits
# all-ones; delta == -right_lsb (borrow... sign per algebra) iff
# right discard near-full.
import re, subprocess
from fractions import Fraction
import h715_forensics as F

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
lns = sorted(miss)
hw = {}; mo = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        h = {}; mm = {}
        for i, l in enumerate(open(f"/root/h491/randv1_{insn}_{mode}_hw_status.txt")):
            if i in miss: h[i] = l.split()
        hw[(insn,mode)] = h
print("%-8s %-5s %-9s %2s %2s | %-18s | %-16s | %s" %
      ("line","insn","via","dl","  ","delta in corr-lsb","in right-lsb(UL)","near-full test"))
for ln in lns:
    se, sig = inp[ln].split()
    for insn in sorted(miss[ln]):
        flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
        p = subprocess.run(["./model_h235","--batch",flag,"--dump-internals"],
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
        corr = d.get("DI_CORR", {})
        tc = d.get("DI_TC", {})
        poly = d.get("DI_POLY", {})
        via = corr.get("via", "?")
        cw = parse_wv(corr["out"])
        c_val = F.wv_val(cw)
        v_pre = 1 + c_val
        i0 = int(poly.get("i0", "0"))
        rsn = int(poly.get("rsn", "0"))
        # model output replica: determine sign choice by matching mo
        mo_line = p.stdout.strip().split()
        neg = None
        for cand in (0, 1):
            vs = -v_pre if cand else v_pre
            if F.round80(vs, "rn").split() == mo_line[1:3]:
                neg = cand; break
        if neg is None:
            print(ln, insn, "REPLICA SIGN FAIL", mo_line); continue
        vs0 = -v_pre if neg else v_pre
        ok = True
        # bracket from hw
        iv = None
        for mi, mode in enumerate(("rn","rd","ru")):
            hwl = hw[(insn,mode)][ln]
            pi = F.preimage(hwl[1], hwl[2], mode)
            iv = pi if iv is None else F.intersect(iv, pi)
        lo, hi, lc, hc = iv
        d_lo = lo - vs0; d_hi = hi - vs0
        if neg: d_lo, d_hi = -d_hi, -d_lo
        # units
        left = parse_wv(tc["left"]); right = parse_wv(tc["right"])
        UL = Fraction(2)**right[1]
        LLSB = Fraction(2)**left[1]
        CL = Fraction(2)**cw[1]
        dl = left[1] - right[1]
        # near-full discard analysis
        mul = parse_wv(tc["mul"]); lf = parse_wv(tc["lf"])
        rf = parse_wv(tc["rf"]); f4 = parse_wv(tc["f4"])
        lfull = mul[2] * lf[2]; shL = lfull.bit_length() - 67
        discL = lfull & ((1 << shL) - 1)
        rfull = f4[2] * rf[2]; shR = rfull.bit_length() - 67
        discR = rfull & ((1 << shR) - 1)
        fracL = discL / float(1 << shL); fracR = discR / float(1 << shR)
        # delta in v_pre space; corr = -(|left|-|right|):
        # left carry (+1 left-lsb to |left|) => corr more negative =>
        # v_pre -LLSB; right carry => v_pre +UL
        cells = "dv=[%+.2f..%+.2f]cl" % (float(d_lo/CL), float(d_hi/CL))
        ulc = "[%+.3f..%+.3f]UL" % (float(d_lo/UL), float(d_hi/UL))
        tests = []
        if d_lo <= -LLSB <= d_hi:
            tests.append("LEFTCARRY(fracL=%.3f)" % fracL)
        if d_lo <= UL <= d_hi:
            tests.append("RIGHTCARRY(fracR=%.3f)" % fracR)
        if not tests:
            tests.append("neither(fL=%.2f fR=%.2f)" % (fracL, fracR))
        print("%-8d %-5s %-9s %2d    | %-18s | %-16s | %s" %
              (ln, insn, via, dl, cells, ulc, " ".join(tests)))
