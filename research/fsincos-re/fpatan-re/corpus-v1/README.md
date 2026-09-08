# FPATAN corpus v1 — inputs for cross-CPU verification

## Current append-only catalog

[CATALOG-D0066.json](CATALOG-D0066.json) contains **7,571,628 unique tuples
across 23 packs**, with zero exact cross-pack duplicates. Its latest
[D0066 extension](extensions/d0066/README.md) adds 445,588 model-independent
mathematical/lattice-boundary, raw-bit and exhaustive-window tests, captured
once on each CPU (D0066 Skylake, D0067 i7), with zero misses or cross-CPU
differences. The earlier [D0063 extension](extensions/d0063/README.md) adds long odd-inner tie
discriminators, and [D0061](extensions/d0061/README.md) adds short odd-chain
discriminators. Both cover both retained parities and their adversarial
neighborhoods. The [D0057 extension](extensions/d0057/README.md) contains
long even-inner tie discriminators.
The [D0046 extension](extensions/d0046/README.md) contains short-correction
tie discriminators. The earlier
[D0042 extension](extensions/d0042/README.md) retains masked ties too. Older packs,
manifests and catalogs are unchanged; use the current catalog to enumerate
both original `inputs/` packs and additive `extensions/` packs.

All current inputs have been observed on Skylake. The common two-context
subset comprises the previous D0042 catalog plus the D0066 extension:
**7,543,172 tuples per context, zero output/C1/exception/full-status
differences**. D0043 covers 4,612,536 tuples, D0044 covers 2,485,048 and D0067
covers 445,588. **The 28,456 rows in
D0046/D0057/D0061/D0063 have not yet run on i7.** Check the
[independent analysis](../ANALYSIS-D0065-D0070.md) and per-host receipts before
any capture. Never rerun an observed or uncertain tuple on the same context.
CPU comparisons do not increase the distinct input count. Hardware results
remain outside this input-only package.

## Original immutable package snapshot

This is a CPU-independent input package, approximately 88 MiB. It contains
**2,818,328 distinct observation tuples** in fifteen gzip packs under
`inputs/`, plus a separate provisional constructive pool. `MANIFEST.json`
records counts, SHA256 hashes, RC/PC coverage and source-manifest hashes.
All native results remain outside this directory, organized by their capture
context. No private ledger, numerical model or predictions are included.

Each native-input line is the existing public protocol:

```text
id rc pc y_sign_exponent y_significand x_sign_exponent x_significand
```

Hexadecimal raw80 words are exact; no decimal conversion is required.
FPATAN consumes y from ST(1) and x from ST(0). The contract is masked
exceptions, clear initial state, a valid two-deep stack, and one instruction
per tuple. Modes are `rn`, `rd`, `ru`, `rz`; PC is 24, 53 or 64. The case ID
does not encode a CPU, allowing outputs from different CPUs to be joined
without changing the inputs. Preserve the entire returned result/status,
not only the numeric output, and record the actual capture identity separately.

## Boundary construction

The corpus builders target interactions between the internal arithmetic cuts
and the final raw80 rounding boundary:

- Joint internal/final ties test whether a changed intermediate rounding rule
  reaches the observable output. A tie at one node can be masked downstream.
- Equal retained states with different discarded bits test whether the
  proposed state representation contains enough information.
- Table-cell boundaries combine numerator cancellation with denominator cuts;
  input pairs must satisfy the actual cell-selection inequalities.
- Exact-square ties must be reachable from raw80 operands. Arbitrary halfway
  values in an abstract multiplication are not necessarily reachable here.
- Power-of-two scaling and sign/octant transforms connect normal, subnormal
  and exponent-boundary cases while exposing exceptional paths separately.
- Independent mathematical bounds and raw-bit strata test the model without
  using its arithmetic to choose every input.

The per-pack analyses give the integer constructions, inverse maps and
coverage limits. A generated boundary pool is distinct from its admitted
hardware observations; excluded or unreachable candidates are not passes.

## No-repeat rule

Every tuple in `inputs/` has already been observed on the recorded Skylake
reference. **Do not run those tuples again there.** Reuse the saved labels.
Before using a pack on another CPU, check that host's existing tuple history
and reserve every fresh tuple durably with the generic one-shot guard. A
previously dispatched but uncertain tuple is held, not retried. Keep the
private supplemental history local; never upload it with this package.

## Provisional theoretical pool

`provisional-exact-square-tie-pool.tsv.gz` retains **all 145,315** exact
external base pairs from D0032, including controls without an endpoint-visible
mutation. Columns include v, E, cell, residual sign, raw operands and the
number of software-predicted positive-restoration/RC differences. The pool
is not in the capture protocol and is **not** a freshness-cleared native pack.

Its full sign/swap/four-RC expansion at PC64 is at most **4,650,080 rows**
before exclusions. Apply local and per-host history checks, reuse any existing
observations, freeze predictions, and split fresh rows into bounded batches.
Do not send the provisional pool to a native capture program as-is. D0033 is
the first admitted subset; most of the pool is not yet hardware-tested.

The exact construction, measured original gap, D0033 results and remaining
adversarial directions are in [ANALYSIS-D0031-D0033.md](../ANALYSIS-D0031-D0033.md).
`../package_corpus_v1.py` builds this package exclusively from authenticated
input sources and independently rejects cross-pack duplicate tuples. It is
exclusive-create; do not overwrite this snapshot for subsequent campaigns.
