# D0055–D0057: joint halfway/outer-boundary construction

2026-09-06. This investigation keeps the full four-addition objective open.
D0046 identifies only the short correction addition among the four fixed
tie rules. Production C, pseudocode and publication files remain unchanged.

## D0055: independent integer-dyadic implementation

The new GMP-integer miner uses signed integer significands and explicit
dyadic exponents, rather than repeated rational normalization. It implements
the exact D0049 inverse and both tie decisions. Long-kernel evaluation stops
when the two outer sums agree, because every remaining numerical input is
then identical; replay mode always evaluates both complete corrections.

Both optimized and ASAN/UBSAN executables replay 95,596 distinct historical
targets and saved carry fixtures identically, agreeing with the independent
integer-dyadic and Fraction graphs. This includes all 93,678 old GMP target
occurrences. The two 1,048,576-target pilots have byte-identical optimized
and sanitized target/log/propagation streams; every pilot tie is replayed.
Receipts are `../tmp/fpatan-re/d0055-selftest/REPORT.json` and
`../tmp/fpatan-re/d0055-preflight.json`.

Separate 4,294,967,296-target C runs record **occurrences**, not unique U
inputs. Native mining reports 173,694,959 even-inner ties with 2,949 outer
changes and 357 H changes; odd-inner has 206,611,815 ties, 3,604 outer changes
and one H change. Both runs completed independent verification. Even-inner
has 1,951 residual preimages, 25 kernel-cut changes and seven exact external
endpoint separators. The odd-inner changed-H square `855b1a3a155070d0`,
e=-9, even parity, has four residual preimages; all remain endpoint-masked.
All original target streams are retained. The independent filter audit
includes all 6,553 outer-carry occurrences from these two full scans.

## D0056: the boundary filter is an arithmetic exclusion

Let the magnitudes of the relevant coefficients be B, C, A, and let T be
the truncated inner product. An exact inner halfway is B+T; either RN64
decision has magnitude B+T +/- h, where h is half one inner RN64 unit.
The exact fourth-power value v obeys

`T/C <= v < (T + tau)/C`,

where tau is a conservative T67 product unit over the selected binade.
The outer product loses less than another conservative unit sigma. Thus
the real expression `S(T) = A + (T/C)*(B+T)` encloses both possible outer
pre-cut magnitudes, with normalized errors bounded by

`E_low = (vmax*h + sigma)/outer_unit`,

`E_high = (vmax*h + (tau/C)*(B + Tmax + h))/outer_unit`.

The signs for the negative even chain are handled by magnitudes; its two
terms have the same sign. Assertions check that the target and outer sum
stay in their stated binades. The uncertainty bounds are deliberately
conservative and depend on coefficient values/precision, not miss labels.

The halfway progression makes `S/outer_unit = alpha*j^2 + beta*j + gamma`
exactly. Within a block starting at j0, its linear part has positive
curvature in `[0, alpha*(width-1)^2]`. If that enlarged interval crosses no
integer, both rounded outer sums must be identical. Exact Euclidean floor
sums enumerate indices in the two possible boundary residue bands without
testing every index individually. Square preimage inversion and complete
Fraction replay then reject false positives and propagate every retained
tie. The complete sampled block recipe is retained in `blocks.tsv`.

Three tests cover exact floor sums/residue enumeration, inclusion and
enclosure of all 30 previously known long outer carries, and complete
small-block forward enumeration. The independent full C scans supply an
additional held-apart check through `d0056_verify_filter.py`.

This is a necessary-condition filter in the unchanged numerical graph,
not a fitted hardware selector. Discarded indices are proved unable to
change that outer sum under these two tie decisions. Randomly sampled
blocks are not the entire polynomial domain and may overlap; their target
index counts are not unique external input counts.

## Exact external long even-inner witnesses

The 1,024-block pilot covers 1,073,741,824 target-index occurrences, selects
24,913 boundary indices, and verifies 1,043 exact U ties. There are 763 outer
changes, 86 H changes, 474 residual preimages, seven kernel-cut changes and
one exact external endpoint separator, at even retained parity.

The 8,192-block run covers 8,589,934,592 index occurrences, selecting 200,745
boundary indices and 8,038 distinct retained U ties. There are 5,912 outer
changes, 742 H changes, 4,099 residual preimages, 30 kernel-cut changes and
eight exact external endpoint separators, all odd retained parity.
All nine external lifts succeed and independently replay the actual
separately truncated reduction, target tie, downstream arithmetic and
output/C1 difference. These nine inputs are the D0057 seeds. The independent
D0055 even-inner run also finds seven external separators; they are separate
evidence and are not silently added to the already-frozen D0057 campaign.

The long odd-inner 262,144-block D0056 run is a separate live investigation
under `../tmp/fpatan-re/d0056-node0-wide/`; inspect its handle and terminal
receipt, not this static note, for completion. D0049's short odd-chain
536,870,912-target run completed: 34,965,885 exact U ties, 3,262 changed H,
14,687 residual preimages, eleven kernel-cut changes and 77 admissible
cell/sign proposals. None produces an external endpoint difference; this
does not prove global masking or identify the short odd-chain rule.

## D0057: hardware identifies nearest/even at the long even-inner addition

D0057 freezes the nine external witnesses, full 3x3 both-operand neighborhoods,
eight sign/octant transformations, all four RC and sampled PC24/53 groups.
All 648 generated pairs pass the local private/public/prior checks; 2,616
fresh tuples are frozen against the 7,119,648-tuple history. There are 72
even-parity and 512 odd-parity target ties, including two even-parity and 34
odd-parity endpoint separators. Therefore the frozen four-rule predictions
disagree with nearest/even on 36 rows for nearest/odd, two for ties-away,
and 34 for ties-zero. This mapping was fixed before native dispatch.

Both optimized and sanitized production-C preflights pass all 2,616 rows.
The two exact-witness and synthetic scorer tests pass. The read-only remote
history audit and staging identity/protocol checks pass, with no warmup
FPATAN execution. Only cleared inputs and generic capture/guard/protocol
helpers are sent to the authorized Skylake host; models, predictions and
private records remain local.

The one-shot capture, authenticated fetch and both scorers are complete.
All 2,616 rows agree with unchanged V7: zero output, C1, exception or
pre-load misses. Nearest/odd fails on 36 union rows (30 output and 18 C1,
overlapping), ties-away on two (two output and two C1), and ties-zero on
34 (28 output and 16 C1). These are exactly the frozen predictions.
Both parities discriminate; all twelve three-PC groups agree. The remote
ledger has integrity `ok` and D0057 `OBSERVED`. Never recapture it.

This identifies **nearest/even at the long even-inner addition among the
four fixed rules**, joining the short correction rule established by D0046.
The long odd-inner and short odd-chain additions remain unresolved. The
unchanged main C, pseudocode and paper are not edited to record this result.

The input-only corpus builder completed its full uniqueness audit:
`CATALOG-D0057.json` has 7,122,264 tuples in twenty packs. The nine seed
inputs and entire 2,616-row challenge are included. No hardware labels or
private data are included, and no old pack/catalog was rewritten. D0046
and D0057 have not yet run on i7; two-context coverage remains 7,097,584
tuples. The combined audit is `../tmp/fpatan-re/d0057-verification.json`.
