# H1511: complete cached Skylake FCOS census has no pair vote

Date: 2026-09-03

Status: **all remaining repository-visible Skylake standalone-FCOS artifacts
audited; 152,135 additional architectural rows have zero endpoint separators;
no orientation evidence and no hardware execution.**

## Scope

H1509 audited the 240,000-operand dense bank.  H1510 audited all nineteen
generic targeted `fcos_{rn,rd,ru}_status.txt` banks.  A filename census found
three remaining non-alias Skylake standalone-FCOS sources:

| Source | Input positions | Modes | Architectural rows |
|---|---:|---:|---:|
| H110 sweep | 50,038 | RN/RD/RU | 150,114 |
| H269 mismatch operands | 7 | RN/RD/RU | 21 |
| H65 polynomial discriminator | 2,000 | RN | 2,000 |
| **Total** |  |  | **152,135** |

The H110 sweep includes two expected architectural `C2` range exits.  H1511
preserves `C2` as an outcome rather than forcing those rows through the finite-
result parser.

The later `skylake-perinsn-20260807` dense and sweep files are byte-identical
to the H110 RN/RD/RU files in all six comparisons, so they are archive aliases,
not additional labels.  The repository's AMD and Pentium-II captures are
explicitly outside this Skylake orientation audit.

## Result

The incumbent and default-off R1382 builds are byte-identical on all 152,135
remaining architectural rows.  There are zero endpoint separators and hence
zero rows on which the exact H1487 pair functions can be scored.

Together, H1509--H1511 account for every repository-visible Skylake
standalone-FCOS cache artifact and audit 2,704,685 cached architectural row
positions without an endpoint-visible pair-A/pair-B vote.  This count is a
row-position census, not a claim that every operand/mode tuple is unique
across historical suites.

The negative result does not imply that pair A and pair B are equivalent:
H1487/H1498 prove their internal Boolean disagreement exactly.  It establishes
that no already-opened repository-visible Skylake FCOS label can resolve the
physical orientation.  A genuinely new observable is required; H1488 remains
the frozen, unopened direct vote.

An independent execution reproduces the JSON byte for byte.

## Artifacts

- `experiments/h1511_remaining_fcos_cache_audit.py`, SHA-256
  `244b39cb52ca79ffc4f8414fa3c4664faa2701f39a3cb9d8c4813235e334a16a`;
- `tmp/ledger33/current/h1511_remaining_fcos_cache_audit.json`, SHA-256
  `8a2ca48492e5de79c02a8d7483b8a2c64592cee94b8214923756a352029d0285`.

The report records both analysis-binary hashes, all input/capture hashes, and
the six byte-identical archive aliases.  No x87 instruction or fresh hardware
capture ran, no H1488 or private-ledger label was opened, and no emulator
behavior/default, academic paper, or PDF changed.  H1488 remains
`FROZEN_UNOPENED`; R96 remains empirical/incomplete; the authoritative
frontier remains eleven mode rows over ten operands.
