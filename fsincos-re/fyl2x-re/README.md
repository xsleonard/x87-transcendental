# Portable FYL2X / FYL2XP1 models

Reproduce the recorded Skylake numerical programs with exact GMP arithmetic.
Both the command-line model and reusable C API return raw80 results, C1 and
masked arithmetic exception flags. No native x87 is required to build or run.

```sh
make
make check PYTHON=python3
build/x87-log < example-inputs.txt
build/log_batch < example-inputs.txt
```

Dependencies: a C11 compiler, Make, GMP development files and Python 3.10+.
`pkg-config` supplies GMP search paths when available. `make check` replays
854 saved hardware witnesses through the CLI, C API and independent Python
model, and checks API errors and the exact FYL2XP1 domain endpoint.

Input lines contain `id instruction rc pc y_se y_sig x_se x_sig`; `rc` is
`rn`, `rd`, `ru` or `rz`, `pc` is 24, 53 or 64, and raw80 words are hexadecimal.
`y` is ST(1) and `x` is ST(0). Output lines contain
`id result_se result_sig C1 exception_bits pre_load_bits`. Exception and
pre-load fields are hexadecimal; C1 is decimal. The pre-load field is zero
for the supported clean raw80-load capture contract.

Embed [log_library.h](log_library.h) and link `build/libx87log.a` plus GMP.
[example_batch.c](example_batch.c) is a complete client. Contexts retain only
immutable constants; each evaluation owns its temporaries. Error returns
leave the caller's result unchanged.

Read the [algorithm and complete pseudocode](ALGORITHM.md),
[validation scope](ACCEPTANCE.md), and [independent reference](model.py).
The model prioritizes explicit, auditable arithmetic over emulator throughput.
FYL2XP1 enforces Intel's specified finite input interval; undefined inputs are
reported as outside scope. The API models numerical effects and defined
arithmetic flags, with the caller responsible for stack state.

Licensing of original work remains undecided at the author's request.
Capture and research scripts are separate from the normal build; they must
never be run against hardware without frozen predictions, history clearance
and permanent no-repeat reservation.
