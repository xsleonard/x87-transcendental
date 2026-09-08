# Publication evidence register

Original publication cutoff: 2026-09-06; trig evidence accounting corrected
2026-09-07. The F2XM1 integration and later i7 confirmations below extend
the evidence through their completed September 7 captures.
This register describes the evidence used by [x87-suite.tex](x87-suite.tex),
including the earlier large completed trig campaigns. The independent
reference replays below were completed for this publication and reuse saved
hardware observations.
The original six-instruction manuscript used saved-data replays. The logarithm
extension adds five fresh guarded hardware captures, each frozen before
execution and retained as an immutable evidence pack.

The paper's main research claim is the FSIN/FCOS/FSINCOS reconstruction.
The [trig findings map](TRIG-FINDINGS.md) records the arithmetic distinctions
and experiments behind that claim. This register keeps the full evidence for
all eight instructions, including routine integration corrections, without
assigning each instruction equal weight in the manuscript.

## Implemented suite

| Instructions | Canonical specification | Scope |
| --- | --- | --- |
| FSIN, FCOS, FSINCOS | [Trig walkthrough](../docs/TRIG-PSEUDOCODE.md) | Standalone and paired schedules; table/tiny paths, exact reduction and final rounding |
| F2XM1, FPTAN | [Executable rational program](../docs/SIBLING-PSEUDOCODE.md) | Complete numerical schedule; sibling wrapper and conversion limits stated explicitly |
| FPATAN | [Executable rational program](../fpatan-re/PSEUDOCODE.md) | Current V7 graph, masked numerical/exception contract |
| FYL2X, FYL2XP1 | [Rational reference](../fyl2x-re/model.py), [full pseudocode](../fyl2x-re/ALGORITHM.md) | Fixed direct/table programs; masked result/C1/exception contract and documented FYL2XP1 domain |

The Itanium transcription is a separate historical reference. Its arithmetic
checks are not evidence of universal Skylake instruction agreement.

## Completed evidence used in the article

Every row below reports no differences in the fields checked. Native runs
count instructions executed; replays count saved rows checked in software.
A row can be checked more than once. Counts of output values and distinct
operands are given separately.

| Evidence | Instruction rows | Controls and checked fields | Stable record |
| --- | --- | --- | --- |
| Native FSIN comparison, Xeon, September 5 review | 3,230,225,472 executions | RN/RD/RU, PC64; result, applicable directed-bound C1, C2 and unchanged operand on range returns; retained completion logs | [Parsed original logs and provenance](evidence/trig-native-fsin-summary.json) |
| H1719 final trig program, replay on i7 | 299,028,167 retained appearances | FSIN/FCOS/FSINCOS; 356,459,555 output lanes; 193,825,064 applicable recorded C1 checks; 193,828,940 C2 checks | [Authenticated report summary](evidence/trig-h1719-summary.json) |
| H1719 final trig program, replay on Xeon | 17,604,112 retained appearances | FSIN/FCOS/FSINCOS; 29,648,279 output lanes; 17,600,228 applicable recorded C1 checks; 17,604,112 C2 checks | [Authenticated report summary](evidence/trig-h1719-summary.json) |
| H1722 later trig challenge | 222,480 executions per CPU | Three instructions, four RC, three PC; outputs, C1/C2 | [Frozen report summary](evidence/trig-h1722-summary.json) |
| F2XM1 H257 independent reference replay | 25,650 | 8,550 per RN/RD/RU; result and C1 | [Replay receipt](evidence/f2xm1-pseudocode-replay.json) |
| Corrected F2XM1 raw80 challenge | 54,128 per CPU | Four RC, selected full PC groups; corrected result/C1 and separately frozen flag rules | [Integration and capture record](evidence/f2xm1-integration.json) |
| FPTAN T0002/T0003 independent reference replay | 495,432 per CPU | All four RC; result, push, C1/C2; raw mapping, hashes, control words and TOP transitions authenticated | [Replay receipt](evidence/fptan-pseudocode-replay.json) |
| FPATAN current catalog independent reference replay | 7,571,628 in 23 packs | 1,892,907 per RC; result, C1, arithmetic exceptions and preload flags; raw mapping, hashes and control words authenticated | [Replay receipt](evidence/fpatan-pseudocode-current.json) |
| D0066/D0067 independent FPATAN challenge | 445,588 per CPU | Four RC; result, C1, exception/preload fields | [Frozen D0070 summary](evidence/fpatan-d0070-summary.json) |
| Original six-instruction witnesses | 724 | Six C instruction paths; 436 additional rational-reference checks | [Raw selected witnesses](evidence/smoke-witnesses.json), [replay](evidence/smoke-replay.json) |

