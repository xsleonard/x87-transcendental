# Source hunt — running log

## 2026-07-19 — standalone FSIN/FCOS

The focused primary-source review and experiment plan are in
[`fsin-source-hunt.md`](fsin-source-hunt.md).  Peter Tang's 1990 implementation
report and 1991 table-lookup paper provide the strongest P5 algorithm lineage
found so far; the latter's breakpoint family contains all eight recovered P5
trigonometric table points.

## 2026-07-14 — FOUND on day one (route 1 paid out immediately)

1. Paper identified: **John Harrison, "Formal Verification of Floating Point
   Trigonometric Functions", FMCAD 2000** (LNCS 1954, pp. 217–233).
   PDF: http://www.cl.cam.ac.uk/~jrh13/papers/fmcad00.pdf (saved as
   `../data/harrison-fmcad00.pdf`; note: downloaded PDF is 6 pages vs the
   17-page proceedings version — verify completeness / find full version).
   Companion paper (libm side): Harrison, Kubaska, Story, Tang, **"The
   Computation of Transcendental Functions on the IA-64 Architecture"**,
   Intel Technology Journal Q4 1999 — saved as
   `../data/harrison-itj-q4-1999.pdf`.

2. **The "lost" Intel assembly source was never lost — Intel contributed it to
   glibc** (`sysdeps/ia64/fpu/`, present through glibc-2.38, removed in 2.39).
   `s_cosl.S` (= `sincosl.s`) contains the complete FSIN/FCOS algorithm
   description and every constant, matching the research dump's structure
   exactly:
   - N·π/2 + α reduction, |α| ≤ π/4, quadrant by 2 lsb of M (i_0 sign flip,
     i_1 sin/cos swap), cos via N+1.
   - Two-part reduced arg r + c.
   - Case 2 (|s| < 2^-33 after moderate reduction): sin = r + c − r³/6,
     cos = 1 − 2^-67  ← the exact 2^-67 from the research dump.
   - Case 4 (large-arg pre-reduction, |s| < 2^-14): 2–3 Taylor terms.
   - small_r (|r| < 2^-3): degree-11 sine S_1..S_5 / degree-10 cosine C_1..C_5.
   - normal_r (2^-3 ≤ |r| ≤ π/4): degree-17 sine kernel PP_1(split hi/lo),
     PP_2..PP_8; degree-16 cosine QQ_1..QQ_8; corrections c(1 + C_1 r²) and
     −c(r + S_1 r² r).
   - The U_hi/U_lo exact-split trick: r_hi = frcpa(frcpa(r)) (≈10-bit r),
     PP_1_hi deliberately only 16 bits so r + PP_1_hi·r_hi³ is EXACT;
     the last add/sub is done in the user's rounding mode.
   - |x| ≥ 2^63 → libm goes Payne–Hanek (`__libm_pi_by_2_reduce`); the IA-32
     FSIN instead sets C2 (documented x87 behavior; the compat layer's
     difference to confirm in the paper).

   Files preserved in `../data/glibc-ia64-fpu/` (see PROVENANCE.md).

3. Mapping to the research dump's "P1..P8": those are PP_1..PP_8 with PP_1
   stored split (PP_1_hi exact-arithmetic piece + PP_1_lo remainder) — so the
   dump's "8 stored non-leading coefficients" is essentially right, with the
   twist that the lead coefficient is engineered for exact computation, not
   just stored.

## Still open

- Verify the fmcad00.pdf completeness (6 pages downloaded vs 17 in LNCS).
- Itanium-vs-x87 instruction question: this code uses fma and frcpa —
  instructions real x87 lacks. Confirm from the paper what the IA-32
  Execution Layer / native P4 relationship actually is (paper says
  "used in the Itanium processor to provide compatibility with IA-32
  hardware transcendentals").
- Compare against real Intel x86 silicon fsincos (Debian host — check
  vendor_id first) to measure how close modern native microcode is to this
  described version.
