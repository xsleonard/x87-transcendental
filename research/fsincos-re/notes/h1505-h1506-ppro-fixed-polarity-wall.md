# H1505--H1507: exact fixed-polarity opcode-search wall

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their bounded results apply only to that
> mispartitioned dataset and do not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: **independent exact formulations remain UNKNOWN; the channel-reuse relaxation
is SAT only by a degenerate five-channel fit; no decoder, selector, or emulator
change.**

## Question

H1504 proved that the recovered `0x611` and `0x612` Pentium Pro patch bodies
cannot share a non-inverting injective twelve-bit opcode mapping when every one
of their 38 decoded values must belong to the current 459-value public P6
recognized-opcode set.  Its independent fixed-polarity extension remained
UNKNOWN.  H1505--H1507 replace and cross-check the generic QF_BV formulation
with independent exact encodings of that same bounded polarity-enabled
question.

This remains a patch-decoder side route.  The public opcode catalogue may be
incomplete for these old bodies, and neither result determines the physical
Skylake multiplier orientation or an R59 selector.

## H1505: exact Boolean CNF

H1505 gives each of the twelve logical opcode bits exactly one of 496 literal
choices: 248 physical `(dword,bit)` channels at either fixed polarity.  It
enforces distinct physical channels across logical positions.  For every one
of the 38 body rows, it introduces twelve decoded-bit variables and excludes
each of the 3,637 unrecognized twelve-bit words with an exact CNF clause.

The resulting DIMACS instance has 12,348 variables and 447,674 clauses.  Z3
4.15.3's DIMACS SAT frontend returned `timeout` after 300 seconds, recorded as
**UNKNOWN**.  Regeneration after the parser fix reproduced the CNF byte for
byte, SHA-256
`f4c39270dd3f3bd96211ca3c379ffdf838839c814df6384385d695032ecd373f`.
The raw solver output is retained; `timeout` is neither SAT nor UNSAT.

Three additional 120-second searches over that immutable CNF using local
search, probabilistic/random-phase search, and lookahead simplification also
timed out.  The local-search diagnostic reached four violated clauses, but it
did not emit a total satisfying assignment.  That count is heuristic only and
is not treated as a near-model or logical result.

## Exact non-injective control

Removing only the cross-logical-bit channel-distinctness clauses produces a
382,202-clause relaxation.  Z3 finds a validated model in under six seconds,
but it uses only five distinct physical channels for twelve logical positions:
seven positions are channel reuses, and one channel is copied into six logical
bits.  All 38 resulting words are recognized, but the construction is exactly
the high-dimensional feature fitting that injectivity was meant to exclude.

This control proves that fixed polarity plus channel reuse can manufacture a
recognized-looking body.  It supplies no physical decoder evidence and does
not weaken H1504's non-inverting UNSAT theorem.

## H1506: exact table CSP

H1506 branches directly on the twelve logical opcode positions.  For each of
the 38 rows it carries the exact subset of the 459 recognized words still
compatible with the partial assignment, enforces a fresh physical channel at
every depth, and chooses the next logical bit by minimum remaining domain.
Reaching a leaf would be a validated SAT mapping; exhausting the tree would be
UNSAT for precisely the same bounded H1504 condition.

The initial 300-second formulation returned UNKNOWN after 114,688 states and
reached depth 9.  An exact algebraic optimization replaced per-candidate
38-row scans with forced-zero/forced-one row masks.  The optimized 300-second
run returned **UNKNOWN** after 1,523,712 states, 1,523,704 cached dead ends, and
maximum depth 10.  It produced no model and did not exhaust the search tree.

Thus the fixed-polarity extension remains unresolved after both an exact CNF
encoding and a structurally different exact table-CSP search.  This is a
computational wall, not an impossibility theorem.

## H1507: independent CVC5 backend

H1507 streams H1505's immutable exact CNF into CVC5 1.3.1 as 447,674 Boolean
assertions.  CNF construction takes 2.97 seconds; the independent Boolean
backend then returns **UNKNOWN / TIMEOUT** after 300.06 seconds.  Its recorded
CNF hash exactly matches H1505.  It produces no model and no UNSAT result.

The fixed-polarity decoder branch is therefore bounded by Bitwuzla QF_BV, Z3
DIMACS SAT, the direct table CSP, and CVC5 Boolean search without a logical
answer.  Further solver-seed fitting is not evidence and is not a priority.

## Relation to the topology frontier

The expanded primary-source search did not change H1499: Intel US 5,195,051
names PP0--PP21 separately from an unlabeled four-level 4:2 tree, its related
sticky-bit patent adds no leaf assignment, and Intel's public formal-
verification articles keep the physical partial-product wiring abstract.  No
public source found here chooses H1498 pair A versus pair B.

H1488 therefore remains the only frozen direct orientation vote and remains
`FROZEN_UNOPENED`.  It was not executed or opened.  Even a surviving H1488
pair would be finite hardware validation of an exact representation, not proof
of global x87 closure.

## Artifacts

- `experiments/h1505_ppro_fixed_polarity_cnf.py`, SHA-256
  `09cac022cd72f3beb2cf60e7bdab7df670533752d317be1912b20cd0d1e4b5be`;
- `tmp/ledger33/current/h1505_ppro_fixed_polarity_cnf.json`, SHA-256
  `a8e3c1926249ea45af4397a9ae897c24378bec91bffe60543b40fd0ec04ecef6`;
- `tmp/ledger33/current/h1505_ppro_fixed_polarity.cnf`, SHA-256
  `f4c39270dd3f3bd96211ca3c379ffdf838839c814df6384385d695032ecd373f`;
- `tmp/ledger33/current/h1505_ppro_fixed_polarity.z3.txt`, SHA-256
  `7ed6120912d915f6ba8ef82ba3ec0b703265a0979bc0a243e0144580ad0c0b6b`;
- `tmp/ledger33/current/h1505_ppro_fixed_polarity_relaxed.json`, SHA-256
  `7c98f2f8a2a15100057de1fb975af3b5fc0ecbeb97b0b09528598b4c2b4d4b6b`;
- relaxed CNF and solver output, SHA-256
  `e59a782938f5b51469f0eca73519cf11f44407dac0ca05a082b45875568b9bf9`
  and `e7a0a808a2cfce8853ac3575432f48fa27a9fd67336e91ffb540bc94c8f20d0f`;
- `experiments/h1506_ppro_opcode_csp.py`, SHA-256
  `26202c74253f0f0527297047c06ba1194294c14469961ef55cbd95998ec34571`;
- initial H1506 report, SHA-256
  `ed8904c5c6f55c398c2886aa366c027371a5fc987eab000d9dcdfb8e5b1701ee`;
  and
- optimized H1506 report, SHA-256
  `81359250208db5390056016a40391c2f2f43005ec835e335756844486787d6ef`;
- `experiments/h1507_cvc5_dimacs_crosscheck.py`, SHA-256
  `f44d0cfbf51f6e0de6fc4546c549284130b5722f75c7dad1345b3a4ea904d71e`;
  and
- `tmp/ledger33/current/h1507_cvc5_dimacs_crosscheck.json`, SHA-256
  `e5cf8fd47512668e01de8291a1adf680ded696c8e996c8524a6825400c48b937`.

No x87 instruction or hardware capture ran, no label or private ledger was
opened, and no manifest, emulator behavior/default, academic paper, or PDF was
changed.  R96 remains empirical/incomplete; the authoritative frontier remains
eleven mode rows over ten operands.