The FPTAN corpus contains 122,900 normal finite raw80 operands, 355,636
successful executions and 139,796 C2 returns per CPU. Each RC has 123,858
observations. PC24 and PC53 have 1,916 each; PC64 has 491,600. These are
input/control tuples; the two CPUs share the same input set. Full exception
words agree between CPUs, but the sibling reference does not predict every
exception latch. Only nine proposed adjacent windows remained complete after
input-history exclusions; broader window completeness is not claimed.

The FPATAN catalog has PC24=117,412, PC53=117,412 and PC64=7,336,804.
The original common two-CPU subset contained 7,543,172 tuples. A later
28,456-case i7 confirmation completed matching results and status words for
all 7,571,628 existing catalog tuples. The latest 445,588-row challenge is
already included in the catalog, so its count must not be added again.
The two host reports are evidence for two recorded contexts, not two disjoint
sets of inputs. The current Markdown replay does not relabel the earlier
2,783,208-row, 14-campaign publication snapshot.

The later logarithm confirmation checks 51,636 selected tuples on the i7,
with complete output/status bytes identical to their Xeon records. Another
890,172 tuples in the Xeon archive remain outside that confirmation. These
two processor extensions are summarized in the
[follow-up receipt](evidence/verification-followup.json).

## F2XM1 subnormal correction

The earlier implementation rounded the tiny-path product to 64 significant
bits, then truncated during subnormal storage. Native raw80 extreme inputs
exposed 8,658 result and 3,177 C1 differences per processor. The direct-raw80
correction was frozen before the two captures and passes every admitted
case, including RZ. The double-rounding alternative still misses 246 results
per processor. All three pre-capture predictions and the old failures remain
part of the discovery record; they are not relabeled as original passes.

The corrected C and rational reference are integrated, with saved-data
regressions and a focused offline regression in the programmer package.
The [integration record](evidence/f2xm1-integration.json) pins the current
sources and the unchanged historical views of the other instructions.
The [current H257 replay](evidence/f2xm1-current-replay.json) is separate from
the original receipt. The full challenge records remain in the research
archive. Its 111 incomplete proposed neighborhoods and held endpoints do not
receive pass credit. The reference reports result/C1; flag hypotheses are
checked separately and do not turn its numerical API into a state emulator.

The follow-up [rounding-to-storage review](../docs/verification-expansion/rounding-boundary-audit.md)
traces every shared conversion caller. It checks exact tiny transfers, bounds
the remaining trig outputs away from raw80 storage limits, and exercises the
separate FPATAN/logarithm packers at destination-format boundaries. It found
no additional numerical defect. Its tests are software checks, not new
hardware observations, and its range arguments apply to the specified
algorithms under their stated entry contracts.

## Trig validation at scale

**222,480 is the size of H1722 alone, not the total trig validation.** The
completed native FSIN run and final-program archive replays belong in the
main evidence table. Their earlier omission substantially understated the
validation history.

The two native FSIN logs cover 1,076,741,824 binary64-derived inputs and
3,230,225,472 executions under RN/RD/RU at PC64. Their counter ranges are
`start=0, count=3000000` and `start=3000000, count=1073741824`, both with seed
`0x1716`. All five mismatch/failure counters are zero. The input-class totals
and three-mode arithmetic reconcile exactly. The comparator checks C2 and
unchanged operands on range returns; on non-C2 returns it checks result bits
and C1 inferred from directed model bounds. It does not record a separate
total of applicable C1 checks. The selected traversal includes special values
and range returns; it does not enumerate all binary64 or raw80 encodings.

The saved record consists of native completion logs. It does not contain
a separate hardware result for each of the billions of executions. The September 5 review identifies the tested model,
and its recorded main-source hash identifies the historical source. The
F2XM1 integration changes only that instruction: restoring its previous
helper/dispatch view reproduces the exact historical whole-file hash.
H1717 subsequently
changed only the paired schedule, leaving standalone FSIN unchanged. The
logs do not independently pin the comparator executable and all its build
dependencies. This provenance limit is retained in the summary and article;
the completed run is not relabeled as a new independent-reference replay.

H1719 records the final trig program's large replay tests and the exact source
files used. We checked every supporting report hash, recalculated the totals
from individual jobs and confirmed that the reports contain no mismatches.
All unchanged dependency hashes match this release; the F2XM1 integration
record proves that the rest of the main C file is byte-identical to the
recorded source. The original
replays ran on both x86 hosts; this publication check inspected their records
without repeating the numerical work or executing hardware.

| H1719 component | Instruction-row appearances | Output lanes | Applicable recorded C1 |
| --- | ---: | ---: | ---: |
| i7 mapped h491 banks and sc_recheck | 281,799,519 | 327,186,732 | 176,600,292 |
| i7 additional h633 banks | 1,572,864 | 1,572,864 | 1,572,864 |
| Xeon available historical h347/sweep/dense banks | 1,948,328 | 1,948,320 | 1,948,320 |
| Shared retained suite, replayed on each host | 15,655,784 | 27,699,959 | 15,651,908 |

