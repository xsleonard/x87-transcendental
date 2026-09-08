# D0012 arithmetic exclusions and D0013 quotient-state discrimination

FPATAN remains **unsolved and unpromoted**. Main C/library are unchanged V4;
V5 is also falsified. No findings here belong in the solution paper.

## D0012: staged arithmetic and shared coefficients

The D0011 two-input final-role conflict is explicitly restricted to its
single-cut operation family. Composed rounders such as RN64(CHOP67(sum)) can
satisfy that small core: the intermediate cut can change a subsequent tie.
This does not invalidate the bounded certificate or validate the composed
graph. None of these fixed, input-independent programs passes the complete
279-group direct frontier:

| Family | Programs | Survivors |
| --- | ---: | ---: |
| Staged producer/read formats | 24,192 | 0 |
| Staged formats with tail reads | 145,152 | 0 |
| Literal fixed-point operand alignment | 960 | 0 |
| Wider/exact quotient consumers with cubic-first tail | 54,000 | 0 |
| Coupled alignment, square and tail roles | 72,576 | 0 |
| Total | 296,880 | 0 |

The best alignment-only program still fails eight raw frontier groups. These
are exclusions of stated families, not proof that no arithmetic graph exists.
Sources and per-program counterexamples are the corresponding
`d0012_*audit.py` and `../tmp/fpatan-re/d0012-*.json` files.

`d0012_coefficient_solve.py` encodes six global coefficient offsets for the
fixed MR64 asymmetric-square, cubic-first CHOP67 tail graph, with ordinary
CHOP67 Horner products and RN64 adds. The 137 direct endpoint constraints
use 1,507 quantized nodes. Four complete independent concrete assignments
calibrate each query, including both coefficient-bound extremes.

Both frozen 69-bit coefficient-grid queries are **UNKNOWN**, not UNSAT:

- `d0012-coefficient-solve-b28-p69-directcheck`: each coefficient offset is
  bounded by 2^28 grid ULPs. The internal 60-second timeout did not return
  promptly; the owned process was terminated after a live 6:20 observation.
- `d0012-coefficient-solve-b8-p69-bounded`: offsets bounded by 256 grid ULPs;
  the isolated worker reached its external deadline and was terminated.

The earlier calibration-search cancellation is separately recorded in
`d0012-coefficient-calibration-cancelled.json`; it produced no solver answer.
All SMT2, UNKNOWN and cancellation artifacts remain intact. Future solver
queries must use an isolated worker with an external deadline. A timeout
cannot exclude a coefficient bank. D0014 investigates a smaller encoding of
the same fixed graph; it does not rewrite these historical results.

## D0013: fresh identical-quotient inputs

The saved-data audit authenticated all 1,640,392 D0001--9 observations.
Among 104,508 selected normal, direct, unrotated PC64 observations, there
were 23,513 C67 quotient states. Of these, 137 had multiple exact external
ratios and none conflicted in output/C1. Those multi-ratio states did not
cover the 137 direct frontier states, so that audit alone did not test the
discarded-ratio hypothesis at the difficult inputs.

D0013 closed that coverage gap with **2,192 fresh raw pairs**: 16 different
exact ratios for each of 137 direct frontier quotient states (136 D0009
failed states and one D0008 resolved control). Both input significands change;
operand exponents and signs remain fixed; the exact C67 quotient is unchanged.
The discarded fraction spans 16 bins, reaching below 1/64 and above 63/64.
An independent integer-only verifier checks all quotient equalities.

The 8,840-observation campaign contains 8,768 PC64 four-RC anchor comparisons
plus 72 PC24/53 controls. Its structural prediction was frozen and its hash
pinned in DISPATCHED before the one-shot execution. Private/public/prior
FPATAN history checks cleared the new tuples; no old anchor was recaptured.
Only generic public capture tooling and cleared inputs were uploaded.

Authenticated result:

- **0 output splits and 0 C1 splits** across all 8,768 anchor comparisons.
- None of the 137 anchor states splits; no fresh group/RC variation occurs.
- The separately frozen, known-incomplete V4 baseline has **2,344 output
  misses and 1,212 C1 misses**. Exception/pre-load flags have zero misses.
- All 36 matched three-PC groups agree in value/status.

This supports quotient-state invariance **on this bank only**, not universal
sufficiency of C67 reduction and not validation of any numerical kernel.
The next arithmetic investigation should focus after the quotient, while
retaining the possibility of unobserved reduction effects elsewhere.

Receipts, raw compressed outputs, independent proof, frozen hypothesis and
both scores are under `../tmp/fpatan-re/d0013/`. Hardware SHA256:
`8755ad0ef9907bcd539a4b9dbe6986fe4b4d88e2f8d531aff18ab4b38c799f14`.
The remote ledger audit is integrity `ok`, with all ten jobs OBSERVED.

## Current acceptance corpus and discipline

The corpus now has **1,649,232 observations**, across D0001--D0009 and D0013.
D0010--D0012 are analysis identifiers, not hardware campaigns. Any future
candidate must pass all ten saved jobs and then fresh frozen discrimination.
Do not repeat any captured/reserved tuple. Compressed guarded acquisition is
mandatory; preserve failed predictions and partial receipts.

Python syntax, D0011 exact tests, D0012 staged/SMT/quotient tests and diff
checks passed at the D0013 checkpoint. Sanitized candidate/library selftests
also passed without numerical changes. Implementation checks do not resolve
the hardware counterexamples. The existing trig code and paper are untouched.
