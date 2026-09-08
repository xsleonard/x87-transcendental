# H1612: RC-dependent policies do not rescue the shared-precision family

Date: 2026-09-04. No general solution or selector. No hardware capture,
emulator/default change, private-ledger action or manuscript/PDF update.

## Question and exact scope

H1610 tested fixed multiplier precision M, Horner-add precision A and
correction precision A or 67, with M,A in `{24,53,64,...,128}`. Its rounding
policy at each operation was common across inputs and architectural RC.
There were 8,911 width vectors per payload, 17,822 width/payload cases.

H1612 first permits **independent policy vectors for each RC**, with the width
vector held fixed. Each of thirteen operations can choose CHOP, nearest-even,
nearest-away, AWAY or JAM based on RC alone. The graph, coefficients, final
RC64 and absent/frozen original numeric payload are unchanged. No mode or C1
label is inferred from the emulator; only the 64 actual output observations
and 27 actual C1 values from H1600 are used.

The first one/two operands in H1610's rejection prefix were both RD. Its
17,546 cases rejected at that point are therefore already impossible under
RC-only policy selection. H1612 revalidates their saved diagrams, widths,
operand identities, mode purity and false output roots. It then explicitly
evaluates every actual mode of all 36 operands for the remaining 276 cases.

## Results

**All 276 remaining cases fail.** There is no complete target-surviving
RC-to-policy map under either payload treatment, so no controls are scored.

| Mode | Cases rejected on outputs alone | Cases rejected with actual C1 |
| --- | ---: | ---: |
| RN | 276 / 276 | 276 / 276 |
| RD | 276 / 276 | 276 / 276 |
| RU | 276 / 276 | 276 / 276 |
| RZ | 268 / 276 | 268 / 276 |

The eight RZ-feasible cases all have M=65 and (A,correction) equal to
(64,64), (65,65), (65,67), or (66,66), under either payload. Their feasible
RZ witnesses are saved, but they fail RN, RD and RU and are not candidates.
The source bank contains 17 RN, 20 RD, 17 RU and 10 RZ operands; C1 counts
are respectively 8, 10, 9 and 0. Missing C1 remains unknown, not zero.

Every mode/case rejection has a saved contradiction core and direct deletion
witnesses. Some are single-operand impossibilities, others pairs or larger
deletion-minimal sets. Minimum cardinality is claimed only where proved.
For example, the most frequent new RD pair is `c6db323ae10c933c` with
`e0bbe34937eeab38` (both exponent `3ffc`), used in 244 cases. This does not
replace the complete per-case certificate with one universal pair.

## Stronger consequence: RC-dependent widths also fail within this family

The inherited 17,546 exclusions are all RD, and RD independently rejects
all 276 newly tested cases. Thus **every allowed width vector has no common
RD policy vector**, under either payload treatment.

Even if M, A and correction precision could themselves depend on RC, the RD
branch would have to select one of those width vectors. None works. Therefore
arbitrary RC-to-width-and-policy selection is excluded **within this exact
bounded class-shared width family**. This is a logical consequence of the
all-width RD exclusion, not an extrapolation from other modes or a claim
about arbitrary per-cut precisions. The report records the derived proof and
its scope explicitly.

## Verification

- All 17,822 parent certificate identities are accounted for, with no missing
  or duplicate cases; all inherited false roots are re-conjoined.
- The remaining 276 cases compile 17,664 actual operand/mode instances.
- Rejoining modes under a common vector agrees with full joint compilation
  in 19,872 complete canonical-function comparisons.
- On the saved H1610 prefixes, another 3,224 canonical-function comparisons
  reproduce the pinned functions exactly. These are not counts-only checks.
- 175,030 direct full-policy replays verify actual outputs and C1 acceptance.
- Inherited tests cover 4,464 signed-neighbor rounding cases, 204 forward/
  inverse C1 cases, two interval endpoints, 2,430 diagram truth-table cases
  and 6,132 nearest-away reference cases.

The numerical compiler and inverse helpers are shared with H1610/H1609;
H1612 is not advertised as an independently implemented arithmetic solver.
H1611 remains the separate arithmetic certificate for the original-width
six-choice family, not for these changed-width cases.

## Artifacts and reproduction

Authoritative output is `tmp/ledger33/current/h1612_rc_shared_operator_precision_v3/`.
The initial empty setup directory and earlier completed v2 evidence remain
preserved. v3 explicitly records the derived RC-dependent-width conclusion.

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1612_rc_shared_operator_precision.py` | `4fff0942a1b8334632df5670d4d3d25d9d03ef02fa17294ae06cf6b11b6ee8ec` |
| `report.json` in the authoritative directory | `73690a8fff6351fc1dff308001b6032e5e7fe24d95d8187387a7ad9a5f836ff7` |
| `rc_precision_diagrams.jsonl.gz` there | `2022f8abb0ed90199a4117e3e11b71d0cbbc5680600c3cbd202de1e29e5c8aae` |

```sh
python3 fsincos-re/experiments/h1612_rc_shared_operator_precision.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing output directories are refused. A separate full replay reproduces
the report and complete compressed diagram stream byte-for-byte. Syntax,
whitespace and normal build/selftest checks accompany integration.

## What remains a genuinely different hypothesis

These exclusions do not cover arbitrary per-cut precision assignments,
omitted widths, changed-width/bypass combinations, operand-dependent history,
nonstandard arithmetic, different graphs or regenerated payload. In particular,
the recent exact-bypass family sends one selected numerical value to **all**
consumers. It does not allow different consumers of square/fourth to choose
between separate raw and materialized versions. A consumer-specific
power-value routing test is therefore distinct, but must be labeled a
hypothesis and validated on controls before being treated as a candidate.
No new physical routing contract was recovered in this turn.

R96 remains empirical/incomplete; source/defaults and direct 45/44 / external
75/74 failure frontier are unchanged. The full bit-exact objective is open.