The shared suite contains all 15 retained paired banks, 72 standalone jobs,
357,360 normalized earlier challenge/review rows and 134 regression fixtures.
It is included in each host's total. Banks overlap, and PC-specific numerical
projections can repeat an operand/mode. The computer running a replay is not necessarily the CPU that produced the
saved results. In particular, the i7 archive is not evidence of Xeon outputs. The inventory records 31 unavailable i7 mode files and
credits no missing mode or unrecorded/undefined flag as a passing check.

The H1717 promotion's 3,379,017 standalone outputs, 23,838,534 retained paired
lanes and 45,517,233-row i7 comb7/9/10 paired census remain valid regression
evidence. Those banks overlap H1719 and are not added again. Earlier
challenges replayed after a correction are regression evidence for the final
program; the original failed predictions remain discovery history.

H1722 subsequently tests 6,180 operands across three instructions, four RC
and three PC settings. Each CPU therefore has 222,480 instruction executions
and 296,640 output-lane checks. Its summary preserves the original report
hash, raw stream hashes, CPU context and full instruction/RC/PC matrix.
This prospective challenge supplements the larger completed campaigns.

## Logarithm evidence

The [authenticated archive replay](evidence/logarithm-replay.json) checks both
the final C implementation and independent rational reference against all
941,808 observations in L0001-L0005. It checks result bits, C1, arithmetic
exception flags, preload flags, raw mapping, hashes, control words and stack
transitions. The final 420,212-case L0005 bank was frozen with the identical
C source before hardware execution; the other packs are regression evidence.

L0001 exposed four published-table transcription differences and the FYL2XP1
table transition. L0002 then passed 145,116 prospective cases. L0003 and L0004
separated underflow timing and forced-inexact behavior; all their historical
misses and frozen predictions are preserved. The final source resolves them
with a single rule based on 64-bit rounding with unbounded exponent.
The [acceptance record](../fyl2x-re/ACCEPTANCE.md) gives the per-pack counts,
source pins, independently selected strata and scope limits.

The [public source audit](evidence/logarithm-public-source-audit.json) checks
77 projected ROM payloads and reproduces the four corrections without using
hardware labels. [Operator ablations](evidence/logarithm-operator-ablations.json)
record differences from the hardware-validated default for seven alternative
arithmetic policies. The normal package checks add 854 saved logarithm
witnesses through the C CLI, API and Python reference; they are not new captures.

## Historical evidence kept separate

Earlier H403 notes report selected 2^32-input binary64-derived traversals for
F2XM1 and FPTAN. Their final raw logs were not recovered and reconciled for
this portable publication package. Those totals are **not included in the article's results table**. The saved-data
replays above check the current pseudocode. A selected 2^32
traversal is neither all binary64 encodings nor all raw80 encodings.

H1725 was in progress at the cutoff and contributes no completed total.
Historical AMD percentages describe the older model tested at that time;
they are not measurements of the current release.

## Attribution and interpretation

Ken Shirriff's published Pentium ROM decode supplies literal data and
algorithm explanations. The exact data file records ROM rows, original
words and seven explicit corrections, including four logarithm-table words
independently derived from mathematical splits and corroborated by Goldmont. Inferred arithmetic precision, order
and observed Skylake behavior are separate contributions. Historical Intel
Itanium source and public Goldmont projections have separately attributed
roles; none establishes identical physical microcode across generations.
See [SOURCES.md](SOURCES.md) and the article's bibliography.

F2XM1's observed unchanged-input policy outside [-1,1] is empirical. Its
corrected subnormal rounding passes the targeted two-processor challenge;
that finite test does not establish all raw80 inputs or arbitrary state.
FPTAN's broad publication replay contains normal finite
inputs, including range returns. Parser support alone does not establish
an equally broad hardware claim for every operand class or incoming state.

## Reproduction

The [suite builder](build_suite.py) checks receipt/source hashes and generates
article counts, tables, complete listings and literal inventories.
[audit_trig_history.py](audit_trig_history.py) regenerates the H1719 and native
FSIN summaries from explicitly named local research records. It checks report
integrity and accounting; it does not rerun the native campaigns. The small
summaries are bundled, while their full research archives are not.
The generated `generated-suite/suite-manifest.json` records publication source and PDF hashes.
The release has a separate file-by-file manifest, preserving original C
sources and comments while supplying a small build interface.

`check_witnesses.py` runs from the bundled data alone after both C models
have been built. The larger `verify_siblings.py` and
`verify_fpatan_catalog.py` commands require the named saved research packs.
Their receipts record the exact verifier and source hashes. They do not
capture hardware, and reject mismatched input mapping or changed artifacts.
