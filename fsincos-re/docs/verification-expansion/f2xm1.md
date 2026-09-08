# F2XM1 verification expansion

The subnormal checks exposed a real rounding bug. On both the Core i7-6700
and the Xeon, the existing program misses 8,658 results and its original C1
prediction misses 3,177 bits in the new challenge. Rounding the tiny-path
product once at raw80 spacing fixes every observed difference. That C
correction and its predictions were frozen before either processor ran.

Each processor completed 54,128 observations once, with permanent ledger
reservations. The complete output/status streams are byte-identical.

| Check | Xeon | Core i7-6700 |
| --- | ---: | ---: |
| Observations | 54,128 | 54,128 |
| Original result differences | 8,658 | 8,658 |
| Original C1 prediction differences | 3,177 | 3,177 |
| Corrected result / C1 differences | 0 / 0 | 0 / 0 |
| Double-rounding alternative result / C1 differences | 246 / 6,323 | 246 / 6,323 |
| Correct flag-predicate / preload differences | 0 / 0 | 0 / 0 |
| Complete three-PC groups | 15,276 | 15,276 |
| Three-PC output/status differences | 0 | 0 |

There are 54,128 distinct input/control tuples tested on two processors,
not 108,256 distinct tuples. Each RC has 13,532 observations. PC24 and PC53
have 15,276 each; PC64 has 23,576. A three-PC group is one operand/RC pair
tested at all three precision settings.

The reviewed integration patch is
[f2xm1-subnormal-rounding.patch](../../tmp/verification-expansion/f2xm1/f2xm1-subnormal-rounding.patch).
It changes the F2XM1 C path and its rational reference. Shared production
code, the paper and release files remain unchanged for the parent session
to integrate. Evidence: [Xeon score](../../tmp/verification-expansion/f2xm1/f0001/SCORE.json),
[i7 score](../../tmp/verification-expansion/f2xm1/f0002/SCORE.json).

## What the existing evidence already covers

The H245 and H257 archives contain far more useful F2XM1 coverage than the
25,650-row publication replay alone suggests. Their manifests were checked
again, and the pinned current C program matches all **915,162 saved output
comparisons**. The independent rational implementation also matches the
25,650 H257 results and C1 bits.

| Saved input set | Operands | Nonzero low 11 significand bits | Normalized exponent range |
| --- | ---: | ---: | --- |
| H245 dense | 240,000 | 239,879 | -3 through -1 |
| H245 sweep | 50,038 | 50,004 | -16382 through 63 |
| H245 target | 6,466 | 6,206 | -32 through 0 |
| H257 | 8,550 | 8,287 | -73 through 0 |

These input sets already test full-width raw80 significands. H245 also
contains 6,466 complete RN comparisons across PC24, PC53 and PC64; their full
saved output/status lines agree. The target and H257 sets include both signed
zeros. None of these four input sets contains a native raw80 subnormal or
pseudo-denormal. The sweep includes the smallest normal input, whose result
is subnormal, under both signs and RN/RD/RU.

The exception words are now inventoried as well. These files show PE for
every finite nonzero input, including the exact endpoints and sampled
out-of-domain inputs; signed zero leaves the exception bits clear. The two
smallest-normal sweep inputs set UE and PE. This is an inventory of saved
processor behavior, not a claim that the existing numerical API predicts
those flags.

The H403 summaries separately record completed 2^32 binary64-derived
traversals, with zero final discrepancies after the signaling-NaN repair.
Those large trials must remain part of the evidence account. Their generator
does not reach native raw80 subnormals, and their final logs/code association
has not been newly authenticated by this local replay. No historical trial
was repeated.

The H245/H257 processor record is the Xeon context. This does not erase the
established Core i7-6700 validation for the other instructions. The two
machines' F2XM1 coverage must be attributed separately.

Evidence: [saved replay and hashes](../../tmp/verification-expansion/f2xm1/SAVED-AUDIT.json),
[historical billion-input trials](../../notes/sibling-exhaustive-validation.md).

## The subnormal storage question

