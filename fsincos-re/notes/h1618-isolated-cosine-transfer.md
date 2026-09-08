# H1618: isolated fixed cosine implementation and cached transfer

Date: 2026-09-04. Status: **CACHED_OUTPUT_PASS_NOT_CLOSURE**.

The exact H1617 arithmetic candidate passes 150,403 distinct cached
instruction/mode/input outputs, including all 52 already-opened reduction
aliases. The baseline has 75 misses on the same bank; the isolated candidate
has zero. This is implementation and cached-transfer evidence, not fresh
validation or a proof of silicon behavior. No canonical emulator, default,
paper/PDF, hardware capture or private ledger was changed.

## Exact implementation and scope

`experiments/h1618_isolated_cosine_transfer.py` verifies the canonical source
hash, inserts one include and one default-off hook into a source string, and
compiles that string from stdin. It never edits the canonical translation
unit. The header is `experiments/h1618_asymmetric_cosine.h`;
`G_H1618_ASYMMETRIC_COSINE` defaults to zero.

The hook is at the beginning of the active, shared
`fsin_operation_class_polynomial` routine, after the existing external
reduction/phase dispatch. It applies only to cosine branches whose residual
magnitude has top exponent -3 and numerical precision at most 64 bits.
Trailing zero padding in the residual container does not count as additional
numerical precision. Thus the exact preimages can enter without silently
extending H1617's width-equivalence premise. Other branches retain incumbent
behavior and are not counted as validation of the new arithmetic there.

The implementation uses the entire fixed graph, including ordinary
`CHOP67(L+R)` and no terminal selector/payload. Multiplications use the plain
integer multiply/round primitive; Horner and correction additions use the
plain accumulator primitive, bypassing conditional FADD-history patches.
Original reduction, quadrant selection and signed final architectural RC
handling remain in place. Merely changing F while retaining the old terminal
machinery would be the different, already-falsified H1358 composition.

Every build explicitly sets `G_ROUND84=0`. Six builds are compared:

| Build | Cached outputs | Misses |
| --- | ---: | ---: |
| Unmodified baseline, O2 | 150,403 | 75 |
| Inserted hook disabled, O2 | 150,403 | 75 |
| Candidate, O0 | 150,403 | 0 |
| Candidate, O2 | 150,403 | 0 |
| Candidate, O3 | 150,403 | 0 |
| Candidate, O2 + UBSan | 150,403 | 0 |

The disabled hook reproduces every baseline output. All four enabled builds
agree on every output, and all six selftests pass. These are local software
builds, not new x87 observations.

## Direct arithmetic and genuine cached aliases

The direct bank is H1616's authenticated 150,351 observations over 37,823
positive normal direct-FCOS operands. The original raw replay and its
transitive source evidence are hash checked. Every operand hits the C hook;
all 491,699 exposed C stages equal the independent H1616/H1617 graph values.
The 37,823 RN endpoint comparisons are software equivalence checks; unlabeled
RN endpoints are not invented hardware observations. All 27 known direct C1
constraints agree with the independently calculated final rounding indicator.

The remaining 52 observations come directly from the H1570/H1573 capture kits
and their H1571/H1574 scores. The importer verifies OPENED_ONCE, zero repeats,
freeze/checksum provenance, original ordered inputs, raw output streams and
recorded status. They are not projected anchor labels.

- All 52 execute the candidate hook; none passes through fallback.
- All 52 reduced magnitudes equal their exact direct anchors numerically.
- All 676 alias stages equal the independently evaluated anchor stages.
- All 52 stored outputs agree with the already-recorded hardware results.
- The 30 alias baseline misses are fixed, with zero alias regressions.
- There are 28 FCOS and 24 FSIN rows, with 23 negative and 29 positive outputs.
  Actual modes are RN/RD/RU; this alias bank has no independent RZ observation.

The total stage comparison count is 492,375. Sign-dependent final rounding
is checked independently, rather than inferred solely from positive-anchor
agreement. This confirms cached transport of the cosine arithmetic through
both instructions, not correctness of the separate sine polynomial or all
FSIN/FCOS reduction domains.

## C1 and fallback claim boundaries

All 52 recorded alias C1 bits agree with the ordinary **magnitude increment**
indicator, giving 79 matching recorded C1 constraints including the 27 direct
ones. Only 37/52 agree with the different, signed numerical-increase
indicator. The distinction matters for negative outputs; it is not an
output error in the candidate. Both indicators and every actual status word
are retained in the report. This is a comparison against recorded C1, not a
complete status-register implementation or a claim about all flag semantics.

