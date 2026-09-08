# Using the x87 numerical models

These programs use integer or rational arithmetic to reproduce x87 results.
Use them to inspect result bits, write compatibility tests or study the
algorithms. They aim to match the processor, whose answer can differ from
the correctly rounded mathematical function.

All shell examples below run from the repository root. The programs and
tests below run entirely in software. Collecting new hardware results uses
separate tools.

## Build and check

For FSIN, FCOS, FSINCOS, FPTAN and F2XM1, use a C11 compiler with
`unsigned __int128` support, such as the tested Clang/GCC configurations,
plus Make and Python 3 for the test scripts:

```sh
make -C fsincos-re/src all
fsincos-re/src/fsincos_skylake --selftest
make -C fsincos-re/src check-paired-regressions
```

The `all` target also builds the separate Itanium reference. Its broader
arithmetic and transcription checks run with:

```sh
make -C fsincos-re/src test
```

The `test` target checks the Itanium reference. The paired check runs six
saved hardware cases for FSINCOS. Larger Skylake test sets are described
in the evidence register.

FPATAN currently has a separate C11/GMP implementation, CLI and static library.
It requires GMP headers/library; the Makefile uses `pkg-config` when available:

```sh
make -C fsincos-re/fpatan-re all
make -C fsincos-re/fpatan-re check
```

