#!/usr/bin/env python3
# h715 (T1/T2, 2026-08-18): theta-band forensics on the R69 residual.
# Inputs: h714_hw3.txt (hw/model outputs, all 3 modes, per operand)
#         h714_dump.txt (DI_* internals from model_di --dump-internals)
# Per operand: parse internals, rebuild the model's pre-round value
# v = 1 - c exactly (Fraction), VERIFY the replica reproduces the
# model's 3-mode outputs, then intersect the chip's 3-mode preimage
# intervals to bracket the chip's value, and derive the needed
# direction + exact delta interval.  T1: correlate direction with
# the sign-chain/classifier fields.  T2: compare the delta interval
# against the predicted effect of a 1-ULP odd/even nudge.
import re, sys
from fractions import Fraction

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

def wv_val(w):
    sg, e2, sig = w
    v = Fraction(sig) * Fraction(2)**e2
    return -v if sg else v

def parse_dump(path):
    ops = {}
    cur = None
    for line in open(path):
        t = line.split()
        if not t: continue
        if t[0] == "DI_IN":
            cur = (t[1], t[2]); ops[cur] = {"in": cur}
        elif cur is None:
            continue
        elif t[0] == "DI_POLY":
            d = ops[cur].setdefault("poly", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = parse_wv(v) if ":" in v else int(v) if v.lstrip("-").isdigit() else v
        elif t[0] == "DI_TC":
            d = ops[cur].setdefault("tc", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = parse_wv(v) if ":" in v else (int(v) if v.lstrip("-").isdigit() else v)
        elif t[0] == "DI_R59":
            d = ops[cur].setdefault("r59", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = int(v) if v.lstrip("-").isdigit() else int(v, 16)
        elif t[0] == "DI_CRIT":
            d = ops[cur].setdefault("crit", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = v if k == "at" else int(v)
        elif t[0] == "DI_BS":
            d = ops[cur].setdefault("bs", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = int(v)
        elif t[0] == "DI_BR":
            d = ops[cur].setdefault("br", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = parse_wv(v) if k == "out" else (v if k in ("br",) else (v if "," in v else int(v, 16) if not v.lstrip("-").isdigit() else int(v)))
        elif t[0] == "DI_CORR":
            d = ops[cur].setdefault("corr", {})
            for kv in t[1:]:
                k, v = kv.split("=")
                d[k] = parse_wv(v) if k == "out" else (int(v) if v.lstrip("-").isdigit() else v)
    return ops

# ---- x87 extended (15-bit exp, 64-bit sig) grid helpers ----
def out_val(se_hex, sig_hex):
    if se_hex == "C2": return None
    se = int(se_hex, 16); sig = int(sig_hex, 16)
    s = (se >> 15) & 1; E = (se & 0x7fff) - 0x3fff
    v = Fraction(sig) * Fraction(2)**(E - 63)
    return -v if s else v

def grid_next_up(se, sig):
    s = (se >> 15) & 1
    if s == 0:
        sig += 1
        if sig == 1 << 64: sig = 1 << 63; se += 1
    else:
        sig -= 1
        if sig < 1 << 63:
            sig = (1 << 64) - 1; se -= 1
    return se, sig

def grid_next_down(se, sig):
    s = (se >> 15) & 1
    if s == 0:
        sig -= 1
        if sig < 1 << 63:
            sig = (1 << 64) - 1; se -= 1
    else:
        sig += 1
        if sig == 1 << 64: sig = 1 << 63; se += 1
    return se, sig

def hex_val(se, sig):
    s = (se >> 15) & 1; E = (se & 0x7fff) - 0x3fff
    v = Fraction(sig) * Fraction(2)**(E - 63)
    return -v if s else v

def preimage(se_hex, sig_hex, mode):
    """value-space interval (lo, hi, lo_closed, hi_closed) mapping to
    this output under mode"""
    se = int(se_hex, 16); sig = int(sig_hex, 16)
    o = hex_val(se, sig)
    up = hex_val(*grid_next_up(se, sig))
    dn = hex_val(*grid_next_down(se, sig))
    if mode == "rd":   # largest grid <= v
        return (o, up, True, False)
    if mode == "ru":   # smallest grid >= v
        return (dn, o, False, True)
    lo = o - (o - dn) / 2; hi = o + (up - o) / 2
    even = (sig & 1) == 0
    return (lo, hi, even, even)

def intersect(a, b):
    lo, hi, lc, hc = a; lo2, hi2, lc2, hc2 = b
    if lo2 > lo or (lo2 == lo and not lc2): lo, lc = lo2, lc2
    if hi2 < hi or (hi2 == hi and not hc2): hi, hc = hi2, hc2
    return (lo, hi, lc, hc)

def round80(v, mode):
    """round Fraction v to the x87 grid; returns (se, sig) hexes"""
    s = 1 if v < 0 else 0
    a = -v if s else v
    E = a.numerator.bit_length() - a.denominator.bit_length()
    while Fraction(2)**E > a: E -= 1
    while Fraction(2)**(E+1) <= a: E += 1
    q = a / Fraction(2)**(E - 63)
    sig = q.numerator // q.denominator
    rem = q - sig
    inc = 0
    if mode == "rn":
        inc = rem > Fraction(1,2) or (rem == Fraction(1,2) and sig & 1)
    elif mode == "ru":
        inc = (not s) and rem > 0
    elif mode == "rd":
        inc = s and rem > 0
    if inc:
        sig += 1
        if sig == 1 << 64: sig = 1 << 63; E += 1
    se = (0x3fff + E) | (0x8000 if s else 0)
    return "%04x %016x" % (se, sig)

def main():
    dump = parse_dump("h714_dump.txt")
    rows = []
    for line in open("h714_hw3.txt"):
        left, h3, m3 = line.strip().split(" | ")
        se, sig, corp, lineno = left.split()
        hw = [x.split("/") for x in h3.split()]
        mo = [x.split("/") for x in m3.split()]
        rows.append((se, sig, corp, int(lineno), hw, mo))
    print("=" * 78)
    print("%-4s %-18s %-6s %3s %2s/%2s %2s %3s %2s %2s %2s %-7s %-4s %3s"
          % ("se", "sig", "corp", "th", "s4", "sd", "i0", "low3",
             "b1", "b2", "d", "branch", "dir", "n_ulp"))
    t1 = []
    for se, sig, corp, lineno, hw, mo in rows:
        d = dump.get((se, sig))
        if d is None:
            print(se, sig, corp, "NO DUMP RECORD"); continue
        poly = d.get("poly", {}); r59 = d.get("r59", {})
        corr = d.get("corr", {}); tc = d.get("tc", {}); br = d.get("br", {})
        via = corr.get("via", "?")
        branch = br.get("br", via)
        i0 = poly.get("i0")
        site = poly.get("site", "?")
        cw = corr.get("out") or br.get("out")
        if cw is None:
            print(se, sig, corp, "NO CORR"); continue
        c_val = wv_val(cw)
        v_pre = 1 + c_val
        v_signed = -v_pre if i0 else v_pre
        # replica check: all three modes must reproduce the model
        ok = True
        for mi, m in enumerate(("rn", "rd", "ru")):
            rep = round80(v_signed, m)
            want = "%s %s" % (mo[mi][0], mo[mi][1])
            if rep != want:
                ok = False
                print(se, sig, corp, "REPLICA MISMATCH", m, rep, want)
        if not ok: continue
        # chip bracket
    	# (C2 rows would need special handling; none expected)
        iv = None
        for mi, m in enumerate(("rn", "rd", "ru")):
            pi = preimage(hw[mi][0], hw[mi][1], m)
            iv = pi if iv is None else intersect(iv, pi)
        lo, hi, lc, hc = iv
        if v_signed < lo or (v_signed == lo and not lc):
            dir_signed = +1
        elif v_signed > hi or (v_signed == hi and not hc):
            dir_signed = -1
        else:
            dir_signed = 0   # model inside chip interval?! (impossible for a miss)
        dir_pre = -dir_signed if i0 else dir_signed
        dir_odd = -dir_pre   # odd.sig +1 lowers v_pre
        # delta interval in v_pre space
        d_lo = (lo - v_signed); d_hi = (hi - v_signed)
        if i0: d_lo, d_hi = -d_hi, -d_lo
        # predicted 1-ulp-odd effect on v_pre: sq * 2^odd.e2 (sign: odd+1 => v_pre down)
        sq = poly.get("sq"); odd = poly.get("odd"); even = poly.get("even")
        pred_odd = wv_val(sq) * Fraction(2)**odd[1] if sq and odd else None
        pred_even = wv_val(d.get("poly", {}).get("f4")) * Fraction(2)**even[1] if even else None
        n_ulp = ""
        if pred_odd:
            r_lo = float(abs(d_lo) / pred_odd); r_hi = float(abs(d_hi) / pred_odd)
            n_ulp = "%.2f..%.2f" % (min(r_lo, r_hi), max(r_lo, r_hi))
        theta = r59.get("theta")
        t1.append(dict(se=se, sig=sig, corp=corp, theta=theta,
                       s4=r59.get("s4"), side=r59.get("side"), i0=i0,
                       low3=r59.get("low3"), b1=r59.get("b1"),
                       b2=r59.get("b2"), dist=r59.get("dist"),
                       rsh=r59.get("rsh"), ce=r59.get("ce"),
                       branch=branch, site=site, dir_pre=dir_pre,
                       dir_odd=dir_odd, n_ulp=n_ulp,
                       d_lo=d_lo, d_hi=d_hi, pred_odd=pred_odd,
                       fire=br.get("fire"), in_region=br.get("in_region"),
                       crit=d.get("crit", {}).get("crit"),
                       pm=d.get("crit", {}).get("pm"),
                       phw=d.get("crit", {}).get("phw")))
        print("%-4s %-18s %-6s %3s %2s/%2s %2s %3s %2s %2s %2s %-7s %+4d %s"
              % (se, sig[-6:], corp, theta, r59.get("s4"), r59.get("side"),
                 i0, r59.get("low3"), r59.get("b1"), r59.get("b2"),
                 r59.get("dist"), branch, dir_odd, n_ulp))
    # ---- T1 correlation: theta!=0 rows ----
    print("=" * 78)
    band = [r for r in t1 if r["theta"] not in (None, 0)]
    print("T1 CORRELATION (theta!=0 rows, n=%d): dir_odd vs sign-chain"
          % len(band))
    for key in ("theta", "s4", "side", "i0", "low3", "b1", "b2",
                "dist", "rsh", "ce", "branch", "fire", "crit", "pm",
                "site", "corp"):
        cnt = {}
        for r in band:
            kk = (r.get(key), r["dir_odd"])
            cnt[kk] = cnt.get(kk, 0) + 1
        parts = []
        vals = sorted(set(k[0] for k in cnt), key=lambda x: (x is None, str(x)))
        clean = True
        for v in vals:
            p = cnt.get((v, +1), 0); m = cnt.get((v, -1), 0)
            parts.append("%s:%d+/%d-" % (v, p, m))
            if p and m: clean = False
        print("  %-7s %s%s" % (key, "  ".join(parts),
                               "   <== CLEAN SPLIT" if clean and len(vals) > 1 else ""))
    # sign(theta) explicitly
    cnt = {}
    for r in band:
        kk = (1 if r["theta"] > 0 else -1, r["dir_odd"])
        cnt[kk] = cnt.get(kk, 0) + 1
    p1, m1 = cnt.get((1, 1), 0), cnt.get((1, -1), 0)
    p2, m2 = cnt.get((-1, 1), 0), cnt.get((-1, -1), 0)
    clean = not ((p1 and m1) or (p2 and m2))
    print("  %-7s dn(+):%d+/%d-  up(-):%d+/%d-%s"
          % ("sgn_th", p1, m1, p2, m2,
             "   <== CLEAN SPLIT" if clean else ""))
    print("=" * 78)
    print("theta==0 rows and non-band rows:")
    for r in t1:
        if r["theta"] in (None, 0):
            print("  %s %s %s th=%s br=%s dir_odd=%+d %s"
                  % (r["se"], r["sig"], r["corp"], r["theta"],
                     r["branch"], r["dir_odd"], r["n_ulp"]))
    import pickle
    pickle.dump(t1, open("h715_t1.pkl", "wb"))
    print("wrote h715_t1.pkl")

main()
