# H1609: architectural-RC-only selection cannot rescue the combined family

Date: 2026-09-04. No new hardware, inferred labels, source/default changes,
private-ledger action, or paper/PDF update. This is an extension of the
specified H1608 mathematical family, not a general impossibility result.

## What changes

H1608 required one shared six-choice vector across all operands and all RC
modes. H1609 allows a completely separate vector for each architectural mode:
every node may choose any of five conventional policies or exact numerical
forwarding as an arbitrary function of RC, but not as a function of operand.
The graph, original finite widths, shared square/fourth, final RC64, and
absent/frozen original numeric payload are unchanged.

Only the 64 actual mode observations are split. Their 27 recorded C1 values
remain attached to the corresponding mode/operand tuples. Missing C1 is
unknown, not zero; unobserved modes are not modeled into the evidence.
Each operand's inverse is rebuilt from its selected mode alone, so this test
does not accidentally require the old cross-mode common prevalue.

## Result

Counts below are named common semantic vectors within each mode. Output-only
and output+C1 counts are identical at this whole-mode intersection, though
individual acceptance functions can differ.

| Mode | Actual operands | Actual C1 constraints | Omitted-payload vectors | Frozen-payload vectors |
| --- | ---: | ---: | ---: | ---: |
| RN | 17 | 8 | 0 | 0 |
| RD | 20 | 10 | 0 | 0 |
| RU | 17 | 9 | 0 | 0 |
| RZ | 10 | 0 | 1,234,517,760 | 1,105,187,328 |

An RC-only rule requires a vector for **every** mode, so any zero mode factor
rejects the full rule. RN, RD and RU each independently suffice here. RZ's
remaining assignments are feasible on its smaller observed bank, not verified
models or candidates that solve the other modes. No control scoring is warranted.

The same minimum two-output **RD** core works under both payload treatments:

| Operand | Actual FCOS/RD output | Source |
| --- | --- | --- |
| `3ffc:e73ffffd2c52df71` | `3ffe:f97ff2968a37b8b1` | H1587 Q008 |
| `3ffc:fcbfffffcee1bd36` | `3ffe:f83dc8dae4171d48` | H1587 Q015 |

Both have observed C1=0, but output bits alone already contradict every common
six-choice vector. Both singleton constraints are feasible. Unlike H1605's
earlier pair, this one quantifies the complete conventional-policy-plus-
multiple-exact-bypass family. It is not an operand selector or fitting rule.

Additional output cores:

- Omitted RN: `ba100000056e0a67` and `de3ffffc6d9a4c39`, minimum size two.
- Omitted/frozen RU: `b72fd2547f8c2fef` and `f4100000059862dd`, minimum size two.
- Frozen RN: `de3ffffc7a17c3dd`, `de3ffffd548db2bf`, `f9dffffdf814cc29`,
  `fa50000007503a2f`; deletion-minimal size four, **not proven minimum**.

All abbreviated operands above have exponent `3ffc`. Full constraints,
inverses, diagrams and per-deletion forward witnesses are in the report.

## Verification and scope

H1609 reuses H1608's compiler and diagram implementation; it does not claim
independent solver authorship. Its distinct checks are:

- All 128 operand/mode/payload instances are compiled using only that mode's
  authentic evidence.
- Rejoining an operand's mode roots under one common vector recovers its
  original H1608 output-only and output+C1 functions exactly: 144 canonical
  function equalities, not just matching counts.
- 4,352 straight-line full-graph replays agree with the single-mode roots.
- Inverse tests pass 4,464 signed-neighbor cases, 204 forward/inverse C1 cases
  and two interval-endpoint checks.
- Every contradictory core has explicit feasible deletion witnesses. The
  feasible RZ modes also retain a common vector and all ten direct replays.

This excludes arbitrary **RC-only** choice among these six operation
semantics. It does not exclude operand-dependent internal states, multiple
changed finite widths, other graphs, edge-specific forwarding, nonstandard
arithmetic, changed payload generation, or a general closed-form solution.
No status convention is inferred for internal micro-operations; C1 is used
only under the explicit ordinary positive final-rounding contract.

## Artifacts

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1609_rc_only_combined_semantics.py` | `0669847f4a7616ccba8217d4317607d3fb45b8e9614920b6d1fc2bf9893d30df` |
| `tmp/ledger33/current/h1609_rc_only_combined_semantics/report.json` | `31d246bd667067e1d81a751acb935202071b11f0e19669b1cb48b099a89b1fb5` |
| `omitted_diagram.json` in that directory | `b8950fd520ce4923598a8507ec0f94d20cc2dcd8cff528bf3ee8a497d2baba61` |
| `frozen_numeric_diagram.json` in that directory | `fcdc9ab31cba355f6d17543e71586bd7e312ebb77c0c3821137874f6d3f6ab95` |

```sh
python3 fsincos-re/experiments/h1609_rc_only_combined_semantics.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing output directories are refused. A separate full replay reproduces
the report and both diagrams byte-for-byte. No emulator behavior is changed;
the unresolved frontier and full goal remain unchanged.
