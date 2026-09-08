# Skylake FPATAN numerical reconstruction

The main C implementation uses the validated **V7 fixed numerical program**.
It has zero known mismatches in **2,783,208 authenticated observations** on
the Skylake Xeon reference, CPUID `00050654`, reported microcode `0x1`.
Of these, **624,312 were prospective observations with V7 predictions frozen
before capture**, including exact midpoints, low-bit index discriminators and
targeted final-rounding boundaries. Clang, GCC 15 and the library batch client
each replay every observation with zero output, C1 or exception differences.

This is a general retained-width arithmetic reconstruction, not an operand
lookup or mathematically correctly rounded `atan2`. It makes no universal
all-raw80 or cross-CPU proof claim. See [ACCEPTANCE.md](ACCEPTANCE.md) for
the requirement-by-requirement evidence and [ALGORITHM.md](ALGORITHM.md)
for the complete numerical graph.

The [programmer's pseudocode](PSEUDOCODE.md) and
[standalone LaTeX paper](paper/README.md) provide an additional readable
specification, constant provenance and confirmed validation record.

## Build and run

Requires a C11 compiler and GMP development headers/library; `pkg-config`
is used when available. Build and run the local, hardware-free checks:

```sh
make
make check
./build/fpatan < inputs.txt > predictions.txt
```

The single source `fpatan_candidate.c` also builds independently:

```sh
cc -O2 -std=c11 -Wall -Wextra -Werror fpatan_candidate.c -lgmp -o fpatan
```

On Homebrew installations, add `-I/opt/homebrew/include` and
`-L/opt/homebrew/lib` if they are not already in the compiler search path.
The historical source filename does not select an experimental mode.
There are no algorithm flags, environment settings, data files or Python
modules required by the executable. GMP provides exact integer/rational
arithmetic, not an arctangent implementation. Apple Silicon can run it.

Input, one case per line:

```text
case_id rc pc y_sign_exponent y_significand x_sign_exponent x_significand
```

`rc` is `rn`, `rd`, `ru` or `rz`; `pc` is 24, 53 or 64. Encodings use
four hexadecimal digits for sign/exponent and sixteen for significand.
These are architectural input controls, not algorithm choices. For example:

```text
example rn 64 3fff 8000000000000000 3fff 8000000000000000
```

Output:

```text
example 3ffe c90fdaa22168c235 1 20 00
```

The fields are case ID, result sign/exponent, result significand, C1,
hexadecimal exception flags and hexadecimal pre-load exception flags.

## Library and contract

`fpatan_library.h` exposes `x87_fpatan_create`, `x87_fpatan_evaluate` and
`x87_fpatan_destroy`. `libfpatan.a` contains the same numerical source as the
standalone program; `example_batch.c` is an independent client. The tests
include the saved native failures that defeated V4, V5 and V6.

Inputs are y from ST(1) and x from ST(0), including signed zeros, normal and
subnormal finite values, pseudo-denormals, infinities, NaNs and unsupported
encodings. The result is the post-pop numerical value, C1 and defined
arithmetic exception flags under a valid two-deep stack, all exceptions
masked, and clear initial latches. Precision-control values are accepted and
checked; the reconstructed result is PC-invariant. Full arbitrary FPU-state
restore, unmasked trap delivery and undefined condition bits are outside
this explicitly documented numerical API.

## Evidence and reuse

The local corpus is retained under `../tmp/fpatan-re/`, with original inputs,
frozen predictions, hardware responses, CPU identity, source hashes and
permanent one-shot receipts. D0001–D0009, D0013, D0022–D0024 and D0026 are all
included. Historical failing predictions are preserved; new replay reports
do not rewrite old results. No private ledger or model code was uploaded.

To replay the entire retained corpus using a locally built executable:

```sh
python3 verify_delivery.py --binary build/fpatan --out /new/replay.json
```

Reports are exclusive-create. Hardware capture is a separate, guarded action;
never rerun an observed, reserved or uncertain tuple. The research history
and further cross-CPU work belong in the handoff, not in the academic paper.
