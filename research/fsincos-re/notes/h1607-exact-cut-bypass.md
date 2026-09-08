# H1607: complete ordinary-round versus exact-bypass audit

Date: 2026-09-04. No common exact-bypass pattern survives on the fixed
thirteen-cut direct-cosine graph, with either omitted or frozen original
numeric payload. This is a finite mathematical-family exclusion, not a
decoded forwarding contract, a general impossibility result, or a selector.
No hardware/C execution, new observation, source/default change,
private-ledger access, or paper/PDF update was performed.

## What was exhaustively tested

Each of H1595's thirteen cuts is independently either normally rounded or
bypassed. A bypass forwards the **exact numerical dyadic result to every
consumer** of that node. A single 13-bit pattern must work for every operand
and architectural rounding mode. Non-bypassed square/fourth, multiplications
and correction use ordinary CHOP67; the four Horner additions use RN64.
Final reconstruction always uses ordinary architectural `RC64(1 + correction)`.

The node order is square, fourth, negative-mul1, negative-add1,
negative-mul2, negative-factor, positive-mul1, positive-add1, positive-mul2,
positive-factor, left, right, correction. Bit one means exact bypass; bit zero
means the ordinary materialization above. Altered square/fourth values are
shared by both arms, and all downstream arithmetic is recomputed.

All `2^13 = 8,192` common patterns were evaluated on H1600's 36 distinct
operands, 64 actually recorded RC outputs and 27 actual C1 constraints,
separately for each payload variant. That is 294,912 operand/pattern
evaluations per variant, 589,824 total—not new hardware observations.
Branches whose numeric values coincide remain separate so that every named
pattern is covered exactly once. There is no timeout, early rejection that
skips later rows, heuristic bound, or floating-point arithmetic.

Payload-omitted uses zero. Frozen-numeric holds each operand's original
consumed signed payload and original scaling exponent fixed before the
correction cut, including when that cut itself is bypassed. It does not
recompute any empirical gate, payload or scale from changed upstream values.
The signed payload is explicitly preserved per operand in the report.

Exact forwarding is a mathematical maximum-information hypothesis, **not**
evidence for unlimited physical precision or a P6 forwarding wire. This binary
family does not contain every intermediate finite precision: exact and rounded
endpoints need not behave like an arbitrary intervening width.

## Results and useful boundaries

| Payload variant | Common patterns matching all outputs | Common patterns matching outputs and C1 | Best failed operands / 36 |
| --- | ---: | ---: | ---: |
| omitted | 0 | 0 | 13 |
| frozen original numeric | 0 | 0 | 14 |

No omitted-payload pattern reaches the H1603 37,441-operand control wall; no
control scoring or frozen-payload fabrication was necessary. The best finite
fits are failures, not candidates. There are 64 patterns tying each best
operand score. A least-bypass representative among the best output-row scores
is mask 4610 (fourth, positive-factor and correction bypass) for omitted,
which fails 13 actual output rows; mask 6146 (fourth, right and correction)
for frozen fails 16 actual output rows over 14 operands. Full pattern scores
and their failed RC/C1 inverse counts are retained, not just the best rows.

Every operand is individually reachable in both variants, so failure comes
from requiring shared behavior. Every operand admits zero or one bypass
except frozen-numeric `3ffc:ffffc00024077827`, which needs at least two.
Its three minimum masks are 3, 2049 and 2050: square+fourth, square+right, or
fourth+right, with all other cuts ordinary. This is conditional reachability,
not a recommended input-specific selector.

C1 removes some output-compatible patterns at `cf62ea1253ad3be5`,
`de400000a2e32d2a`, and `f9e0000229067583` in both variants. No C1 constraint
is needed for the common-family exclusion, however. The C1 calculation is
the H1599 conditional positive-final-round inverse: the recorded result is
above the common prevalue iff recorded C1 is one. Unknown status lanes remain
unknown; no internal rounding event's C1 behavior is inferred.

## Compact, directly verified contradictions

Here `S,N,P,L,R` are Boolean **bypass choices**, respectively square,
negative-factor, positive-factor, left and right. These predicates describe
acceptance of fixed operation patterns for named observations; they do not
classify arbitrary external operands or propose chip gates.

For omitted payload, the minimum two-operand core is:

| Operand | Sufficient recorded mode/result | Complete acceptance predicate |
| --- | --- | --- |
| `3ffc:b72fd2547f8c2fef` | RU → `3ffe:fbea1ff3e2c2275c` (H1580 E001) | `not (S or N or L)` |
| `3ffc:ba100000056e0a67` | RN → `3ffe:fbc91f1ca0fa9a3a` (H1091 comb13 index 2080977 / H1378 old-03) | `S or N or L` |

