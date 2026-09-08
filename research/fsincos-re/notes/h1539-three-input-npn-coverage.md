# H1539 exact three-input NPN coverage audit

Status: **coverage boundary only; no selector and no promotion**.

## Purpose

H1535--H1538 close several complete three-input circuit classes over the
expanded named-history universe. H1539 enumerates all 256 Boolean truth
tables and quotients them by input permutation, input complementation, and
output complementation (NPN equivalence) to determine exactly what those
audits do and do not cover.

This prevents two opposite errors: describing a bounded structural result as
all three-input logic, or launching an undifferentiated 256-function feature
fit without identifying the missing physical mechanism.

## Exact classification

The exhaustive transform produces the standard 14 NPN classes. The orbits
are disjoint, contain all 256 truth tables, and have sizes summing to 256.
The current 34,473-row universe contains both constant-zero and constant-one
literal histories, so H1535's complete XOR3 audit also covers the reducible
XOR2 class by using zero as the third input.

The completed experiments cover nine NPN classes:

- six unate classes through H1536/H1538;
- three-input parity through H1535;
- two-input XOR/XNOR through H1535 plus the verified zero literal;
- the 2:1 mux class through H1537.

These nine orbits contain 136 of the 256 truth tables. Five binate NPN
classes, containing the other 120 truth tables, remain unsearched:

| representative | orbit | convenient template |
|---:|---:|---|
| `0x06` | 24 | `a AND (b XOR c)` |
| `0x16` | 16 | `popcount(a,b,c) == 1` |
| `0x18` | 8 | `a == b == c` (an opposite-minterm pair) |
| `0x19` | 48 | `a ? (b OR c) : (b XOR c)` |
| `0x1e` | 24 | `a XOR (b OR c)` |

The classification and template-to-orbit mapping are generated and asserted,
not entered as assumed labels.

## Interpretation

H1538's result is correctly a complete unate-class theorem, not a theorem
about all three-input Boolean logic. H1535/H1537 add the canonical parity and
mux binate classes, but five other binate classes remain mathematically
possible over three named histories.

There is presently no multiplier, rounder, carry-select, or decoded-control
provenance for those five arbitrary truth functions. Searching them merely
because they are the remaining entries in a truth-table quotient would be a
feature fit, not evidence of the closed physical law required for promotion.
They are recorded as a precise logical gap, not candidate selectors.

No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1539_three_input_npn_coverage.py`, SHA-256
  `0cd37b47f258f9a39a75a879745741101753c118be48d7fd68bb225ce763774d`;
- `tmp/ledger33/current/h1539_three_input_npn_coverage.json`, SHA-256
  `35b9b31cae7d9833cfe34f715541f5325e0d591a6e3a7a392216e083c5bdc709`.

The JSON pins the H1535--H1538 reports and immutable wall inputs.
