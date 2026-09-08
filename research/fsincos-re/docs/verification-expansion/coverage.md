# Trig and FPATAN coverage audit

The existing trig evidence is extensive. The remaining accounting problem is
to distinguish completed input/control combinations from overlapping replay
counts and historical records that do not establish the precision setting.
Both the Core i7-6700 and the Xeon are represented below.

The six bounded capture jobs are complete and scored. They confirm one
F2XM1 rounding bug and the proposed FPTAN handling of unsupported encodings.
The logarithm and FPATAN confirmations pass without algorithm changes.
The fixes are isolated patches for integration review.

## Authenticated trig checkpoint

The checkpoint was frozen at 2026-09-07 14:10:47 UTC. The audit verified all
completed shard payload hashes, input/prediction/result receipts, processor
context identifiers, portable observation manifests, and exact index mappings
to the frozen selection. The indices are ordered, disjoint, and cover every
selected case in that completed prefix. The original numerical scorer was
not rerun; its saved results and their input/output hashes were authenticated.

| Recorded processor | Completed H1725 shards | New PC64 cases | Result/C1/C2 differences |
| --- | ---: | ---: | ---: |
| Core i7-6700 | 3,258 | 101,049,148 | 0 |
| Xeon | 6,622 | 395,308,432 | 0 |

These totals are a fixed checkpoint. H1725 continues beyond it and was not
restarted or interrupted by this audit. At that checkpoint, 115,333,056 i7
and 93,789,828 Xeon cases remained in the cleared selections.

The [completed-prefix receipt](../../tmp/verification-expansion/coverage/h1725-completed-prefix.json)
contains every shard's receipt hashes and the counts for each instruction and
rounding mode. The [reconciliation](../../tmp/verification-expansion/coverage/trig-reconciliation.json)
also authenticates all 513 subordinate H1719 report hashes, deduplicates the
named normalized reference sets, and confirms their PC64 cases do not overlap
the H1725 selections.

| Processor | Distinct cases with direct recorded CPUID | Additional cases with older FMS-only attribution |
| --- | ---: | ---: |
| Core i7-6700 | 101,271,628 | 0 |
| Xeon | 395,631,136 | 257,136 |

The second table combines that H1725 checkpoint with the normalized H1712,
H1714, H1715, September 5 review and H1722 records. It includes their recorded
PC24/PC53 cases as well as PC64. It is an attributable lower bound for those
sources, not a replacement total for every historical test.

H1719's 299,028,167 i7 and 17,604,112 Xeon replay appearances remain valuable
regression evidence. Their overlapping appearances are not added again.
Older instruction/rounding-mode coverage with unknown PC remains separate;
it is neither a PC64 pass nor proof that an input was never tested. Likewise,
the 31 absent historical mode files do not identify 31 missing tuples.

The full cleared H1725 selection is also smaller than the original Cartesian
matrix. Its prior exclusions, possible-history holds and binary64-domain
holds cannot be converted into pass credit when the running selection ends.

## FPATAN boundary search

The original `a0064-below` query is satisfiable. It has **4,247** legal integer
significand pairs within its original bounds. The earlier continued-fraction
construction did not find one, and its saved UNKNOWN receipt is unchanged.

The new checker counts the integer points between the two rational bounds
using exact floor sums. It constructs 16 explicit pairs, all of which satisfy
the original unmodified SMT query in Z3. The floor-sum helper also agrees with
brute-force sums on 3,000 small signed test cases.

- [Exact count and witnesses](../../tmp/verification-expansion/coverage/a0064-below-exact-count.json)
- [Original-query SMT checks](../../tmp/verification-expansion/coverage/a0064-below-smt-review.json)
- [Reproducible exact checker](../../tmp/verification-expansion/coverage/audit_boundary.py)

This closes the failed witness search. It does not establish processor results
for the newly constructed pairs, and no hardware instruction was executed by
this mathematical check. The four previously resolved FPATAN addition tie rules
were not reopened.

## FPATAN confirmation on the i7

All **28,456** previously Xeon-only tie-discriminator cases have now been
captured once on the i7. The unchanged C program matches every result, C1 and
arithmetic/preload exception field. The complete result/status bytes are
identical to the authenticated Xeon records. All 116 complete three-PC groups
agree as well.

The existing i7 ledger was checked against its 7,543,172 prior cases before
the new reservation. It now includes the additional 28,456 observed rows,
bringing common coverage of the existing 23-pack FPATAN catalog to 7,571,628
tuples. This confirms the already-established rules on the second processor;
the numerical algorithm and its tie rules were unchanged.

