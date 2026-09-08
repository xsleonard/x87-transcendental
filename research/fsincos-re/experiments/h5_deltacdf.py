#!/usr/bin/env python3
"""Measure the hw-kernel deviation distribution Delta = T_hw - T_ref via
boundary-crossing statistics under RN + RD captures.

All arithmetic in exact integers at a common power-of-2 scale."""
import sys
from collections import defaultdict
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"

def dec_int(se, sig):
    """return (val_num, val_exp): value = val_num * 2^val_exp, val_num int"""
    if sig == 0: return 0, 0
    s = -1 if se >> 15 else 1
    return s * sig, (se & 0x7FFF) - 16383 - 63

inputs = open(f"{SCR}/dense_qn.txt").read().split("\n")
dump   = open(f"{SCR}/dense_ref_dump.txt").read().split("\n")
hw_rn  = open(f"{SCR}/dense_rn.txt").read().split("\n")
hw_rd  = open(f"{SCR}/dense_rd.txt").read().split("\n")

# t-bin edges in units of ulp
TBINS = [0, 1/256, 1/128, 1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1.0]
def tbin(t):
    for i in range(len(TBINS)-1):
        if t < TBINS[i+1]: return i
    return len(TBINS)-2

# stats[(rbin, side, updown)][tbin] = [crossed, total]
stats = defaultdict(lambda: [[0,0] for _ in range(len(TBINS)-1)])

di = 0
n = 0
for li, line in enumerate(inputs):
    if not line.strip(): continue
    se, sig = int(line[:4],16), int(line[5:21],16)
    e = (se & 0x7FFF) - 16383
    r_abs = sig * 2.0**(e-63)
    rbin = int(r_abs*32)           # 32nds
    fs = dump[di].split(); fc = dump[di+1].split(); di += 3
    rn_f = hw_rn[li].split(); rd_f = hw_rd[li].split()
    for side, fld, off in (("sin", fs, 1), ("cos", fc, 1)):
        a_n, a_e = dec_int(int(fld[1],16), int(fld[2],16))
        b_n, b_e = dec_int(int(fld[3],16), int(fld[4],16))
        # common scale
        E = min(a_e, b_e)
        T = a_n * (1 << (a_e - E)) + b_n * (1 << (b_e - E))   # T_ref = T * 2^E
        if T == 0: continue
        Ts = 1 if T > 0 else -1
        aT = abs(T)
        # ulp exponent of T_ref: find binade
        bl = aT.bit_length() - 1          # 2^bl <= aT < 2^(bl+1) at scale E
        ue = bl - 63                       # ulp = 2^(E+ue)
        if ue < 0:
            aT_sc = aT << (-ue); usc = 1 << 0   # rescale so ulp integer: T*2^-ue
            # work at scale E+ue: T value = aT_sc * 2^(E+ue) ... simpler: ulp_num = 2^ue<1 impossible with ints
            # instead scale everything by 2^-ue
            scale_shift = -ue
            aTs = aT << scale_shift
            ulp = 1 << 0
            # boundaries in this scale: representables are multiples of 1... no:
            # representable grid = multiples of 2^ue at scale E = multiples of 1 at scale E+ue... 
            pass
        # unified: work at scale E2 = E + min(ue,0)... choose S so that ulp = 2^k integer and T integer:
        if ue >= 0:
            Ti = aT; ulp = 1 << ue; SE = E
        else:
            Ti = aT << (-ue); ulp = 1; SE = E + ue
        q, rem = divmod(Ti, ulp)
        # rem in [0, ulp); T_ref = (q*ulp + rem)*2^SE * Ts
        frac = rem / ulp
        # hw outputs at same side
        idx = 1 if side == "sin" else 3
        hn_n, hn_e = dec_int(int(rn_f[idx],16), int(rn_f[idx+1],16))
        hd_n, hd_e = dec_int(int(rd_f[idx],16), int(rd_f[idx+1],16))
        # convert hw to scale SE (exact: hw exps >= SE always? ensure)
        def tosc(vn, ve):
            sh = ve - SE
            return vn << sh if sh >= 0 else None
        hn = tosc(hn_n, hn_e); hd = tosc(hd_n, hd_e)
        if hn is None or hd is None: continue
        if Ts < 0: hn = -hn; hd = -hd     # mirror to positive frame
        # RD in positive frame becomes floor for positive T... careful: for negative
        # values RD rounds down (more negative) = away in magnitude; after mirroring
        # hd_pos = -hd = magnitude rounded UP. So mirrored 'hd' behaves as CEIL.
        lower = q * ulp; upper = lower + ulp
        mid2  = 2*lower + ulp              # 2*midpoint
        if Ts > 0:
            # edge family from RD (floor): crossed up if hd >= upper; down if hd < lower
            t_up = (ulp - rem)/ulp; t_dn = rem/ulp if rem else 1.0
            b = stats[(rbin, side, "up")] ; bb = tbin(t_up); b[bb][1]+=1; b[bb][0]+= (hd >= upper)
            b = stats[(rbin, side, "dn")] ; bb = tbin(t_dn); b[bb][1]+=1; b[bb][0]+= (hd < lower)
        else:
            # mirrored: hd acts as ceil: crossed up (in mirrored frame) if hd > upper?? 
            # ceil(T_hw) > ceil-cell of T_ref  <=> T_hw > upper; down <=> T_hw <= lower
            t_up = (ulp - rem)/ulp; t_dn = rem/ulp if rem else 1.0
            b = stats[(rbin, side, "up")] ; bb = tbin(t_up); b[bb][1]+=1; b[bb][0]+= (hd > upper)
            b = stats[(rbin, side, "dn")] ; bb = tbin(t_dn); b[bb][1]+=1; b[bb][0]+= (hd <= lower)
        # midpoint family from RN: nearest boundary above/below at half-grid
        # distance to mid boundary above:
        if 2*rem < ulp:
            t_mu = (ulp - 2*rem)/(2*ulp); t_md = (2*rem + ulp)/(2*ulp)
        else:
            t_mu = (3*ulp - 2*rem)/(2*ulp); t_md = (2*rem - ulp)/(2*ulp)
        # crossed if hn differs from RN(T_ref) in that direction:
        # RN(T_ref): nearest multiple of ulp (ties even)
        num2 = 2*rem
        if num2 > ulp or (num2 == ulp and (q & 1)): rnref = upper
        else: rnref = lower
        b = stats[(rbin, side, "mu")]; bb = tbin(t_mu); b[bb][1]+=1; b[bb][0]+= (hn > rnref)
        b = stats[(rbin, side, "md")]; bb = tbin(t_md); b[bb][1]+=1; b[bb][0]+= (hn < rnref)
    n += 1

print(f"analyzed {n} inputs")
# print crossing curves for selected rbins
sel = [4,5,6,7,8,10,12,14,16,18,20,22,24]   # r in 32nds: 4=0.125..
print("side dir rbin(r~) : crossing rate per t-bin  [t bins: " +
      ", ".join(f"<{TBINS[i+1]:.4g}" for i in range(len(TBINS)-1)) + "]")
for side in ("sin","cos"):
    for ud in ("up","dn","mu","md"):
        for rb in sel:
            st = stats.get((rb, side, ud))
            if not st: continue
            tot = sum(x[1] for x in st)
            if tot < 3000: continue
            row = " ".join(f"{(100.0*c/t if t else 0):6.2f}" for c,t in st)
            print(f"{side} {ud} r~{rb/32:.3f}: {row}")
