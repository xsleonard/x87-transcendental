# H1531: shared-tree topology cross-check

Date: 2026-09-04

Status: **the cached R1272 discriminator chooses one H1486 spelling locally,
but no H1486 topology survives global shared-tree replay; physical orientation
remains unresolved; no selector or paper/PDF change.**

## Question

H1528--H1530 give a total, table-free decoder for the pair-A/pair-B swap
defect but do not identify the physical Skylake orientation. R1272 is an
already validated user of a held level-2 carry from the same reconstructed
right-product compressor tree. H1531 tests whether that older hardware fact
can orient the new quotient without another capture.

The test has two deliberately separate levels:

1. transfer the name `held level-2 carry` to each H1486 layout and evaluate the
   unique cached R1272-positive leg; and
2. select each layout globally for every existing consumer of the reconstructed
   product tree, then replay the complete H1272 heterogeneous cached wall.

`G_R1531TREEPAIR=1..4` is an analysis-only source hook for the four fixed
H1486 layouts. Zero retains the documented P5 pairing and is the default.
Every binary was compiled with `G_ROUND84=0`.

## Result

The R1272 discriminator is direct FCOS
`3ffc:d80000000b15da62` in RU. At absolute right-product column
`right_shift+4=67`, hardware requires the held carry to be zero so that the
hard-3x low-block merge reaches the comparator.

| H1486 layout | held carry | d800 exact | cached changes | fixes | regressions | candidate misses |
|---|---:|---:|---:|---:|---:|---:|
| `pair_02_14_35_hold2` | 1 | no | 3 | 0 | 3 | 12 |
| `pair_02_15_34_hold2` | 1 | no | 4 | 0 | 4 | 13 |
| `pair_03_14_25_hold2` | 1 | no | 4 | 0 | 4 | 13 |
| `pair_03_15_24_hold2` | 0 | yes | 3 | 0 | 3 | 12 |

Thus a literal transfer of the R1272 node name chooses only
`pair_03_15_24_hold2` on d800. But the global shared-tree test rejects all
four layouts. The wall contains 204,788 unique hardware legs and checks
2,798,209 duplicate occurrences for agreement. The documented pairing has
nine pre-existing misses; every H1486 layout adds three or four regressions
and fixes none.

The last layout, which preserves d800, regresses the already exact cached
legs `f9e0000000a5925b/RN`, `fcc0000003541b35/RN`, and
`e7400000015584c1/RU`. The other layouts also regress d800 and/or the existing
placement controls listed in the machine-readable report.

## Interpretation boundary

This is not evidence that H1530's abstract decoder is wrong. It proves a
narrower and useful negative: the R1272 signal cannot orient the quotient by
literally replacing the one shared product-tree topology. A coordinate-aware
isomorphism could remap each older selected wire so that its validated Boolean
function is retained, but then the older wire supplies no independent
orientation constraint. Treating d800 alone as a physical vote would therefore
be circular.

The universal H1530 decoder remains exact. Its pair-A/pair-B physical choice
remains open, H1488 remains the frozen direct vote, and no emulator behavior or
default is changed. The ledger-free frontier remains eleven mode rows over ten
operands.

## Artifacts

- `experiments/h1531_shared_tree_topology_audit.py`, SHA-256
  `32c06ed0749ff30590cbdff21113e8a9cd9a86b460f2a156c9af945555185665`;
- `tmp/ledger33/current/h1531_shared_tree_topology_audit.json`, SHA-256
  `f5390ab5206222843eb4407f0d28ea97365cb32ec701db58b6dc0c3ab93fc5da`;
- topology score reports 1--4, SHA-256 respectively
  `715a885cf0403fc54ffb92afece1229d5cfcdcb629312647fba7632217d30474`,
  `2639e4eb31d6a44c1fdde07ea5bdbbb0d46fa5587ec8c6b1f83e66e0343daa98`,
  `211c255b4367e93eb58d6dc9e42de701ee5f21444244e8e7ec1d09901307dbeb`,
  and `e31e5084cc6a55060863b2e8f76cea4df54bc423ba8b5c2c5feb765e06de9635`.

No x87 instruction or fresh hardware capture ran, no label or private ledger
was opened, and no manifest or academic paper/PDF changed.
