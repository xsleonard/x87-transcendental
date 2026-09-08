# H1606: no single changed materialization width rescues the fixed-policy graph

Date: 2026-09-04. Exact finite hypothesis audit; no hardware, C-model run,
new label, emulator/default change, or manuscript/PDF update.

## A precision change, not another fixed-width policy search

H1602/H1605 excluded the five conventional policies at the original widths.
H1606 changes one node's retained precision and still permits **every other
operation's policy to vary**, with one common policy vector across inputs.
It is not a one-node arithmetic perturbation with the rest left ordinary.

For each of the thirteen H1595 materializations, choose a new width from
64 through 72, or exact numerical forwarding. Exclude that node's original
width; all other node widths remain original. This gives nine alternatives
per node, 117 width hypotheses per payload treatment, 234 total. For each,
all thirteen policies remain free among CHOP, nearest-even, nearest-away,
AWAY and JAM. Final architectural rounding is still RC64.

The common operation sequence, coefficients and shared square/fourth
dependencies are unchanged. Payload is either absent or the original numeric
value and scale frozen. Exact forwarding passes the entire exact dyadic result
to **every** consumer of the changed node. It is a mathematical retention
hypothesis, not a decoded bypass bus, fused instruction or physical-width fact.
At an exact node all five policy labels are equivalent; counts remain named
assignments, not counts of distinct circuits.

The check uses H1600's authenticated output/C1 constraints and ordinary-final-
rounding inverse. Changed intermediate precisions do not change that inverse.
One common prevalue per operand must satisfy all its actual recorded modes.
No unobserved mode, C1, precision-control setting or hardware value is filled in.

## Results

**All 234 hypotheses are rejected.** None reaches the full target bank, so
none is a candidate for the H1603 control wall. Rejecting a required prefix
is sufficient; untested later operands are not counted as successes or misses.

The deterministic check order begins with the H1605 same-RD pair, then the
H1604 pair, then the remaining operands in lexical order. The stopping counts
are:

| Required operand prefix | Rejected hypotheses |
| --- | ---: |
| 2 operands | 211 |
| 4 operands | 19 |
| 9 operands | 4 |

Every square-width alternative, including the exact square, is rejected by
the first same-RD pair. Widening the final negative factor to any of 65..72
or exact survives that first pair but fails by the four-operand prefix.
Fourth width 64 with frozen payload is the other four-operand case.

The four nine-operand cases retain the left product at 64 or 65 bits, under
either payload treatment. Those variants pass both old two-operand cores
under some common policy assignments, but the surviving assignments fail
when `3ffc:c6db323ae10c933c` is added. The report retains the complete prefix
counts; these are rejection sequences, not minimum unsatisfiable cores or
best-fit candidates.

## Verification

The solver parameterizes the exact numerical graph and constructs a finite
multi-valued decision diagram over common operation policies. It preserves
every policy assignment by grouping only identical local numeric outputs.
Each finite-width operation has at most two outputs for these five policies;
an exact-forward node has one. Intersecting the resulting per-input diagrams
computes the exact surviving assignment set without search timeouts.

Before changing widths, the parameterized traversal reproduces all 72
per-operand/payload policy counts from H1602 at the original widths. The
changed-width audits traverse 4,126,720 complete numeric leaves and compare
4,790 independently executed policy vectors against diagram acceptance and
actual recorded outputs/C1. This direct replay includes an accepting witness
for every individually satisfiable checked operand, plus deterministic
random vectors. H1602's separate diagram and nearest-away selftests also run.
Those checks supplement the exhaustive graph construction; they are not
substitutes for coverage of the policy assignment space.

Each hypothesis's entire allocated diagram, variable widths, policy names,
checked operand roots and final false root is preserved in the compressed
certificate stream. A false prefix is retained rather than discarded when
the next hypothesis starts. All original evidence hashes are checked.

## Limits and next distinction

This excludes exactly one changed materialization among the specified finite
width alternatives, with a globally fixed conventional policy vector. It
does not exclude two or more simultaneous width changes, widths below 64 or
above 72, RC/input-dependent width or policy choices, nonstandard rounding,
new forwarding routes, a different graph, changed coefficients or regenerated
payload. Testing exact forwarding does **not** prove that every untested
finite width between 73 and an exact product length behaves identically.

H1607 separately tests every combination of exact cut bypasses while keeping
each remaining cut's ordinary policy. These two families are not the same:
neither alone exhausts simultaneous multiple bypasses **and** arbitrary
conventional policy choices at the remaining cuts. That combined common
operation-semantic family remains a distinct next test, not a license to fit
per-input bypass predicates. No global impossibility or recovered chip rule
is claimed.

## Artifacts

Paths relative to `fsincos-re`:

- `experiments/h1606_single_width_policy_solve.py`, SHA-256
  `487b2a2ed81bdf540ffaa90ab6edff59c01a26bb8ee8b4f1f2735e0ec46993ef`.
- `tmp/ledger33/current/h1606_single_width_policy_solve/report.json`, SHA
  `fbb7e0fea67ed5803ebe7a0b5ab0622d7f04e77ac9b59b1eae6143e2b8f6c5f1`.
- `hypothesis_diagrams.jsonl.gz` in the same directory, SHA
  `5ed06257e990d177ed6be6674f1c3066553b4cd0a8db6bf38f690e23b3cac21d`.

```sh
python3 fsincos-re/experiments/h1606_single_width_policy_solve.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing output directories are refused. A separate full main-task replay
reproduces the report and complete diagram stream byte-for-byte. Syntax and
whitespace checks pass. The tested source remains unchanged at H1598's 0339
hash; R96 is empirical/incomplete, speculative selectors off, and direct
45/44 and external 75/74 failure frontiers unchanged. The full
bit-exact emulation objective is still open.
