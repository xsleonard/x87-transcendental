#!/usr/bin/env python3
"""Pin Delta(r) = T_hw - T_ref per fine r-bin by intersecting interval
constraints from RN+RD captures; output the curve for sin and cos sides."""
import sys
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
NB = 210   # r-bins over [0.125, 0.7855]
def rbin(r): return min(NB-1, int((r - 0.125) / (0.7855 - 0.125) * NB))

def dec_int(se, sig):
    if sig == 0: return 0, 0
    s = -1 if se >> 15 else 1
    return s * sig, (se & 0x7FFF) - 16383 - 63

inputs = open(f"{SCR}/dense_qn.txt").read().split("\n")
dump   = open(f"{SCR}/dense_ref_dump.txt").read().split("\n")
hw_rn  = open(f"{SCR}/dense_rn.txt").read().split("\n")
hw_rd  = open(f"{SCR}/dense_rd.txt").read().split("\n")

# per (side, rbin): running intersection [lo, hi] as Fractions of 2^-80 ints
LO = defaultdict(lambda: None); HI = defaultdict(lambda: None)
CNT = defaultdict(int); EMPTY = defaultdict(int)
SC = 80  # store bounds as integer multiples of 2^-SC (scaled)

di = 0
for li, line in enumerate(inputs):
    if not line.strip(): continue
    se, sig = int(line[:4],16), int(line[5:21],16)
    e = (se & 0x7FFF) - 16383
    r_abs = sig * 2.0**(e-63)
    rb = rbin(r_abs)
    fs = dump[di].split(); fc = dump[di+1].split(); di += 3
    rn_f = hw_rn[li].split(); rd_f = hw_rd[li].split()
    for side, fld in (("sin", fs), ("cos", fc)):
        a_n, a_e = dec_int(int(fld[1],16), int(fld[2],16))
        b_n, b_e = dec_int(int(fld[3],16), int(fld[4],16))
        E = min(a_e, b_e)
        T = a_n * (1 << (a_e - E)) + b_n * (1 << (b_e - E))
        if T == 0: continue
        neg = T < 0
        aT = abs(T)
        bl = aT.bit_length() - 1
        ue = bl - 63
        if ue >= 0: Ti = aT; ulp = 1 << ue; SE = E
        else: Ti = aT << (-ue); ulp = 1; SE = E + ue
        q, rem = divmod(Ti, ulp)
        idx = 1 if side == "sin" else 3
        hn_n, hn_e = dec_int(int(rn_f[idx],16), int(rn_f[idx+1],16))
        hd_n, hd_e = dec_int(int(rd_f[idx],16), int(rd_f[idx+1],16))
        sh_n = hn_e - SE; sh_d = hd_e - SE
        if sh_n < 0 or sh_d < 0: continue
        hn = hn_n << sh_n; hd = hd_n << sh_d
        if neg: hn = -hn; hd = -hd
        lower = q * ulp
        # RD (true) on original sign: for pos: floor cell; for neg (mirrored):
        # hd_mirrored acts as ceil.
        # constraints on T_hw (mirrored positive frame):
        # from hd: pos: hd <= T_hw < hd + ulp ; neg-mirrored (ceil): hd - ulp < T_hw <= hd
        if not neg: lo1, hi1 = hd, hd + ulp
        else:       lo1, hi1 = hd - ulp, hd
        # from hn: rn cell: [hn - ulp/2, hn + ulp/2] (2x scale to stay integer)
        lo2x, hi2x = 2*hn - ulp, 2*hn + ulp
        lo = max(2*lo1, lo2x); hi = min(2*hi1, hi2x)   # 2x scale
        if lo > hi: continue
        # Delta*2 = [lo - 2*T, hi - 2*T] at scale 2^SE; rescale to 2^-SC ints
        dlo = (lo - 2*Ti); dhi = (hi - 2*Ti)
        shift = SC + SE + 1   # value = d * 2^(SE-1) -> * 2^SC
        if shift >= 0: dlo <<= shift; dhi <<= shift
        else: dlo >>= -shift; dhi >>= -shift
        k = (side, rb)
        CNT[k] += 1
        if LO[k] is None: LO[k], HI[k] = dlo, dhi
        else:
            nlo, nhi = max(LO[k], dlo), min(HI[k], dhi)
            if nlo > nhi: EMPTY[k] += 1   # keep old (report contamination)
            else: LO[k], HI[k] = nlo, nhi

print("side  r_mid   n    empty  Delta_lo*2^70  Delta_hi*2^70  width*2^80")
for side in ("sin","cos"):
    for rb in range(0, NB, 3):
        k = (side, rb)
        if CNT[k] < 300 or LO[k] is None: continue
        rmid = 0.125 + (rb+0.5)*(0.7855-0.125)/NB
        lo70 = LO[k] / 2**10 / 2**0  # 2^-80 -> *2^70 => /2^10
        hi70 = HI[k] / 2**10
        print(f"{side} {rmid:7.4f} {CNT[k]:5d} {EMPTY[k]:5d} {lo70/1.0:14.4f} {hi70/1.0:14.4f} {HI[k]-LO[k]:10d}")
