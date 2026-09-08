# H1622–H1626: unchanged arithmetic survives a fresh one-shot challenge

2026-09-04. Research evidence, not a confirmed general FSIN/FCOS solution.
The academic paper/PDF and canonical emulator/defaults are unchanged.

## Result and scope

The fixed H1618 arithmetic predicts all **1,668 fresh outputs and all 1,668
C1 observations**, over 417 positive direct FCOS inputs at PC64 in RN, RD,
RU and RZ. The incumbent agrees on 1,665 outputs and fails three. No
candidate parameters, boundaries, selectors or coefficients were changed
after seeing these observations. H1624 is now **OPENED_ONCE**; never rerun
it, including any individual tuple.

This is genuine prospective finite validation, not another cached-label fit.
It is still limited to direct positive cosine inputs in [1/8, 1/4). It does
not prove universal correctness even in this binade, actual multiplier-port
wiring, other residual domains, the sine-polynomial path, or complete status
behavior. Recorded full status words are retained; only C1 is predicted by
this experiment. In particular, ordinary final-prevalue exactness does not
imply that the instruction's precision flag is clear: the new discriminators
have C1=0 and SW=3820.

The exact candidate remains the WHOLE H1617/H1618 split graph:

```text
T_p = normalized magnitude truncation to p bits
R_p = nearest-even rounding to p bits
S = T67(x*x)
F = T67(S*T64(S))
N = R64(C1 + T67(F*R64(C3 + T67(F*C5))))
P = R64(C2 + T67(F*R64(C4 + T67(F*C6))))
C = T67(T67(S*N) + T67(F*P))
Y = architectural_RC64(1+C)
```

Here C1 through C6 are the native polynomial coefficients, not the x87 C1
status bit. The graph has no input classifier or literal output ledger.
Do not substitute only F while retaining incumbent terminal/history patches:
that different program was already falsified by H1358. R84 is OFF throughout
all software comparisons. The isolated hook remains default-off and retains
its existing cosine-branch, residual-binade -3, numerical-precision <=64 guard.

## H1622: software-only adversarial search

Version 2 scans 1,856,968 distinct external significands without new hardware
labels. Its disjoint, first-occurrence-retained origins are:

| Origin | Inputs | Selection |
| --- | ---: | --- |
| Known frontier neighborhoods | 376,878 | Radius 4,096 about the 46 H1621 positive-direct anchors |
| Domain endpoints | 512 | First/last 256 significands of the binade |
| Domain-wide samples | 131,072 | Fixed Python seed `0x1622c06764` |
| H1579 proxy stream | 499,995 | Old label-free software preimages |
| H1586 proxy stream | 848,511 | Old label-free software preimages |

Both older proxy banks remain SOFTWARE_ONLY_NOT_FROZEN. Their historical
captured subsets are not assumed fresh: all actual manifests/history outside
the software-only banks participate in the subsequent audit.

The scanner emits all 48 model disagreements and 431 controls: 384 selected
rounding-boundary controls, 31 periodic domain-wide controls, and 16 domain-edge
controls. The boundary selection uses four samples per cell of square-low3,
fourth-product normalization cut (66/67), and final remainder edge
(0, 1, half-1, half, half+1, denominator-1). These are TEST selection cells,
not gates added to the candidate.

All 479 events receive 1,916 independent mode/output/C1 checks. Their outputs
also agree with separate baseline O2 and candidate O0/O2/O3/UBSan builds.
Complete scanner inputs, event rows, binary, logs and hashes are preserved.

The initial H1622 scanner failed before any event because its diagnostic
normalization assertion used a helper that strips trailing zeroes rather
than plain product bit length. Its header-only event file, original source,
binary, inputs and failed run-status are preserved in the original directory.
It exited scanner8/builder1; this was not a candidate counterexample. Version
2 corrects that metadata computation and uses new filenames/output directory.
Neither version changes the candidate arithmetic. Do not overwrite the
initial failure or present it as a completed search.

## H1623/H1624: local audit, immutable freeze, once-only execution

H1623 searches public history, including compressed text, and all 26 files
in the private local supplemental history. Any occurrence of a proposed
16-hex significand rejects the input, irrespective of exponent, instruction,
mode or host: intentionally stricter than full-tuple freshness. Only declared
software-generation directories and the audit's own files are excluded.
Private paths, contents and hashes are neither published nor copied remotely.

Of 479 proposals, 62 collide with public history; four collide with private
history, all within the public rejection set. The remaining 417 have zero
selected public/private collisions. They comprise two separators, all 384
boundary controls, and all 31 domain-wide controls. All 16 proposed endpoint
controls are rejected; do not claim fresh endpoint coverage.

H1624 takes ALL 417 eligible operands, sorted, in all four modes: 1,668
distinct full tuples, with 96 boundary cells represented. It independently
replays every prediction and the five C builds, rechecks every selected input
against public/private history immediately before freeze, and pins the
positional manifest, per-mode inputs, runner, source provenance, and scorer.
A separate pre-capture check verifies all manifest/input alignments and
terminal quotient/remainder/C1 decisions without importing the producer.
No labels were opened before freeze. Freshness is a conservative statement
about available local history, not a claim that all captures anywhere are known.

The i7 at `142.132.217.24` timed out on read-only SSH; this is not a missing
authorization. The user-authorized Xeon at `45.32.204.118` was available:
GenuineIntel family6/model85/stepping4, reported Skylake/IBRS, microcode0x1.
Its existing capture binary matches
`9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1`.
The local canonical harness hash is
`aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1`.

