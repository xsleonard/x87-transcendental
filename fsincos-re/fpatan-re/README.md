# Skylake FPATAN reconstruction

**Current: V7 is integrated into the main C implementation and library.**
The unchanged main C program now matches **7,571,628 distinct retained
Skylake observations** in twenty-three corpus packs. The newest
[independent challenge](ANALYSIS-D0065-D0070.md) adds 445,588 fresh tuples
per CPU: mathematical/SMT-lattice boundaries, raw-bit strata and exhaustive
two-operand windows, selected without importing candidate arithmetic.
Both CPUs pass every output/C1/exception check and their complete raw output
streams are byte-identical. Hardware also distinguishes
**nearest/even at all four formerly masked RN64 additions** among the four
fixed tie rules: long odd-inner, long even-inner, short odd-chain and short
correction. Each has endpoint-visible evidence at both retained parities.
The four challenges total 28,456 rows, with zero baseline output/C1/exception
misses; every alternative rule is falsified at each targeted addition.
See the [completed tie-rule investigation](ANALYSIS-D0058-D0062.md),
the earlier [joint-boundary construction](ANALYSIS-D0055-D0057.md),
the earlier [algebraic inverse and masking proofs](ANALYSIS-D0048-D0053.md),
[D0045–D0047](ANALYSIS-D0045-D0046.md),
[D0041–D0044](ANALYSIS-D0041-D0044.md),
[D0037–D0040](ANALYSIS-D0037-D0040.md), the earlier
[restored-boundary/discarded-history challenge](ANALYSIS-D0034-D0036.md), the
[exact-square-tie challenge](ANALYSIS-D0031-D0033.md), and the reusable
[FPATAN corpus v1](corpus-v1/README.md) with its
[append-only current catalog](corpus-v1/CATALOG-D0066.json).
The common **7,543,172-tuple subset also passes on i7**, with zero output,
C1, exception or complete captured-status differences from Skylake. The older
28,456 tuples from D0046/D0057/D0061/D0063 have not yet run on i7. This comparison is
agreement between two recorded CPU contexts, not all-generation transfer.
This completes the four-node fixed-rule investigation; broader all-input
and cross-CPU claims remain unproven.

At the original delivery, both interfaces, plus a GCC 15 build, matched **2,783,208 retained
observations** with zero output, C1 or exception differences. **624,312
observations were prospective tests of unchanged V7**, including the final
rounding-boundary challenge. See [DELIVERY.md](DELIVERY.md) for build/use,
[ALGORITHM.md](ALGORITHM.md) for the fixed graph, and
[ACCEPTANCE.md](ACCEPTANCE.md) for scope and evidence limits.

