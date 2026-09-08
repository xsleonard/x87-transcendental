# x87 Transcendental Reconstruction

## Source code

The implementation is C. Start with these files:

| Instructions | Source file | Supporting code |
| --- | --- | --- |
| FSIN, FCOS, FSINCOS, FPTAN, F2XM1 | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | [Current trig kernels](fsincos-re/src/general/) |
| FPATAN | [fpatan_candidate.c](fsincos-re/fpatan-re/fpatan_candidate.c) | [C API](fsincos-re/fpatan-re/fpatan_library.h), [library wrapper](fsincos-re/fpatan-re/fpatan_library.c) |
| FYL2X, FYL2XP1 | [log_model.c](fsincos-re/fyl2x-re/log_model.c) | [C API](fsincos-re/fyl2x-re/log_library.h), [library wrapper](fsincos-re/fyl2x-re/log_library.c) |

The [source map](SOURCE.md) identifies the entry functions, arithmetic helpers,
constants, tests and examples. The separate
[Itanium reference](fsincos-re/src/fsincos_itanium.c) implements the published
Itanium algorithm. Research scripts, captured data and release copies occupy
much of the repository; the table above points to the maintained implementations.

From the repository root, `make` builds all models and `make check` runs the
saved-example and API checks. See [build prerequisites](#build-and-try-it) below.

## Project scope

The main work is reconstructing **FSIN, FCOS and FSINCOS**: the exact
operation order and intermediate rounding needed to reproduce the tested
Intel processors. Standalone sine/cosine and paired FSINCOS use different
polynomial schedules. The reconstruction also identifies the standalone
operand-width rule and the shared table calculation's rounding destinations.
It builds on Ken Shirriff's published Pentium constants and explanations.[^ken]

A second family covers **FPTAN and FPATAN**. The shorter **F2XM1, FYL2X
and FYL2XP1** implementations come last. Together they give programmers a
complete transcendental reference. A separate program
translates the published Intel Itanium algorithm. Supported inputs, status
flags and evidence differ by instruction; see the
[evidence register](fsincos-re/paper/EVIDENCE.md).

## Build and try it

Build all models from the repository root with Make, a C11 compiler supporting
`unsigned __int128`, and GMP headers/library (`pkg-config` supplies the GMP paths
when available). Python 3 is also required for the checks:

```sh
make
make check
```

The individual builds below are also available.

The unary models require Make and a C11 compiler with `unsigned __int128`
support. Their software arithmetic runs on the Apple Silicon development
host as well as the tested x86 configurations.

```sh
make -C fsincos-re/src all
fsincos-re/src/fsincos_skylake --batch --rc=rn < fsincos-re/examples/unary-raw80.txt
```

This evaluates FSINCOS for +0, +0.5 and +1, returning sine and cosine as
raw80 hexadecimal fields. Select `--fsin-standalone`, `--fcos-standalone`,
`--fptan` or `--f2xm1` after `--batch` for another unary instruction.

FPATAN has a separate GMP-backed CLI and C library:

```sh
make -C fsincos-re/fpatan-re all
fsincos-re/fpatan-re/build/fpatan < fsincos-re/examples/fpatan-raw80.txt
```

The logarithm pair has its own GMP-backed CLI and C library:

```sh
make -C fsincos-re/fyl2x-re all
fsincos-re/fyl2x-re/build/x87-log < fsincos-re/fyl2x-re/example-inputs.txt
make -C fsincos-re/fyl2x-re check PYTHON=python3
```

See the [programmer guide](fsincos-re/docs/PROGRAMMER-GUIDE.md) for
prerequisites, exact input/output formats, rounding modes, a complete C
example and the limits of each interface.

## Instructions and algorithms

| Instruction | Mathematical role | Implementation / explanation |
| --- | --- | --- |
| FSIN | Sine | [Trig pseudocode](fsincos-re/docs/TRIG-PSEUDOCODE.md), standalone calculation |
| FCOS | Cosine | [Trig pseudocode](fsincos-re/docs/TRIG-PSEUDOCODE.md), standalone calculation |
| FSINCOS | Paired sine and cosine | [Trig pseudocode](fsincos-re/docs/TRIG-PSEUDOCODE.md), separate paired calculation |
| FPTAN | Tangent, with a pushed result | [Tangent guide](fsincos-re/docs/ALGORITHMS.md#tangent-fptan), internal sine/cosine division |
| FPATAN | Quadrant-sensitive arctangent of y/x | [Executable pseudocode](fsincos-re/fpatan-re/PSEUDOCODE.md), [C interface](fsincos-re/fpatan-re/fpatan_library.h) |
| F2XM1 | $2^x-1$ | [Exponential guide](fsincos-re/docs/ALGORITHMS.md#exponential-f2xm1), linear/polynomial/table program |
| FYL2X | $y\log_2(x)$ | [Logarithm algorithm](fsincos-re/fyl2x-re/ALGORITHM.md), [C API](fsincos-re/fyl2x-re/log_library.h) |
| FYL2XP1 | $y\log_2(1+x)$ | [Logarithm for small increments](fsincos-re/fyl2x-re/ALGORITHM.md), same C API |

All eight architectural transcendental instructions have models.[^intel]
FSQRT and general x87 arithmetic are
outside this transcendental reconstruction project.

## Programmer's pseudocode

Start with the [algorithm guide](fsincos-re/docs/ALGORITHMS.md), then
read the [complete trig walkthrough](fsincos-re/docs/TRIG-PSEUDOCODE.md)
and the executable [F2XM1/FPTAN specification](fsincos-re/docs/SIBLING-PSEUDOCODE.md)
or [FPATAN reference pseudocode](fsincos-re/fpatan-re/PSEUDOCODE.md).
The [logarithm reference](fsincos-re/fyl2x-re/ALGORITHM.md) includes both
polynomial paths, all four table corrections and final rounding semantics.
The paper includes these listings directly from their source files, so its
pseudocode and constants stay in sync with the code.

Keep every rounding step shown in the pseudocode. For example, the
standalone trig multiply is

$$M(a,b)=T_{67}\!\left(T_{67}(a)T_{64}(b)\right),$$

where $T_p$ truncates to $p$ significant bits. An ordinary host multiply
need not produce the same value. FSINCOS also has a different order of polynomial evaluation from two standalone calls.

## Checks and evidence

```sh
fsincos-re/src/fsincos_skylake --selftest
make -C fsincos-re/src check-paired-regressions
make -C fsincos-re/fpatan-re check
python3 fsincos-re/paper/check_witnesses.py
```

The witness check replays 724 saved hardware examples for the original six
instructions, including 436 independent rational-reference checks. The
logarithm `make check` adds 854 hardware witnesses through the CLI, C API
and independent rational reference.
The integrated F2XM1 storage correction is covered by
`make -C fsincos-re/src check-f2xm1-regressions`; its
[integration record](fsincos-re/paper/evidence/f2xm1-integration.json) retains
the raw80 boundary evidence. These small checks reuse saved results. The separate
`make -C fsincos-re/src test` target tests the Itanium reference.
For larger validation, see the [trig corpus](fsincos-re/corpus-suite/README.md),
[FPATAN corpus](fsincos-re/fpatan-re/corpus-v1/README.md) and
[per-instruction evidence](fsincos-re/paper/EVIDENCE.md). New hardware tests use separate capture tools that keep a record of earlier
inputs.

## Paper and research materials

The article, **Reconstructing FSIN, FCOS and FSINCOS from Public Constants
and Processor Tests**, is available as [PDF](output/pdf/x87-suite.pdf)
and [LaTeX source](fsincos-re/paper/x87-suite.tex). Its three family sections run in that order, with each family
keeping its algorithms, constants and evidence together. The explanation
focuses on the final calculation and the derivation of the sine/cosine rules;
development history stays in the research records. The appendices follow
the same order and preserve all eight specifications and 239 literal entries.
See [publication and build details](fsincos-re/paper/README.md) and the
[review record](fsincos-re/paper/PUBLICATION-REVIEW.md).

The [programmer release](output/release/x87-suite-review-v6/README.md) is a
local package with one Makefile for building and checking the code. Licensing
of original work is **undecided**. The package has not been published, and no
archival identifier has been assigned. Earlier trig and FPATAN papers are kept
in the research archive.

The [source register](fsincos-re/paper/SOURCES.md) connects public source
material to the new reconstruction and validation. The
[research README](fsincos-re/README.md) and `fsincos-re/notes/` preserve the
historical investigation. Current usable models live in `fsincos-re/src/`
and the `fsincos-re/fpatan-re/` and `fsincos-re/fyl2x-re/` libraries; the programmer guide identifies their entry points.

The tests show agreement on their recorded inputs and processors. They do
not prove a match for every input or CPU generation. The programs also do
not emulate every aspect of x87 state or trap handling.

[^ken]: Ken Shirriff, [Pi in the Pentium: reverse-engineering the constants in its floating-point unit](https://www.righto.com/2025/01/pentium-floating-point-ROM.html), January 2025. The project attributes published constants and explanations separately from its behavioral reconstruction.
[^intel]: Intel, [64 and IA-32 Architectures Software Developer's Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), transcendental instruction inventory and instruction reference.
