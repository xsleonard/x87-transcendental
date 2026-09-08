# D0026–D0027: final rounding wall and numerical delivery

**V7 passes the final fresh challenge and is promoted to the main C program
and library.** All **2,783,208 retained observations** match in output, C1,
exception flags and pre-load flags. Of these, **624,312** were prospective
tests of unchanged V7. This completes the documented Skylake masked numerical
reconstruction/delivery contract, not an exhaustive all-raw80 or cross-CPU
proof. See [ACCEPTANCE.md](ACCEPTANCE.md) for the requirement audit.

## D0026: targeted final-rounding transitions

The local GMP C miner found 2,048 adjacent external-significand brackets
crossing an RN or RD output value. An independent Python implementation
confirmed every bracket. Five neighboring inputs at each bracket were
expanded across signs, octants and common exponent scales, with 8,192
independent full-exponent controls. No hardware labels were used in mining.

The cleared, frozen bank contains **90,112 raw pairs / 363,256 observations**.
Both sanitized Clang and GCC 15 matched all frozen Python predictions before
dispatch. The one-shot Skylake result has:

- zero output, C1, exception or pre-load-flag misses;
- 1,984 observed underflow rows;
- 1,404 complete PC24/PC53/PC64 groups, no value/status differences.

The immutable capture is authenticated, scored and terminal/OBSERVED. Ledger
integrity is `ok`; all fourteen jobs are OBSERVED. Never repeat their tuples.
The initial local miner build had an oversized seed literal; it was corrected
before any mining or capture. Its empty failed-build output is preserved as
`d0026-rounding-boundary-seeds.failed-compilation.tsv`.

## D0027: implementation and delivery

The main `fpatan_candidate.c` now contains the exact V7 executable tokens,
with explanatory comments updated and historical code comments retained.
The short ROM coefficient set, two-chain polynomial and general lower-tie
index rule are unconditional. `architecture.POLICY` defaults to V7. The
library continues to wrap the same main C file, without numerical switches.
The archived V7 source and every frozen campaign snapshot are unchanged.

A token-level comparison caught a transient transcription error during
integration; it was corrected before compilation/replay. Final main/V7 tokens
are identical after removing comments. No unverified arithmetic change was
introduced in promotion.

Three complete, independent local replays each pass all fourteen jobs and
all 2,783,208 observations:

- Clang standalone executable;
- GCC 15 standalone executable;
- the public library API via its independent batch client.

The library test now includes original D0008, D0009 and D0022 hardware
counterexamples under every RC/PC, alongside special values and invalid API
arguments. Sanitizer tests, all 26 arithmetic/solver unit tests, architecture
and protocol selftests, synthetic compressed-guard/pipeline/mutation tests,
syntax checks, D0025 certificate reproduction and diff checks pass.

The final audit also counts actual operand classes and RC/PC coverage from
every input file, validates source/CPU/result pins, checks the no-native-atan
source constraint, and builds/tests a freshly extracted source-only package.
Its durable status is **PASS** in `d0027-delivery-checks.json`.

## Artifacts

Under `../tmp/fpatan-re/`:

- `d0026/`: original frozen input/predictions, native output and every receipt.
- `d0026-rounding-boundary-{seeds.tsv,mining.json}`: software-only seed evidence.
- `d0027-v7-prepromotion-replay.json`: authenticated thirteen-job checkpoint.
- `d0027-{main,gcc15,library}-full-replay.json`: complete final replays.
- `d0027-delivery-checks.json`: source identity, corpus inventory, thirteen
  successful check commands and fresh-package verification.
- `fpatan-d0027-v1-source.tar.gz`: source-only standalone/library release,
  build files, regression tests, algorithm/contract documentation and a
  public evidence manifest. No private data or raw captures are packaged.

No existing trigonometric implementation, academic paper, historical solver
artifact or original capture was changed by this work. Additional CPUID
transfer and exhaustive verification remain distinct research questions;
they are not silently claimed by this numerical delivery.
