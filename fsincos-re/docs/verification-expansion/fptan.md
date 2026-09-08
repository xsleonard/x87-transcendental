# FPTAN verification expansion

The focused FPTAN challenge passes on both the Core i7-6700 and the Xeon:
12,024 new instruction/control tuples per processor, with zero differences
from the frozen task-local candidate and exception predictions. Their complete
output/status streams are byte-identical. The original entry point mishandles
unsupported raw80 encodings; a general check before normalization fixes all
observed cases while preserving the previously validated canonical algorithm.
The change remains isolated for integration review.

The audit also resolves the outstanding bounded mathematical query, rechecks
saved normal-finite flags and precision behavior, and corrects the window
accounting. No shared production source or publication file was changed.

## Fresh results on both processors

Each of 1,002 admitted operands was tested under four RC modes and three PC
settings. Both jobs were reserved before execution, completed once, and retain
authenticated capture, source, input and permanent-ledger receipts. Neither
job may be recaptured. Both ledgers pass their integrity checks and retain the
earlier T0002/T0003 observations.

| Check | Xeon | Core i7-6700 |
| --- | ---: | ---: |
| Captured tuples | 12,024 | 12,024 |
| Candidate tangent / push / C1 / C2 differences | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Frozen exception / preload differences | 0 / 0 | 0 / 0 |
| Complete three-PC groups | 4,008 | 4,008 |
| Three-PC value/status differences | 0 | 0 |
| Original baseline tangent / push differences | 3,240 / 3,240 | 3,240 / 3,240 |
| Original baseline C1 / C2 differences | 534 / 288 | 534 / 288 |

Every baseline difference belongs to the 270 unsupported-encoding operands.
Those encodings were outside the earlier exact-rational reference contract;
this is an extension of raw-input handling, not a failure found among the
previously validated normal inputs. The new tuples have no overlap with
T0002/T0003. Their union contains 507,456 distinct modern tuples per processor;
this does not include or deduplicate the older H245/H403 campaigns.

The measured exception rules are IE for unsupported encodings and signaling
NaNs; no exception for quiet NaNs; DE+PE+UE for true subnormals; DE+PE for
pseudo-denormals; PE for successful normal finite calls; and no exception on
C2 range returns. Preload flags are clear and stores add no exception flags
throughout this pack. Fixed zero and infinity endpoints were held by history
checks and do not receive new coverage credit here.

- [Final two-processor verification](../../tmp/verification-expansion/fptan/FINAL-VERIFICATION.json)
- [Xeon score](../../tmp/verification-expansion/fptan/verification-expansion-fptan-v1-xeon-score/SCORE.json)
- [i7 score](../../tmp/verification-expansion/fptan/verification-expansion-fptan-v1-i7-score/SCORE.json)

## What was already covered

The H245 sibling archive contains 240,000 dense, 50,038 sweep and 6,466 target
inputs under RN/RD/RU. Its 27 recorded payload hashes verify. The dense and
sweep inputs are all normal finite values. The target contains 6,464 normal
values and both signed zeros; the zeros return unchanged, push positive one,
and set no exception flags under all three recorded rounding modes. H245 also
contains the target's RN PC24/PC53/PC64 comparisons. Its original checksum
manifest covers outputs and CPU information, not the input files; the input
mapping is supported by the retained runner and current input files, and this
audit records their hashes separately.

The three-PC comparison was rechecked for all 6,466 H245 target operands:
zero value/status differences, including both signed zeros.
[PC comparison receipt](../../tmp/verification-expansion/fptan/H245-PC-RECHECK.json).

The later H403 binary64 campaigns already tested signaling and quiet NaNs and
corrected the NaN/pushed-value behavior. They should not be described as wholly
untested. Those campaign summaries do not establish native raw80 subnormal
or unsupported-encoding coverage.

T0002 and T0003 each retain 495,432 normal-finite observations. This audit
authenticates their manifests, input streams and raw hardware hashes, then
checks every captured exception word. On each processor, all 355,636
successful calls set PE alone, all 139,796 C2 returns set no exception flags,
and preload flags are clear throughout. There are zero differences from
that rule. This is retrospective validation of the normal-finite flag rule;
it does not validate extrapolation to special encodings or subnormals.

