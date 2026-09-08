# H1602: no common fixed rounding-policy assignment on the thirteen-cut graph

Date: 2026-09-04. An exact finite family exclusion, not a claim that a general
FSIN/FCOS solution is impossible. No hardware or C-model execution, inferred
label, emulator/default change, or academic paper/PDF update.

## What is stronger than H1595/H1600

H1600 permits each operand its own faithful rounding choices. It establishes
that one internal path can satisfy all that operand's actual modes and C1,
but does not provide a rule shared by different inputs.

H1602 instead assigns one fixed policy independently to **each operation** of
the full thirteen-cut H1595 graph. That same thirteen-policy vector must
satisfy all 36 operands, their 64 authenticated RC observations and 27 actual
C1 constraints. All intermediate values are recomputed with shared square/
fourth dependencies; this is not thirteen separate one-operation ablations.

The permitted policies at each cut are magnitude truncation, nearest-even,
nearest with ties away, magnitude away, and round-to-odd/jam. Products and
the correction retain their proposed 67-bit precisions; four Horner additions
remain 64-bit. Final rounding is ordinary architectural RC64. Payload is
either absent everywhere or each original consumed numeric payload is frozen
as in H1595. The latter is an empirical scaffold, not a replacement law.

There are 5^13 = **1,220,703,125 named policy assignments per payload variant**.
This is not a count of distinct circuits or distinct observed behaviors.
There are no exact half-way internal operations on this finite traversed bank,
so nearest-even and nearest-away coincide here. All operation signs are fixed
on the traversed bank, making signed upward/downward rules equivalent to one
of the included truncation/away rules at each respective cut. Neither fact
claims that ties or sign changes cannot occur elsewhere.

## Complete finite solve

`h1602_fixed_operation_policy_solve.py` constructs a reduced ordered
multi-valued decision diagram whose variables are the thirteen policy
choices, not bits/features of the external operand. The diagram is a finite
constraint solver; it is **not an emulator decision tree or a fitted selector**.

For each exact operand, each node computes the exact dyadic operation on the
current altered inputs and groups policies that produce the same value.
CHOP and AWAY span every faithful neighbor at that cut. The traversal
therefore reaches every H1595 numerical path, including paths requiring
several simultaneous altered operations. At the leaf the common prevalue
must belong to H1600's joint RC/C1 interval. Every accepted departure-mask
set is checked for exact equality with H1600, not just equal cardinality.

The resulting per-operand diagrams are intersected symbolically, preserving
all policy assignments including skipped variables. No timeout or heuristic
search cutoff is involved. Reduced-diagram counts and conjunction/evaluation
are separately tested against exhaustive small truth tables.

Both payload variants have **zero common policy assignments**. The solver
finds 23 contradictory operand pairs with omitted payload and eight with
frozen numeric payload. A shared two-operand contradiction is:

| Operand | Actual observed modes | Actual C1 available |
| --- | --- | --- |
| `3ffc:b0000000044ca2bf` | RN/RD/RU/RZ | none admitted here |
| `3ffc:cdcc0585c940196f` | RU | 1 |

Each operand alone admits policies, so the two-operand core has minimum
cardinality. The report preserves a policy vector and full straight-line
arithmetic replay for each core deletion: it satisfies the other operand
and fails the removed operand. There is no inference of unobserved modes.

The b000 accepted predicate depends on only square, negative factor, positive
factor, left product and correction policy. Omitted-payload cdcc depends on
those same five; frozen-payload cdcc additionally depends on fourth and right
product. These are dependencies of the acceptance predicate for these exact
operands, not general claims that earlier Horner operations have no effect.
The independent H1604 audit addresses the compact core and the necessity of
the extra RC/C1 constraints separately; H1602 itself checks the full join.

## Checks and scope

- The traversal covers 290,560 omitted-payload and 287,744 frozen-payload
  numerical paths over 36 operands. Accepted counts 135,616 and 133,376
  reproduce H1600 exactly. These are paths, not hardware samples.
- 9,216 independently evaluated complete policy vectors agree with both
  diagram acceptance and actual output/C1 checks. These randomized checks
  supplement, rather than replace, exhaustive diagram construction.
- 2,430 exhaustive toy truth-table assignments test diagram conjunction,
  counting and witness extraction. 6,132 rational-neighbor cases independently
  test nearest-away rounding, including both signs, ties and exact values.
- Every H1600 input evidence hash is checked. Original source snapshots,
  captures and SAT/UNSAT/UNKNOWN artifacts are retained unchanged.

H1602's original two-operand core alone does not cover architectural-RC-
dependent internal policies: those operands are observed in different modes.
The follow-up H1605 certificate uses a different pair, both actually RD, and
does exclude arbitrary RC-only selection among these policies at each cut.
Read `h1605-same-mode-policy-core.md` before repeating an RC-only extension.
Different internal widths, forwarding/fusion, changed operation graphs,
input/control-dependent nonstandard rounding and regenerated payload logic
remain outside both exclusions.

No common fixed-policy candidate survives to the control wall. H1603 prepares
the already recorded direct control bank for future independently specified
semantics; passing it would be a regression result, not fresh validation.
The direct 45/44 and external 75/74 failure frontiers remain unchanged. R96
is still empirical/incomplete, and the full bit-exact emulation goal is open.

## Artifacts and replay

Paths relative to `fsincos-re`:

- `experiments/h1602_fixed_operation_policy_solve.py`, SHA-256
  `35c787a27bf25d750cf2f6f45cd29aaab6ceb5cf057ac46d8cd41227ead508da`.
- `tmp/ledger33/current/h1602_fixed_operation_policy_solve/report.json`, SHA
  `8fef73d4ff104dc7bc5d945f7c418a873f4ab6e08b3b1b660f7abdd28b1d76ba`.
- `omitted_diagram.json` in that directory, SHA
  `f8e7c984abb64735b537a1f595f25a0daaacdd98f2189a105bc61d9fdbc8e837`.
- `frozen_numeric_diagram.json`, SHA
  `ba72faa73025fb99c5812e03cd47aa59864ec10480be792663395274372a9f09`.

The diagrams preserve all nodes, variable/policy names, operand roots and
the final false root. There are 1,413/3,099 allocated nodes respectively,
including intermediate intersection nodes, not just the final reduced root.

```sh
python3 fsincos-re/experiments/h1602_fixed_operation_policy_solve.py --selftest
python3 fsincos-re/experiments/h1602_fixed_operation_policy_solve.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

The script refuses an existing output directory. It requires the hash-locked
H1600 report and historical evidence, not a rebuilt current C model.
The main task's separate full replay reproduces the report and both complete
diagrams byte-for-byte. Syntax and whitespace checks pass.
