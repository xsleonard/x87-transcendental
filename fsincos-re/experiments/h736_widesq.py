#!/usr/bin/env python3
# h736: the wide-square hypothesis on the via=default randv1 rows.
# Chip left product = chop67( (m*m) * odd ) with the square UNCHOPPED
# (model: chop67( chop67(m*m) * odd )).  For each via=default miss:
# does the wide-square left differ from the model's by EXACTLY the
# +1 lsb the bracket demands?  Also compute the same for 'right'
# (fourth from wide square) and check the clean-rate: how often the
# two lefts differ at all (predicts miss density ~2^-10 if this is
# the rule).
import re, subprocess
from fractions import Fraction

def parse_wv(s):
    sg, e2, hx = s.split(":")
    return (int(sg), int(e2), int(hx, 16))

miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), set()).add(m.group(1))
inp = open("/root/h491/randv1_inputs.txt").read().splitlines()
print("%-8s %-5s %-9s | model_left_lsb_delta_under_wide_sq | needed" )
for ln in sorted(miss):
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
        tc = d.get("DI_TC", {}); poly = d.get("DI_POLY", {})
        corr = d.get("DI_CORR", {})
        via = corr.get("via","?")
        mag = parse_wv(poly["mag"]); odd = parse_wv(poly["odd"])
        sq = parse_wv(poly["sq"]); left = parse_wv(tc["left"])
        # model: left = chop67(sq.sig * odd.sig)
        lm_full = sq.__getitem__(2) * odd[2]
        shm = lm_full.bit_length() - 67
        lm = lm_full >> shm
        # wide: m^2 exact then * odd, chopped at the SAME value grid
        wide_full = (mag[2] * mag[2]) * odd[2]
        # align: value = wide_full * 2^(2*mag.e2 + odd.e2)
        # model left value grid: lsb = 2^left.e2
        # wide left at that grid:
        ew = 2*mag[1] + odd[1]
        shift = left[1] - ew
        lw = wide_full >> shift if shift >= 0 else wide_full << -shift
        delta = lw - left[2]
        print("%-8d %-5s %-9s | wide-sq left delta = %+d lsb | (bracket says %s)"
              % (ln, insn, via, delta,
                 "-1 corr-lsb exactly" if ln == 242813 else "see h735"))
