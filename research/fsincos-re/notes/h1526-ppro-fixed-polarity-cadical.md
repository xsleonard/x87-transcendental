# H1526: explicit CaDiCaL replay of the Pentium Pro polarity query

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: exact immutable-CNF backend audit, UNKNOWN; no decoder, selector,
hardware, emulator, or paper/PDF change.

## Question

H1505 encoded the bounded Pentium Pro fixed-polarity opcode-mapping question
as a 12,348-variable, 447,674-clause DIMACS instance. H1507 loaded that exact
instance into CVC5's default Boolean backend and timed out. H1522 subsequently
showed that the same local CVC5 1.3.1 installation's explicit CaDiCaL backend
can decide some exact bit-blasted queries that its other backends leave
UNKNOWN. H1526 therefore tests the missing explicit backend without changing
the H1505 proposition.

## Exact replay

The runner pins and verifies both inputs before constructing the solver:

- H1505 CNF SHA-256
  `f4c39270dd3f3bd96211ca3c379ffdf838839c814df6384385d695032ecd373f`;
- H1467 report SHA-256
  `63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74`.

It selects `QF_SAT`, CVC5 option `sat-solver=cadical`, and a 300,000 ms
per-query limit. A SAT result would be decoded through H1507's independent
mapping validator and replayed over all 38 body rows. The immutable CNF parses
as the expected 12,348 variables and 447,674 clauses.

## Result

CVC5 1.3.1 CaDiCaL returned `UNKNOWN / TIMEOUT` after 300.017 seconds. It
emitted neither a model nor an UNSAT result. Runtime and backend agreement have
no semantic force, so the fixed-polarity extension remains unresolved.

This corrects the backend-coverage record: the earlier CVC5 audit did not
explicitly select CaDiCaL; H1526 does. It does not weaken H1504's exact
non-inverting UNSAT theorem and does not justify more seed or backend fitting.
The branch remains bounded by the current 459-value public P6 recognized-opcode
condition, which may itself be incomplete for Pentium Pro patch programs.

## Artifacts

- `experiments/h1526_ppro_fixed_polarity_cadical.py`, SHA-256
  `23f7a96418ebaad8d58e7110015149608f1e677b4a6d4820398bcf3d8016c799`;
- `tmp/ledger33/current/h1526_ppro_fixed_polarity_cadical.json`, SHA-256
  `9f3f9d6a90547ce97196ce8c6717c8c81304bdce72364edb75c48311354fff9d`.

No x87 instruction or hardware capture ran, no label or private capture ledger
was opened, and no manifest, emulator behavior/default, or academic paper/PDF
changed. H1488 remains `FROZEN_UNOPENED`; R96 remains empirical/incomplete;
the authoritative frontier remains eleven mode rows over ten operands.
