# FSIN, FCOS and FSINCOS: programmer pseudocode

This walkthrough was relocated intact from the root README during suite
organization. Its arithmetic is unchanged; the special-case comment now avoids an old
section number. For the other
instructions, start with the [algorithm guide](ALGORITHMS.md).

The current Skylake `FSIN`, `FCOS` and `FSINCOS` algorithm is below. The
[unified LaTeX paper](../paper/x87-suite.tex) includes the same walkthrough in
Appendix A alongside the equations, evidence and limitations.

Read it as: **reduce the angle, select a kernel, restore the quadrant sign,
then round the result**. Standalone FSIN/FCOS and paired FSINCOS share
reduction, table and tiny paths, but use different polynomial schedules.

This is Python-like pseudocode over **exact signed integer/dyadic values**.
Ordinary `+`, `-`, `*`, `/` and powers are exact; only named rounding operations
discard bits. Do not translate it using host `float` or `double` arithmetic.
`**` is exponentiation, `divmod` is integer quotient/remainder, and `% 4`
returns a nonnegative quadrant even for negative inputs. Coefficient arrays
use one-based indices. The returned lanes are numerical values; x87 stack
and exception-state emulation are outside this walkthrough.

### Entry, reduction and dispatch

`x80(se, sig)` denotes the exact value of an x87 encoding, and
`normalized_parts` supplies the 64-bit significand and unbiased exponent.
Specials are handled before reduction: quiet and propagate valid NaNs,
return the masked indefinite for infinities and invalid encodings, and return
signed zero for sine / +1 for cosine on zero inputs. Pseudo-denormals are valid
and use the tiny external-input bypass. Special-case condition bits are not
specified here.

```text
def reduce(x):
    # Direct-path boundary as an exact x87 magnitude.
    if abs(x) < x80(0x3ffe, 0xc90fdaa22168c234):
        return x, 0
    s, e = normalized_parts(abs(x))       # abs(x) = s * 2**(e-63)
    M66 = 0x3243f6a8885a308d3
    dividend = s << (e + 2)
    q, remainder = divmod(dividend, M66)
    if 2 * remainder > M66: q += 1        # No halfway tie: M66 is odd.
    residual = (dividend - q * M66) * 2**(-65)
    if signbit(x): return -residual, -q
    return residual, q

def trig(op, x, rc):
    if special_encoding_or_zero(x):
        return special_values(op, x)     # Handle special values before reduction.
    if abs(x) >= 2**63: return C2_operand_unchanged(x)
    phases = [0, 1] if op == FSINCOS else [0 if op == FSIN else 1]
    y, c1 = {}, {}
    if abs(x) < 2**(-68):                 # External-input bypass.
        return select_lanes(phases, [x, 1]), 0
    residual, quadrant = reduce(x)
    r = abs(residual)
    if 2**(-32) <= r < 1/4 and op == FSINCOS:
        pair = paired_poly(r)            # Compute once, not two FSIN/FCOS calls.
    for phase in phases:                 # 0: external sine; 1: external cosine.
        n = (quadrant + phase) % 4
        cosine = (n & 1) != 0
        negative = (n >> 1) ^ (0 if cosine else signbit(residual))
        if r < 2**(-32):
            y[phase], c1[phase] = tiny(r, cosine, negative, rc)
        else:
            if r >= 1/4: u = table(r, cosine)
            elif op == FSINCOS: u = pair[int(cosine)]
            else: u = standalone_poly(r, cosine)
            y[phase], c1[phase] = finish(u, negative, rc)
    return y, c1[phases[-1]]              # FSINCOS C1 comes from external cosine.
```

`y` and `c1` are maps keyed by phase: 0 is external sine, 1 is external cosine.
`select_lanes` selects those same requested phases. The final external cosine
lane supplies FSINCOS C1, including when its quadrant selects internal sine.

### Explicit rounding operators

`T67` / `T64` truncate magnitude to 67 / 64 significant bits, preserving sign.
`RN64` rounds once to nearest-even at 64 bits. `RC64(value, rc)` rounds to
64 bits in the requested mode: nearest-even (RN), down (RD), up (RU), or
toward zero (RZ). These widths are significand widths, not storage sizes.

