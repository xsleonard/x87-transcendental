#!/usr/bin/env python3
"""Prototype Pentium-structure kernel (P5 ROM constants) vs Skylake dense
RN capture.  Exact-integer soft x87: every op = one RN64 rounding."""
import random
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"

def rn64b(s, sig, E):
    """value = sig * 2^E (sig>0 int) -> (s, e, sig64) with sig64 bit63 set"""
    b = sig.bit_length()
    sh = b - 64
    if sh <= 0:
        return (s, E + b - 1 + 63 - 63, sig << (-sh)) if sh else (s, E + 63, sig)
    top = sig >> sh
    rem = sig & ((1 << sh) - 1)
    half = 1 << (sh - 1)
    if rem > half or (rem == half and (top & 1)):
        top += 1
        if top >> 64:
            top >>= 1; sh += 1
    return (s, E + sh + 63, top)
# rep: (sign, e, sig) value = (-1)^s * sig * 2^(e-63); zero = sig 0
def fmul(a, b):
    if a[2] == 0 or b[2] == 0: return (0, 0, 0)
    return rn64b(a[0] ^ b[0], a[2] * b[2], (a[1] - 63) + (b[1] - 63))
def fadd(a, b):
    if a[2] == 0: return b
    if b[2] == 0: return a
    ea, eb = a[1] - 63, b[1] - 63
    E = min(ea, eb)
    v = ((-1)**a[0]) * (a[2] << (ea - E)) + ((-1)**b[0]) * (b[2] << (eb - E))
    if v == 0: return (0, 0, 0)
    return rn64b(1 if v < 0 else 0, abs(v), E)
def fneg(a): return (a[0] ^ 1, a[1], a[2]) if a[2] else a
def enc(v):
    if v[2] == 0: return (0, 0)
    return ((v[0] << 15) | (v[1] + 16383), v[2])

ROM = {}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p = line.rstrip("\n").split("\t")
    if p[0] == "row": continue
    ROM[int(p[0])] = (int(p[1], 16), int(p[2]), int(p[4], 16))

def C(row, prec):
    ef, s, sig68 = ROM[row]
    e = ef - 0xFFFD              # value = sig68 * 2^(e-68)
    b = sig68.bit_length()
    sh = b - 64
    sig = sig68 >> sh
    if prec == 'r':
        rem = sig68 & ((1 << sh) - 1); half = 1 << (sh - 1)
        if rem > half or (rem == half and (sig & 1)):
            sig += 1
            if sig >> 64: sig >>= 1; b += 1
    return (s, (e - 68) + (b - 1) + 63 - 63 + 63 - 63 + 0 + (b - 1) - (b - 1) + 63 - 63 + 63, sig) if False else (s, (e - 68) + (b - 1), sig)

GRID = [18, 22, 26, 30, 36, 44, 52, 60]
SINROW = {18:181, 22:182, 26:183, 30:184, 36:177, 44:178, 52:179, 60:180}
COSROW = {18:189, 22:190, 26:191, 30:192, 36:185, 44:186, 52:187, 60:188}
ONE = (0, 0, 1 << 63)

def pent_sincos(rv, prec):
    rf = rv[2] * 2.0 ** (rv[1] - 63)
    if rf < 16 / 64:
        rsq = fmul(rv, rv)
        p = C(162, prec)
        for row in (161, 160, 159, 158, 157):
            p = fadd(fmul(p, rsq), C(row, prec))
        rcube = fmul(rsq, rv)
        sin = fadd(rv, fmul(p, rcube))
        q = C(168, prec)
        for row in (167, 166, 165, 164, 163):
            q = fadd(fmul(q, rsq), C(row, prec))
        cos = fadd(ONE, fmul(q, rsq))
        return sin, cos
    b = min(GRID, key=lambda k: abs(rf - k / 64))
    sinT = C(SINROW[b], prec); cosT = C(COSROW[b], prec)
    bl = b.bit_length()
    bb = (0, bl - 1 - 6, b << (64 - bl))
    a = fadd(rv, fneg(bb))
    if a[2] == 0:
        S4 = (0, 0, 0); C4 = ONE
    else:
        asq = fmul(a, a)
        p = C(172, prec)
        for row in (171, 170, 169):
            p = fadd(fmul(p, asq), C(row, prec))
        acube = fmul(asq, a)
        S4 = fadd(a, fmul(p, acube))
        q = C(176, prec)
        for row in (175, 174, 173):
            q = fadd(fmul(q, asq), C(row, prec))
        C4 = fadd(ONE, fmul(q, asq))
    sin = fadd(fmul(sinT, C4), fmul(cosT, S4))
    cos = fadd(fmul(cosT, C4), fneg(fmul(sinT, S4)))
    return sin, cos

