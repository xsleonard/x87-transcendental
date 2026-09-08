# h1400-h1403: causal localization of the final ten FCOS operands

Date: 2026-09-02

Status: negative mechanism result.  The residuals localize to the unresolved
R59 carry choice at the resolution tested here, but no shared closed-form
selector has been recovered.  The default model is unchanged and remains 11
ledger-disabled failing mode/operand rows over ten operands.  R96 remains an
empirical, incomplete support model.

## Question and fixed truth

The h1378 ledger-disabled miss file contains eleven failing architectural
legs over ten operands.  For each operand, h1400 replayed all four rounding
modes.  The eleven failing outputs use their previously captured hardware
truth; the other 29 legs use the matched ledger-disabled outputs, whose
full-suite comparison already establishes them as exact.  A disjoint cached
control bank contributes 149,764 exact all-mode FCOS legs.  The experiment
did not execute x87 and did not repeat any hardware capture.

Each materialized stage was perturbed by exactly one numerical ulp in each
direction.  The payload and aligned difference use one unit in their native
integer coordinates.  Separate builds force the unresolved final R59 carry
to zero and one.  These interventions are causal reachability probes, not
candidate correction laws.

## Stage-by-stage result

`repair` counts the eleven residual legs made correct.  `target regressions`
counts damage to the other 29 rounding-mode legs of the ten target operands.
`exact operands` requires all four rounding modes to be correct.  `control
regressions` is measured over the 149,764-leg cached control wall.

| Stage | -1: repair / target regressions / exact operands / control regressions | +1: repair / target regressions / exact operands / control regressions |
|---|---:|---:|
| square | 2 / 0 / 2 / 22,108 | 10 / 2 / 9 / 34,134 |
| fourth power | 8 / 0 / 7 / 7,995 | 3 / 0 / 3 / 10,326 |
| negative FMUL 1 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| negative FADD 1 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| negative FMUL 2 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| negative FADD 2 | 8 / 8 / 6 / 62,294 | 3 / 1 / 3 / 25,981 |
| positive FMUL 1 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| positive FADD 1 | 1 / 0 / 1 / 0 | 0 / 0 / 0 / 0 |
| positive FMUL 2 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| positive FADD 2 | 8 / 0 / 7 / 17,133 | 3 / 0 / 3 / 21,660 |
| terminal left product | 8 / 6 / 7 / 47,821 | 3 / 1 / 3 / 23,573 |
| terminal right product | 7 / 0 / 6 / 8,566 | 3 / 0 / 3 / 10,519 |
| payload formation | 3 / 0 / 3 / 10,284 | 7 / 0 / 6 / 9,039 |
| aligned difference | 3 / 0 / 3 / 9,170 | 7 / 0 / 6 / 8,329 |
| terminal result | 8 / 6 / 7 / 42,834 | 3 / 1 / 3 / 23,452 |
| R59 final carry | 3 / 0 / 3 / 20,743 | 8 / 0 / 7 / 18,710 |

No fixed signed perturbation at any earlier stage makes all ten operands
all-mode exact without collateral.  The apparent earliest intervention is
the square, but it is not a shared hidden-square law: `square +1` damages two
target legs and 34,134 controls, while the two signs split the corner rows.
One corner is all-mode exact under either square sign.  These are downstream
boundary aliases, not evidence for a signed square error.

The first and second negative FMUL inputs, first negative FADD, and both
positive FMULs are entirely inert under the bounded +/-1 probe.  This rules
out a one-ulp error at those materializations as the source of these eleven
legs; it does not rule out a wider or differently encoded hidden state.

The final carry is the smallest sufficient intervention for every operand.
Carry one makes all four modes exact for b000, ba10, cca, d0d0, d920, f410,
and fa50 (eight failing legs because d0d0 contributes RD and RZ).  Carry zero
makes all four modes exact for the three far-corner operands.  Neither force
is a global rule: applying a constant carry to the whole control wall causes
18,710 or 20,743 regressions respectively.  The still-missing object is the
selector for that carry.

