# D0028: fresh-build C verification — 2026-09-06

The resumed goal, **create verified x87 FPATAN as C implementation**, was
checked against the actual delivered source, package and original observations.
No numerical changes were needed. The existing C implementation and optional
library remain the fixed V7 program, with no algorithm-selection flags.

## New verification

- The current delivered files match their D0027 hashes, and the source-only
  archive is unchanged. Its extracted build files and C sources also match
  the current implementation. Main/V7 executable tokens remain identical
  after removing comments.
- A new temporary extraction was built with Clang address/undefined-behavior
  sanitizers and `-fno-sanitize-recover=all`, and separately with GCC 15.
  Both standalone/library builds and regression tests pass.
- Clang static analysis of the main C source and library reports no diagnostics.
- The freshly built **sanitized standalone program** and **GCC library client**
  each replay all **2,783,208 observations across fourteen jobs**, with zero
  result, C1, exception or pre-load-flag differences. Every output-stream hash
  also matches the previously verified release transcript.
- All 26 arithmetic/solver unit tests pass, the D0025 exact equivalence
  certificate reproduces, and the diff check passes.

These are new software verification runs against preserved hardware evidence,
not new hardware captures. No native tuple was repeated, no private ledger
was read, and neither numerical code nor the paper was modified.

## Artifacts

Under `../tmp/fpatan-re/`:

- `d0028-reverification.json`: final status **PASS**, source/archive hashes,
  fresh build location, check commands and complete replay results.
- `d0028-{sanitized,gcc-library}-full-replay.json` and their replay logs.
- `d0028-{sanitized-build,gcc-build,static-analysis,unit-tests,certificate,diff-check}.json`.
- `d0028-started.json`: initial source identities and fresh build location.

The deliverable remains `fpatan_candidate.c` (a historical filename),
`fpatan_library.h`/`.c`, and the D0027 source package. Build/use is documented
in `DELIVERY.md`. Verification covers the documented Skylake masked numerical
contract; it is not an exhaustive all-raw80 or cross-CPU equivalence proof,
nor a promise to model arbitrary unmasked/restore-state behavior.