For frozen numeric payload, the minimum core is:

| Operand | Sufficient recorded mode/result | Complete acceptance predicate |
| --- | --- | --- |
| `3ffc:b0000000044ca2bf` | RN → `3ffe:fc3a6170f7389cfa` (H1091 comb7 index 452822 / H1378 old-02) | `N or P or L` |
| `3ffc:cdcc0585c940196f` | RU → `3ffe:fad8efc715aca496` (H1580 E007) | `not (N or P or L) and (S or R)` |

The remaining bypass bits do not affect acceptance on these core operands.
Both contradictions follow from output bits alone. Added modes and available
C1 flags do not change the corresponding core acceptance sets. Neither
chosen core has a same-RC two-single-output contradiction: the first uses
RU/RN, the second RN/RU. This report therefore does **not** claim that
architectural-RC-dependent bypass patterns are excluded.

All singleton subsets are satisfiable, proving minimum cardinality two.
For omitted b72 use mask 0; for omitted ba100 use mask 1 (square bypass).
For frozen b000 use mask 32 (negative-factor bypass); for frozen cdcc use
mask 1. Complete exact/selected stages and actual-mode outputs for these
witnesses are in `core_certificate.individual_witnesses`.

The compact predicates are checked against the complete enumeration and a
second straight-line integer replay of **every** pattern for the four core
operand/variant cases: 32,768 full replays. Each singleton witness is also
checked against the independent rational operation replay. These checks do
not import an MDD/Boolean solver or replace the full arithmetic enumeration
with a fitted formula.

## Independence, completeness and previous forwarding work

The new script explicitly spells out the graph and its bypass traversal,
using H1592's tested unbounded-integer dyadic primitives and factual constants.
Every endpoint is checked both by forward architectural rounding/C1 inequalities
and against the pinned H1600 exact inverse intervals. Each operand's traversal
asserts that the set of visited masks is exactly `[0,8192)`. The full raw
artifact preserves each signed correction and each acceptance result.

The primitive/reference tests include 14,322 signed rational-grid quantizer
comparisons, 128 independent rational full-graph replays (1,664 stage checks),
and 128 all-bypass comparisons with the directly evaluated unrounded
degree-twelve polynomial `sum(C_i*x^(2*i)) + payload`. The ordinary/no-bypass
boundary agrees with H1592's established ordinary replay on all 64 actual
mode rows. The largest exact numerator encountered across the full traversal
is 882 bits; this is an observed software integer size, not a chip-width
estimate or a search cutoff.

H1607 changes all thirteen materializations, including coupled square/fourth
and terminal operations. This supplies a full coupled binary exact-bypass
exclusion within the stated numerical family. No physical forwarding
contract is recovered.

## Artifacts and reproduction

Authoritative output:
`tmp/ledger33/current/h1607_exact_cut_bypass_v2/`.
The earlier output directory remains preserved. Every H1600 input evidence
hash is checked against its pinned report, including historical source
`tmp/ledger33/current/h1598_source_before.c` (SHA-256
`de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`).
The historical source is not executed. H1603 evidence is pinned separately;
H1603 is not scored without a common survivor.

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1607_exact_cut_bypass.py` | `7284102dccc49f891e02f698d24a067d10dfa36b79966e5089a53140b028a59d` |
| `report.json` | `11368cc368f62c54dd916b436f58dc31f70130945045fcece8c676449b7b1938` |
| `all_bypass_outcomes.tsv.gz` | `28db492bd01bc57b66da23683cbb25783c2fc1b9741bbb9b22389bab8fc46b48` |
| `all_pattern_scores.tsv` | `518e3e4af0366c477641e51988e2a5cc2163a291c706fe9ff5ebc53d75e82370` |

From the repository root, select a fresh output directory:

```sh
python3 fsincos-re/experiments/h1607_exact_cut_bypass.py --selftest
python3 fsincos-re/experiments/h1607_exact_cut_bypass.py \
  --root fsincos-re --output-dir /private/tmp/NEW-H1607-DIRECTORY
```

Existing output directories are refused. A separate local rerun reproduces
the report, raw gzip and complete score table byte-for-byte. Syntax and
whitespace checks pass. No selector or repaired endpoint is claimed; different
widths, edge-specific forwarding, graph changes, input/control-dependent
semantics and regenerated payload logic remain outside this finite family.
