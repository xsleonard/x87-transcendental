# Research

The maintained library is in the repository's root `include/` and `src/`.
This directory contains the numerical research implementations, experiments,
capture tools and manuscripts supporting that library.

Original research material is covered by the repository's
[LGPL-3.0-only license notice](../LICENSE.md). Third-party material retains its
existing terms, attributions and notices.

- [Research overview](PROJECT-README.md) and [source map](SOURCE.md).
- [Instruction studies and tools](fsincos-re/).
- `make -C research check` runs the small research acceptance suite.
- `make -C research/fsincos-re/src test` checks the separate Itanium reference.

Large captures, database catalogs, generated reports and session notes remain
in ignored local storage. Experiments may require those local inputs; the
library's normal tests use the compact fixtures in `tests/data/`.
Research paths beginning with `fsincos-re/` resolve beneath this directory.
Paper tools write generated output under `research/output/`.
