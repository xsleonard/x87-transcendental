# Op-level extraction: sinl/cosl (= FSIN/FCOS algorithm), s_cosl.S

Extracted instruction-by-instruction from `data/glibc-ia64-fpu/s_cosl.S`
(glibc-2.38). This is the ground truth a bit-exact reimplementation must
reproduce. Line numbers refer to that file.

## Arithmetic model

- Register format: IA-64 FP registers (64-bit significand, 17-bit exponent).
- `fma.s1 / fms.s1 / fnma.s1 x = a, b, c`: fused a·b±c with a SINGLE rounding
  to 64-bit significand, using status field **sf1** — by IA-64 software
  convention: round-to-nearest-even, 64-bit precision, widest-range exponent
  (wre=1), traps disabled. All intermediate arithmetic uses s1.
- `….s0`: user status field — user's rounding mode. Used ONLY for (a) the one
  final result operation of each path, (b) dummy ops that set user flags
  (inexact / denormal / invalid).
- `fms x = a, f1, b` ≡ a − b; `fma x = a, f1, b` ≡ a + b; `fnma x = a, b, c`
  ≡ c − a·b. f0 = +0.0, f1 = +1.0.
- `fcvt.fx.s1` = round FP to 64-bit signed int significand per sf1 (nearest
  even); `fcvt.xf` = int→FP, always exact.
- `frcpa.s1 f = f1, g` = architecturally-defined table lookup approximation
  to 1/g (top-8-significand-bits table, IA-64 SDM `fp_ieee_recip`), ~8.886
  valid bits. **[OPEN: transcribe the exact 256-entry table]**
- `fnorm.s1` = normalize (identity on normal values; raises denormal fault
  path for denormals).
- `getf.sig r = f` = raw 64-bit significand → integer register.
- `fmerge.se f = a, b` = sign+exponent of a, significand of b (used as a
  plain move `f = a` when a=b); `fmerge.s f = a, b` = sign of a, rest of b
  (abs via `fmerge.s f = f0, x`... sign of +0 → |x|; move via `f1,x` → +|x|
  wait: `fmerge.s FR_abs_x = f1, FR_norm_x` takes sign of f1(+) → abs).

## Entry (sinl: N_inc=0; cosl: N_inc=1) and dispatch

```
norm_x = fnorm.s1(x)
N_signif = fma.s1(x, sig_invpi_2to63, rshf_2to64)     [L907]
  where sig_invpi_2to63 = setf.sig 0xA2F9836E4E44152A  (= (2/π)·2^62 as
        significand·2^63 scaling; value = 0.6366…·2^63)
        rshf_2to64 = 1.5·2^127  ("right shift" const, pins exponent so the
        rounded significand's low bits = round-to-nearest-int(x·2/π))
dispatch on |x| (via exponent):
  x = 0                → ZERO
  denormal             → fnorm then common path
  NaN/Inf/NatVal       → SPECIAL: result = fmpy.s0(x, f0)  (QNaN, invalid on
                          SNaN/Inf)
  |x| >= 2^63          → ARG_TOO_LARGE (libm: __libm_pi_by_2_reduce
                          Payne–Hanek → r,c,N; then SMALL_R / NORMAL_R.
                          x87 FSIN/FCOS/FSINCOS instead: C2:=1, no result)
  2^24 <= |x| < 2^63   → LARGER_ARG (Step 8 pre-reduction)
  |x| <  π/4  (compare |x| < pi_by_4 = trunc-to-64-bit π/4) →
        r = x, c = 0, N_Inc = Sin_or_Cos
        |x| < 2^-3 (exponent compare) → SMALL_R_0 else NORMAL_R_0
  else (π/4 <= |x| < 2^24) → moderate reduction below
```

N (moderate path): `N_float = fms.s1(N_signif, 2^-64, rshf)` (rshf=1.5·2^63)
recovers float N; `GR_N_Inc = getf.sig(N_signif)` takes the integer N from
the significand's low bits (two's complement); then `+= Sin_or_Cos`.
Quadrant bits used everywhere: i_1 = bit0 of N_Inc (0: sine kernel, 1:
cosine kernel), i_0 = bit1 (result sign).

## Moderate reduction (π/4 <= |x| < 2^24)  [L1013–1145]