In particular, d0d0 is not forced to be an earlier arithmetic exception.
Its tie row has `theta=0`, `k=8`, `ce=-72`, `s4=66`, `side=1`, `b1=b2=1`,
payload 3, and discarded coordinate zero.  Forcing carry one repairs RD and
RZ while preserving RN and RU.  R1382's s4-qualified hard-3x merge is an
upstream way to reach the same endpoint choice, but its greater than 17
billion-input software search produced no fresh architectural separator.
Without an independent label it remains an observational alias and stays
default off.

## Shared-selector searches

The h1393 branch banks contain four band, two tie, and three corner selector
positives.  Corner-only QX and Q long-propagate aliases were independently
falsified by fresh, frozen, one-shot hardware banks: 31/31 and 75/75 pairs
selected the incumbent.  h1396 found no repair in fused-terminal or R60
redundant representations.  h1397 found no compact structural DNF: the band
requires at least a residual singleton after its best two-row terms, and the
two tie rows require separate singleton terms.

h1401 removes branch separation and exhausts 7,924 literal two-wire patterns
over 6,864 named signals and 34,473 constrained rows.  It finds zero exact
physical-carry gates and zero exact incumbent-flip gates.  Adding d0d0 cannot
turn a gate that already fails the original nine positives into an exact
ten-positive gate.

h1402 then tests fixed one-bit radix-block K/P/G recurrences in the structural
style of R1158 over the unified bank including d0d0: widths 1, 2, 4, 8, 16,
and 32; integer, absolute, and cut alignment; eight suffix depths; zero, one,
and exact boundary seeds; all 64 transition laws; and all 16 Boolean
compositions with the incumbent.  There is no exact direct or composed
recurrence.  The best direct recurrence has 5,789 errors (six positives and
5,783 controls).  The best composition has ten errors: it preserves every
control while leaving all ten positives unfixed, so it is merely equivalent
to the incumbent on the constrained wall.

h1403 grants one extra attached-history bit and exhausts the affine two-bit
recurrence

    state_next = (a*state + b*symbol + c) mod 4

over the same widths, alignments, and depths, five seeds, optional final tail
symbol, all 64 `(a,b,c)` laws, and all 16 four-state decoders.  It finds zero
exact physical-carry recurrences and zero exact incumbent-flip recurrences.
Its best scores are identical to h1402: 5,789 direct errors, or ten flip
errors with no control errors.

## Bounded conclusion

At +/-1 materialization resolution, the ten residual operands are final-R59
selector failures, not evidence that one common earlier value is wrong.
Earlier perturbations can reach the same architectural neighbor, but no
shared earlier sign survives the target modes and control wall.  The causal
result does not prove that the physical selector has no upstream provenance;
it proves that the presently tested earlier-value mechanisms are neither
necessary nor sufficient, whereas the unresolved carry is sufficient per
operand.

There is no surviving closed-form candidate to promote or to send to a new
hardware capture.  R1158 and R1378 remain the strongest validated structural
recurrences, but direct one-bit and two-bit attempts to reuse their recurrence
idiom for this final selector are falsified here.  The honest frontier remains
11 ledger-disabled legs.  No manifest was frozen because no software-selected
candidate survived the cached wall.

## Artifacts

- `experiments/h1400_causal_stage_localization.py`
- `tmp/ledger33/current/h1400_causal_stage_localization.txt`
- `tmp/ledger33/current/h1400_causal_stage_localization_details.tsv`
- `tmp/ledger33/current/h1401_allbranch_two_wire_gate.txt`
- `experiments/h1402_current_r59_carry_recurrence.py`
- `tmp/ledger33/current/h1402_current_r59_carry_recurrence.txt`
- `experiments/h1403_two_bit_r59_radix_recurrence.py`
- `tmp/ledger33/current/h1403_two_bit_r59_radix_recurrence.txt`