The current tiny path forms the exact product of the input and the saved
67-bit log(2) constant. It rounds the product to 64 significant bits, then
`sf_to_x87` truncates additional bits if the result is subnormal. Rounding
to 64 significant bits and then truncating can differ from rounding once
at the spacing of representable raw80 subnormals.

For example, raw input `0000:000000000000010e` under RU produces
`0000:00000000000000bc` on both processors. The original code returns
`0000:00000000000000bb`. The corrected code matches the processors under
all three tested PC settings. This observation is retained in both captures;
it was not recaptured after finding the difference.

Three rules were frozen before new hardware results:

- The current program: round to 64 significant bits, then truncate on store.
- Round the exact tiny-path product directly to raw80, including subnormals.
- Round to 64 significant bits, then round again at raw80 spacing.

Before final history exclusions, the prepared request had 8,832 result
differences between the first two rules and 270 between direct rounding
and double rounding. The final captured subset retains 8,658 and 246,
respectively, and hardware selects direct raw80 rounding on all of them.
Each rule's C1 prediction is retained separately; the final-rounding C1 of
the double-rounded alternative is not silently equated with its first
rounding increment.

An exact arithmetic check also removes one apparent missing case. For
exponent-field 0 or 1 inputs, the product in subnormal output units is
`m * 0x58b90bfbe8e7bcd5e / 2^67`, with `0 < m < 2^64`. The constant has
exactly one trailing zero bit. An exact integer result would require `m`
to be divisible by `2^66`; an exact halfway result would require
`m = 2^65 mod 2^66`. Both are impossible in that range. Double rounding can
still create a halfway intermediate, which the request explicitly tests.
This proves a property of the stated arithmetic, not the silicon's choice
of arithmetic. [Exact check](../../tmp/verification-expansion/f2xm1/TINY-ROUNDING-EXCLUSION.json).

An isolated C implementation of direct raw80 rounding matches the exact
rational alternative on all 54,968 prepared rows. Its optimized and
ASan/UBSan outputs agree. A separate exact-integer check covers all native
subnormal significands from 0 through 4,096 with both signs and all four RC
settings, plus deterministic larger subnormal, pseudo-denormal and minimum
normal strata: 47,504 checks pass. It also retains zero differences on the
915,162 saved output comparisons. The proposed C correction was frozen
before either capture and needed no change after seeing their results.
The matching rational-reference edit was then checked against all 108,256
saved observations. The patch applies cleanly with `git apply --check`,
but has not been applied to shared files.

The changed C branch is reachable only at normalized input exponents at or
below -16382. Nonzero binary64-derived inputs have normalized exponents at
least -1074, and special inputs return before that branch. The correction
therefore leaves the entire binary64-derived input domain unchanged. This
explains why the old billion-input runs passed while the raw80 tests found
this bug.

Evidence: [frozen predictions](../../tmp/verification-expansion/f2xm1/request-v1/PREDICTIONS-FROZEN.json),
[isolated C check](../../tmp/verification-expansion/f2xm1/DIRECT-HYPOTHESIS-PREFLIGHT.json),
[integer check](../../tmp/verification-expansion/f2xm1/DIRECT-TINY-INTEGER-CHECK.json),
[saved regression](../../tmp/verification-expansion/f2xm1/DIRECT-SAVED-REPLAY.txt),
[C replay against the new capture](../../tmp/verification-expansion/f2xm1/CORRECTED-C-CAPTURE-REPLAY.json),
[corrected rational replay](../../tmp/verification-expansion/f2xm1/CORRECTED-RATIONAL-REPLAY.json).

## Prepared coverage and history exclusions

The independent generator produced 7,266 operands. It uses raw-bit strata,
dyadic joins, both signs, and inverse mathematical output boundaries. It
does not call the candidate, import its constants, or read hardware labels.
The inverse constructions use rational bounds on log(2) and log(1+y).
A separate MPFR program confirms all 192 bracket floors at both 384 and
768 bits using directed bounds on `log1p(y)/log(2)`.

After local saved-data, public/corpus and private-history checks, 5,964
operands remain for remote review: 1,974 native subnormals, 48
pseudo-denormals and 3,942 normals. They produce 54,968 frozen input/control
rows. Main boundary and extreme-input families use every RC/PC combination;
the broader exponent/significand controls use all RC settings at PC64.
RZ is explicitly included. The proposal includes signed zero, but existing
records and conservative history holds are respected instead of forcing
those common inputs into a new capture.