```
s = fnma.s1(N_float, P_1, x)          // s = x − N·P_1   (proven EXACT)
w = fma.s1(N_float, P_2, f0)          // w = N·P_2  (P_2 stored NEGATIVE…
                                      //  …table value is the negative piece)
r = fms.s1(s, f1, w)                  // r = s − w  … but see sign note
[test |s| vs 2^-33 → p6 (big s) / p7 (tiny s)]
p6: c = fms.s1(s, f1, r)              // c = s − r      (exact 2sum part)
    c = fms.s1(c, f1, w)              // c = (s−r) − w  [L1136]
    rsq  = fma.s1(r, r, f0)
    frcpa#1: r_hi = frcpa.s1(f1, r)   // executed on this path at L1067
    |r| < 2^-3 ? → SMALL_R_1 : NORMAL_R_1
```
Sign note: with the stored (negative) P_2, w = N·P_2 is the NEGATIVE of the
write-up's w; `r = s − w` and `c = (s−r) − w` in the code equal the write-up's
`r = s + w`, `c = (s−r) + w`. Net: identical values.

### Tiny-s tail (|s| < 2^-33, Case 2)  [SINCOSL_S_TINY, L1148–1279]

```
w2  = fma.s1(N_float, P_3, f0)        // (p7, at L1059)
U_1 = fma.s1(N_float, P_2, w2)        // U_1 = N·P_2 + w2      [L1080]
r   = fms.s1(s, f1, U_1)              // r = s − U_1           [L1109]
U_2 = fms.s1(N_float, P_2, U_1)       // U_2 = N·P_2 − U_1 (exact resid)
s'  = fms.s1(s, f1, r)                // s' = s − r
rsq = fma.s1(r, r, f0)
U_2 = fma.s1(U_2, f1, w2)             // U_2 += w2
tmp = r                (sine)  |  tmp = 1.0            (cos, p10)
c   = fms.s1(s', f1, U_1)             // c = (s−r) − U_1
(p12: i_0=1) tmp = fnma.s1(tmp, f1, f0)   // tmp = −tmp
t1  = fma.s1(S_1, r, f0)              // t1 = S_1·r
DUMMY fma.s0(S_1, S_1, f0)            // sets user inexact flag
c   = fms.s1(c, f1, U_2)              // c −= U_2
sine (p9):  poly = fma.s1(t1, rsq, c)     // S_1·r·r² + c
cos  (p10): poly = fma.s1(f0, f1, −2^-67) // = −2^-67
FINAL: (p11) Result = fma.s0(tmp, f1, poly)    // tmp + poly
       (p12) Result = fms.s0(tmp, f1, poly)    // tmp − poly  (tmp already −)
```

## Pre-reduction (2^24 <= |x| < 2^63)  [SINCOSL_LARGER_ARG, L1282–1513]

```
N_0f = fma.s1(x, Inv_P_0, f0)
N_0  = fcvt.xf(fcvt.fx.s1(N_0f))                 // nearest int, exact back
x'   = fnma.s1(N_0, P_0, x)                      // Arg' = x − N_0·P_0
w    = fma.s1(N_0, d_1, f0)
N_f  = fma.s1(x', Inv_pi_by_2, f0)               // NOTE: plain fma +
N    = fcvt.xf(fcvt.fx.s1(N_f)); N_int=getf.sig  //  fcvt, NOT rshf trick
N_Inc = N_int + Sin_or_Cos
s = fnma.s1(N, P_1, x')                          // s = x' − N·P_1
w = fnma.s1(N, P_2, w)                           // w = w − N·P_2
[test |s| vs 2^-14 → p8 big / p9 tiny]
p8: r = fma.s1(s, f1, w)                         // r = s + w  (true signs)
    c = fms.s1(s, f1, r)                         // c = s − r
    c = fma.s1(c, f1, w)                         // c = (s−r) + w
    |r| < 2^-3 ? → SMALL_R : NORMAL_R
```

### Case 4 (|s| < 2^-14)  [SINCOSL_LARGER_S_TINY, L1516–1750]

