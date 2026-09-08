# D0042: early and table RN64 halfway adversaries

This append-only extension contains **2,485,048 distinct native tuples** and
an input-only construction pool of **8,562 external base pairs**. It targets
the two inner RN64 additions in the long/direct kernel and the odd-chain and
correction additions in the short/table kernel, including both parity cases,
both-operand neighbors, sign/octant transformations and all four RC.

`inputs.txt.gz` uses the main corpus capture protocol. `MANIFEST.json` pins
its bytes and coverage: 621,262 rows per RC, 2,465,856 at PC64, and 9,596
each at PC24 and PC53. The full append-only catalog is
[CATALOG-D0042.json](../../CATALOG-D0042.json), totaling 7,097,584
unique tuples across 18 packs.

`early-table-halfway-input-pool.tsv.gz` preserves every successful
construction, even when changing its tie decision is masked downstream.
Its columns are `node search cell residual_sign y_se y_sig x_se x_sig`.
This is not a native-protocol pack and is not an additional observation
count. No hardware labels, numerical predictions or private records are
included in this extension.

The four isolated opposite-halfway controls have zero observable separators
throughout this batch. Passing these tests adds exact-halfway event coverage;
it does not identify the hidden tie rules. Read
[D0041–D0044](../../../ANALYSIS-D0041-D0044.md) for the construction, measured
masking and per-host completion evidence.

These inputs are already observed on both recorded Skylake and i7 contexts,
with zero output/C1/exception/full-status differences. D0042 and D0044 retain
the respective native receipts. Never run these tuples again on either
context. Any new CPU context requires local
history checks and durable one-shot reservations. Reuse saved results on an
already observed context. Keep private supplemental history local.