The coordinator's all-class reconstruction of the historical raw80 generator
found 24 additional conservative operand holds. Both remote public-history
checks completed with no unread files. Their further exclusions leave
5,894 operands: 1,944 native subnormals, 48 pseudo-denormals and 3,902
normals. The final stream has 54,128 rows, 840 fewer than the locally
prepared stream. A held operand does not receive new coverage credit and
is not declared never tested. Of 244 proposed neighborhood/bracket groups,
133 remain complete after all exclusions.

The public capture records the control word, pre-instruction status,
post-instruction status, result and post-store status. It executes one F2XM1
per admitted line. The guard reserves the complete job before execution and
preserves started or uncertain reservations. Synthetic tests check complete
execution, duplicate rejection, partial failure and rejection of a second
job attempting a failed tuple. New captures are dispatched only by the
coverage session.

Separate flag hypotheses were also frozen before capture. Six prepared rows
separate tininess before final raw80 rounding from classification of the
stored raw80 result. An exact lattice calculation shows that testing before
or after the unbounded 64-bit rounding gives the same answer for every
legal input to this tiny-product arithmetic: the closest product below the
minimum normal is already more than half a subnormal ULP below it, so no
64-bit rounding mode can carry it to the boundary. The observations therefore
cannot distinguish those two earlier decision points.
[Equivalence check](../../tmp/verification-expansion/f2xm1/UNDERFLOW-PREDICATE-EQUIVALENCE.json).
These prospective flag hypotheses were not retroactively attributed to the
old numerical API. Both processors match the earlier tininess predicates
on every row. Classifying the stored result instead misses six observations:
rounding produces the minimum normal value while UE remains set. Native
subnormal operands set DE, UE and PE; pseudo-denormals set DE and PE, with
UE when the product is tiny. Preload flags remain clear. The native capture
source was compiled and inspected before each guarded run; no job was retried.

Evidence: [input construction](../../tmp/verification-expansion/f2xm1/proposal-v1/INPUT-POOL-FROZEN.json),
[independent MPFR audit](../../tmp/verification-expansion/f2xm1/INDEPENDENT-CONSTRUCTION-AUDIT.json),
[local clearance](../../tmp/verification-expansion/f2xm1/clearance-v1/LOCAL-CLEARANCE.json),
[generator review](../../tmp/verification-expansion/coverage/generator-clearance-review.json),
[synthetic guard tests](../../tmp/verification-expansion/f2xm1/SYNTHETIC-PREFLIGHT.json),
[final request](../../tmp/verification-expansion/f2xm1/FINAL-REQUEST.json),
[history provenance](../../tmp/verification-expansion/f2xm1/REQUEST-PROVENANCE-REVIEW-v2.json).

## Remaining scope and integration

The patch must be integrated into the shared program and reference before
removing the paper's F2XM1 subnormal limitation. Its C arithmetic was written
and frozen before the new observations; the general correction has both
prospective two-processor evidence and saved regression checks. This session
has not changed the publication or release package.

The new captures establish RZ and raw80 extreme-input behavior on the tested
families, including relevant full PC groups. They do not make every proposed
window complete: historical holds still leave 111 groups incomplete. Common
excluded operands, including the smallest subnormal encodings and signed
zeros, must not be credited to this capture. Signed-zero RN/RD/RU evidence
comes from the older Xeon records; a new RZ zero observation is not claimed.

This challenge uses finite valid raw80 values and pseudo-denormals with
masked exceptions and a clear, one-deep starting stack. Unsupported raw80
encodings remain outside the rational reference's input contract; the C
entry point's normalization of those encodings needs a separate interface
decision if it is exposed as a complete architectural emulator. NaN/infinity
coverage, arbitrary initial state, unmasked traps and additional processor
generations are not extended by these captures. The H403 final-log/code
association is still a provenance task. No history hold or software-only
check is counted as a processor observation.

Original-work licensing remains undecided.
