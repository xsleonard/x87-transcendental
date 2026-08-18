#!/usr/bin/env python3
# h729: classify the randv1 mismatches.  Per operand: which insn/
# modes missed, hw/mo outputs, reduced-argument distance to the
# nearest k*pi/2 (stress-slice vs natural), and for rows reaching
# the cos-kernel gate (DI_R59 present) the exact +-1 retained-lsb
# test in all modes (h715c logic).
import re, subprocess
from fractions import Fraction
import h715_forensics as F

PI_FRAC = int(
    "243F6A8885A308D313198A2E03707344A4093822299F31D0082EFA98EC4E6C89"
    "452821E638D01377BE5466CF34E90C6CC0AC29B7C97C50DD3F84D5B5B5470917", 16)
PI = Fraction((3 << 512) | PI_FRAC, 1 << 512)

miss = {}
for l in open("h728.log"):
    m = re.match(r"MISMATCH (\w+) (\w+) line (\d+)", l)
    if m: miss.setdefault(int(m.group(3)), []).append((m.group(1), m.group(2)))
inp = open("randv1_inputs.txt").read().splitlines()
hw = {}; mo = {}
for insn in ("cos","sin"):
    for mode in ("rn","rd","ru"):
        hw[(insn,mode)] = open(f"randv1_{insn}_{mode}_hw.txt")
        mo[(insn,mode)] = open(f"randv1_{insn}_{mode}_mo.txt")
# stream to the needed lines
want = sorted(miss)
vals = {k: {} for k in want}
for key in hw:
    hlines = hw[key].read().splitlines(); mlines = mo[key].read().splitlines()
    for ln in want:
        vals[ln][key] = (hlines[ln], mlines[ln])

def x_of(se_hex, sig_hex):
    se = int(se_hex,16); sig = int(sig_hex,16)
    E = (se & 0x7fff) - 0x3fff
    return Fraction(sig, 1 << 63) * Fraction(2)**E

for ln in want:
    se, sig = inp[ln].split()
    x = x_of(se, sig)
    q = x / (PI/2)
    k = int(q + Fraction(1,2))
    dist = float(abs(x - k*(PI/2)))
    import math
    ld = math.log2(dist) if dist > 0 else float("-inf")
    print("line %-8d %s %s  |x-k*pi/2| ~ 2^%.1f (k=%d)  misses=%s"
          % (ln, se, sig, ld, k, vals[ln] and miss[ln]))
    for insn in ("cos","sin"):
        flag = "--fcos-standalone" if insn=="cos" else "--fsin-standalone"
        p = subprocess.run(["./model_di","--batch",flag,"--dump-internals"],
            input="%s %s\n" % (se, sig), capture_output=True, text=True)
        di = p.stderr
        has_r59 = "DI_R59" in di
        if not any(i==insn for i,mm in miss[ln]): continue
        # gate test for rows with DI_R59: +-1 RU reproduction vs hw
        if has_r59:
            r59 = {}
            for lline in di.splitlines():
                if lline.startswith("DI_R59"):
                    for kv in lline.split()[1:]:
                        kk, vv = kv.split("=",1)
                        r59[kk] = vv
                if lline.startswith("DI_POLY"):
                    poly = dict(kv.split("=",1) for kv in lline.split()[1:])
                if lline.startswith("DI_CORR") or lline.startswith("DI_BR"):
                    last_corr = lline
            m2 = re.search(r"out=(\d+:-?\d+:[0-9a-f]+)", last_corr)
            cw = tuple(int(v,16) if i==2 else int(v)
                       for i,v in enumerate(m2.group(1).split(":")))
            v_pre = 1 + F.wv_val(cw)
            i0 = int(poly.get("i0","0"))
            RU = Fraction(2)**(int(r59["rscale"]) + int(r59["k"]))
            verdict = []
            for j in (-1, 1):
                vp = v_pre + j*RU
                vs = -vp if i0 else vp
                # sin path: output sign handled by residual_sign upstream;
                # compare magnitudes against hw with model's sign
                ok = True
                for mi, mode in enumerate(("rn","rd","ru")):
                    hwl = vals[ln][(insn,mode)][0].split()
                    rep = F.round80(vs, mode).split()
                    if rep[1] != hwl[2] or rep[0][-3:] != hwl[1][-3:]:
                        ok = False
                if ok: verdict.append("%+d" % j)
            th = r59.get("theta")
            print("    %s: GATE row theta=%s branch-dump ok; +-1RU all-mode fit: %s"
                  % (insn, th, verdict if verdict else "NONE"))
        else:
            print("    %s: NO DI_R59 (non-gate path — sine kernel or other)" % insn)
