# D0036 append-only FPATAN corpus extension

This pack adds **837,600** input tuples from the one-shot restored-quadrant
boundary and nonzero discarded-history challenge. The combined sixteen-pack
index is [CATALOG-D0036.json](../../CATALOG-D0036.json): **3,655,928 unique
tuples**, with zero cross-pack duplicates. The original root manifest and
fifteen input packs are unchanged.

`inputs.txt.gz` uses the original FPATAN capture protocol and has already
been observed on the recorded Skylake reference. Reuse those saved labels
there; do not capture the same tuples again. On another CPU, check that host's
history and durably reserve each fresh tuple before capture. Keep results and
capture identity separate from this CPU-independent input package.

Two construction pools are also retained:

- `quadrant-boundary-input-pool.tsv.gz`: seed, family, target restoration,
  target RC, numerator-neighbor offset, and the two positive raw operands.
  These windows were expanded into the admitted D0036 pack.
- `nonzero-cut-history-input-pool.tsv.gz`: cell, m, K, B and raw operands for
  the entire 31,232-pair D0035 construction scan. Only its selected groups
  were admitted into D0036; the remaining pool is not freshness-cleared.

Neither pool is a native capture-protocol pack. Model endpoints and retained
state traces were stripped. They contain no hardware labels or private
records. Preserve every original SHA256 and use a new extension/catalog for
future additions instead of overwriting this snapshot.

See [ANALYSIS-D0034-D0036.md](../../../ANALYSIS-D0034-D0036.md) for construction,
verification, results, limits and remaining adversarial work.
