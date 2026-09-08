# D0014: exact shared-coefficient and interpolation obstruction

This advances the investigation but does **not** solve FPATAN. No numerical
candidate, C/library default, trig implementation or paper was changed. No
hardware was executed. The D0013 corpus remains 1,649,232 observations across
ten jobs. The previous status-only response made no goal progress; this
continuation resolves an open computational question and adds independently
checkable structural evidence.

## The previously UNKNOWN question

D0012 asked whether changing six globally shared coefficients could rescue
one fixed direct-path graph:

```text
z = CHOP67(y/x)
u = RN64(z * CHOP64(z))
c = CHOP67(z*u)
h = A123
for k = 122 down to 118:
    h = RN64(Ak + CHOP67(u*h))
angle = z + CHOP67(c*h)
```

The 137 saved direct quotient states constrain the final angle using all
four rounding modes and C1. This graph is an analysis hypothesis, not the
main V4 implementation. It was motivated by earlier terminal feasibility;
it was never validated as a complete arithmetic solution.

`d0014_integer_coefficient_solve.py` replaces the mixed integer/real encoding
with centered integer significand differences. Exact inverse terminal
products eliminate the final multiplier, leaving 1,370 retained integer
nodes. Four full concrete assignments (P5 and three bound-extreme choices)
are checked using the independent integer rounder before each query is frozen.
There are no per-input coefficients or fitted selectors.

| Coefficient bounds, in each coefficient's 69-bit grid ULP | Z3 result | Total elapsed |
| --- | --- | ---: |
| +/-256 | UNSAT | 2.64 s |
| +/-2^28 | UNSAT | 15.62 s |

CVC5 1.3.1 independently parsed the exact frozen second SMT2 and also returned
UNSAT (32.85 s). Every solver worker exited normally; no deadline was reached.
The old D0012 SMT2 and UNKNOWN/cancellation records remain unchanged. The
new results resolve those coefficient boxes for this fixed graph; they do
not retroactively turn old timeouts into solver answers.

## A stronger, solver-free certificate

The continuous relaxation admits arbitrary real coefficients within the same
boxes and independent rounding errors at every operation/input. CHOP error
is enclosed by its signed one-ULP interval; RN64 error is enclosed by +/-half
an ULP. Strict endpoints and parity restrictions are deliberately relaxed.
The exact terminal inverse still constrains the final 64-bit h118 carrier.
Thus every exact execution is included, along with many impossible ones.

The +/-2^28 relaxation is UNSAT. A nonnegative combination of four native
input constraints and three coefficient-bound inequalities has all six
variable coefficients cancel and a right side of -1. Its consequence is
the contradiction **0 <= -1**.

`verify_d0014_certificate.py` independently reconstructs this certificate:

- authenticates all 171,920 original D0009 capture rows and the core's 16
  native observations;
- reads the public ROM TSV directly;
- reconstructs C67 division and the square with a separate integer rounder;
- finds the allowed h118 endpoints by monotone integer binary search, without
  importing the original interval/preimage or graph implementations;
- rebuilds the rounding-error envelope and every necessary inequality; and
- verifies the weighted contradiction using only exact rational arithmetic.

The verifier passes. This is stronger evidence than two solvers agreeing
on a potentially shared encoding error.

## Wide coefficient box and seven-input polynomial identity

The box was then expanded to **+/-2^60 69-bit-grid ULPs** for all six
coefficients. In absolute units those half-widths are 2^-10 for A118,
2^-11 for A119/A120, and 2^-12 for A121/A122/A123. This allows far more than
low-bit ROM changes.

The original fixed-binade encoder correctly refused this box before writing
a query: one intermediate product can cross a binade. That refusal is not
a SAT/UNSAT/UNKNOWN result. The separate wide error-envelope implementation
uses the largest ULP over each interval and propagates monotonically rounded
endpoint bounds. It remains a sound relaxation across such crossings.

The wide continuous relaxation is also UNSAT (9.72 s). Its certificate has
**seven observation inequalities and no active coefficient-bound inequality**.
The coefficient box is still needed to justify the rounding-error bounds;
do not claim unbounded coefficient exclusion. The independent verifier
authenticates and reconstructs all **28 native observations over seven inputs**,
then verifies another exact 0 <= -1 contradiction.

There is a simpler closed-form representation. Let u_i be those seven distinct
squared carriers. For any polynomial P of degree at most five,

```text
w_i = 1 / product_{j != i}(u_i - u_j)
sum_i w_i * P(u_i) = 0
```

The inferred h118 intervals, widened by every admitted arithmetic error,
force this sum strictly away from zero. `d0014_interpolation_certificate.py`
independently checks all six annihilated moments and the interval separation.
After normalizing sum(abs(w_i)) to one, the separation is approximately
**0.000611324 h118 ULPs**; all calculations and the certificate are exact
rationals. This proves a structural conflict, not just a failed search over
constants. It is a closed-form *exclusion*, not a closed-form FPATAN solution.

## Retained artifacts

All artifacts are under `../tmp/fpatan-re/`:

- `d0014-integer-coefficients-{b8,b28}-centered.{smt2,json}`
- `d0014-b28-cvc5-crosscheck.json`
- `d0014-continuous-coefficients-b28-relaxed.{smt2,json}`
- `d0014-continuous-coefficients-b60-wide-relaxed.{smt2,json}`
- `d0014-continuous-{b28,b60}-certificate.json`
- `d0014-independent-{b28,b60}-certificate.json`
- `d0014-interpolation-certificate.json`

Queries are frozen before solving and output reports are exclusive-create.
Current generators also include the later wide-binade support; query hashes
pin the exact historical formulas. All worker handles are terminal.

## Consequence and next work

Do not spend further effort tuning near-P5 constants for this fixed MR/cubic
graph. Its failure is more fundamental than coefficient low bits. A genuine
survivor needs a different arithmetic/dataflow mechanism, terminal/leading
combination, or independently justified polynomial representation. The seven
inputs form a useful necessary structural test; passing them would still be
discovery evidence, not closure or permission to ignore the rest of the corpus.
The separate table-path failure also remains unresolved.

Four new test groups pass: centered quantizer signs/ties, eight complete
random coefficient assignments, wide-box rounding-error enclosures on all
137 states, and certificate mutation rejection. The independent certificate
verifiers pass for both boxes. Main C remains byte-identical to D0009's frozen
source. No numerical model is promoted, and no paper update is warranted.

Final checkpoint checks also pass: all eleven D0011/D0012/D0014 test groups,
Python compileall, `git diff --check`, the existing sanitized C candidate and
library selftests, and an authenticated D0013 structural-score replay. The
replay reproduces the existing score without rewriting it. Every solver/test
session started in this continuation is confirmed terminal; no job needs
polling or restarting.
