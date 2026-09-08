# H1482: P5 sticky-state and R1475 reachability audit

Date: 2026-09-03

Status: the documented P5 sticky/overflow carrier and direct exact-product-bit
interpretations are falsified.  R1475 remains a label-selected, default-off
X2-internal hypothesis; H1477 remains unopened.

## Source-defined state

Intel US 5,195,051 places Booth partial-product generation in X1, the
four-level carry-save tree and sticky generation in X2, and final carry
propagation and rounding in WF:

<https://patents.google.com/patent/US5195051A/en>

That patent incorporates application 07/861,077, issued as US 5,260,889.  The
sticky patent exposes a concrete state rather than an inferred feature family:
trailing-zero encoders for the 67-bit multiplicand and 64-bit multiplier, their
sum, two precision-selected threshold comparisons for the two possible product
ranges, the product-overflow bit, and an overflow-controlled mux selecting the
final sticky bit.  Its extended-precision constants are `0x46` and `0x45`:

<https://patents.google.com/patent/US5260889A/en>

## Result

H1482 reconstructs the right-product operands on the sixteen H1472 rows and
the two established d0d0/d800 anchors.  The operand trailing-zero sums range
only from zero through seven.  They are therefore below both PC64 patent
constants on every row, so the two pre-sticky candidates are equal and the
selected sticky is constant.  Either possible comparator-polarity reading
misses 9/18 labels.

The negative result is not dependent on those literal constants or on the
scanned patent's overflow-mux wording.  H1482 exhausts every pair of thresholds
from zero through 132, independently complements the two comparator outputs,
and tests both overflow-mux polarities.  None of the 141,512 laws is exact;
the best laws retain five label errors.

The exact-value result is stronger.  H1482 adds H1476's 22 disjoint
exact-lattice rows as software function comparisons, giving forty rows.  The
R1475 function has both values, but every exact right product has the same
25-bit window from `cut-17` through `cut+7`:

```text
low to high: 1010101010101010111000000
```

No absolute product bit 0--130, no cut-relative bit -80--66, and no complement
of one is identical to R1475 over the forty rows.  The split is therefore not
an ordinary exact-product boundary bit.  It distinguishes redundant internal
encodings that cancel to the same exact boundary value.

## Causal interpretation

The R1475 operands are intermediate X2 carry-save signals.  They can influence
a selector implemented combinationally in X2, but US 5,195,051 does not expose
them as WF-latched state.  A later micro-operation could consume their XOR only
through an undocumented latch or sideband.  The one documented cross-stage
candidate, US 5,260,889's sticky/overflow state, cannot encode the observed
split.

This narrows the physical claim without deciding it.  It does not falsify a
Skylake-specific X2 control gate, and it does not validate R1475.  The frozen
H1477 vote remains the next direct discriminator.

## Artifacts

- `experiments/h1482_p5_sticky_reachability.py`, SHA-256
  `e64b4aa2d95a439dde88585a1a5af81eda676c7fffbd05507cfed0e6c4ecc171`;
- `tmp/ledger33/current/h1482_p5_sticky_reachability.json`, SHA-256
  `06a16961407ea10ebfa486a4ba3ac167872cc4f486416de2fea85e79af92af79`;
- local US 5,195,051 PDF, SHA-256
  `3d83be8935b39383aa4dc6d6409a1085cf477c9c528d40d22e1ec67d298ee09e`;
- local US 5,260,889 PDF, SHA-256
  `774403ae438c0a5f3037161749d3e3e8f00a6e69f96ca00816915ca3f0d2eff1`.

No x87 instruction ran, no private ledger or H1477 label was opened, and no
emulator default or academic paper/PDF changed.