```text
def M(x, y):  return T67(T67(x) * T64(y))
def A(x, y):  return RN64(x + y)
def MR(x, y): return RN64(T67(x) * T64(y))  # One rounding of exact port product.
```

`MR(x, y)` is not `RN64(M(x, y))`: the latter adds an intermediate truncation.
Keep the operand order of `M`; its input cuts differ.

### Standalone and paired polynomial kernels

`S6`, `C6`, `S4`, `C4` and `ROM` are the native signed constants from
[`p5_rom_constants.h`](../src/p5_rom_constants.h), including the
corrected table words. Do not substitute Taylor coefficients or compute the
table with a host math library.

```text
def standalone_poly(r, cosine):
    K = C6 if cosine else S6
    square = M(r, r)
    fourth = M(square, square)            # Includes T64 on the second port.
    odd = M(fourth, K[5])
    odd = A(K[3], odd)
    odd = A(K[1], M(fourth, odd))
    even = M(fourth, K[6])
    even = A(K[4], even)
    even = A(K[2], M(fourth, even))
    left = M(square, odd)
    right = M(fourth, even)
    if cosine: return 1 + T67(left + right)
    return r + M(r, A(left, right))

def paired_poly(r):
    square = T67(r * r)
    p, q = S6[6], C6[6]
    for i in [5, 4, 3, 2, 1]:
        p = RN64(T67(p * square) + S6[i]) # Every product is cut before RN64.
        q = RN64(T67(q * square) + C6[i]) # Including the last on BOTH arms.
    sine = r + T67(RN64(p * square) * r)
    cosine = 1 + T67(q * square)
    return [sine, cosine]
```

The standalone graph groups odd and even coefficient indices; FSINCOS uses
two Horner chains sharing one square. Each returns a positive-residual
prevalue. The caller applies the quadrant sign **before** final architectural
rounding. All earlier rounding stays fixed regardless of RC.

### Shared table kernel, tiny results and final rounding

Table centers are `b/64`, with `b` in `{18, 22, 26, 30, 36, 44, 52}`.
Selection and center subtraction must remain exact at cell boundaries.

```text
def horner4(square, K):
    v = K[4]
    for i in [3, 2, 1]: v = A(K[i], M(square, v))
    return v

def table(r, cosine):
    if r < 1/2: b = 18 + 4 * floor(16 * (r - 1/4))
    else: b = 36 + 8 * min(2, floor(8 * (r - 1/2)))
    a = r - b/64
    square = M(a, a)
    K = copy(S4)
    K[4] -= 2**(-25)                      # Validated coefficient adjustment.
    p = horner4(square, K)
    q = horner4(square, C4)
    v = A(a, M(M(square, p), a))
    w = MR(square, q)
    ts, tc = ROM[b]
    if cosine: return tc + T67(-M(ts, v) + M(tc, w))
    return ts + T67(M(tc, v) + M(ts, w))

def tiny(r, cosine, negative, rc):
    lead = 1 if cosine else r
    toward_zero = (rc == RZ or (rc == RD and not negative)
                   or (rc == RU and negative))
    if toward_zero: lead = pred64(lead)
    return (-lead if negative else lead), int(not toward_zero)

def finish(u, negative, rc):
    signed = -u if negative else u
    y = RC64(signed, rc)
    return y, int(abs(y) > abs(signed))   # C1 is a magnitude increment.
```

`pred64(v)` is the greatest nonnegative value with a 64-bit significand
strictly below positive `v`; at a power of two it crosses into the preceding
binade. Non-bypass tiny values keep their leading magnitude under RN or
rounding away from zero (C1=1), and take the predecessor toward zero (C1=0).
The separate external-input bypass returns C1=0 in every mode. For the other
paths, C1 records only a final magnitude increment, not whether the whole
instruction was exact.

The source counterparts are
[`standalone_polynomial.h`](../src/general/standalone_polynomial.h),
[`paired.h`](../src/general/paired.h),
[`standalone_table.h`](../src/general/standalone_table.h) and
[`standalone_tiny.h`](../src/general/standalone_tiny.h); the reducer
and entry points live in [`fsincos_skylake.c`](../src/fsincos_skylake.c).
