# H1566--H1567: pair A fails the balanced boundary-carry wall

Date: 2026-09-04

Status: **pair A falsified on 2/8 fresh rows; pair B scores 4/8; no selector
promotion.**

## Purpose

H1488 selected pair A over pair B on a fresh six-row bank.  That result was
clean but deliberately finite.  H1496 had already constructed a disjoint
software-only surface from 30,000,000 exact modular-lattice plateau samples.
Its selected eight rows contain two of each exact pair pattern `0000`, `0011`,
`1100`, and `1111`; pair A and pair B are each balanced four merge/four
no-merge.  Four rows make the pairs disagree and four are unanimous controls.
All rows are endpoint-visible at absolute target column 46.

H1566 turns that pre-existing surface into a one-shot hardware challenge.  It
does not refit or reorder the H1496 selection.

## Freeze and capture discipline

The freezer verified the H1496 report and its exact pattern balance.  Before
freezing, the eight significands occurred nowhere else in repository-visible
evidence; the only allowed source was H1496 itself.  The private 26-file
supplemental ledger had zero collisions.  H1566 froze one RN, three RD, and
four RU FCOS/PC64 tuples.  `FREEZE.json` is SHA-256
`972b03288c2132b7c14233b79fc83102d479207879a292e45cf4c3ed8e1e53a4`.

Under the user's standing authorization, the immutable kit was copied to the
Skylake Xeon VM oracle.  The host had no prior H1566 path, the repository
capture source matched byte-for-byte, and every copied freeze/input/runner
hash was checked before execution.  The runner observed all eight identities
exactly once and reported zero repeats.  The raw files are preserved under
`transfer-tests/h1566/hardware-output/`; `OPENED.json` records the opened-once
state separately from the immutable freeze.

## Result

H1567 was written and self-tested before the labels were opened.  It validates
the manifest hash, each per-mode input hash, positional order, and exact row
counts.  The hardware result is:

| Candidate or endpoint | Exact rows |
|---|---:|
| pair A | 6/8 |
| pair B | 4/8 |
| incumbent/hard merge | 2/8 |
| R1382/no merge | 6/8 |
| other endpoint | 0/8 |

Pair A misses one `1100` disagreement under RN and one `1111` unanimous
control under RU.  The latter is especially decisive: both abstract pair
functions request a merge, while hardware selects no merge.  Thus no choice
between the four H1486 compressor layouts can implement the selector.  Across
the 28 H1486 labels, six H1488 labels, and eight H1566 labels, pair A is now
40/42 and pair B 36/42.  Those are falsified finite candidates, not approximate
solutions to promote.

## Interpretation

H1495's boundary-carry identity remains exact mathematics for each chosen
redundant representation.  H1567 shows that the chip's hidden selector is not
either of those boundary carries.  This is independent of H1564's topology
wall: H1564 rejects using an H1486 layout as the already validated shared
R1263/R1272 tree, while H1567 now rejects even treating pair A as a separate
general selector on the fresh lattice.

The pair-layout branch is closed as a selector hypothesis.  The strongest
remaining directions are an absolute ROM/control-state recovery or a truly
new observable, not further fitting of these boundary-carry functions.  No
emulator behavior/default or academic paper/PDF changed.  R96 remains
empirical/incomplete, and the authoritative ledger-free frontier remains
eleven mode rows over ten operands.

## Artifacts

- `experiments/h1566_freeze_pair_a_adversarial.py`, SHA-256
  `dd6af99c579cd31268d5ad073bff7e528a7ace25f75ed896322f40de6dbf2319`;
- `experiments/h1567_score_pair_a_adversarial.py`, SHA-256
  `24b54597b1e08dda9e7befedf3c74295a6b58fd4e3c44af259572f2fb97585a7`;
- `transfer-tests/h1566/FREEZE.json`, SHA-256
  `972b03288c2132b7c14233b79fc83102d479207879a292e45cf4c3ed8e1e53a4`;
- `tmp/ledger33/current/h1567_pair_a_adversarial_score.tsv`, SHA-256
  `ab8473d2a99d8cc2dfc379a316c55b484f0b4e422d53713c79d6e526e089d3a2`;
- `tmp/ledger33/current/h1567_pair_a_adversarial_report.txt`, SHA-256
  `7f8118b22f75d3ee500d5b3801729eb7a026ae51a39a8c8ef8aebf7c03b40041`;
- `transfer-tests/h1566/OPENED.json` and raw
  `transfer-tests/h1566/hardware-output/`.
