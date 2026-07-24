#!/usr/bin/env python3
"""Fine Delta(r) curve (2048 bins) -> locate plateau jumps; test dyadic
alignment in r and r^2; test envelope scaling (sin/r^3, cos/r^2)."""
import sys
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
NB = 2048
RLO, RHI = 0.125, 0.7855
def rbin(r): return min(NB-1, int((r - RLO) / (RHI - RLO) * NB))
def dec_int(se, sig):
    if sig == 0: return 0, 0
    s = -1 if se >> 15 else 1
    return s * sig, (se & 0x7FFF) - 16383 - 63
inputs = open(f"{SCR}/dense_qn.txt").read().split("\n")
dump   = open(f"{SCR}/dense_ref_dump.txt").read().split("\n")
hw_rn  = open(f"{SCR}/dense_rn.txt").read().split("\n")
hw_rd  = open(f"{SCR}/dense_rd.txt").read().split("\n")
LO = {}; HI = {}; CNT = defaultdict(int); EMPTY = defaultdict(int)
SC = 84
di = 0
for li, line in enumerate(inputs):
    if not line.strip(): continue
    se, sig = int(line[:4],16), int(line[5:21],16)
    e = (se & 0x7FFF) - 16383
    r_abs = sig * 2.0**(e-63)
    rb = rbin(r_abs)
    fs = dump[di].split(); fc = dump[di+1].split(); di += 3
    rn_f = hw_rn[li].split(); rd_f = hw_rd[li].split()
    for side, fld in (("s", fs), ("c", fc)):
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
        idx = 1 if side == "s" else 3
        hn_n, hn_e = dec_int(int(rn_f[idx],16), int(rn_f[idx+1],16))
        hd_n, hd_e = dec_int(int(rd_f[idx],16), int(rd_f[idx+1],16))
        sh_n = hn_e - SE; sh_d = hd_e - SE
        if sh_n < 0 or sh_d < 0: continue
        hn = hn_n << sh_n; hd = hd_n << sh_d
        if neg: hn = -hn; hd = -hd
        if not neg: lo1, hi1 = hd, hd + ulp
        else:       lo1, hi1 = hd - ulp, hd
        lo2x, hi2x = 2*hn - ulp, 2*hn + ulp
        lo = max(2*lo1, lo2x); hi = min(2*hi1, hi2x)
        if lo > hi: continue
        dlo = lo - 2*Ti; dhi = hi - 2*Ti
        shift = SC + SE + 1
        dlo = dlo << shift if shift >= 0 else dlo >> -shift
        dhi = dhi << shift if shift >= 0 else dhi >> -shift
        k = (side, rb)
        CNT[k] += 1
        if k not in LO: LO[k], HI[k] = dlo, dhi
        else:
            nlo, nhi = max(LO[k], dlo), min(HI[k], dhi)
            if nlo > nhi: EMPTY[k] += 1
            else: LO[k], HI[k] = nlo, nhi
import json
out = {}
for (side, rb), lo in LO.items():
    hi = HI[(side, rb)]
    rmid = RLO + (rb + 0.5) * (RHI - RLO) / NB
    out.setdefault(side, []).append(
        (rb, rmid, CNT[(side, rb)], EMPTY[(side, rb)], lo/2**14, hi/2**14))  # *2^70
for side in out: out[side].sort()
json.dump(out, open(f"{SCR}/delta_curve.json", "w"))
# summarize jumps for sin: consecutive bins where mid-value changes by > tol
for side in ("s","c"):
    rows = out[side]
    print(f"--- side {side}: {len(rows)} bins; sample around r=0.30..0.34 ---")
    for rb, rmid, cnt, emp, lo, hi in rows:
        if 0.298 < rmid < 0.345:
            print(f"  r={rmid:.5f} n={cnt:3d} e={emp:2d} D70=[{lo:9.4f},{hi:9.4f}]")
print("wrote delta_curve.json")
