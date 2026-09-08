# H1486--H1489: surviving propagate class resolves to two functions

Date: 2026-09-03

Status: H1477's sole 10/10 precommitted class contains exactly two formally
distinct functions, not four interchangeable spellings.  The H1488 one-shot
Skylake Xeon discriminator selects pair A on 6/6 rows and falsifies pair B on
the two opposing rows.  Pair A was not promoted; the later balanced H1566 wall
falsifies it on 2/8 fresh rows.  The paper/PDF remains untouched.

## Complete 28-label replay

H1486 combines the sixteen opened H1472 rows, the established d0d0/d800
anchors, and the ten fresh H1477 labels.  The resulting hardware truth is
balanced, with fourteen merges and fourteen no-merges.  Repeating H1479's
complete search over seventy arithmetic-exact P5 layouts, 866 signals per
layout, and both polarities leaves exactly four of 121,240 literals:

```text
pair_02_14_35_hold2.final.propagate.-18
pair_02_15_34_hold2.final.propagate.-18
pair_03_14_25_hold2.final.propagate.-18
pair_03_15_24_hold2.final.propagate.-18
```

No exact-product bit at any tested cut-relative position from -80 through +66,
or its complement, equals the hardware truth.  Each survivor is instead the
XOR/propagate bit of a redundant final carry-save pair at product cut minus
eighteen.  The four names differ in how the six level-one compressor outputs
are paired and which level-two result is held for the final compression.

The four spellings are not a common arithmetic invariant.  On 200,000
deterministic normalized 67-by-64-bit products, all four possible paired
patterns occur: 82,677 `0000`, 17,133 `0011`, 17,117 `1100`, and 83,073
`1111`.  The very first sample gives `0011`.  Thus the 28-label equality is a
real out-of-sample survival but does not identify a unique representation.

## Exact two-function partition

H1487 reconstructs the complete 136-bit radix-8 Booth/carry-save graph as an
independent QF_BV circuit.  Under normalized 67-bit multiplicand and 64-bit
multiplier constraints, it asks for disagreements at both possible cut-minus-
eighteen columns, absolute columns 45 and 46.  Z3 4.15.3 proves:

- layout 0 XOR layout 1 is UNSAT;
- layout 2 XOR layout 3 is UNSAT; and
- layout 0 XOR layout 2 is SAT.

Therefore the four survivors collapse exactly to two functions over every
normalized input at the relevant columns.  Pair A contains the two `pair_02`
layouts; pair B contains the two `pair_03` layouts.  This is an exact
representation result, but it does not identify which pairing, if either,
exists in Skylake.

## Frozen independent discriminator

H1485 already contained six exact external, endpoint-visible operands from a
seed disjoint from H1471/H1476 and from the d0d0/d800 anchors.  No H1485 label
has been opened.  H1486 evaluates the two newly isolated functions on that
pre-existing bank:

- two rows are `0000`;
- two rows are `1111`;
- one row is `0011`; and
- one row is `1100`.

The last two rows force pair A and pair B to opposite endpoints.  H1488 audits
the repository-visible evidence and the private supplemental ledger, finding
zero collisions in both, then freezes all six FCOS/PC64 tuples.  Each pair has
three merge and three no-merge predictions.  The mode split is one RN, three
RD, and two RU.  The four unanimous rows test whether either function survives
at all; the two disagreement rows identify the surviving pair if exactly one
does.  State is `FROZEN_UNOPENED`, with one observation maximum per tuple.

H1489 was written and self-tested before any H1488 label was opened.  It
validates all frozen hashes and input ordering, classifies each hardware value
as incumbent/no-merge/other, and reports pair-A and pair-B survival separately.

## One-shot Skylake Xeon result

On 2026-09-04 the user gave standing authorization for precommitted campaigns
on both x87 research hosts and clarified the host map.  Immediately before
copying H1488, every embedded freeze hash matched; no local or remote H1488
output or opened sidecar existed; and a fresh search found zero unexpected
repository paths and zero collisions in the 26-file private supplemental
ledger.  The private ledger's identity and contents remain unpublished.

