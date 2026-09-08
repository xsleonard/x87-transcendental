# D0017–D0020: additional exclusions and certified diagnostics

These are negative/diagnostic results, not a completed FPATAN solution.
They use saved observations only. No main numerical default, trig source or
paper was changed. The subsequent source-guided V6 work is in
[ANALYSIS-D0021.md](ANALYSIS-D0021.md).

## D0017: signed arithmetic and retained residuals

- 77,760 fixed signed-truncation programs: no survivor on 279 direct groups.
  Products distinguish magnitude CHOP, floor, ceiling and away-from-zero;
  sums also test RN. Choices apply to fixed operation roles, not operands.
- 13,824 two-part residual programs: no survivor. A `(high, low)` carrier
  propagates both multiplication cross terms and the residual product. Fixed
  role bits determine whether each producer retains its own rounding loss.
  Residuals are exact, RN64 or CHOP67. Complete exact-residual propagation
  reconstructs the exact polynomial; this identity is checked separately.

Artifacts: `d0017-signed-truncation-audit.json` and
`d0017-residual-state-audit.json` under `../tmp/fpatan-re/`.

## D0018: separate programs per architectural RC

The earlier all-mode tests could reject a recipe even if it works in one
mode. D0018 therefore tests each program independently in RN/RD/RU/RZ, on
279 rows per mode. Families: internal-RC (15,552), signed (77,760), residual
(13,824). Every family has zero survivors in every mode: 428,544 separate
mode-restricted program tests. This excludes only those specified families.
It does not prove that real hardware ignores RC internally.

Artifacts: `d0018-rc-factorization-{internal-rc,signed,residual,summary}.json`.

## D0019: mathematical versus silicon diagnostics

Twenty-four alternating rational Taylor terms give certified atan bounds.
The bank contains 137 distinct unrotated direct quotient/interval states and
548 saved four-mode observations. All diagnostic outputs/C1 are certified;
no interval remains UNKNOWN.

| Diagnostic | Incompatible groups | Output differences | C1 differences |
| --- | ---: | ---: | ---: |
| Exact atan of CHOP67 ratio | 63 | 141 | 71 |
| Exact atan of external ratio | 83 | 153 | 83 |
| Exact P5 polynomial of CHOP67 ratio | 66 | 146 | 74 |

Correct mathematical atan is not a silicon replacement. A local independent
MPFR checker verifies all 274 transcendental enclosures at 768-bit precision;
an independent integer rounder checks all 1,644 variant/RC predictions.
False enclosures and malformed data are correctly rejected.

Artifacts: `d0019-certified-atan-diagnostic.json` and
`d0019-independent-diagnostic-verification.json`. Sources include
`d0019_check_atan_bounds.c` and `verify_d0019_diagnostic.py`.

## D0020: leading term inside the final product

The exact identity `z + z*u*H(u) = z*(1 + u*H(u))` moves a rounding site
across the leading term. The 79,380 programs explicitly materialize this
near-one factor with fixed formats up to 128 bits or exact arithmetic.
None survives the direct frontier. Prior expression-tree audits retained
the leading z outside the product; this is a distinct terminal family.

Artifact: `d0020-factored-lead-audit.json`.

## Independent replay

`verify_d0017_d0020.py` authenticates 1,228,664 original D0008/D0009 rows and
all 1,140 frontier observations, then independently reconstructs every saved
counterexample: **599,508 successful replays**. It uses separately written
integer rounding, direct quotient, operation schedules and quadrant handling,
not the audited kernels. This is full counterexample replay, not a sample.
The immutable receipt is `d0017-d0020-independent-replay.json`.

Six additional unit-test groups pass, including signed rounding, complete
residual and factored identities, atan reduction/nesting, preserved interval
uncertainty and diagnostic score reconstruction.