The kit was copied only to the new directory
`/root/fsincos-h1624-fixed-candidate`; unrelated services, including CoDUO,
were untouched. The runner verifies hashes and CPU identity, atomically
creates `hardware-output`, and invokes the capture binary once for each mode
without timing, warm-up, selftest or repetition. The harness executes one
FCOS per input, clears exceptions, captures SW before popping the result,
and explicitly sets PC64/RC. Four modes are different tuples, not repeats.
Remote start/completion both report `2026-09-04T23:59:59Z`.
The complete outputs/metadata were copied locally once and remain immutable.

## H1625/H1626: scoring, independent verification and frontier

| Input | Mode | Incumbent significand | Frozen candidate = hardware |
| --- | --- | --- | --- |
| `3ffc:b71173fe7ed36c1b` | RD | `fbeb79af4212e2d1` | `fbeb79af4212e2d2` |
| `3ffc:b71173fe7ed36c1b` | RZ | `fbeb79af4212e2d1` | `fbeb79af4212e2d2` |
| `3ffc:e74000022201600a` | RU | `f97ff29643246fc7` | `f97ff29643246fc6` |

All outputs have exponent field3ffe. Each row has actual SW3820 and C1=0,
matching the frozen prediction. These are three independent mode tuples but
only two new residual operands. The two separator operands contribute eight
observations, of which five have shared candidate/incumbent predictions.
All 1,536 boundary-control and 124 domain-wide-control output/C1 observations
pass. There are zero candidate output misses and zero candidate C1 misses.

H1626 imports no candidate, scorer, freezer or arithmetic/parser modules.
Its separate exact Fraction quantizer evaluates the full fixed graph for
each of the 417 inputs, independently authenticates positional raw alignment,
and confirms all 1,668 outputs/C1 bits and scoring totals. It then reconciles
the new misses with the hash-pinned H1621 frontier, checking tuple/operand
deduplication and eight existing baseline/candidate compiler builds.

The current lower-bound incumbent frontier is now **50 failing positive-direct
mode/residual rows over48 residual operands**, or **81 failing external rows
over79 operands** including earlier aliases. The candidate matches every
reconciled observed output. All four baseline builds reproduce their wrong
values; all four candidate builds reproduce the recorded correct values.
This does not count the same hardware observation again or impute an
unobserved alias/mode. Older47/46 and78/77 totals are the H1621 frontier.

Software reruns of H1625 and H1626 reproduce the score TSV and both complete
report JSONs byte-for-byte in `/private/tmp/h1626-root-replay.5VjhE3`.
These are re-reads/recomputations, never repeated hardware instructions.
Python syntax, shell syntax, canonical build/selftests and diff/whitespace
checks pass. Canonical source remains
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`;
R1531/R1382/R1475/QX/Q speculative switches remain zero. R96 in the incumbent
remains empirical/incomplete. The active full solution goal is unachieved.

## Artifact anchors

Paths below are relative to `fsincos-re`; the JSON reports pin their additional
source, input, binary, raw-capture and helper artifacts.

| Artifact | SHA256 |
| --- | --- |
| `tmp/ledger33/current/h1622_fixed_candidate_challenge_bank/run-status.json` | `9c9534a325304eadcf46054fe8976b965a028dcd6c6e8c747bb823298e01c7b4` |
| `tmp/ledger33/current/h1622_fixed_candidate_challenge_bank_v2/bank.json` | `d9f2e5ec5668dc50efb8f50fd230ffe8e76a31c36e608310ab2dd70cdf303fce` |
| `tmp/ledger33/current/h1623_fixed_candidate_freshness/report.json` | `aa0bcd9eb017665859cd401d15115a5dcbf6fe58d4bf1de257cf5478ab9ab46b` |
| `transfer-tests/h1624/FREEZE.json` | `8683d8b34c7b7c7089081cc6fcf3dd90a484c2b61942d679a507ea41c5bc7d4d` |
| `transfer-tests/h1624/manifest.tsv` | `6734db5d4b0cca3df1d42c0d82c93b598ecbb0e7ce331c21b7ebf616f5d90c0d` |
| `transfer-tests/h1624/run_capture.sh` | `87b6adbf58cb345d47e64f732225e8c8a5f01298a375fc9ed6c97af47fb64429` |
| `transfer-tests/h1624/OPENED.json` | `52229edea816e627337ca09ea3945cf583652657cfa0501f1ed4e0711d77e142` |
| `tmp/ledger33/current/h1625_fixed_candidate_score/report.json` | `ef2624cdbcb0fbf277d306ef21becc510e043e19b78a4e29e4eadf4aeccf39bf` |
| `tmp/ledger33/current/h1626_fresh_frontier_verification/report.json` | `e4e0bae20a5a24e067a887c49784ec3d83ebc64031ab9f897e63d94d67075a80` |

New execution/verification sources are
`experiments/h1624_freeze_fixed_candidate.py` (SHA542f1b85...),
`experiments/h1624_run_capture.sh` (SHA87b6adbf...),
`experiments/h1625_score_fixed_candidate.py` (SHA9fa9d0f1...), and
`experiments/h1626_verify_fresh_frontier.py` (SHA27439bf1...). Full hashes are
pinned by the freeze and reports. H1622v2/H1623 source hashes are retained in
their own bank/audit provenance. Do not rewrite earlier failed-run artifacts.

## Next work

Keep this graph fixed. Audit its transfer beyond the current hook guard with
authenticated retained observations and explicit hit/fallback accounting;
include wider residual precision and neighboring binades before claiming
general cosine behavior. The sine-polynomial path, signed/reduced routing,
full architectural status and a general mechanism remain separate obligations.
Further hardware campaigns require fresh audited tuples and pre-frozen
predictions under the already-granted host authorization, not another request
for the same permission. No paper update or canonical promotion follows from
this finite pass alone. Do not return to fitting a terminal boundary selector.
