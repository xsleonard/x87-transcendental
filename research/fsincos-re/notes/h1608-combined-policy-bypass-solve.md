# H1608: the combined conventional-policy / exact-forwarding family fails

Date: 2026-09-04. Analysis-only finite-family exclusion. No general solution,
emulator change, new hardware observation, or manuscript/PDF update.

## The previously untested combination

H1602 varied five conventional policies with no bypass. H1606 changed one
width or bypass while varying those policies. H1607 varied all bypasses but
kept ordinary policies elsewhere. Their negative results did **not** exhaust
multiple simultaneous bypasses with freely selected policies elsewhere.

H1608 tests that combination. Each of the thirteen H1595 operations chooses
CHOP, nearest-even, nearest-away, AWAY, JAM, or exact numerical forwarding.
There is one common vector across all inputs and architectural modes. The
first five choices retain each node's original 64- or 67-bit width. Exact
forwards the complete numerical dyadic to every consumer. The shared square
and fourth, both polynomial arms, and all descendants are recomputed.

This is `6^13 = 13,060,694,016` named vectors per payload treatment, not that
many distinct physical circuits. Payload is either absent or the original
consumed signed numeric value and scale, frozen before any changes. The
coefficient values and operation graph are fixed; final rounding is RC64.
The constraints are H1600's 36 operands, 64 actual outputs and 27 actual C1
observations. Unknown modes/status are not supplied by the model.

## Result

**Zero shared vectors survive either payload treatment, even using only
output bits.** All 36 operands remain individually feasible. No candidate
reaches the H1603 cached control bank.

Minimum two-operand output cores are:

| Payload | First operand | Second operand |
| --- | --- | --- |
| omitted | `3ffc:b72fd2547f8c2fef` | `3ffc:ba100000056e0a67` |
| frozen original numeric | `3ffc:b72fd2547f8c2fef` | `3ffc:f4100000059862dd` |

Each singleton is feasible; full stage/output replays of deletion witnesses
are retained. These are contradictions among fixed operation choices, not
input-classification trees or recovered chip gates. H1609 separately checks
the architectural-RC-only extension instead of assuming these cores exclude it.

## Exhaustiveness and verification

The compiler builds ordered six-valued decision diagrams. At an operation,
the five conventional policies have at most two numerical results, and exact
adds at most one. All six labels remain represented, including labels that
produce identical numbers. Backward liveness analysis keeps every value needed
by an unexecuted operation. Numerical suffixes are reused only when all those
values are identical. Canonical dyadics remove trailing zero bits; unused
round-history metadata is not part of this explicitly numerical graph.

This is an exact optimization, not a search cutoff: every named assignment
has a branch. It represents 56,949,480 distinct numerical paths for omitted
payload and 55,864,728 for frozen payload, using 374,410 and 374,314 distinct
live suffix states respectively. Those are software counts, not hardware
widths or independently sampled observations. Both complete diagrams and
every operand's output/output+C1 roots are preserved.

Checks beyond the exact construction:

- Restricting to the five non-exact choices gives the **identical canonical
  Boolean function** saved by H1602 for all 72 operand/payload cases. This
  compares all assignments, not just accepted counts.
- Restricting each node to ordinary/exact gives H1607's complete output-only
  and output+C1 bitsets: 144 complete 8,192-pattern bitsets agree.
- 4,896 straight-line full-graph replays compare both acceptance roots to
  forward architectural outputs and actual C1 inequalities.
- Independent rational-grid tests cover 42,966 rounding cases, 128 complete
  graphs / 1,664 stages, and 128 all-exact direct degree-twelve polynomials.
- Restriction logic passes 1,596 exhaustive small truth-table cases; inherited
  H1602 tests add 2,430 diagram and 6,132 nearest-away reference checks.

The implementation reuses H1602's tested quantizer/diagram primitives and
H1595's graph. It is not an independently recovered hardware specification.
Rational reference checks and separate execution paths supplement, rather
than replace, the complete finite enumeration.

## Artifacts and limits

Paths are relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1608_combined_policy_bypass_solve.py` | `498746dcc91a35b326785af800cbc864b4ad5f53e4d801d89f3136c474e829f6` |
| `tmp/ledger33/current/h1608_combined_policy_bypass_solve/report.json` | `842bd5ff9c73c8e8e3dd4dedeb5874df86f01501c8d45d899554e80857cb4ec4` |
| `omitted_diagram.json` in that directory | `48994082295b697f467f7c4dd54ec2cdf303980ca4caee0f676443603f0502c2` |
| `frozen_numeric_diagram.json` in that directory | `050b857ee10067ab92e9e4944270fd370bdd9f3a9f8e63797525a67441b2d628` |

```sh
python3 fsincos-re/experiments/h1608_combined_policy_bypass_solve.py --selftest
python3 fsincos-re/experiments/h1608_combined_policy_bypass_solve.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing directories are refused. Separate full replay reproduces the report
and both diagrams byte-for-byte. Syntax, whitespace and build/selftest checks
are recorded with integration.

The exclusion does not cover other finite widths, edge-specific forwarding,
changed graphs/coefficients, nonstandard rounding, operand-dependent control
or history, or regenerated payload. Exact numerical forwarding is not proof
about every intermediate finite width and not decoded physical wiring.
H1609 supplies a separate RC-only result. No selector is promoted; R96 remains
empirical/incomplete, source/defaults and the direct 45/44 / external 75/74
failure frontier remain unchanged. The full bit-exact goal is still open.
