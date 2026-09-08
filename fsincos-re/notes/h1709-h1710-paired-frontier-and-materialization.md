# H1709–H1710: paired frontier and fixed product materialization

Follow-up H1712: fresh paired validation now passes 13,800 one-shot tuples,
27,456 lane outputs and 13,728 C1 checks. The outstanding work is promotion
and confirmed paper integration, not the fresh campaign described below as
H1710's next step. Read `h1711-h1712-paired-fresh-validation.md`.

2026-09-05. The preceding H1708 turn was concrete progress: standalone
promotion and paper delivery completed. This continuation makes independent
progress on required paired FSINCOS. No hardware, private material, new
capture labels, main-source/default change or paper/PDF edit occurred.
The full goal remains active; neither paired alternative is promoted.

## Result

The current paired implementation has **three retained sine-lane misses over
two operands** in the checked inventory. There are no cosine-lane misses.
One fixed arithmetic change repairs all three: materialize the last sine
Horner product at CHOP67 before adding the first sine coefficient at RN64.
This is the same kind of materialization already used by the paired cosine
arm, not an operand classifier or a correction of the final output.

The minimal last-edge alternative and an all-Horner-products-materialized
alternative both pass the entire retained census with zero regressions:

| Metric | Incumbent paired | Last-edge alternative | All-edge alternative |
| --- | ---: | ---: | ---: |
| Instruction/RC appearances | 11,919,273 | 11,919,273 | 11,919,273 |
| Finite/special lane results | 23,838,534 | 23,838,534 | 23,838,534 |
| C2 responses | 6 | 6 | 6 |
| Sine-lane misses | 3 | 0 | 0 |
| Cosine-lane misses | 0 | 0 | 0 |
| Cosine-bound C1 checks | 11,919,267 | 11,919,267 | 11,919,267 |
| Cosine-bound C1 misses | 0 | 0 | 0 |

These are overlapping retained appearances, not unique hardware tuples or
fresh observations. Actual modes are RN/RD/RU; this census supplies no RZ
hardware evidence. The C1 column tests the explicit rule comparing the
external cosine result with its toward-zero bound. It does not claim a full
status emulator. Special C1 is not predicted by the new numerical interface.

Both alternatives have identical output-stream hashes on every scored bank
and mode. This is finite numerical agreement, not proof that the schedules
are equivalent over all external inputs. No new arbitrary state/history
gate, coefficient fit, or physical multiplier-port assertion is introduced.

## Exact retained frontier

| Operand | Mode | Hardware sine | Incumbent sine |
| --- | --- | --- | --- |
| 3ffc:c060000000d78237 | RD | 3ffc:bf3ed1ea9755cbd7 | 3ffc:bf3ed1ea9755cbd8 |
| 3ffc:c060000000d78237 | RU | 3ffc:bf3ed1ea9755cbd8 | 3ffc:bf3ed1ea9755cbd9 |
| 3ffc:b400000004ea29f8 | RD | 3ffc:b3130fc9731657e8 | 3ffc:b3130fc9731657e9 |

The first operand is comb4 index398986; the second is comb7 index683781.
RN and every cosine result remain correct. RZ changes predicted by software
are not retroactively credited as observed or treated as fresh capture tuples.

These misses are separate from the 81 formerly failing standalone rows, all
of which were resolved before this turn. The old claim that a paired cosine
coin is statistically unmodelable came from projecting observations into
the wrong standalone frame. H624 already showed ordinary paired-frame
agreement on its subset. H1709 now checks both lanes over the larger retained
inventory: the actual surviving residual here is in sine, not that old coin.

## Fixed paired program

For positive residual magnitude r, let S=CHOP67(r*r). Starting from the sixth
native sine/cosine coefficient, evaluate four steps down through coefficient2
using RN64(v*S+Ki). The minimal candidate then uses, on **both** arms:

```text
v = RN64(CHOP67(v*S) + K1)
sine_tail   = CHOP67(RN64(p*S) * r)
cosine_tail = CHOP67(q*S)
sine prevalue   = r + sine_tail
cosine prevalue = 1 + cosine_tail
```

Final signed RC64 uses the exact reduction quadrant and residual sign.
The all-edge alternative materializes CHOP67(v*S) before every coefficient
addition, not only K1. Both use the established shared ROM, exact M66 reducer,
table program and tiny predecessor rule. Cross-instruction table/tiny transfer
is supported by retained observations but still needs the targeted paired
prospective/domain checks described below.

