# H1514: complete cached FSIN/FSINCOS census has no pair vote

Date: 2026-09-03

Status: **166 repository-visible Skylake capture files and 6,748,240
architectural rows audited; zero current/R1382 endpoint separators; no
orientation evidence and no hardware execution.**

## Scope

H1509--H1511 exhausted the repository-visible standalone-FCOS caches.  H1514
tests whether the same narrow internal merge difference becomes visible
through a sibling instruction schedule.  It covers every repository-visible
Skylake standalone-FSIN and paired-FSINCOS result file, including:

- dense and sweep banks under RN/RD/RU;
- the standalone-FSIN RZ dense, sweep, and H347 banks;
- targeted H110--H224 table, polynomial, carry, and microcontrol suites;
- H285--H349 adversarial and million-row broad paired suites;
- H65 standalone-FSIN and paired polynomial captures; and
- H172 precision-control variants.

The audit reconciles its hard-coded corpus map against an independent
repository filename inventory.  All 166 non-alias capture files are accounted
for.  Twelve later per-instruction dense/sweep files are byte-identical to the
canonical H110/H177 RN/RD/RU captures and are recorded as aliases rather than
new labels.  AMD and Pentium-II artifacts are explicitly excluded from this
Skylake orientation question.

## Result

| Instruction path | Architectural rows | Current/R1382 separators |
|---|---:|---:|
| Standalone FSIN | 2,196,958 | 0 |
| Paired FSINCOS | 4,551,282 | 0 |
| **Total** | **6,748,240** | **0** |

Because the current and default-off R1382 models are byte-identical on every
row, none of these already-opened hardware results can expose pair A versus
pair B.  The exact H1487 pair functions are not asserted equivalent; their
Boolean disagreement remains proven.  The result establishes that no cached
sibling-instruction endpoint reaches an architecturally visible instance of
that disagreement.

Combined with H1509--H1511, the complete repository-visible Skylake
instruction cache contributes 9,452,925 audited architectural row positions
without an orientation vote.  H1512--H1513 separately close the raw-state
transfer/history evidence: their 48 visible rows all belong to the common
`0000` branch.

An independent full execution reproduces the JSON byte for byte.

## Artifacts

- `experiments/h1514_cached_sibling_pair_audit.py`, SHA-256
  `3804cc7676b9d15a76a18764ab4bb92b12b19ee0e77684c9c8215d601dc87b46`;
- `tmp/ledger33/current/h1514_cached_sibling_pair_audit.json`, SHA-256
  `e421c253ca912f56a2b5faf41ab966e4db1b6e0e23641a2f5b89c372b1712fe2`.

The report records both analysis-binary hashes, every input and capture hash,
and all twelve archive aliases.  No x87 instruction or fresh hardware capture
ran, no H1488 or private-ledger label was opened, and no emulator
behavior/default, academic paper, or PDF changed.  H1488 remains
`FROZEN_UNOPENED`; R96 remains empirical/incomplete; the authoritative
frontier remains eleven mode rows over ten operands.
