# H1564: shared-tree graph-automorphism wall

Date: 2026-09-04

Status: **no H1486 layout can be the one shared R1263/R1272 product tree by
graph isomorphism; no selector promotion.**

## Question

H1531 selected each of the four H1486 compressor layouts globally.  Every
layout regressed three or four cached rows, but its conservative claim boundary
left open a topology-relative remapping of the older R1263/R1272 consumer.
H1564 asks whether any actual automorphism of the six-to-three-to-two-to-one
compressor graph can supply that remapping.

This matters because the four H1486 formulas were found as final-propagate
aliases.  If they describe the same physical product tree already used by the
validated R1263/R1272 rule, the two uses must admit one consistent graph
embedding.  An arbitrary new wire fit is not such an embedding.

## Exact graph result

At the first-level-group granularity, the published tree has exactly 16
automorphisms.  They may:

- exchange the two inputs of any second-level compressor;
- exchange the two long second-level branches that meet at level 3; and
- exchange the two inputs of the held second-level branch.

They cannot exchange the held branch with either long branch.  The held branch
is the unique level-2 node that bypasses level 3 and feeds the final compressor
directly.  The final node is unique as well.  Exhaustive enumeration confirms
that all 16 automorphisms fix both structural roles.  Therefore the
R1263/R1272 signal must remain the held level-2 carry, and R1263's final-kill
qualifier must remain the final-node kill.  Relabeling the two long branches or
their leaves cannot change either value.

## Cached hardware wall

The union of H1531's changed rows contains five distinct baseline-exact
constraints: four R1263 comparator equalities and the one R1272 hard-3x merge.
Their required signal vector, in the fixed order retained in the report, is

```text
11011
```

The published row-ordered tree is an exact positive control.  The four H1486
layouts fail as follows:

| Layout | Held PP groups | Signal pattern | Errors / 5 |
|---|---|---|---:|
| published `01/23/45` | 4,5 | `11011` | 0 |
| `pair_02_14_35_hold2` | 3,5 | `01101` | 3 |
| `pair_02_15_34_hold2` | 3,4 | `01100` | 4 |
| `pair_03_14_25_hold2` | 2,5 | `00110` | 4 |
| `pair_03_15_24_hold2` | 2,4 | `00010` | 3 |

This reproduces H1531's complete three/four/four/three regression vector from
the internal signals and cached labels, rather than inferring it only from
architectural output differences.

H1564 also checks a strict superset of graph isomorphisms: every same-column
`sum`, `carry`, first-CSA `sum`, and first-CSA `carry` bit at all eleven tree
nodes, both direct and complemented.  That is 88 literals per layout, still
using the existing R1263 final-kill qualifier.  The published tree has three
finite-wall aliases including the intended `l2_2.carry`; every H1486 layout has
zero.  Thus even an arbitrary single-wire retarget at the same physical column
does not rescue one of the four candidates.

## Interpretation

The result narrows H1531's earlier escape clause.  No graph-relative rename,
and no same-column one-wire rename with either polarity, makes an H1486 layout
consistent with the already validated shared-tree consumers.  A repair would
need a different consumer circuit, a different compressor representation, or
a genuinely new control observable.

Consequently the H1486 pair-A/pair-B formulas remain exact abstract
representations and finite candidate selectors, but they do not currently have
a consistent physical interpretation as the one shared P5-style product tree.
Choosing between them by row-arrival or drawing geometry would therefore be a
heuristic, not a hardware proof.  The subsequently opened H1488 one-shot bank
selects pair A on 6/6 rows and falsifies pair B on its two disagreement rows.
The later balanced H1566 wall then falsifies pair A on 2/8 fresh rows (and
scores pair B only 4/8).  Thus neither the topology theorem nor the broader
hardware evidence permits either pair to be promoted.

The next structural direction remains absolute ROM/control-state recovery or a
new observable.  H1488 is now `OPENED_ONCE`, with zero repeats; neither pair-A
layout is promoted.  H1566 is also `OPENED_ONCE`, with zero repeats, and
closes pair A as a general selector candidate.

## Artifacts

- `experiments/h1564_shared_tree_automorphism_wall.py`, SHA-256
  `5b6c5bdae5d52c312da7ae8bbe919e8572314de900e2d19ad5527efb53e6938e`;
- `tmp/ledger33/current/h1564_shared_tree_automorphism_wall.json`, SHA-256
  `7b68d89b80c2f532c9536be6b33caa5f0121e875ae4bdc1c8c0555882645f7f6`.

H1564 itself ran no x87 instruction or fresh hardware capture and opened no
label or private-ledger entry.  The later H1488 result changes neither H1564's
graph theorem nor any manifest, emulator behavior/default, academic paper, or
PDF.  R96 remains empirical/incomplete, and the authoritative frontier remains
eleven mode rows over ten operands.
