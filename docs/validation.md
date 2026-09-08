# Validation and confidence limits

`make check` builds and runs the offline library suite. It uses independent
integer/rational references and compact saved hardware observations; it requires
no external arithmetic library, research archive or native hardware capture.
The fixtures in `tests/data/` retain the capture metadata needed to identify
their expected hardware results.

## Default regression suite

- The finite-arithmetic oracle checks exact operations, rounding, cancellation,
  large exponent gaps, subnormal encoding and unmasked exponent adjustments
  against Python `Fraction` and integer arithmetic.
- Numerical replay covers 1,800 hardware rows, including 1,720 C1 values,
  506 C2 values and 1,006 complete exception masks. Independent references cover
  the applicable arctangent, tangent, exponential and logarithm witnesses.
  Scorer tests reject missing condition-code metadata.
- Architectural tests cover masked and unmasked results, special operands,
  suppressed writes, pushes and pops. The special-value matrix has 14,848 cases
  across all 64 exception-mask combinations and four rounding modes.
- The packaged [outcome corpus](../tests/data/outcome-witnesses.json.gz) contains
  22,528 full-state hardware captures spanning 88 operand families, four rounding
  modes and all 64 masks at PC64. Its metadata records the Xeon CPU signature
  `00050654`, microcode `0x1`, and original capture and prediction hashes.
- C tests check unchanged outputs on error, raw80 conversion, explicit controls,
  shared-context concurrency, compatibility APIs and the masked adapter example.
  Consumer-link and symbol tests check that internal names remain private.

Full-state hardware captures are labeled separately from older observations
whose expected stack writeback follows the instruction contract. Pending
exceptions and empty/full-stack behavior belong to the emulator integration.

The arithmetic oracle can also be run directly after `make check`:

```sh
python3 tests/arithmetic/check_finite.py build/x87trans-finite-test
```

## Expanded offline replay

The optional replay tools authenticate larger saved captures against their
source receipts and acceptance inventories. `replay_binary.py` reads FPATAN
and logarithm packs under `research/fsincos-re/tmp/`; `replay_expanded.py`
reads FPTAN/F2XM1 packs under its `verification-expansion/` subdirectory.
These local datasets are outside the source package and are not required by
the default suite. The tools report the observations and fields checked
against the selected build:

```sh
python3 tools/validation/replay_binary.py build/x87trans-outcomes
python3 tools/validation/replay_expanded.py build/x87trans-cli
python3 tools/validation/prepare_state_witnesses.py --full-h1656 --output /tmp/all-states.json
python3 tests/regression/outcomes.py build/x87trans-outcomes /tmp/all-states.json
```

The complete state corpus contains 37,986 cases: 26,081 valid arithmetic
prestates and 11,905 stack/pending cases. The latter require Bochs. Adding the
22,528 packaged outcome cases gives the 60,514-case emulator corpus. Follow the
[Bochs integration procedure](bochs.md) to build the adapter, then replay with:

```sh
python3 tools/integration/run_bochs.py /path/to/bochs /tmp/all-states.json tests/data/outcome-witnesses.json.gz
```

## Build and consumer checks

Exercise Release static/shared builds and Debug ASan/UBSan builds when changing
library behavior or its build configuration. The deterministic raw80 sanitizer
sample checks API invariants; it is not a numerical oracle.

`make package` creates a source archive and prints its path. From the repository
checkout, verify that archive independently of the research tree:

```sh
python3 tools/validation/check_package.py /path/to/source.tar.gz --libdir lib
python3 tools/validation/check_package.py /path/to/source.tar.gz --libdir lib/test-triplet
```

The package checker verifies the file manifest, runs the offline suite, and
checks installed and vendored C/C++ consumers and relocated pkg-config paths.
It disables GMP discovery and checks the absence of external arithmetic linkage.
Generated packages and build/run reports belong in ignored `output/` or local
scratch storage. Temporary plans and migration receipts are not documentation.

## Remaining limits

This is a reconstructed Skylake profile, not a universal x87 implementation or a
claim of correctly rounded transcendental mathematics. Its numerical programs
reproduce internal precision cuts and CPU-specific results. A finite test set
cannot prove every raw80 input, boundary or processor stepping. Result bits,
exception flags and C1 each need evidence.

F2XM1 infinities and FYL2XP1 outside its accepted finite domain return
OUTSIDE_SCOPE; the adapter must choose a fallback. Undefined condition bits,
arbitrary malformed restore histories and complete CPU/platform exception
machinery are outside the arithmetic library. Bochs tests its configured guest
#MF path; they do not certify every legacy platform's external IRQ13 wiring.
See [the API contract](api.md) for the exact boundary.
