# D0063: endpoint-visible long odd-inner ties

This input-only extension contains 872 tuples from three exact external
long odd-inner tie witnesses, full 3x3 operand neighborhoods, sign/octant
orbits and all four RC modes, with sampled PC24/53. Its separate construction
pool retains all three seed pairs (two even parity, one odd).

All tuples were observed once on Skylake `00050654:0x1`; reuse those saved
labels rather than recapturing. They have not yet run on i7. Audit any
destination's history before a fresh-context capture.

The unchanged model has zero output/C1/exception/pre-load misses.
Nearest/odd, ties-away and ties-zero fail on 18, ten and eight union rows.
This identifies nearest/even at this addition among four fixed rules;
it is not a universal hardware proof. Hardware results and model predictions
are outside the input-only package.

See [the investigation](../../../ANALYSIS-D0058-D0062.md) and
[the immutable catalog](../../CATALOG-D0063.json).