See the [FPATAN build details](../fpatan-re/DELIVERY.md#build-and-run) for
nondefault GMP include/library locations. Both programs run on the Apple Silicon development machine. Other compilers
and ABIs may need additional checks.

## Input values: raw80

The unary CLI takes two hexadecimal fields per line: a 16-bit sign/exponent
field followed by the explicit 64-bit significand. For normal encodings,

$$x=(-1)^s S\,2^{E-16383-63},$$

where `s` is bit 15 of the first field, `E` is its low 15 bits, and `S`
is the second field interpreted as an integer. Subnormal and special
encodings require separate handling; see the algorithm documents and Intel's
format description.[^intel]

| Value | Sign/exponent | Significand |
| --- | --- | --- |
| +0 | `0000` | `0000000000000000` |
| -0 | `8000` | `0000000000000000` |
| +0.5 | `3ffe` | `8000000000000000` |
| +1 | `3fff` | `8000000000000000` |
| -1 | `bfff` | `8000000000000000` |

The [sample unary input](../examples/unary-raw80.txt) contains +0, +0.5 and
+1 in that order. Use raw encodings when preserving low bits, signed zeros
or NaN payloads matters. Converting through a host `double` loses inputs
outside its representable subset. A host `long double` is ABI-dependent.

## Unary instruction commands and output

```sh
fsincos-re/src/fsincos_skylake --batch --fsin-standalone --rc=rn < fsincos-re/examples/unary-raw80.txt
fsincos-re/src/fsincos_skylake --batch --fcos-standalone --rc=rn < fsincos-re/examples/unary-raw80.txt
fsincos-re/src/fsincos_skylake --batch --rc=rn < fsincos-re/examples/unary-raw80.txt
fsincos-re/src/fsincos_skylake --batch --fptan --rc=rn < fsincos-re/examples/unary-raw80.txt
fsincos-re/src/fsincos_skylake --batch --f2xm1 --rc=rn < fsincos-re/examples/unary-raw80.txt
```

With no instruction flag, batch mode selects FSINCOS. Put `--batch` first
and choose only one instruction flag.

| Instruction | Successful line | Meaning |
| --- | --- | --- |
| FSIN / FCOS / F2XM1 | `OK se sig` | One raw80 result |
| FSINCOS | `OK s_se s_sig c_se c_sig` | Sine then cosine; this is output order, not a stack-memory image |
| FPTAN | `OK t_se t_sig p_se p_sig` | Tangent then pushed value; ordinary finite results push +1 |

For example, the sample FSINCOS command produces:

```text
OK 0000 0000000000000000 3fff 8000000000000000
OK 3ffd f57743a2582f7f44 3ffe e0a94032dbea7cee
OK 3ffe d76aa47848677021 3ffe 8a51407da8345c92
```

The F2XM1 command produces:

```text
OK 0000 0000000000000000
OK 3ffd d413cccfe7799211
OK 3fff 8000000000000000
```

The trig CLI prints `C2` for range rejection. It does not print the unchanged
input or push a new result in that case; retain the corresponding input if
you are integrating the output into an emulator. Special FPTAN results may
push a second copy of the special value instead of +1, as represented by
the two output fields.

`--rc=rn`, `--rc=rd`, `--rc=ru` and `--rc=rz` select nearest/even, down, up
and toward zero. Internal rounding still follows the steps in the algorithm. The
unary batch format does not expose all status fields or accept a per-row
precision-control value. In particular, it does not print C1. To inspect those fields, use the evidence tools or a wrapper that exposes
and checks them. The new
FPTAN reference replay covers all four RC modes on its identified normal
finite corpus. F2XM1's H257 replay covers RN/RD/RU; its later raw80 boundary
challenge covers all four RC settings on both processors, including selected
complete groups at all three PC settings.

The integrated F2XM1 tiny path rounds directly to raw80, fixing the earlier
subnormal-storage truncation. For example, input `0000 000000000000010e`
under `--rc=ru` returns `OK 0000 00000000000000bc`; the old program returned
`...00bb`. Keep final format rounding when translating the reference.
[Correction and validation](../paper/evidence/f2xm1-integration.json).

The internal `sf_to_x87` helper only converts a carrier. It is not a general
format-aware rounding API: callers must already have an exactly representable
result or perform destination rounding first. The follow-up
[storage-boundary review](verification-expansion/rounding-boundary-audit.md)
checks the other instruction paths and explains their different underflow rules.

## FPATAN CLI

FPATAN takes two raw80 operands in the order `y`, then `x`, plus explicit
rounding and precision controls:

```text
case_id rc pc y_se y_sig x_se x_sig
```

```sh
fsincos-re/fpatan-re/build/fpatan < fsincos-re/examples/fpatan-raw80.txt
```

The example evaluates the instruction with y=x=+1:

```text
example 3ffe c90fdaa22168c235 1 20 00
```

The output fields are case ID, result sign/exponent, result significand,
C1, hexadecimal arithmetic exception bits, and hexadecimal preload
exception bits. Here `20` means the precision exception bit is set.
The control values are `rn/rd/ru/rz` and `24/53/64`. PC is accepted and
validated even though the reconstructed result is PC-invariant.

## Embedding FPATAN in C

The existing [library header](../fpatan-re/fpatan_library.h) exposes a
reusable context and a raw80 result structure. A readable complete example
is [fpatan_client.c](../examples/fpatan_client.c):

```sh
cc -O2 -std=c11 -Wall -Wextra -Werror \
  -Ifsincos-re/fpatan-re \
  fsincos-re/examples/fpatan_client.c \
  fsincos-re/fpatan-re/build/libfpatan.a \
  $(pkg-config --libs gmp) \
  -o fsincos-re/fpatan-re/build/fpatan_client
fsincos-re/fpatan-re/build/fpatan_client
```

This command assumes `pkg-config` can locate GMP. If GMP is already in the
default library search path, `-lgmp` can replace that substitution.

Expected output:

```text
3ffe c90fdaa22168c235 C1=1 exceptions=20
```

The API assumes two valid stack operands, masked exceptions and initially
clear exception flags. It returns the result after the instruction's stack
pop, C1 and arithmetic exceptions. Your emulator must update the actual
stack, saved state and trap handling. Invalid RC/PC arguments are API errors;
unsupported raw80 encodings are inputs whose instruction behavior is modeled.

There is no single C library API for all eight instructions. The unary
program uses global configuration and includes older experimental code, so
it cannot be treated as a library that safely handles concurrent calls.
FPATAN and the logarithm pair have separate context-based APIs.

## Logarithms: FYL2X and FYL2XP1

```sh
make -C fsincos-re/fyl2x-re all
make -C fsincos-re/fyl2x-re check PYTHON=python3
fsincos-re/fyl2x-re/build/x87-log < fsincos-re/fyl2x-re/example-inputs.txt
```

These programs require C11 and GMP. Input is
`id instruction rc pc y_se y_sig x_se x_sig`, where the instruction is
`fyl2x` or `fyl2xp1`. The operand order is `y=ST(1), x=ST(0)`.
Output is `id result_se result_sig C1 exceptions pre_load_flags`.
Raw80 and flag fields are hexadecimal; C1 is decimal.

For embedding, include [log_library.h](../fyl2x-re/log_library.h), create
an `x87_log` context, call `x87_log_evaluate` and link `libx87log.a` plus GMP.
The [complete batch client](../fyl2x-re/example_batch.c) demonstrates the API.
`X87_LOG_BAD_ARGUMENT` rejects invalid controls; `X87_LOG_OUTSIDE_SCOPE`
rejects FYL2XP1 finite magnitudes above $1-\sqrt{1/2}$ and infinite `x`.
Errors leave the result unchanged. Unsupported raw80 encodings and NaNs use
the instruction-level exception/result behavior rather than a host float cast.

The result includes C1 and masked arithmetic exception flags. The caller
owns the stack pop and broader FPU state. PC24/53/64 are accepted; the
internal numerical program retains its fixed precisions. The check target
compares 854 saved hardware observations through the CLI, API and independent
rational reference, and verifies the exact domain endpoint and API errors.
See [the algorithm](../fyl2x-re/ALGORITHM.md) and
[acceptance record](../fyl2x-re/ACCEPTANCE.md) for larger evidence.

## Further reading and checks

- [Algorithm guide](ALGORITHMS.md): shared notation and the instruction families.
- [Trig pseudocode](TRIG-PSEUDOCODE.md): exact reduction, standalone and paired
  schedules, table/tiny paths and final rounding.
- [FPATAN pseudocode](../fpatan-re/PSEUDOCODE.md): executable rational reference.
- [F2XM1/FPTAN specification](SIBLING-PSEUDOCODE.md): complete rational
  programs and literal data, independently replayed against saved hardware.
- [Logarithm pseudocode](../fyl2x-re/ALGORITHM.md): direct and split-table programs.
- [Evidence register](../paper/EVIDENCE.md): counts, provenance and remaining gaps.
- [Trig corpus tooling](../corpus-suite/README.md) and
  [FPATAN corpus](../fpatan-re/corpus-v1/README.md): larger test sets.

Offline tests compare the code with saved results. To test another CPU, use
the hardware capture tools on a suitable x86 machine. Those tools track
previously captured and reserved inputs to avoid repeating observations.

For an offline check that needs only the bundled sources and witnesses:

```sh
python3 fsincos-re/paper/check_witnesses.py
```

Build both C programs first. This checks 724 hardware examples across all
six instructions and 436 independent reference evaluations. The full
archive replays described in the paper require the separately retained
research captures. The paper itself rebuilds with Python 3.10+ and Tectonic:

```sh
python3 fsincos-re/paper/build_suite.py
```

Tectonic may download its TeX packages and fonts on its first build.

[^intel]: Intel, [64 and IA-32 Architectures Software Developer's Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), Volumes 1 and 2. Pin the consulted revision when citing architectural details.