```
V_hi = fma.s1(N, P_2, f0)              // = −(write-up V_hi); sign flipped
U_hi = fma.s1(N_0, d_1, f0)
w2   = fma.s1(N, P_3, f0)
A    = fms.s1(U_hi, f1, V_hi)          // U_hi + V_hi in true signs
V_lo = fnma.s1(N, P_2, V_hi)           // exact resid of V_hi rounding
U_lo = fms.s1(N_0, d_1, U_hi)          // exact resid of U_hi rounding
U_hiabs = |U_hi|, V_hiabs = |V_hi|
w2   = fms.s1(N_0, d_2, w2)            // w = N_0·d_2 − w2 (true signs now)
t    = fma.s1(U_lo, f1, V_lo)
p7 (U_hiabs >= V_hiabs): a = fms.s1(U_hi, f1, A); a = fms.s1(a, f1, V_hi)
p8 (else):               a = fma.s1(V_hi, f1, A); a = fms.s1(U_hi, f1, a)
   // both = write-up's (bigger − A) + smaller, in flipped-sign bookkeeping
C_hi = fma.s1(s, f1, A)
t    = fma.s1(t, f1, w2)
C_lo = fms.s1(s, f1, C_hi)
C_lo = fma.s1(C_lo, f1, A)             // C_lo = (s − C_hi) + A
t    = fma.s1(t, f1, a)
C_lo = fma.s1(C_lo, f1, t)
r    = fma.s1(C_hi, f1, C_lo)
rsq  = fma.s1(r, r, f0)
c    = fms.s1(C_hi, f1, r); c = fma.s1(c, f1, C_lo)   // c=(C_hi−r)+C_lo
tmp  = r (sine) | 1.0 (cos);  (p12) tmp = −tmp (via fms.s1(f0,f1,tmp))
sine: poly = fma.s1(rsq, S_2, S_1); rcube = fma.s1(rsq, r, f0)
      poly = fma.s1(rcube, poly, c)
cos:  poly = fma.s1(rsq, C_2, C_1); poly = fma.s1(rsq, poly, f0)
FINAL: (p11) Result = fma.s0(tmp, f1, poly)
       (p12) Result = fms.s0(tmp, f1, poly)
```

## SMALL_R (|r| < 2^-3)  [L1754–1936]

Entries: SMALL_R (r,c,N_Inc ready), SMALL_R_0 (|x|<π/4: r=x, c=0),
SMALL_R_1 (moderate path). All converge on:

```
rsq = fma.s1(r, r, f0)
Z   = fma.s1(rsq, rsq, f0)                       // r^4
cos (p10): c = fnma.s1(c, r, f0)                 // c := −c·r
           r = fmerge.s(f1, f1)                  // r := 1.0
sine (p9): Z = fma.s1(Z, r, f0)                  // r^5
Z = fma.s1(Z, rsq, f0)                           // sine r^7 | cos r^6
sine: poly_lo = fma.s1(rsq, S_5, S_4); poly_hi = fma.s1(rsq, S_2, S_1)
      poly_lo = fma.s1(rsq, poly_lo, S_3)
      DUMMY fma.s0(S_4, S_4, f0)                 // user inexact
      poly_hi = fma.s1(poly_hi, rsq, f0)
      poly = fma.s1(Z, poly_lo, c)
      poly_hi = fma.s1(r, poly_hi, f0)           // r·r²·(S_1+r²S_2)
cos:  same shape with C_5..C_1, no trailing ·r on poly_hi
(p12) r = fms.s1(f0, f1, r)                      // r := −r  (leading term!)
poly = fma.s1(poly, f1, poly_hi)
FINAL: (p11) Result = fma.s0(r, f1, poly)        // r + poly
       (p12) Result = fms.s0(r, f1, poly)        // (−r) − poly
```

## NORMAL_R (2^-3 <= |r| <= π/4) — THE MAIN PATH  [L1939–2245]