Evidence: [saved-data audit](../../tmp/verification-expansion/fptan/SAVED-EVIDENCE-AUDIT.json).

## Bounded query resolved without hardware

The original `a0051-e16` query permits periods 20,861 through 41,720 inclusive.
For each of these 20,860 periods, the first checker derives and intersects the
exact integer significand bounds from all six original SMT assertions. Every
intersection is empty. A separate check uses the saved directed rational
enclosures and tests the two integers surrounding each enclosure's midpoint.
Even the closest candidate exceeds the allowed distance by a factor of
approximately 1.191112.

The result is **UNSAT for this original bounded query**. It says nothing about
other periods, other targets or all-input hardware correctness. The original
500 ms UNKNOWN receipt remains unchanged. An attempted additional Z3 check
could not run because the available temporary package lacks its Python API;
neither of the successful exact checks depends on that package.

- [Exact integer-bound enumeration](../../tmp/verification-expansion/fptan/QUERY-RESOLUTION.json)
- [Independent rational check](../../tmp/verification-expansion/fptan/QUERY-INDEPENDENT-CHECK.json)
- [First checker](../../tmp/verification-expansion/fptan/resolve_query.py)
- [Independent checker](../../tmp/verification-expansion/fptan/check_query_independently.py)

## Missing boundary and window members

The 938 original held operands break down exactly as recorded: 54 in the
binary64-significand domain, 418 in the known normal-generator domain and
466 held by public/corpus occurrences. The original clearance records zero
private holds. Among these, 384 distinct operands are needed to fill missing
window members or bracket endpoints.

Two of those operands, `4000:c90fdaa22168c235` and
`c000:c90fdaa22168c235`, occur in the mapped H245 FPTAN inputs. They are not
fresh operands. Their historical RN/RD/RU observations do not automatically
supply RZ, every PC setting or i7 evidence. The other 382 were not found in
the locally mapped H245, H267, H269 and H384 FPTAN input sets. That is a limit
of this reconciliation, not a claim that they were never tested elsewhere.
No held operand has been put into the fresh special-value request.

There is also a wording correction in the earlier coverage summary. The
WINDOWS.json file declares **32 windows, each including both signs**. Nine
of those complete two-sign windows survived; considered separately, 25 of
the 64 one-sign windows survived. Calling these “9 of 32 signed windows”
was imprecise. The 747 incomplete signed bracket instances share operands
and must not be counted as 747 distinct missing inputs.

Evidence: [held members and their exact window/bracket mappings](../../tmp/verification-expansion/fptan/HELD-MEMBERS.json).
The six recovered RN/RD/RU records for the two H245 boundary operands are
[retained separately](../../tmp/verification-expansion/fptan/RECOVERED-LEGACY-ROWS.json).

## Prepared focused challenge and candidate

The frozen proposal contains 1,032 operands, each under all four RC and
three PC settings: 12,384 tuples per processor before remote clearance.

| Input class | Operands |
| --- | ---: |
| True subnormal | 226 |
| Pseudo-denormal | 100 |
| Unsupported encoding | 270 |
| Normal finite, including dispatch joins | 340 |
| Signaling NaN | 48 |
| Quiet NaN | 48 |

Fixed zero/infinity endpoints were proposed but held locally, so this pack
does not claim new coverage of them. The raw-class strata are independent
of candidate arithmetic. Dispatch-join tests are explicitly model-guided.

The original FPTAN entry point passes unsupported encodings to a helper that
normalizes their significands instead of rejecting them. The task-local
correction checks that encoding class before normalization and returns the
indefinite NaN. It is a general class rule, not an operand-specific correction.
It passes every focused hardware observation on both processors.

The published exact-rational sibling reference explicitly rejects unsupported
encodings as outside its input contract. This proposal therefore extends the
raw-input wrapper's behavior; it is not a demonstrated failure within that
reference's previously stated numerical scope.

The correction and unchanged baseline have frozen predictions. Separate
exception hypotheses predicted IE for unsupported encodings/infinities and
signaling NaNs; DE for nonzero exponent-zero operands; PE on successful finite
nonzero calls; and UE for true subnormal results. Every hypothesis exercised
by the final admitted pack passes. The held infinity/zero cases are not
claimed as new confirmation.

