# Working spec: the Itanium IA-32-compat FSIN/FCOS/FSINCOS algorithm

Source: the 2000 Intel formal-verification paper (Itanium IA-32 compatibility;
stated to be the same algorithm as Intel's double-extended math library),
as collected in the initial research dump. This file is the ground-truth spec
we reconstruct against; unknowns are marked **[UNKNOWN]**.

## Historical placement

| Era        | CPUs                | FSINCOS implementation                     |
|------------|---------------------|--------------------------------------------|
| 1980–1987  | 8087 / 80287        | CORDIC; no FSINCOS instruction              |
| 1987–1993  | 80387 / 486         | FSINCOS added; iterative/CORDIC-derived     |
| 1993–1999  | Pentium / P6        | undocumented transition to polynomial       |
| 2000–      | NetBurst onward     | polynomial/microcode, revised per generation|

The Pentium (1993) version is a *different*, table-assisted design (2 sine
variants — 4- and 6-term, 2 cosine variants, 16 sin/cos constants at multiples
of 1/64, reconstruction via sin(a+b) identity at b = n/64). Its constant ROM
was physically decoded in 2025. Useful as contrast; NOT our target.

Our target — the 2000-documented version — is explicitly **table-free**.

## Algorithm skeleton

1. **Domain gate:** |x| ≥ 2^63 → IA-32-compatible rejection/special handling
   (C2 set, operand unchanged — x87 semantics). [Details **[UNKNOWN]**: exact
   flag/register behavior sequencing in this version.]
2. **Range reduction:** N ≈ round(x · 2/π); x = N·(π/2) + r with |r| ≤ π/4.
   Uses the legacy *limited-precision* π approximation for x87 compatibility
   (NOT a correctly-rounded infinite-π reduction — this is the famous
   "fsin is inaccurate for large args" property, preserved deliberately).
   **[UNKNOWN]**: the exact stored π/2 (or 2/π) bit patterns and the reduction
   arithmetic (how many partial products, what precision each step).
3. **Two-part reduced argument:** y = r + c, where c is a small correction
   carrying the low-order information lost during reduction.
4. **Path select by |r| magnitude** (variable-length polynomial paths):
   - |r| extremely tiny (documented case: |r| < 2^-33) → near-identity;
     cos path returns 1 − 2^-67 (rounds to 1 under round-to-nearest but
     preserves directed-rounding behavior).
   - small r → short polynomial;
   - medium r → intermediate polynomial;
   - up to π/4 → full kernel.
   **[UNKNOWN]**: the exact thresholds and the shorter kernels' degrees and
   coefficients.
5. **Full sine kernel — odd, degree 17, Remez/minimax (not Taylor):**

   p(y) = y + P1·y³ + P2·y⁵ + … + P8·y¹⁷    (8 stored non-leading coefficients)

   Evaluated Horner-style in r²:

   ```c
   // Compensated polynomial sine, |r| <~ pi/4, y = r + c
   r2 = r * r;

   poly = P8;
   poly = P7 + r2 * poly;
   poly = P6 + r2 * poly;
   poly = P5 + r2 * poly;
   poly = P4 + r2 * poly;
   poly = P3 + r2 * poly;
   poly = P2 + r2 * poly;
   poly = P1 + r2 * poly;

   sin_r = r + (r * r2) * poly;
   correction = c * (1 - 0.5 * r2);   // ~= c * cos(r): angle-addition compensation
   result = sin_r + correction;
   ```

   Closed form: sin(r+c) ≈ r + r³·(P1 + r²·(P2 + … + r²·P8)) + c·(1 − r²/2).

   The correction step is the linearized angle-addition formula
   sin(r+c) = sin(r)cos(c) + cos(r)sin(c) ≈ sin(r) + c·cos(r), with cos(r)
   approximated as 1 − r²/2 for this term.

   **[UNKNOWN]**: P1..P8 numerical values (double-extended bit patterns).
6. **Cosine kernel:** even polynomial counterpart. **[UNKNOWN]**: degree
   (presumably 16, i.e. 1 + Q1·y² + … + Q8·y¹⁶ or similar), coefficients, and
   its compensation term (≈ −c·sin(r), presumably −c·r or −c·(r − r³/6)).
7. **Quadrant fix-up:** N mod 4 selects sine/cosine swap and sign for each of
   the two outputs (FSINCOS produces both).
8. **No lookup table anywhere** — explicitly atypical vs the Pentium ROM design.

## Precision model

- Everything runs in double-extended (64-bit mantissa) — this is both the x87
  register format and the Itanium FP register format, which is *why* the same
  algorithm serves both the IA-32-compat instructions and Intel's
  double-extended libm.
- **[UNKNOWN]**: where the algorithm relies on fused multiply-add (Itanium has
  FMA; x87 does not) — a critical faithfulness question when transplanting the
  algorithm: an FMA-based evaluation rounds differently than an x87
  mul-then-add chain. If the shipped IA-32-compat code used fma, native-P4
  microcode cannot have been literally the same arithmetic. Investigate what
  the paper's verification model assumed per operation.

## Known open questions (the reconstruction targets)

1. P1..P8 bit patterns (and cosine-side Q coefficients).
2. Shorter-kernel thresholds/degrees/coefficients.
3. Exact reduction constants and step-by-step reduction arithmetic (incl. how
   c is produced).
4. Rounding/precision of each operation (FMA vs separate mul/add; any
   double-precision intermediates?).
5. Quadrant bookkeeping details (N computation exact rounding; parity mapping).
6. Special-value handling (±0, denormals, |x| in [2^62, 2^63), NaN/Inf, C2).

## Source-hunt status

See `source-hunt.md` (running log).

## Skylake standalone-FCOS near-1 terminal: the closed-form
## correction model (RECONSTRUCTED, Rounds 57→61, 2026-08)

Unlike the sections above (the 2000-paper target spec), this section is
a reconstruction RESULT: the bit-exact model of the Skylake FCOS
terminal's retained-unit deviations in the 3ffc near-1 band, derived
from ~35M labeled hardware captures and shipped as closed-form integer
logic in `src/fsincos_skylake.c` (`--round60-fcos-tie-gate`; Rounds
59/60/61 — the Round-57 statistical tables are deleted). The
[processor comparison](skylake-comparison.md) describes the supporting experiments.

### Frame quantities (all integer, from the model's own terminal)

With sq = chop67(m·m), f4 = chop67(sq·sq), left = chop67(sq·neg),
right = chop67(f4·pos), the payload carrier (Rounds 52/53) forms the
terminal subtract M = S − B at scale `rscale`, retained R = M >> k,
k = width(M) − 67.  Then:

    low3  = sq mod 8;   lp = low3 mod 2
    disc  = M mod 2^k
    θ     = disc            if disc ≤ 2          (down side)
          = disc − 2^k      if disc ≥ 2^k − 2    (up side, θ ∈ {−2,−1})
          (|θ| > 2: no deviation — outside the near-tie band)
    ce    = rscale + k ∈ {−73, −72};  phase  phw = ce mod 8 ∈ {7, 0}
    s4    = width(sq²) − 67 ∈ {66, 67};  t4 = sq² mod 2^s4
    sqlow = sq − 2^66
    Mg    = low3·sqlow − t4        (≡ low3·sqlow − (sqlow² mod 2^s4))
    rdisc = (f4·pos) mod 2^rsh,  rsh = width(f4·pos) − 67
    b1    = [3·rdisc ≥ 2^rsh];   b2 = [3·rdisc ≥ 2^(rsh+1)]
    side  = [m ≥ 0xB504F333F9DE6800]        (integer 1/√2 pivot)
    quadrant = (s4, side)

### The u-floor (shared by tie gate and θ band)

    u = K·⌊(a·low3 + G1·b1 + G2·b2 + p·lp + W(d) ∓ T) / Q⌋ + par·lp

Quadrant tuples (a, G1, G2, p, Q, K, par; W(d), d = |e2(left)−e2(right)|):

    (66,hi): 2,2,1, 0, 4,1,0;  W = −5(d−7)
    (66,lo): 4,1,0, 0, 2,1,0;  W = −9 −5(d−9)
    (67,lo): 4,2,1,−2, 4,2,1;  W = −5(d−7)
    (67,hi): 2,2,3,−3, 8,2,1;  W = −4 −2(d−7)

### Tie gate (θ = 0; Round 60)

T = 0.  **fire ⇔ Mg < u·2^66**; fire drops one retained unit (R−1).

### θ band (θ ∈ {±1, ±2}; Rounds 59/61)

T = c0 + cb1·b1 + cb2·b2 + clp·lp + cd·(d−7), per (direction, |θ|,
quadrant); (66,hi) and (67,lo) share every vector:

    dir  |θ|  (66,hi)/(67,lo)   (67,hi)          (66,lo)
    dn    1   ( 8, 1,−1, 1,−3)  ( 2, 1, 0, 0, 4) ( 1, 1,−1, 1, 0)
    dn    2   (18, 0, 0, 0,−6)  never fires*     (12, 0, 0, 0,−3)
    up    1   ( 6,−1, 0, 1,−1)  ( 6, 1, 0,−2, 0) ( 7,−1, 1, 1,−2)
    up    2   ( 6, 0, 0, 1, 0)  (12, 0, 0, 0, 0) ( 8, 1, 0, 1,−2)

    *dn-θ2-(67,hi): 4 isolated anomaly rows / 1,062,340 — modeled clean.

Region (fireable band): dn ⇔ Mg < u·2^66 (T subtracted);
up ⇔ Mg ≥ u·2^66 (T added).  Inside the region every row deviates
(dn → R−1, up → R+1) EXCEPT at block-critical cells:

    pm   = run length of ~(S XOR B) upward from bit k
    critical ⇔ (pm + phw) ≡ 7 (mod 8)  and  pm ∈ {7, 8}

At critical cells the deviation is decided by two bits of M
(the **block-start law**, h662k):

    bs = k + 8 + ((8 − phw) mod 8)     (first 8-bit block start ≥ k+8)
    up:  fire ⇔ M bit bs
    dn:  fire ⇔ M bit (k+8)  AND  M bit bs

Mechanistic reading: an 8-bit carry-select adder confirming a
mispredicted carry/borrow against the next block's sum bit at its
start position (consistent with the Pentium-lineage FPU structural
prior: radix-8 Booth, 4:2 CSA tree, carry-predict over unsummed low
product bits).

### Validation and residuals

Hardware scoring (cos × rn/rd/ru, model vs capture): comb7 2/5.84M,
comb9 13/19.85M, comb11+comb12 (W1 window, blind) 0/6.07M.  All
residuals belong to three documented families: borrow-edge
reconstruction rows (magnitude ≡ …0001 with a zero run through the
boundary), h658 anomaly rows, and the h656 tie-residual class
(9/6.86M).  No statistical machinery remains in the cos path.

### Scope caveat — the FSINCOS paired lane

This model covers the STANDALONE FCOS schedule only.  The FSINCOS
cos-lane deviations at the same inputs are deterministic but read
schedule/datapath state that is provably not a function of any
operand bit field (h662y purity failure; h663c steering verdict);
their deliverable is the characterized statistical model + two causal
inputs (criticality; the lud2 left-tail ladder = the two-column
truncation shift between schedules), as tested by experiments h662m–h663c.