The [programmer's pseudocode](PSEUDOCODE.md) and
[FPATAN paper](paper/README.md) specify the same program, including literal
ROM provenance, RC/PC behavior, raw80 classes and flags. The pseudocode is
checked directly against the publication snapshot's 2,783,208 observations; its blocks are shared
with the paper's appendix.

There is no operand ledger or algorithm-selection flag. This is a validated
Skylake numerical reconstruction, not a universal all-input/cross-CPU proof
or an emulation of arbitrary unmasked/restore-state behavior. The existing
trig implementation and paper are unchanged.

## Historical pre-promotion checkpoints

**Current: V7 passes D0023 and D0024, 261,056 fresh observations with zero
misses, and all 2,158,896 prior observations.** The complete corpus totals
2,419,952 observations. All tested numerically distinct index alternatives
are falsified; D0025 proves that odd/lower ties are output-equivalent within
the fixed graph for every input. This does not prove the hidden silicon
selector or universal hardware agreement. Final hard-rounding verification
and acceptance/delivery work remain; main C/library are still V4 and the
paper is unchanged. See [D0024–D0025](ANALYSIS-D0024-D0025.md).

## Historical D0023 checkpoint

**Current: V7 passes the fresh D0023 midpoint challenge, but is not yet
promoted.** All 194,808 new observations match in output, C1 and exception
flags, following zero misses on 2,158,896 saved observations. The complete
corpus now totals 2,353,704 observations. V7 uses V6's source-guided polynomial
with a general nearest-index/lower-tie rule. Frozen upper/even and rounded
reciprocal alternatives fail; odd ties and CHOP67 reciprocal are not yet
distinguished. D0024 targets unmasked denominator bits and closer midpoint
neighbors. Main C/library remain V4; no paper changes. See
[D0023](ANALYSIS-D0023.md) and [HANDOFF.md](HANDOFF.md).

## Historical V6 rejection checkpoint

**Current: FPATAN remains unsolved.** [D0022](ANALYSIS-D0022.md) prospectively
falsified V6: 12 output and 8 C1 differences in 509,664 fresh observations.
All failures share the exact table midpoint 19/64; the lower neighboring
cell explains them, but the general index/tie rule still needs discrimination.
The complete corpus is 2,158,896 observations across eleven one-shot jobs.
Main C/library and paper are unchanged. Read [HANDOFF.md](HANDOFF.md).

## Historical V6 discovery checkpoint (superseded by D0022)

**Latest: V6 matches all 1,649,232 saved observations, but remains unpromoted
pending fresh prospective validation.** [D0021](ANALYSIS-D0021.md) derives a
two-chain polynomial from independent public Goldmont operation incidence;
its distinct add classes resolve every saved V4/V5 failure without an operand
selector. `fpatan_candidate_v6.c` is self-contained and takes no algorithm
flags. Sanitized C/Python parity passes 9,844 cases. Goldmont lineage is not a
Skylake behavior proof. Main C/library remain V4; the paper is unchanged.
Read [HANDOFF.md](HANDOFF.md) and D0022's actual receipts before any capture.

## Superseded analysis checkpoint

**Current: FPATAN remains unsolved.** The latest
[D0015/D0016 analysis](ANALYSIS-D0015-D0016.md) rejects the tested compensated,
internal-RC and sticky representations, plus 210 wider-accumulator/shared-
coefficient families. No new numerical model survives or is promoted. Earlier
[D0014 analysis](ANALYSIS-D0014.md) independently proves that changing the
six shared coefficients cannot rescue the tested MR-square/cubic-first graph,
even within a broad continuous coefficient box. This excludes an arithmetic
hypothesis; it does not validate a new model. The latest hardware
[D0012/D0013 evidence](ANALYSIS-D0012-D0013.md) includes 8,768 fresh
identical-quotient comparisons with zero output/C1 splits. That tests a
structural invariance, not numerical correctness: V4 still misses 2,344
outputs and 1,212 C1 values in the same 8,840-row campaign. The current
acceptance corpus has **1,649,232 observations across ten one-shot jobs
(D0001--D0009 and D0013)**. Main C/library remain unpromoted V4; V5 is also
falsified. Read [HANDOFF.md](HANDOFF.md) before using historical counts below.

## Historical numerical checkpoints

The latest offline [D0010/D0011 analysis](ANALYSIS-D0010-D0011.md) gives
independently checked terminal-arithmetic exclusions, not a new solution.
V5 cannot be rescued by coefficient changes alone with its terminal graph
unchanged. The tested fixed schedules in the alternative asymmetric-square
family also fail. No additional hardware or paper update was performed.

**Latest: neither V4 nor V5 is solved.** D0009 prospectively falsified V5 with
470 output and 324 C1 differences in 171,920 fresh observations. Exception
flags match. All data are retained; the complete corpus now has 1,640,392
observations across nine one-shot campaigns. See the current handoff before
using older passing counts below. The main C/library have not been promoted.

`fpatan_candidate.c` is one runnable numerical candidate. It uses exact GMP
integer/rational arithmetic, the public P5 ROM constants and one fixed
operation graph. It does not call host `atan`, use native FPATAN, consult an
operand ledger, or require algorithm-selection flags. The current checkpoint
and remaining acceptance requirements are in [HANDOFF.md](HANDOFF.md).

**Current status: D0008 falsifies this candidate.** In 1,056,744 fresh
observations there are seven output and seven C1 differences (eleven affected
observations over five operand pairs), with no exception-flag differences.
It is not a completed or promoted reconstruction. The saved corpus totals
1,468,472 observations through D0008; older passing results below remain
historical evidence, not a claim of current closure.

An unpromoted V5 analysis candidate matched all 1,468,472 saved D0001--8 rows.
It uses the short ROM coefficient set for table-reduced arguments and a
CHOP64 `z` read at the final tail multiply. `graph_v5.py` and
`fpatan_candidate_v5.c` implement it for prospective discrimination; the
main candidate/library remain V4. D0009 subsequently falsified V5; its saved
discovery agreement must not be presented as fresh proof.

## Build and run locally

With GMP headers/libraries on the normal compiler search path:

```sh
cc -O2 -std=c11 -Wall -Wextra -Werror fpatan_candidate.c -lgmp -o fpatan_candidate
./fpatan_candidate --selftest
```

On this Apple Silicon host, add `-I/opt/homebrew/include` and
`-L/opt/homebrew/lib`. No x86 hardware is needed to run the model.

Each input line is:

```text
case_id rc pc y_sign_exponent y_significand x_sign_exponent x_significand
```

`rc` is `rn`, `rd`, `ru` or `rz`; `pc` is 24, 53 or 64. Encodings are raw
x87 extended precision: four hexadecimal digits for sign/exponent and sixteen
for significand. These are architectural input controls, not model choices.

Each output line is:

```text
case_id result_sign_exponent result_significand C1 exception_flags pre_load_flags
```

Exception fields are hexadecimal x87 status bits 0 through 5. The contract is
a valid two-deep stack with all exceptions masked and latches initially clear,
loading y then x from their raw80 memory encodings. Pointer/register save
images, unmasked trap delivery and undefined condition bits are not modeled.

## Evidence and discipline

- V4 finite graph: 164,624 saved output/C1 comparisons match, including the
  independently frozen 71,080-case D0004 challenge.
- D0005 architectural predictions: 67,392 output and C1 comparisons match;
  4,032 exception predictions were falsified because pseudo-denormals also
  signal DE. The corrected rule passed D0006's fresh pseudo-denormal controls.
- D0006: 59,904 outputs/C1 match. Its 138 flag misses establish pre-rounding
  tininess detection even when the rounded result is minimum normal. The
  corrected C/Python replay matches all 291,920 observations through D0006.
- GCC 15 and Clang warning-clean builds and Clang address/undefined-behavior
  sanitizer replay pass. All original failed predictions remain unchanged.
- D0007's fresh 119,808-case confirmation passes outputs, C1 and exception
  flags. The candidate now matches 411,728 saved observations. The remote
  ledger is healthy and all seven campaigns are terminal/OBSERVED.
- Larger fresh balanced finite/rounding-adversarial verification remains;
  the observation count includes symmetry and RC/PC repetitions.

D0008 performed the larger balanced finite challenge and found the failures
above. Its frozen predictions and raw results are preserved. Future captures
must use the streaming compressed format and `compressed_guard.py`: its
reservations include the complete legacy history, and legacy capture inserts
are deliberately blocked to prevent bypassing compressed reservations.

`fpatan_library.h` and `fpatan_library.c` expose the same candidate as a reusable
C API; `example_batch.c` is a client and `test_library.c` tests its contract.
Sanitizer and D0001--7 replay parity pass. API parity does not resolve D0008.

Run `verify_c_candidate.py --graph architecture --binary /absolute/binary
--jobs d0001 d0002 d0003 d0004 d0005 d0006 d0007 --out /new/report.json` for local replay.
Reports are exclusive-create. Hardware acquisition is separate and protected
by `campaign.py`, remote tuple reservations and private/public history checks.
Never rerun an observed or reserved hardware tuple.

The mathematical MPFR oracle is diagnostic only: correctly rounded atan2 is
not the silicon algorithm. No experimental results belong in the paper.
