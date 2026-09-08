# D0061: endpoint-visible short odd-chain ties

This input-only extension contains 2,904 tuples from ten exact external
short odd-chain tie witnesses, their full 3x3 operand neighborhoods,
sign/octant orbits and all four RC modes, with sampled PC24/53 groups.
The separate construction pool retains all ten seed pairs.

All tuples were observed once on Skylake `00050654:0x1`; reuse those saved
labels rather than recapturing. They have not yet been observed on the i7
context. Audit any destination's history before a fresh-context capture.

The unchanged model has zero output/C1/exception/pre-load misses. Both tie
parities discriminate nearest/even from the other fixed rules; this is
evidence for the targeted addition, not a universal hardware proof.
Results and model predictions are outside this input-only extension.

See [the analysis](../../../ANALYSIS-D0058-D0062.md) and
[the immutable catalog](../../CATALOG-D0061.json).