- [Local source and prior-input review](../../tmp/verification-expansion/coverage/verification-expansion-ties-i7-v1/LOCAL-REVIEW.json)
- [Scored hardware results](../../tmp/verification-expansion/coverage/verification-expansion-ties-i7-v1/SCORE.json)
- [Cross-processor comparison](../../tmp/verification-expansion/coverage/verification-expansion-ties-i7-v1/CROSS-CPU.json)
- [Permanent reservation ledger](../../tmp/verification-expansion/coverage/verification-expansion-ties-i7-v1/LEDGER-AUDIT.json)

## Shared capture coordination

| Instruction | New cases on Xeon | New cases on i7 | Outcome |
| --- | ---: | ---: | --- |
| F2XM1 | 54,128 | 54,128 | Existing subnormal rounding fails; frozen direct-rounding correction passes |
| FPTAN | 12,024 | 12,024 | Frozen raw-encoding wrapper extension and exception rules pass |
| FYL2X / FYL2XP1 | 0 | 51,636 | Unchanged algorithm matches saved Xeon results |
| FPATAN | 0 | 28,456 | Unchanged algorithm matches saved Xeon tie-discriminator results |

Each F2XM1 processor run exposes 8,658 result differences and 3,177 C1
differences in the existing implementation. The correction rounds the exact
tiny product directly to the spacing of raw80 subnormals and matches every
new result and C1 bit. Both processors returned identical complete output and
status streams. The [F2XM1 report](f2xm1.md) explains the saved regressions,
independent arithmetic, flag checks and
[combined C/reference patch](../../tmp/verification-expansion/f2xm1/f2xm1-subnormal-rounding.patch).

For FPTAN, the original wrapper differs on all 3,240 unsupported-encoding
tuples per processor. The proposed class check rejects those encodings before
normalization; it matches every tangent result, pushed value, C1 and C2 bit.
Canonical-input predictions are unchanged. This extends the earlier rational
reference's stated input contract. The separately frozen exception and
preload rules also pass, all 4,008 complete three-PC groups agree, and both
processors returned identical output/status streams. See the
[FPTAN report](fptan.md) and
[isolated wrapper patch](../../tmp/verification-expansion/fptan/fptan-unsupported-encoding.patch).

The logarithm i7 confirmation completed and passed: 51,636 observations match
the unchanged model, independent rational predictions and saved Xeon results,
including full recorded output/status bytes. The permanent ledger contains
51,636 observed reservations. See the [logarithm report](logarithms.md).

The old raw80 generator was located in the public i7 research tree. Its source
and all-class inverse are preserved in the coverage work directory. The
inverse includes the formerly skipped subnormal, pseudo-denormal, NaN and
unsupported-encoding branches. Fixed zero, infinity and unit branches remain
conservative holds. The implementation agrees with the unchanged observed C
generator on 30,000 cases spanning all seven strata and three seeds; 100,000
additional generated cases check the inverse.

That review adds 24 F2XM1 and 3 FPTAN possible-generator holds to the proposed
streams. Unknown seeds remain an explicit historical-visibility limit. The
generator receipt is [here](../../tmp/verification-expansion/coverage/generator-clearance-review.json).
No held operand receives fresh-test credit.

The primary public-history scans completed with no unread records: 24,408
files on the i7 and 10,510 on the Xeon. These primary receipts support the
clearances. An optional faster cross-check matched the i7 holds; its Xeon run
encountered an incomplete gzip being written by H1725 and was excluded from
clearance. Both results remain in the
[cross-check record](../../tmp/verification-expansion/coverage/history-crosscheck-review.json).

The coordinator preserves whole-job reservations and never repeats a started,
failed or uncertain capture. Workers score authenticated returned results
against predictions frozen before capture. Shared production code, the paper,
publication summaries and release packages are unchanged by this work.

The [final dispatch receipt](../../tmp/verification-expansion/coverage/DISPATCH-FINAL.json)
authenticates the six completion records, hardware streams, scores and ledger
entries. It records new processor observations separately from distinct input
tuples and from the much larger historical trig checkpoint.

## Remaining work

Integrate and review the F2XM1 C/reference correction and FPTAN wrapper
extension before updating the manuscript or release. The tested masked,
initially clear states do not establish arbitrary incoming state or unmasked
trap behavior.

The i7 logarithm confirmation covers a selected 51,636-case set; another
890,172 tuples in the Xeon archive remain without an i7 confirmation here.
FPTAN still has incomplete boundary windows whose held operands cannot be
treated as fresh. Its previously unresolved `a0051-e16` query is now excluded
by two exact checks within the original finite bounds; that mathematical
result supplies no missing hardware observations.

The newly constructed FPATAN `a0064-below` witnesses have not been tested on
hardware. H1725 is still running, and historical unknown-PC and possible-input
holds remain accounting limits even when its cleared selection completes.