The C implementation computes the paired polynomial once and maps the two
internal prevalues to the external sine/cosine outputs; it does **not** call
the promoted standalone polynomial twice. C1 selects the last external cosine
lane, which may be the internal sine branch after odd-quadrant reduction.
Special/range handling precedes normal arithmetic. No main-source hooks or
experimental defaults are changed: the analysis builder inserts an explicitly
enabled, isolated entry into an in-memory source copy.

## Causal and independent checks

`h1710_localize_paired_misses.py` tests64 fixed schedules per operand: the
five sine Horner edges each fused or CHOP67-materialized, crossed with direct
RN64 versus double-rounded terminal p*S. All three actual RC observations
per operand are read from the pinned raw streams, including controls.
Exactly32 schedules per operand survive, all with the last Horner product
materialized. Thus that cut is necessary **within this bounded family**;
earlier-edge choices and the extra terminal double round remain unseparated
by the two operands. This is not a universal uniqueness theorem.

An independent signed-dyadic polynomial and rational reducer/table verifier
checks baseline, minimal and all-edge C builds at O0/O2/O3/UBSan. All1,028
software operands, four modes and12 builds pass:49,344 instruction-row checks,
96,960 lane outputs and94,272 per-lane C1 indicators. The bank includes both
signs, the full polynomial exponent range in its sampled inputs, reduction
exponents through62, near-M66 multiples, boundary encodings, tiny/denormal,
invalid/NaN/infinity and C2 cases. It is software evidence, not hardware
coverage of every listed class. Five software contrasts are exactly the
three retained fixes plus the two unobserved RZ predictions.

## Corpus provenance

H1709 checks15 inventories: the structured sweep, dense bank, h285/h292/h301/
h307/h314/h320/h347/h349, comb4, h589, h590f, h590k and comb7.
Existing SHA256SUMS are checked for per-instruction and trig captures. The
sweep/dense use retained shared positional inputs, as documented in H1627.
StageA has no original checksum manifest here: its files are snapshot-pinned,
not falsely upgraded to original-manifest provenance. Comb7 input order is
the sorted unique significands from ties_comb7.txt with exponent3ffc, exactly
as documented by H624; all1,947,982 raw positions are checked in each mode.
Comb4 has its explicit535,045-row input stream. No old capture runner runs.

## Artifacts and anchors

All report paths below are beneath `tmp/ledger33/current/`:

- `h1709_paired_retained_census/report.json`:
  `700e0656409c0f420371a96ea86f6def4485e96a382de763af5094e257cbdd60`.
  Its `frontier.json` retains every miss, not just examples.
- `h1710_last_retained_census/report.json`:
  `4e6300a1b0600c63786e9890d53e444eef8578c49fb846d43b02f23d97f60549`.
- `h1710_all_retained_census/report.json`:
  `810d3ed89e828d3c4178230e7c5f3307f75de43abf300491eabcfa7d0e78c87d`.
- `h1710_independent_paired_program/report.json`:
  `9800d366202639dac4f031fc7e8058db402f3dfe53ff1f1cadb2772bee4723a2`.
- `h1710_paired_program/localization.json`: full64-schedule integer audit.
- `h1710_paired_program/`: baseline/minimal/all O2 binaries, plus exact
  copies of the initial baseline header and builder before adding alternatives.
- `experiments/h1710_paired_program.h`:
  `945daac7efe60ee2125222f39598ba3eb1998f9026986bde566cc90a44e7e027`.

Builders, verifiers and their report hashes pin the exact source/program,
compiler variants and independent modules. The two full alternative censuses
reuse H1709's scorer; their experiment field identifies that scorer and the
binary hash identifies the model. Counts must not be mistaken for three
independent capture sets.

## Next required evidence, not a new completion definition

Keep both paired alternatives default-off and the paper unchanged. Seek
fresh, endpoint-visible last-product materialization discriminators plus
rounding-boundary/common-prediction controls. Include negative and reduced
polynomial routes, relevant dispatch boundaries and actual RZ/PC evidence.
Also seek a minimal-vs-all-edge separator or establish their numerical
equivalence on a justified domain; do not infer physical fusion from agreement.

Freeze the fixed candidate and independent predictions before hardware,
perform public/private local tuple freshness checks, and run every eligible
tuple at most once on the authorized Xeon45.32.204.118. Existing tuples,
including these two operands' observations, are closed. H1688 reservations
and unresolved private matches remain reservations; no private information
is published. Standing host authority already applies without another ask.

No unrelated state, cross-CPU or hidden-netlist proof gate is added. The paired
goal is not complete because the new fix has no fresh adversarial hardware
validation yet. Current standalone source/paper hashes remain exactly H1708.
