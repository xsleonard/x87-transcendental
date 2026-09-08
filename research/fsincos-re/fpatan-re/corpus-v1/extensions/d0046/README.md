# D0046: endpoint-visible short correction ties

This append-only extension contains **22,064 native input tuples**: all
76 verified external witnesses, their 3-by-3 operand neighborhoods,
sign/octant transformations, all four RC and sampled PC24/53 controls.
Each RC has 5,516 rows; PC64 has 21,888 rows and PC24/53 each have 88.

The inputs expose the short-kernel correction RN64 tie decision. On the
recorded Skylake context, nearest/even passes while nearest/odd, ties-away
and ties-zero fail on 366, 224 and 142 union rows respectively. This does
not resolve the other three additions' hidden tie rules. Read
[D0045–D0047](../../../ANALYSIS-D0045-D0046.md) for scope and evidence.

`inputs.txt.gz` uses the standard native protocol. The separate
`visible-correction-tie-input-pool.tsv.gz` contains 76 base constructions,
with columns `node search cell residual_sign y_se y_sig x_se x_sig`.
It is not a native-protocol pack or an additional observation count.
Neither file includes model predictions, hardware labels or private records.

The combined [CATALOG-D0046.json](../../CATALOG-D0046.json) contains 7,119,648
unique tuples in 19 packs. Original packs/manifests/catalogs are unchanged.
These new inputs have been observed on Skylake only, not yet i7. Never
repeat them on the recorded Skylake context. Before another-context capture,
check its history and reserve fresh tuples durably; keep private history
local and treat uncertain observations as held, not retryable.