An additional 2,632 software-only guard cases cover signs, neighboring
binades, larger reduced operands and special encodings. All 2,272 rows that
do not enter the hook reproduce baseline outputs. The 360 hook hits are
software tests, not hardware labels. Neither count expands the established
hardware-validation domain.

## Reproduction and immutable artifacts

Paths below are relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1618_asymmetric_cosine.h` | `df5a4b9114c0a754a68274d29c1252257c449af34f68769c6e5f83b85584c6cf` |
| `experiments/h1618_isolated_cosine_transfer.py` | `bb321f62daa8d06168bbd3ee6e872f25afe370fe51f14676c63a574141cb4d19` |
| `tmp/ledger33/current/h1618_isolated_cosine_transfer/report.json` | `b184f29cb7534c6e667f1780b6fdca6a7bb0e52d368e5891700391ff54910112` |
| `experiments/h1618_verify_replay.py` | `639ba25c659db2987a0263ff370b730c1078f1f8bb835b1f714e3cfa9cedd6ab` |
| `tmp/ledger33/current/h1618_replay_verification.json` | `b559479dedf422c5e1b01f050f515f8157019f47437ba8d46c3d64d53d9432ed` |

The main report records all 49 compressed output/selected-trace hashes,
compiler identity, six binary hashes, every miss and alias, and the exact
source transformation. Deterministic candidate diagnostics are explicitly
selected traces, not mislabeled complete raw legacy dumps. The in-memory
translation-unit hash is
`a919000a8d9b47cb34e12a41f87f9516f626b78c141f6152170605feed68cac5`;
the separate included header is pinned above.

A second complete run at `/private/tmp/h1618-root-replay.W4mOEf/audit`
reproduces all 49 observation/trace artifacts byte-for-byte and all result
fields exactly. Five binaries are also byte-identical. The O0 binary differs
in 47 bytes confined to its Mach-O UUID and code-signature blob; every byte
outside those metadata ranges is identical. The verifier checks load-command
bounds and all differences, and preserves both original files. The replay
report therefore has a different binary hash and SHA-256
`1e31259ef1f1714acd28dc30bdc29feb42d745052d5c746213ad878500e148b3`.
Do not describe the two complete report files as byte-identical.

```sh
python3 fsincos-re/experiments/h1618_isolated_cosine_transfer.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
python3 fsincos-re/experiments/h1618_verify_replay.py \
  fsincos-re/tmp/ledger33/current/h1618_isolated_cosine_transfer \
  NEW_OUTPUT_DIRECTORY NEW_VERIFICATION_JSON
```

Both commands refuse existing output targets. Python syntax, normal
build/selftest, whitespace and diff checks pass. Canonical source remains
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`;
all five speculative selector defaults remain zero.

## Next gates

H1619–H1621 subsequently complete the listed broader raw-cache audits in
gate1: see `h1619-raw-stagea-candidate-audit.md` and
`h1620-h1621-heterogeneous-candidate-frontier.md`. They also extend the
incumbent frontier to47/46 positive-direct and78/77 external; the unchanged
fixed candidate passes it. Fresh adversarial validation, remaining domains,
general mechanism and full status are still open. The historical H1618
artifacts and counts below are preserved, not retroactively rewritten.

1. Audit broader retained raw captures and domain coverage with this exact
   candidate and R84 disabled. The old H1376/H1377 large-suite scores used
   R84 and cannot be reused as candidate evidence. H1204 documents sorted,
   unique `ties_CORPUS.txt` operand reconstruction for the eight raw stage-A
   RN/RD/RU streams; authenticate ordering and raw hashes, do not invent RZ.
   H1509/H1510/H1511 also identify existing dense, targeted and sweep captures.
2. Freeze new adversarial disagreements and agreement controls only after the
   broader cache gate. Audit full tuples against repository and private local
   capture history before any one-shot execution. No private ledger was read
   or fresh manifest prepared in H1618. Standing i7/Skylake authorization
   already applies; never repeat a tuple merely for confirmation.
3. Establish general mechanism, remaining domains and required full status
   behavior before promoting anything or updating the paper/PDF.

The unmodified incumbent's direct 45/44 and external 75/74 frontier is
unchanged. The candidate passes that cached frontier but is not installed;
R96 remains empirical/incomplete, and the full bit-exact goal is unachieved.
