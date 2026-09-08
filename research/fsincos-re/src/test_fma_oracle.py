#!/usr/bin/env python3
"""Oracle test for the soft IA-64 fma engine (fsincos_ref --fma-test).

Generates random and adversarial (a, b, c, op, rc) vectors, computes the
exact result with rational arithmetic, rounds it to a 64-bit significand in
the requested mode (unbounded exponent, matching the wre register model),
and compares bit-for-bit with the C engine.

Exponent fields are kept moderate so results stay far from the double-
extended denormal boundary (the engine's x87 store path denormalizes there,
which is out of scope for this engine test).
"""
import random
import subprocess
import sys
from fractions import Fraction

BIN = sys.argv[1] if len(sys.argv) > 1 else "./fsincos_ref"
N_RANDOM = 6000
N_CANCEL = 3000
N_TIES = 2000
random.seed(20260715)

def dec(se, sig):
    sign = -1 if (se >> 15) & 1 else 1
    e = se & 0x7FFF
    if sig == 0:
        return Fraction(0), sign
    assert e not in (0, 0x7FFF)
    return sign * Fraction(sig, 1) * Fraction(2) ** (e - 16383 - 63), sign

def round_sig64(x, rc, neg_zero_sign_rd=False):
    """round Fraction to 64-bit significand, unbounded exponent; return
    (se, sig) in x87 encoding (assumes result within normal field range)."""
    if x == 0:
        return (0x8000 if rc == 1 and neg_zero_sign_rd else 0x0000), 0
    sign = 1 if x < 0 else 0
    a = abs(x)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    # a = f * 2^e, f in [1,2); significand integer = a * 2^(63-e)
    scaled = a * Fraction(2) ** (63 - e)
    i = scaled.numerator // scaled.denominator
    frac = scaled - i
    if rc == 0:  # RN even
        if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and (i & 1)):
            i += 1
    elif rc == 2:  # RU (toward +inf)
        if frac > 0 and sign == 0:
            i += 1
    elif rc == 1:  # RD
        if frac > 0 and sign == 1:
            i += 1
    # rc == 3: RZ, truncate
    if i == 1 << 64:
        i >>= 1
        e += 1
    ef = e + 16383
    assert 0 < ef < 0x7FFF, f"exponent out of normal range: {e}"
    return (sign << 15) | ef, i

def rand_val(emin=16000, emax=16800):
    se = (random.getrandbits(1) << 15) | random.randint(emin, emax)
    sig = random.getrandbits(64) | (1 << 63)
    return se, sig

cases = []
# 1) plain random
for _ in range(N_RANDOM):
    a, b, c = rand_val(), rand_val(), rand_val()
    cases.append((a, b, c, random.randint(0, 2), random.randint(0, 3)))
# 2) cancellation: c ~ -(a*b) with low-bit noise
for _ in range(N_CANCEL):
    a, b = rand_val(16300, 16500), rand_val(16300, 16500)
    va, _ = dec(*a)
    vb, _ = dec(*b)
    prod = va * vb
    se_c, sig_c = round_sig64(prod, 0)
    sig_c ^= random.getrandbits(2)          # jiggle low bits
    if sig_c >> 63 == 0:
        sig_c |= 1 << 63
    se_c ^= 1 << 15                          # opposite sign -> subtraction
    cases.append((a, (se_c, sig_c), (0x3FFF, 1 << 63), 0, random.randint(0, 3)))
    # note: (a * c) + 1?? keep the canonical shape instead:
    cases[-1] = (a, b, (se_c, sig_c), 0, random.randint(0, 3))
# 3) tie cases: products with exactly representable halves
for _ in range(N_TIES):
    # a has few significant bits so a*b + tiny sits at a tie
    abits = random.randint(1, 8)
    asig = ((random.getrandbits(abits) | 1) << (64 - abits)) | (1 << 63)
    a = ((random.getrandbits(1) << 15) | random.randint(16380, 16390), asig)
    bsig = ((random.getrandbits(6) | 1) << 57) | (1 << 63)
    b = ((random.getrandbits(1) << 15) | random.randint(16380, 16390), bsig)
    # c: shifted so alignment produces a guard-bit-only remainder
    c = ((random.getrandbits(1) << 15) | random.randint(16310, 16330),
         (1 << 63) | (random.getrandbits(1) << 62))
    cases.append((a, b, c, random.randint(0, 2), random.randint(0, 3)))

inp = []
for (ase, asig), (bse, bsig), (cse, csig), op, rc in cases:
    inp.append(f"{ase:04x} {asig:016x} {bse:04x} {bsig:016x} {cse:04x} {csig:016x} {op} {rc}")

proc = subprocess.run([BIN, "--fma-test"], input="\n".join(inp) + "\n",
                      capture_output=True, text=True, check=True)
outs = proc.stdout.split()
assert len(outs) == 2 * len(cases), f"{len(outs)} vs {2*len(cases)}"

fails = 0
for i, ((a, b, c, op, rc)) in enumerate(cases):
    va, _ = dec(*a)
    vb, _ = dec(*b)
    vc, _ = dec(*c)
    if op == 0:
        exact = va * vb + vc
    elif op == 1:
        exact = va * vb - vc
    else:
        exact = vc - va * vb
    # sign of exact zero: matches IEEE rules the engine implements
    neg_rd = False
    if exact == 0:
        # x + (-x): +0 except RD -> -0 ; also (+0)+(+0) etc. — our generated
        # operands are nonzero so cancellation zero: sign = RD ? 1 : 0
        neg_rd = True
    want = round_sig64(exact, rc, neg_zero_sign_rd=neg_rd)
    got = (int(outs[2 * i], 16), int(outs[2 * i + 1], 16))
    if want != got:
        fails += 1
        if fails <= 10:
            print(f"MISMATCH case {i}: a={a} b={b} c={c} op={op} rc={rc}")
            print(f"  want {want[0]:04x} {want[1]:016x}")
            print(f"  got  {got[0]:04x} {got[1]:016x}")

print(f"fma oracle: {len(cases)} cases, {fails} mismatches")
sys.exit(1 if fails else 0)
