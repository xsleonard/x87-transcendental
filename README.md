# x87trans

A C library implementing the reconstructed Skylake **FSIN, FCOS, FSINCOS,
FPTAN, F2XM1, FPATAN, FYL2X and FYL2XP1** numerical programs for emulation.
Each instruction has a named function and a source file under [src/](src/).

The library takes raw 80-bit operands and explicit guest controls, and returns
numerical values, arithmetic flags, C1/C2 and writeback information. The
emulator owns its registers, stack, tags and exception delivery. This is a
**Skylake emulation preview**: masked special values and unmasked arithmetic
outcomes share one explicit result contract. The ABI remains provisional.
See the [API contract](docs/api.md) before applying results to guest state.

Build with CMake 3.20+, a C11 compiler supporting `unsigned __int128`, and GMP:

```sh
cmake -S . -B build
cmake --build build
```

From this checkout, `make` builds the library, `make check` runs offline checks,
`make tools` builds command-line clients, and `make examples` builds a C example.
Python 3 is needed for saved-witness tests, not for the library build or runtime.

```c
#include <x87trans/x87trans.h>

x87t_context *context = x87t_create();
x87t_control control = X87T_CONTROL_INIT;
x87t_raw80 x = { 0x3ffe, UINT64_C(0x8000000000000000) }; /* +0.5 */
x87t_result result;

if (context) {
    x87t_error error = x87t_fsincos(context, x, &control, &result);
    if (error == X87T_OK && result.completion == X87T_COMPLETE) {
        /* result.primary is sine; result.pushed is cosine.
         * Check cc_known and exceptions_known before updating guest status. */
    }
    x87t_destroy(context);
}
```

For CMake consumers, link `x87trans::x87trans` through `add_subdirectory` or an
installed package. Static consumers also link GMP; the exported target carries
that dependency. [Integration instructions](docs/integration.md) cover C/C++,
installation, pkg-config and the [Bochs adapter](docs/bochs.md).

| Location | Contents |
| --- | --- |
| [include/x87trans/x87trans.h](include/x87trans/x87trans.h) | Public types and all eight functions |
| [src/](src/) | Canonical implementation, private arithmetic and compiled constants |
| [SOURCE.md](SOURCE.md) | Instruction and helper source map |
| [tests/](tests/) | Saved hardware regressions, independent references and API tests |
| [tools/](tools/) | CLI consumers, optional old API adapters, validation and packaging |
| [docs/](docs/) | Contract, integration, algorithms, provenance and migration |
| [research/](research/) | Preserved research sources, manuscripts and evidence |

Tests include 1,800 numerical witnesses, 22,528 new hardware outcome witnesses,
independent rational references, concurrency and integration contracts. The Bochs
adapter passed 60,514 guest instruction/state checks. See
[validation and limits](docs/validation.md). No hardware capture is part of a
normal build or check. Agreement is scoped to the retained evidence and selected
profile, without a universal claim across CPU generations.

Original-work licensing remains undecided; no distribution license is assigned
by this reorganization. [Provenance](docs/provenance.md) records the source and
constant origins. The [migration guide](docs/migration.md) explains the old
paths and the completed relocation of campaign data into `research/`.