inputs = [l for l in open(f"{SCR}/dense_qn.txt").read().split("\n") if l.strip()]
hw = [l for l in open(f"{SCR}/dense_rn.txt").read().split("\n") if l.strip()]
random.seed(7)
idxs = random.sample(range(len(inputs)), 5000)
for prec in ("t", "r"):
    mm_s = mm_c = 0
    # also split mismatches by region
    reg = {"poly": [0, 0], "tab": [0, 0]}
    for i in idxs:
        se, sig = int(inputs[i][:4], 16), int(inputs[i][5:21], 16)
        neg = (se >> 15) & 1
        rv = (0, (se & 0x7FFF) - 16383, sig)
        rf = sig * 2.0 ** (rv[1] - 63)
        region = "poly" if rf < 0.25 else "tab"
        sin, cos = pent_sincos(rv, prec)
        if neg: sin = fneg(sin)
        hf = hw[i].split()
        hs = (int(hf[1], 16), int(hf[2], 16)); hc = (int(hf[3], 16), int(hf[4], 16))
        ok_s = enc(sin) == hs; ok_c = enc(cos) == hc
        mm_s += not ok_s; mm_c += not ok_c
        reg[region][0] += not ok_s; reg[region][1] += not ok_c
    print(f"prec={prec}: sin mm {mm_s}/5000  cos mm {mm_c}/5000   "
          f"poly-region (s,c)={tuple(reg['poly'])} tab-region={tuple(reg['tab'])}")

# ---------- variant grid over table-region details ----------
def pent_tab(rv, tprec, pprec, combine, s4ord):
    rf = rv[2] * 2.0 ** (rv[1] - 63)
    b = min(GRID, key=lambda k: abs(rf - k / 64))
    sinT = C(SINROW[b], tprec); cosT = C(COSROW[b], tprec)
    bl = b.bit_length()
    bb = (0, bl - 1 - 6, b << (64 - bl))
    a = fadd(rv, fneg(bb))
    asq = fmul(a, a)
    p = C(172, pprec)
    for row in (171, 170, 169):
        p = fadd(fmul(p, asq), C(row, pprec))
    if s4ord == 0:
        S4 = fadd(a, fmul(p, fmul(asq, a)))
    else:
        S4 = fadd(a, fmul(fmul(p, asq), a))
    q = C(176, pprec)
    for row in (175, 174, 173):
        q = fadd(fmul(q, asq), C(row, pprec))
    t = fmul(q, asq)                      # C4 - 1
    if combine == 0:
        C4 = fadd(ONE, t)
        sin = fadd(fmul(sinT, C4), fmul(cosT, S4))
        cos = fadd(fmul(cosT, C4), fneg(fmul(sinT, S4)))
    else:                                  # delta form
        u = fadd(fmul(sinT, t), fmul(cosT, S4))
        sin = fadd(sinT, u)
        v = fadd(fmul(cosT, t), fneg(fmul(sinT, S4)))
        cos = fadd(cosT, v)
    return sin, cos

sel = [i for i in idxs if int(inputs[i][5:21],16) * 2.0**(((int(inputs[i][:4],16))&0x7FFF)-16383-63) >= 0.25][:3000]
print(f"\ntable-region grid on {len(sel)} samples:")
best=[]
for tprec in ("t","r"):
    for pprec in ("t","r"):
        for combine in (0,1):
            for s4ord in (0,1):
                mm=0
                for i in sel:
                    se, sig = int(inputs[i][:4],16), int(inputs[i][5:21],16)
                    neg=(se>>15)&1
                    rv=(0,(se&0x7FFF)-16383,sig)
                    sin,cos=pent_tab(rv,tprec,pprec,combine,s4ord)
                    if neg: sin=fneg(sin)
                    hf=hw[i].split()
                    if enc(sin)!=(int(hf[1],16),int(hf[2],16)): mm+=1
                    if enc(cos)!=(int(hf[3],16),int(hf[4],16)): mm+=1
                best.append((mm,tprec,pprec,combine,s4ord))
best.sort()
for mm,tp,pp,cb,s4 in best[:8]:
    print(f"  tprec={tp} pprec={pp} combine={cb} s4ord={s4}: mismatches {mm}/{2*len(sel)}")
