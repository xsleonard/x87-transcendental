# FPATAN acceptance audit — D0027

Scope is the original handoff contract: a runnable, general bit-exact
numerical reconstruction for the authorized Skylake Xeon reference, under
the documented masked/clear/two-deep-stack contract. No new requirement for
physical microcode recovery, arbitrary restore history or unmasked traps is
introduced. Conversely, corpus agreement is not presented as an exhaustive
proof over every raw80 pair or every CPU.

## Requirements and evidence

| Requirement | Evidence and result |
| --- | --- |
| One runnable general C program | `fpatan_candidate.c` is self-contained apart from standard C and GMP. Its executable tokens exactly match the prospectively tested V7 source. No algorithm flags, host atan, native FPATAN, operand ledger or fitted exception selector. |
| Finite full-range inputs and quadrant restoration | Explicit exact-integer/rational graph in `ALGORITHM.md`; tiny, direct, table and quadrant paths; all original finite challenges and D0026's full-exponent controls replay exactly. |
| Signed zeros, denormals, pseudo-denormals, infinities, NaNs, invalid encodings | Total raw80 classifier and explicit result/priority handlers; D0005–D0007 class and underflow campaigns replay exactly with the final C, including the corrections discovered in their historical frozen scores. Canonical held both-special cases are documented/synthetic coverage, not invented native captures. |
| RN/RD/RU/RZ and relevant PC behavior | All four modes, PC24/PC53/PC64, architectural final rounding and C1 are represented. All recorded results match. D0026 has 1,404 complete three-PC groups with no value/status differences. |
| Applicable numerical/status effects | All output bits, C1, IE/DE/ZE/OE/UE/PE and pre-load exception flags match every retained row. Stack-pop depth and control words are validated by the capture protocol. Undefined C0/C2/C3, arbitrary save images and unmasked trap delivery are not promised by this API. |
| Structurally justified arithmetic, not fitting | Independent Goldmont operation incidence supports the two-chain polynomial and distinct sum classes; public P5 ROM constants are retained. V7 uses one general nearest/lower-tie index law. D0025 proves the odd/lower representation equivalence within the graph. No literal input corrections. |
| Prospective verification | D0023: 194,808; D0024: 66,248; D0026: 363,256. Total **624,312**, zero misses, with immutable predictions and source pins before one-shot execution. |
| Complete corpus replay | **2,783,208 observations in all fourteen jobs**, no omissions or mismatches. Independently compiled Clang, GCC 15 and the library client each replay the full corpus. |
| Reusable API and regression protection | `fpatan_library.*` wraps the identical implementation; sanitizer tests exercise every RC/PC, invalid API arguments and original failures from D0008, D0009 and D0022. |
| Build, syntax and reproducibility | Warning-clean C11 builds, sanitized candidate/library tests, 26 arithmetic/solver tests, protocol/architecture checks, D0025 exact certificate verification, `make all check`, and a freshly extracted source-package build. The durable final result is `d0027-delivery-checks.json`. |
| Preservation and one-shot discipline | Original captures, rejected predictions, SAT/UNSAT/UNKNOWN evidence and source pins are retained. D0026's ledger audit is `ok`, all fourteen jobs OBSERVED. No capture repeated; no private ledger/model code uploaded. Existing trig code and paper were not modified by this FPATAN work. |

## Authoritative artifacts

All generated records below are under `../tmp/fpatan-re/`:

- `d0027-main-full-replay.json`: final standalone Clang replay.
- `d0027-gcc15-full-replay.json`: independent compiler replay.
- `d0027-library-full-replay.json`: public API client replay.
- `d0026/{MANIFEST,C-PREFLIGHT,GCC15-PREFLIGHT,HISTORY,STAGED,DISPATCHED,STARTED,COMPLETE,SCORE,LEDGER-AUDIT}.json`:
  final prospective challenge, source/CPU identity and one-shot receipts.
- `d0026-rounding-boundary-mining.json`: 2,048 independently checked adjacent
  RN/RD transition brackets, no hardware labels used in mining.
- `d0025-midpoint-alias-certificate.json`: 106 rigorously enclosed states,
  3,392 independent endpoint checks; an exact candidate-graph identity.
- `d0027-delivery-checks.json`: source identity, final check commands,
  corpus inventory and clean source-package build validation.

D0001 predates per-job source copies. Its original pinned source bytes still
exist unchanged and are hash-checked; the replay explicitly records this
resolution. No historical snapshot is fabricated.

## Interpretation

The delivered model is a validated reconstruction with **zero known misses**
for the specified Skylake numerical contract. Its arithmetic is not a call
to correctly rounded mathematical atan2, which measurably differs from the
processor. The evidence does not prove universal equivalence for all raw80
pairs, a hidden silicon datapath, or transfer to another CPUID/microcode.
Those limits are not concealed by the word “bit-exact.” The numerical program,
prospective validation and delivery gates above are the completed work.
