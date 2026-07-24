#!/usr/bin/env python3
"""Compare fsincos_ref --batch output against x87_capture output.

usage: compare_runs.py inputs.txt ref_out.txt hw_out.txt

Classifies each input by algorithm path (same rules as the dispatch) and
reports, per path: total, exact-match count, C2 agreement, and ulp-delta
histogram for mismatches (in ulps of the hardware result).
"""
import sys
from collections import defaultdict

def path_of(se, sig):
    e = (se & 0x7FFF) - 16383
    if sig == 0:
        return "zero"
    if (se & 0x7FFF) == 0x7FFF:
        return "special"
    if e >= 63:
        return "C2-range"
    if e >= 24:
        return "large"
    if e >= 0:
        return "moderate"
    # pi/4 = 0x3FFE C90FDAA22168C234...
    if e == -1 and sig >= 0xC90FDAA22168C234:
        return "moderate"
    if e >= -3:
        return "quick-normal"
    return "quick-small"

def val(se, sig):
    if sig == 0:
        return 0.0
    s = -1 if se >> 15 else 1
    return s * sig * 2.0 ** ((se & 0x7FFF) - 16383 - 63)

def ulp_delta(se_a, sig_a, se_b, sig_b):
    """distance in units of b's ulp; None if signs/exponent wildly differ."""
    if se_a == se_b:
        return abs(sig_a - sig_b)
    # adjacent exponents: normalize into b's frame (coarse)
    ea, eb = (se_a & 0x7FFF), (se_b & 0x7FFF)
    if (se_a >> 15) != (se_b >> 15):
        return None
    d = ea - eb
    if abs(d) > 2:
        return None
    va = sig_a * (2.0 ** d)
    return abs(va - sig_b)

def main():
    inputs = [l.split() for l in open(sys.argv[1]) if l.strip()]
    ref = [l.strip() for l in open(sys.argv[2]) if l.strip()]
    hw = [l.strip() for l in open(sys.argv[3]) if l.strip()]
    assert len(inputs) == len(ref) == len(hw), (len(inputs), len(ref), len(hw))

    stats = defaultdict(lambda: {"n": 0, "exact": 0, "c2_ok": 0, "c2_bad": 0,
                                 "sin_diff": defaultdict(int), "cos_diff": defaultdict(int),
                                 "gross": 0, "examples": []})
    for (inp, r, h) in zip(inputs, ref, hw):
        se, sig = int(inp[0], 16), int(inp[1], 16)
        p = path_of(se, sig)
        st = stats[p]
        st["n"] += 1
        if r == h:
            st["exact"] += 1
            if r == "C2":
                st["c2_ok"] += 1
            continue
        if (r == "C2") != (h == "C2"):
            st["c2_bad"] += 1
            if len(st["examples"]) < 5:
                st["examples"].append((inp, r, h))
            continue
        rf, hf = r.split(), h.split()
        ds = ulp_delta(int(rf[1], 16), int(rf[2], 16), int(hf[1], 16), int(hf[2], 16))
        dc = ulp_delta(int(rf[3], 16), int(rf[4], 16), int(hf[3], 16), int(hf[4], 16))
        for name, d in (("sin_diff", ds), ("cos_diff", dc)):
            if d is None:
                st["gross"] += 1
                if len(st["examples"]) < 5:
                    st["examples"].append((inp, r, h))
            elif d > 0:
                b = ("1" if d <= 1 else "2" if d <= 2 else "<=8" if d <= 8
                     else "<=64" if d <= 64 else ">64")
                st[name][b] += 1
                if b == ">64" and len(st["examples"]) < 5:
                    st["examples"].append((inp, r, h))

    total = sum(s["n"] for s in stats.values())
    texact = sum(s["exact"] for s in stats.values())
    print(f"TOTAL {total}  exact-match {texact}  ({100.0*texact/total:.3f}%)\n")
    for p in sorted(stats):
        s = stats[p]
        print(f"[{p}] n={s['n']} exact={s['exact']} ({100.0*s['exact']/s['n']:.2f}%)"
              f" c2_mismatch={s['c2_bad']} gross={s['gross']}")
        if s["sin_diff"]:
            print(f"    sin ulp-diffs: {dict(s['sin_diff'])}")
        if s["cos_diff"]:
            print(f"    cos ulp-diffs: {dict(s['cos_diff'])}")
        for inp, r, h in s["examples"]:
            x = val(int(inp[0], 16), int(inp[1], 16))
            print(f"    ex: x={inp[0]} {inp[1]} ({x:.6g})")
            print(f"        ref {r}")
            print(f"        hw  {h}")
    print()

if __name__ == "__main__":
    main()
