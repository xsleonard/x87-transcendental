#!/usr/bin/env python3
"""h615: the h377 FSIN residual input scored in the FCOS frame.

Input c01c:ccb8a935dddf4000 (FSIN, odd-quadrant cosine
producer): trace gives dist=7 low3=7 le2=-72 payload=8
active=1.  Hardware (rd) sits one unit below the chop model.
Questions: (1) is the row in the near-boundary zone; (2) what
req2 does hardware require in the EU frame; (3) what does the
Round-57 FCOS rule predict for the SAME terminal operands
(cross-schedule datum: FSIN schedule vs FCOS-fitted rule)."""
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h453_chain_variants import recover_m
from h577_three_term import qrow3
from h588_select import split_words
from h609_ref_predictor import load_model, predict
import h539_D_library as DL

MUL = 0x7AE04F9E812D5BC4F
# hardware significands for the 3 modes (from the fixture,
# line 9): rn/ru match the model; rd is one below.
HW = {"rn": 0xF85BCA6C81CE1D87, "rd": 0xF85BCA6C81CE1D86,
      "ru": 0xF85BCA6C81CE1D87}
# NOTE the fixture's rn/ru entries: model matches hardware
# there (gate says only rd result differs).

m = recover_m(MUL)
print(f"recovered m: {m:#x} ({m.bit_length()} bits)")
while m.bit_length() > 64:
    m >>= 1
while 0 < m.bit_length() < 64:
    m <<= 1
mhex = f"{m:016x}"
(m2, R, A, P, B_full, rsh, rdisc, lsh, ldisc, s4, t4,
 bshift, k, dist, low3) = qrow3(mhex)
print(f"replica: dist={dist} low3={low3} k={k} R={R:#x}")
M = A + P - ((B_full >> rsh) << bshift)
disc = M & ((1 << k) - 1)
theta = disc if disc <= 2 else (disc - (1 << k)
                                if disc >= (1 << k) - 2 else None)
print(f"disc={disc:#x} (k={k}) theta={theta}")
F = rsh - bshift
kf = k + F
APf = (A + P) << F
EU = (APf - B_full) >> kf
Vlow = (APf - B_full) - (EU << kf)
print(f"EU={EU:#x} R={R:#x} R-EU={R - EU}")
ce = -72
for z in (-1, 0, 1):
    refs = [final_cosine_result(-(EU + z), ce, md)
            for md in ROUNDING_MODES]
    tag = ""
    if refs == [HW[md] for md in ROUNDING_MODES]:
        tag = "  <== HARDWARE"
    print(f"refs(EU{z:+d}): {[f'{s:x}' for s in refs]}{tag}")
side = "up" if (theta is not None and theta <= 0) else "dn"
qr = DL.qrow(mhex)
f4v, rfv = qr[2], qr[3]
S, C = split_words(f4v, rfv)
st = ((S + C) >> max(rsh - 59, 0)) & 63
tau = t4 / (1 << s4)
mf = (m & ((1 << 63) - 1)) / (1 << 63)
xd12 = min(11, (rdisc * 12) >> rsh)
print(f"features: side={side} tau={tau:.6f} mf={mf:.6f} "
      f"xd12={xd12} st={st}")
fits, cbest = load_model()
key = (dist, low3, ce, side)
p = predict(fits, cbest, key, xd12, mf, st, tau, Vlow, kf, rfv)
print(f"FCOS rule prediction for {key}: {p}")
if p is not None:
    fire, req2p, src = p
    refs = [final_cosine_result(-(EU + req2p), ce, md)
            for md in ROUNDING_MODES]
    match = refs == [HW[md] for md in ROUNDING_MODES]
    print(f"rule req2p={req2p} -> sigs "
          f"{[f'{s:x}' for s in refs]}; matches hardware: "
          f"{match}")
