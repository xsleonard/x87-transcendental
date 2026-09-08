# Logarithm verification on the Core i7-6700

The final fixed FYL2X and FYL2XP1 implementations pass **51,636 new observations
on the Core i7-6700**, with zero result, C1, arithmetic-exception or preload-flag
differences. The complete captured output/status stream is byte-for-byte
identical to the corresponding saved Xeon stream. The numerical
implementations are unchanged. This closes the absence of i7 confirmation
for the selected logarithm cases.

The final authenticated receipt is
[RESULT.json](../../tmp/verification-expansion/logarithms/RESULT.json), with
the detailed [score](../../tmp/verification-expansion/logarithms/l0006-i7/FINAL-SCORE.json)
and [permanent-ledger audit](../../tmp/verification-expansion/logarithms/l0006-i7/LEDGER-AUDIT.json).

## What the saved records establish

The five current logarithm packs contain 941,808 saved observations. Their
input, source, manifest and hardware hashes were authenticated, along with
their start/completion receipts. All five identify the Xeon processor context
`00050654:0x1`. None supplied an i7 result before this extension. This is a
conclusion about the earlier logarithm records, not the project's other instructions, which
already have substantial validation on both processors.

The local audit is [LOCAL-HISTORY.json](../../tmp/verification-expansion/logarithms/LOCAL-HISTORY.json).
It does not establish that an absent i7 observation is safe to repeat. Before
staging any new logarithm material, the dispatcher separately audited the i7's
public research files: 33 roots, 24,380 files and 18,411,971,560 decoded bytes,
with no FYL2X/FYL2XP1 hit or unread file. Its
[receipt](../../tmp/verification-expansion/coverage/i7-logarithm-history.json)
is retained unchanged. Permanent processor-specific reservations still govern
the actual capture.

## The bounded confirmation

The request selects inputs from authenticated L0005, so every requested i7
case has a saved Xeon comparison. Selection uses operand encodings, original
construction categories and a deterministic hash rank; hardware output values
do not select cases. It retains every admitted L0005 table-boundary pair and
FYL2XP1 direct/table-join pair, plus stratified coverage of the other families.
Original source-model rounding constructions remain identified as such;
they are not relabeled as independent mathematical input generation.

| Coverage | Completed amount |
| --- | ---: |
| Distinct ordered instruction/operand pairs | 8,801 |
| FYL2X instruction/control cases | 33,724 |
| FYL2XP1 instruction/control cases | 17,912 |
| Total cases | 51,636 |
| Each of RN, RD, RU and RZ | 12,909 |
| PC64 | 35,204 |
| Each of PC24 and PC53 | 8,216 |
| Pairs with all four RC and all three PC settings | 2,054 |

Every selected pair retains its complete four-RC group. Coverage includes
FYL2X's direct and table paths; FYL2XP1's tiny, direct and wide-add/table paths;
near-one values; all admitted table boundaries; the documented FYL2XP1
endpoints; tiny-path joins; underflow, overflow and rounding constructions;
exact subnormal products; signed zero; subnormals and pseudo-denormals;
unsupported encodings; quiet/signaling NaNs and NaN priority. Infinite y
operands and FYL2X infinite x operands are included. FYL2XP1 retains its
existing documented input-domain contract.

Local supplemental, i7 public-history and corpus operand-pair checks produced
no holds in this selected set. A separate input-structure audit confirms all
32 FYL2X table indices and both signs in each applicable finite arithmetic path.
These conservative checks do not claim access
to unavailable history or knowledge of unknown generator seeds. The complete
counts and selection description are in
[COVERAGE.json](../../tmp/verification-expansion/logarithms/l0006-i7/COVERAGE.json).

## Review completed before hardware

- All 51,636 frozen predictions match the authenticated Xeon observations in
  the unchanged C CLI, the C API batch program and an ASan/UBSan build.
- Independent exact-rational evaluation agrees on every selected case.
  Result bits, C1, arithmetic exceptions and preload exception flags match;
  the protocol checks control words and the two-deep-to-one-deep stack pop.
- The saved comparison includes 3,038 subnormal outputs, 3,608 underflow-flag
  cases, 1,140 overflow-flag cases, and exceptional-input behavior. These
  counts now apply to both identical processor streams.
- The existing 854 bundled hardware witnesses pass through the C CLI, C API
  and rational reference, including the exact FYL2XP1 domain-bound check.
- The unchanged guard passed synthetic checks for successful whole-job
  reservation, duplicate-tuple refusal, refusal after STARTED, input-hash
  tampering, unresolved history, and preservation of reservations and partial
  output after capture failure. No native instruction was executed by these
  synthetic checks.

Receipts: [LOCAL-REVIEW.json](../../tmp/verification-expansion/logarithms/LOCAL-REVIEW.json)
and [GUARD-CHECKS.json](../../tmp/verification-expansion/logarithms/GUARD-CHECKS.json).
No numerical discrepancy was found in the local checks.

## Dispatch and remaining scope

[REQUEST.json](../../tmp/verification-expansion/logarithms/REQUEST.json) identifies
the frozen input and source hashes, public-only transfer bundle, existing guard,
required returned records and conservative runtime allowance. The bundle
contains inputs, the public capture/protocol/guard, and manifests; it contains
no saved hardware labels, numerical implementation, predictions or supplemental
material. The coverage session alone dispatches the capture, after checking
the processor identity, reservations and current resources. It must preserve
the running H1725 campaign and never repeat a started or uncertain request.

The returned data were authenticated and compared with the frozen predictions
and Xeon baseline using
[score_i7.py](../../tmp/verification-expansion/logarithms/score_i7.py).
The i7 reports signature `000506e3` and microcode `0xf0`; the start receipt
matches the processor model and capture-binary hash checked before dispatch.
All 51,636 permanent reservations are marked `OBSERVED`, and the ledger
integrity check passes. Every complete three-PC comparison group also agrees
across PC24, PC53 and PC64. No capture was repeated.

This establishes the selected two-processor comparison. The remaining
890,172 tuples in the 941,808-row Xeon archive are not established on i7 by
this work. It does not exhaust raw80 pairs. Arbitrary incoming x87 state,
unmasked exception delivery and other processor generations remain outside
this task. No paper, production source or release file has been changed.