The Xeon identified as family 6, model 85, stepping 4, with model string
`Intel Xeon Processor (Skylake, IBRS)`.  Its capture source is byte-identical
to `capture-kit/x87_capture.c` (SHA-256
`aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1`).
All six copied freeze/input/runner hashes matched before execution.  The
runner then observed the six unique FCOS/PC64 tuples exactly once and reported
zero repeats.  The raw output was mirrored without rerunning the campaign.

H1489 reports:

- pair A exact: 6/6;
- pair B exact: 4/6, missing both precommitted disagreement rows;
- endpoints: three incumbent/hard-merge and three R1382/no-merge; and
- other endpoints: zero.

Thus the hardware vector selects pair A, the two `pair_02` layouts, over pair
B on this fresh bank.  The four unanimous controls also pass.  This is a clean
out-of-sample orientation result, but it is not a global proof: H1564 shows
that neither pair-A layout can simultaneously serve as the already validated
shared R1263/R1272 P5-style tree under any graph automorphism or same-column
one-wire retarget.  Pair A therefore remains an exact abstract function and a
surviving finite candidate, not a validated Skylake circuit or a closed-form
solution to the remaining R59 misses.  No emulator behavior/default or
academic paper/PDF changed.

## Artifacts

- `experiments/h1486_surviving_propagate_class.py`, SHA-256
  `d70fb34b25446fbb9d755c2720ac9a595144814e165ac4a5d9d8123306cdcfa2`;
- `tmp/ledger33/current/h1486_surviving_propagate_class.json`, SHA-256
  `e06a0a18fea031544cdae168195d17f0c1519f6431065757e5f162e16037b12c`;
- `experiments/h1487_propagate_pair_equivalence.py`, SHA-256
  `f38f2f02c905aadc19658086283349a07ee6aa2d4f0917e821a7db7467e7bcf2`;
- `tmp/ledger33/current/h1487_propagate_pair_equivalence.json`, SHA-256
  `c19fdf1587f8f87243e0ee46e57b42776fb17654fc6f51719a6c1d235c3a396f`;
- `experiments/h1488_freeze_propagate_pair_discriminator.py`, SHA-256
  `bb699209dde34a63ce39475b6648bc1d3c6b952a751ebe9aab70edd45aa536d2`;
- `transfer-tests/h1488/FREEZE.json`, SHA-256
  `b3057b0dea1cbbb9656b409b1ce61df74fe3765146f23884b08119ad493f8fc8`;
- `transfer-tests/h1488/manifest.tsv`, SHA-256
  `a7587d55b9442b8aee7b43d75a062b32256ff23fc9c7b30c6f72417516f67594`;
- `experiments/h1489_score_propagate_pair_discriminator.py`, SHA-256
  `30e7b05953dd65b1b90a4b40312776a5ec4c29e89b6bdc0038370970f06bd162`.
- `tmp/ledger33/current/h1489_h1488_score.tsv`, SHA-256
  `a3346676e0532e3f9fd49aebfc918cff86b470bc11d13f06f9c5b88780c990a6`;
- `tmp/ledger33/current/h1489_h1488_report.txt`, SHA-256
  `dfa6b770d2b001f054e990880f7189ca0da64186c68a02236fcdee223b38e4bf`;
- `transfer-tests/h1488/OPENED.json` and the raw files under
  `transfer-tests/h1488/hardware-output/`.

The H1486 and H1487 reports reproduce byte-for-byte.  H1488 is now
`OPENED_ONCE`; its immutable `FREEZE.json` remains unchanged.  No emulator
behavior changed and the academic paper/PDF was not edited.  R96 remains
empirical/incomplete and the ledger-free frontier remains eleven mode rows
over ten operands.

Postscript: H1566 subsequently opened H1496's precommitted balanced eight-row
wall.  Pair A scores only 6/8 and is falsified; pair B scores 4/8.  See
`notes/h1566-h1567-pair-a-adversarial.md`.  H1488 remains valid evidence that
pair A transfers farther than pair B, but neither is a general selector.
