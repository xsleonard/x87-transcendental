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