Entries: NORMAL_R (larger-arg/huge), NORMAL_R_0 (|x|<π/4),
NORMAL_R_1 (moderate; frcpa#1 already done at L1067). Unified sequence:

```
rsq    = fma.s1(r, r, f0)
h1     = frcpa.s1(f1, r)                         // ~1/r, 8.886 bits
poly   = fma.s1(rsq, PP_8, PP_7)   | fma.s1(rsq, QQ_8, QQ_7)
rcube  = fma.s1(r, rsq, f0)
r_hi   = frcpa.s1(f1, h1)                        // ~r, table-rounded
poly   = fma.s1(rsq, poly, PP_6)   | … QQ_6
sine corr = fma.s1(C_1, rsq, f0)                 // C_1·r²   (C_1 ≈ −1/2)
cos  corr = fma.s1(S_1, rcube, r)                // r + S_1·r³
r_hi_sq = fma.s1(r_hi, r_hi, f0)                 // exact (10-bit r_hi)
r_lo   = fms.s1(r, f1, r_hi)
poly   = fma.s1(rsq, poly, PP_5)   | … QQ_5
sine corr = fma.s1(corr, c, c)                   // c·(1 + C_1 r²)
cos  corr = fnma.s1(corr, c, f0)                 // −c·(r + S_1 r³)
sine: U_lo = fma.s1(r, r_hi, r_hi_sq)            // r·r_hi + r_hi²
      U_hi = fma.s1(r_hi, r_hi_sq, f0)           // r_hi³ (exact)
cos:  U_lo = fma.s1(r_hi, f1, r)                 // r_hi + r
      U_hi = fma.s1(QQ_1, r_hi_sq, f1)           // 1 + QQ_1·r_hi² (exact)
poly   = fma.s1(rsq, poly, PP_4)   | … QQ_4
sine: U_lo = fma.s1(r, r, U_lo)                  // r² + r·r_hi + r_hi²
      U_hi = fma.s1(PP_1, U_hi, f0)              // PP_1_hi·r_hi³ (exact)
poly   = fma.s1(rsq, poly, PP_3)   | … QQ_3
sine: U_lo = fma.s1(r_lo, U_lo, f0)              // r_lo·(…)
      U_hi = fma.s1(r, f1, U_hi)                 // r + PP_1_hi·r_hi³ (EXACT)
cos:  U_lo = fma.s1(r_lo, U_lo, f0)              // r_lo·(r+r_hi)
      U_lo = fma.s1(QQ_1, U_lo, f0)
poly   = fma.s1(rsq, poly, PP_2)   | … QQ_2
sine: U_lo = fma.s1(PP_1, U_lo, f0)
sine: poly = fma.s1(rsq, poly, PP_1_lo)
cos:  poly = fma.s1(rsq, poly, f0)
V      = fma.s1(U_lo, f1, corr)
DUMMY  fma.s0(PP_5, PP_4, f0) | fma.s0(QQ_5, QQ_5, f0)   // user inexact
sine: poly = fma.s1(rcube, poly, f0)             // r³·(PP_1_lo + r²(PP_2+…))
cos:  poly = fma.s1(rsq, poly, f0)               // r⁴(QQ_2+…)
tmp    = +1.0 (p11) | −1.0 (p12)   (fma.s1/fms.s1 of f0,f1,±f1)
V      = fma.s1(poly, f1, V)
FINAL: (p11) Result = fma.s0(tmp, U_hi, V)       //  U_hi + V
       (p12) Result = fms.s0(tmp, U_hi, V)       // −U_hi − V
```

## Zero / special

```
x = ±0 : sinl → x (sign preserved, fmerge move); cosl → fma.s0(f1,f1,f0)=1.0
NaN/Inf: Result = fmpy.s0(x, f0)   // QNaN; invalid raised for SNaN/Inf
denormal: fnorm.s1 raises what's needed; rejoin main dispatch with norm_x's
          exponent
```

## Exactness inventory (why bit-exact reimplementation is tractable)

Proven/derivable exact (no rounding): s = x−N·P_1 (paper thm); c-chains
(2sum residuals: s−r, C_hi−r, U/V residual fms after fma of same product);
r_hi² and r_hi³ products (10-bit r_hi); PP_1_hi·r_hi³ (16-bit coeff × 30-bit
value); r + PP_1_hi·r_hi³ and 1 + QQ_1·r_hi² (Sterbenz-style alignment);
fcvt.xf; all fmerge/abs/negations.
Genuinely rounded (must round-to-nearest 64-bit correctly): x·2/π (+rshf),
w = N·P_2, r = s∓w, every Horner fma step, rsq, rcube, U_lo chain products,
corr chain, V sums, and the FINAL s0 op (user mode).

## Deltas: libm sinl/cosl vs x87 FSIN/FCOS/FSINCOS (per FMCAD00 paper)

1. |x| ≥ 2^63: libm → Payne–Hanek (__libm_pi_by_2_reduce); FSIN/FCOS → set
   C2, leave operand. (FSINCOS likewise.)
2. Flags: x87 sets C1 (result rounded up) / precision; the IA-64 emulation of
   those side effects is outside this file's scope.
3. sincosl (libm_sincosl.S) computes BOTH outputs (FSINCOS analog) — same
   tables; TODO: verify its op sequence matches this file's two predicated
   halves computed simultaneously.

## Open items for bit-exactness

1. ~~frcpa table~~ **RESOLVED**: exact 256-entry `fp_ieee_recip` table
   transcribed to `../data/frcpa-recip-table.h` (from the IA-64 SDM vol 3
   Operation pseudocode via the VTune instruction-reference mirror; raw page
   saved as `../data/frcpa-operation-page.html`). Semantics:
   index = significand bits {62:55}; out significand = 1.tttttttttt (10 table
   bits at {62:53}, rest zero); out exponent = 0x1FFFF − 2 − in exponent;
   sign preserved.
2. sf1 assumption (RN/64-bit/wre) — confirm glibc's FPSR setup for ia64
   (psABI software conventions) to be sure no path depends on wre beyond
   avoiding intermediate under/overflow (none expected for these ranges).
3. ~~libm_sincosl.S cross-check~~ **RESOLVED**: active constant tables are
   byte-identical to s_cosl.S (diff hits are only commented-out legacy
   `//data4` lines); structure is the dual-output FSINCOS shape — both PP and
   QQ kernels computed simultaneously, i_1 swaps which kernel feeds
   ResultS/ResultC (p12/p14 swap), each output finished by its own s0 op.