The optimized and ASan/UBSan candidate predictions agree on all 12,384 rows
with clean stderr. Baseline/candidate changes affect only the 3,240 unsupported
tuples. The candidate also reproduces all 495,432 saved T0002 predictions
byte for byte. Dependency snapshots match the authenticated original source
pins except for the intended task-local change.

The independent exact-rational sibling reference also agrees with every
canonical operand/RC prediction in the proposal: 3,048 checks, each shared
across the three PC settings. Its contract intentionally excludes the 1,080
unsupported operand/RC combinations, which were counted separately.
[Independent reference parity](../../tmp/verification-expansion/fptan/RATIONAL-PARITY.json).

All four existing validation tests pass, including the synthetic durable
guard's success, duplicate, partial-failure and no-retry checks. Two additional
synthetic tests verify every new exception/preload bit and distinguish a
baseline mismatch from a candidate mismatch. No hardware instructions are
executed by these software checks.

- [Original hardware request](../../tmp/verification-expansion/fptan/focus-v1/HARDWARE-REQUEST.md)
- [Input freeze](../../tmp/verification-expansion/fptan/focus-v1/INPUTS-FROZEN.json)
- [Prediction freeze](../../tmp/verification-expansion/fptan/focus-v1/PREDICTIONS-FROZEN.json)
- [Complete saved regression](../../tmp/verification-expansion/fptan/CANDIDATE-REGRESSION.json)
- [Integration patch with the tested class check](../../tmp/verification-expansion/fptan/fptan-unsupported-encoding.patch)
- [Prepared scorer](../../tmp/verification-expansion/fptan/score_focus.py)

The [task-local C masked-state adapter](../../tmp/verification-expansion/fptan/masked_prediction.c)
also implements the exception rules. It was assembled after capture from the
already frozen rules, so its checks are software replay. Its optimized and
sanitized versions reproduce the 12,024 frozen focused predictions exactly,
and it reproduces all result/push/C1/C2/exception/preload fields of the 495,432
saved T0002 observations. [Adapter verification](../../tmp/verification-expansion/fptan/MASKED-ADAPTER-VERIFICATION.json).

## History clearance and remaining gaps

Both remote public-history scans completed successfully without unread
records. The i7 scan covered 24,408 files and the Xeon scan 10,510 files.
Their requests authenticate the exact union containing this FPTAN proposal.
The coordinator also checked the observed raw80 generator's complete class
handling against its retained C source; the new inverse checker identifies
three more held FPTAN operands.

Combining both remote intersections and the generator check removes 30
distinct operands. The final pack contains **1,002 operands and 12,024 tuples
per processor**, retaining complete four-RC by three-PC groups for every
operand. Every retained prediction is copied unchanged from the original
freeze. A separate review checks the entire subset and every complete group.

- [Final authenticated subset](../../tmp/verification-expansion/fptan/final-v1/SUBSET.json)
- [Subset review](../../tmp/verification-expansion/fptan/final-v1/SUBSET-REVIEW.json)
- [Completed history clearance](../../tmp/verification-expansion/fptan/final-v1/CLEARANCE.json)
- [Final job paths, exact hashes and upload allowlist](../../tmp/verification-expansion/fptan/final-v1/DISPATCH-REQUEST.json)

The coordinator completed both captures using the existing per-processor
FPTAN ledgers. Missing historical results and held operands still receive no
hardware pass credit. The 384 held window/bracket operands are not closed as
complete RC/PC/processor groups: only two were recovered in locally mapped
H245 inputs, and the examined older i7 directories supplied no additional
FPTAN banks. Further reconciliation needs attributable saved observations;
conservative holds cannot simply be recaptured.

There are no unresolved flag hypotheses among the new admitted observations.
Fixed endpoints that were held, arbitrary incoming stack state and unmasked
traps remain outside this new confirmation. Finite checks on these two
Skylake-family processors do not establish all-input or all-generation behavior.

Shared production sources, publication files, release files and research
history are unchanged. Original-work licensing remains undecided.
