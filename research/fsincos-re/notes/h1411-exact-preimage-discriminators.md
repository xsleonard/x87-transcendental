# H1411 exact-preimage hardware discriminators

`experiments/h1411_exact_preimage_discriminators.py` is an analysis-only
follow-up to h1404.  It consumes the three preserved SAT preimages, verifies
their exact M66 equations at scale 2^-66, reconstructs the bit-by-bit
carry/borrow histories, and replays both instructions under RN/RD/RU/RZ in
the incumbent C model.  It neither executes x87 hardware nor changes an
emulator option.

For the two negative residuals, the correct q=0 control is the **signed**
direct operand.  This keeps `rsn` equal and avoids confusing residual-sign
history with quotient history.

## Ranked pairs

| Rank | Reduced state | q=0 control | Exact external preimage | q / side | Natural bit entering column 64 | Two's-complement CPA carry into 64 | Exposed cosine trace | Incumbent paired endpoints |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | d0d0 | FCOS `bffc d0d000000cc0b3f8` | FCOS `4001 c2895aa22102bc95` | 4 / - | borrow=1 | carry=0 | byte-identical | identical RN/RD/RU/RZ |
| 2 | d920 | FCOS `3ffc d920000000749eaa` | FSIN `3fff e433daa22177560a` | 1 / + | carry=1 | carry=1 | byte-identical | RN external is +1; RD/RU/RZ identical |
| 3 | cca0 | FCOS `bffc cca0000009242f0c` | FCOS `403b 9b96fed99478343c` | 892177135061317282 / - | borrow=0 | carry=1 | only `DI_RED.i0` and `DI_POLY.i0` differ | expected opposite sign; exact after sign and RD/RU polarity normalization |

The d0d0 pair is the cleanest first hardware discriminator.  It preserves
the instruction, signed reduced residual, complete exposed pipeline, output
sign, and every incumbent endpoint.  It also exercises the state for which
R1382 changes RD/RZ.  A hardware split between these two operands therefore
cannot be attributed to any presently exposed post-reduction field or to an
existing instruction-specific output rule; it would directly support a
reduction/subtraction-history qualifier on the terminal selector.

The d920 pair is still the cleanest positive-side test of the originally
proposed M66 carry into column 64.  Its complete exposed trace, including
`i1/i0`, collides.  Because mapping q=1 back to the cosine producer requires
FSIN, the incumbent already predicts a one-bit RN difference.  A capture must
therefore be scored against the per-instruction expected endpoints rather
than tested for naive equality.

The cca0 pair is the high-q polarity control.  The exact subtraction has no
natural borrows in any column, while the equivalent `A + ~R + 1` CPA carries
through every column 0..127.  Its expected q mod 4 = 2 output-sign control
changes `i0`; after removing only that control, the entire exposed datapath
collides.  RN/RZ magnitudes match directly, and the directed modes match
under the required sign transformation (`direct RD == external RU` and
`direct RU == external RD`).

## Constraint on carry-source hypotheses

Column 64 is not a universal nonzero-quotient tag:

```text
                         d0d0   d920   cca0
two's-complement CPA C64   0      1      1
natural add-carry/borrow   1      1      0
```

Thus neither conventional column-64 polarity maps all three external
witnesses to one common bit.  Under the two's-complement CPA convention,
columns 2, 3, 4, 11, 12, 54, 55, and 60 carry in all three external
witnesses and have no reducer history in the q=0 controls.  Columns 54, 55,
and 60 are consequently better shared candidates than column 64 if the next
hypothesis requires a single active-low-limb reduction carry.  This is only
a bit-vector discriminator fact, not evidence that Skylake retains or routes
one of those wires.

Together the three pairs separate the main causal alternatives:

1. d0d0 tests subtraction-borrow or generic nonzero-q history while holding
   every exposed endpoint determinant fixed.
2. d920 tests a true positive-side carry into column 64 against the q=0
   bypass, with a known cross-instruction endpoint baseline.
3. cca0 distinguishes a physical complemented CPA-carry interpretation from
   a natural borrow interpretation and tests whether any effect is high-q
   only.

## Artifact and capture discipline

The authoritative replay is
`tmp/ledger33/current/h1411_exact_preimage_discriminators.json` (30,047
bytes, SHA-256
`a26037c368527218efb6797487557c5ba0345f1c4b8107455450127997f5beeb`).
It contains every carry/borrow run, selected-column values, trace hashes and
field differences for all four modes, and the complete 2-instruction x
4-mode output matrix for each operand.

No private supplemental ledger was accessed.  Therefore these are ranked
software discriminators, **not** a frozen capture manifest and not a claim of
tuple freshness.  Before any one-shot hardware execution, the selected rows
still require the normal repository-visible plus private-ledger duplicate
audit and a frozen unopened manifest.  No hardware label has been opened.
