# Verification expansion results

The four sessions finished their assigned work. The new tests found a real
F2XM1 subnormal-rounding bug and confirmed a general FPTAN check for unsupported
raw80 encodings. The F2XM1 correction is now integrated in the current C
program, rational reference, manuscript and v3 programmer package; its
[integration record](../paper/evidence/f2xm1-integration.json) preserves the
original capture history. The separate FPTAN correction remains an isolated
patch awaiting integration.

Six hardware jobs completed once, producing 212,396 processor observations.
The parent checked all 18 final-handoff file hashes, 54 capture-receipt hashes
and six decompressed hardware-output hashes against the final dispatch record.
No prepared hardware request remains pending. The separate H1725 campaign
continues under its existing controller.

## Findings

| Work | Result | Detailed report |
| --- | --- | --- |
| F2XM1 | The old program loses the rounding decision when storing a subnormal result. On each processor it misses 8,658 results and 3,177 C1 predictions. The correction, frozen before capture, passes all 54,128 cases per processor and the saved 915,162-result regression. | [F2XM1](verification-expansion/f2xm1.md) |
| FPTAN | Rejecting unsupported encodings before normalization fixes all 3,240 affected tuples per processor. The candidate, canonical arithmetic and frozen exception rules pass all 12,024 new cases per processor. The unsupported encodings extend the earlier rational reference's contract. | [FPTAN](verification-expansion/fptan.md) |
| FYL2X/FYL2XP1 | The unchanged programs pass 51,636 selected i7 cases, with complete output/status bytes identical to the saved Xeon results. | [Logarithms](verification-expansion/logarithms.md) |
| FPATAN | All 28,456 formerly Xeon-only tie cases pass on the i7. The existing 23-pack catalog now has matching results on both processors for all 7,571,628 tuples. | [Coverage audit](verification-expansion/coverage.md) |

The two unresolved mathematical searches also have definite answers.
FPATAN's original `a0064-below` query has 4,247 legal pairs; 16 explicit
witnesses satisfy the unchanged SMT constraints. FPTAN's original
`a0051-e16` query has no solution within its finite bounds, established by
two exact checks. Neither mathematical result adds hardware coverage for
unexecuted inputs.

The trig audit authenticates completed H1725 data at the fixed
2026-09-07 14:10:47 UTC checkpoint: 101,049,148 new i7 PC64 cases and
395,308,432 new Xeon PC64 cases, with zero reported result/C1/C2 differences.
The detailed report reconciles these with normalized older records without
adding overlapping replay appearances. Later controller progress does not
extend that fixed audit automatically.

## Tested changes and integration status

- [F2XM1 C and rational-reference patch](../tmp/verification-expansion/f2xm1/f2xm1-subnormal-rounding.patch): integrated. It rounds the tiny-path product directly at raw80 spacing, including subnormals. Preserve the distinction between result rounding and underflow classification. The tests reject classification using the stored result, but cannot distinguish two mathematically equivalent earlier predicates.
- [FPTAN encoding-check patch](../tmp/verification-expansion/fptan/fptan-unsupported-encoding.patch): reject unsupported raw encodings before normalization. The separately verified masked-state adapter is documented in the FPTAN report; it is not part of the earlier numerical API contract.

The F2XM1 integration updates the shared implementation, independent reference,
pseudocode and regression checks together. Publication evidence retains the old
program's failures and identifies the corrected source. Earlier release
snapshots keep their historical behavior; v3 contains the correction. The
same integration and review steps remain necessary for the separate FPTAN patch.

## Remaining coverage limits

- F2XM1 history holds leave 111 proposed neighborhood groups incomplete.
  Common held endpoints, including the smallest subnormal encodings and
  signed zeros, were not captured again. New RZ coverage must not be extended
  to excluded zero inputs. Broader exceptional-encoding and state behavior
  was not established by this finite-input campaign.
- FPTAN retains 384 held operands needed for incomplete windows or brackets.
  Six old RN/RD/RU observations were recovered for two operands, which does
  not complete every RC/PC/processor combination. The corrected accounting
  is 9 complete two-sign windows out of 32, or 25 individual signed windows
  out of 64.
- The logarithm confirmation covers a selected subset. Another 890,172
  tuples from the Xeon archive do not acquire i7 coverage from this work.
- Unknown historical PC settings, conservative holds and missing logs remain
  evidence limits. H403's final-log/code association remains to be reconciled.
  Finishing H1725's cleared selection will not turn excluded cases into passes.
- Arbitrary incoming state, unmasked exceptions and other processor
  generations remain outside the new confirmations. Both tested machines,
  the Core i7-6700 and the Xeon, belong to the Skylake family.

Final records: [six-job dispatch](../tmp/verification-expansion/coverage/DISPATCH-FINAL.json)
and [frozen handoff](../tmp/verification-expansion/coverage/FINAL-HANDOFF.json).
Original-work licensing remains undecided.
