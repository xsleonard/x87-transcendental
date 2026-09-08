# Source code map

The maintained C implementations are in three directories under `fsincos-re/`.
This map links to those files directly. Build all models with `make` from the
repository root; run the saved-example and API checks with `make check`.

## Instruction entry points

| Instruction | File | Function to start reading |
| --- | --- | --- |
| FSIN | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | `fsin_ref` |
| FCOS | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | `fcos_ref` |
| FSINCOS | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | `fsincos_ref`, then `general_paired_ref` in [general/paired.h](fsincos-re/src/general/paired.h) |
| FPTAN | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | `fptan_ref`, then `fptan_core` |
| F2XM1 | [fsincos_skylake.c](fsincos-re/src/fsincos_skylake.c) | `f2xm1_ref`, then `f2xm1_core` |
| FPATAN | [fpatan_candidate.c](fsincos-re/fpatan-re/fpatan_candidate.c) | `fpatan_raw80` |
| FYL2X, FYL2XP1 | [log_model.c](fsincos-re/fyl2x-re/log_model.c) | `log_raw80` |

The unary entry functions are internal to a shared translation unit that also
contains the CLI and older experimental paths. There are no separate maintained
`fsin.c`, `fcos.c`, `fptan.c` or `f2xm1.c` files. FPATAN and the logarithms expose
public library wrappers:

- FPATAN: [fpatan_library.h](fsincos-re/fpatan-re/fpatan_library.h) and
  [fpatan_library.c](fsincos-re/fpatan-re/fpatan_library.c), entry
  `x87_fpatan_evaluate`.
- FYL2X/FYL2XP1: [log_library.h](fsincos-re/fyl2x-re/log_library.h) and
  [log_library.c](fsincos-re/fyl2x-re/log_library.c), entry `x87_log_evaluate`.

## Trig kernels, arithmetic and constants

| Purpose | Source |
| --- | --- |
| Standalone FSIN/FCOS polynomial | [general/standalone_polynomial.h](fsincos-re/src/general/standalone_polynomial.h) |
| Standalone FSIN/FCOS table path | [general/standalone_table.h](fsincos-re/src/general/standalone_table.h) |
| Standalone FSIN/FCOS tiny inputs | [general/standalone_tiny.h](fsincos-re/src/general/standalone_tiny.h) |
| Paired FSINCOS | [general/paired.h](fsincos-re/src/general/paired.h) |
| Software floating-point arithmetic | [ia64_sf.h](fsincos-re/src/ia64_sf.h) |
| Pentium ROM constants | [p5_rom_constants.h](fsincos-re/src/p5_rom_constants.h) |
| F2XM1 constants | [f2xm1_constants.h](fsincos-re/src/f2xm1_constants.h) |
| Reciprocal table | [frcpa-recip-table.h](fsincos-re/data/frcpa-recip-table.h) |
| Published Itanium algorithm reference | [fsincos_itanium.c](fsincos-re/src/fsincos_itanium.c) |

The `general/` headers are included by `fsincos_skylake.c` and use its internal
types and helpers. They are part of that implementation, rather than standalone
public headers.

## Builds, tests and examples

| Component | Build definition | Tests / example |
| --- | --- | --- |
| Whole suite | [Root Makefile](Makefile) | `make check`; `make check-itanium` for additional Itanium checks |
| Unary models and Itanium reference | [src/Makefile](fsincos-re/src/Makefile) | [Paired regressions](fsincos-re/src/test_general_paired.py), [F2XM1 regressions](fsincos-re/src/test_f2xm1.py), [sample input](fsincos-re/examples/unary-raw80.txt) |
| FPATAN | [fpatan-re/Makefile](fsincos-re/fpatan-re/Makefile) | [API tests](fsincos-re/fpatan-re/test_library.c), [C client](fsincos-re/examples/fpatan_client.c) |
| FYL2X/FYL2XP1 | [fyl2x-re/Makefile](fsincos-re/fyl2x-re/Makefile) | [API tests](fsincos-re/fyl2x-re/test_api.c), [witness checks](fsincos-re/fyl2x-re/check_witnesses.py), [C client](fsincos-re/fyl2x-re/example_batch.c) |
| Saved hardware examples across instruction families | Built models above | [check_witnesses.py](fsincos-re/paper/check_witnesses.py) |

The [programmer guide](fsincos-re/docs/PROGRAMMER-GUIDE.md) explains build
prerequisites, CLI formats, rounding controls and embedding the libraries.

## Other repository directories

| Location | Contents |
| --- | --- |
| [fsincos-re/docs/](fsincos-re/docs/) | Programmer documentation and executable reference pseudocode |
| [fsincos-re/paper/](fsincos-re/paper/) | Manuscripts, citations and recorded evidence |
| [fsincos-re/experiments/](fsincos-re/experiments/), [experiments/](experiments/) | Investigation and validation scripts |
| [fsincos-re/notes/](fsincos-re/notes/) | Research chronology and handoffs |
| [fsincos-re/capture-kit/](fsincos-re/capture-kit/) | Programs for collecting native x87 hardware results |
| [fsincos-re/corpus-suite/](fsincos-re/corpus-suite/) | Trig corpus tooling and validation records |
| [fsincos-re/data/](fsincos-re/data/) | Source material and tables, including the reciprocal header used by the C build |
| `output/`, `fsincos-re/output/`, `fsincos-re/deliverables/` | Generated artifacts and packaged snapshots |
| `tmp/`, `fsincos-re/tmp/` | Scratch files and campaign working data |

Edit the maintained files linked above when changing a model. The packaged
copies under `output/release/` are release snapshots.
