# H1605: a same-RD contradiction excludes architectural-RC-only policy selection

Date: 2026-09-04. Exact finite certificate under the H1595 graph assumptions.
No emulator change, hardware execution, new label, or paper/PDF update.

## Two existing observations suffice

The two operands below were each already observed once in standalone FCOS/RD.
H1600 authenticates their outputs and their actual C1=0 status:

| Operand | Observed output |
| --- | --- |
| `3ffc:de3ffffc8c13c97c` | `3ffe:f9fe744bc4145c55` |
| `3ffc:e73ffffd2c52df71` | `3ffe:f97ff2968a37b8b1` |

The five allowed per-operation policies remain CHOP, nearest-even,
nearest-away, AWAY and JAM. Let `T={nearest-even, nearest-away, AWAY}` and
`Z={CHOP,JAM}`. Write S, N, L and C for the policies at square, negative
factor, left product and terminal correction respectively.

For both payload treatments, the complete output-acceptance predicates are:

```text
de3...c97c:  N in Z OR (S in Z AND L in Z AND C = CHOP)
e73...df71:  N in T AND (S = AWAY OR L in T OR C != CHOP)
```

Their contradiction is direct. To satisfy e73, N must be in T, so de3 then
requires S and L in Z and C=CHOP. Those requirements make all three of
e73's remaining alternatives false. The two predicates cannot both hold.

This is a predicate over **operation-policy choices for two fixed test
operands**, not a fitted predicate over input bits and not an emulator rule.
Every other operation policy is quantified freely, not silently fixed to
the incumbent. Both operands separately admit many policy vectors.

## Independent certificate construction

H1602 found the contradictory pair using a multi-valued decision diagram.
H1605 does not import its diagram construction, conjunction or evaluator.
Instead it traverses all complete numerical faithful paths directly with
the H1592 exact dyadic arithmetic and H1595 graph. For every local output,
it records the set of policy names that produce that output on the actual
altered inputs. A complete numerical path therefore corresponds to a
Cartesian product of thirteen nonempty policy sets.

These products partition policy space: at every node the policy sets are
disjoint and cover all five choices. H1605 verifies that their volumes sum
to exactly 5^13 for each operand/payload case. At each leaf it evaluates
the stored output from the numerical correction and checks the displayed
predicate on **every** member of that leaf's four-variable projection.
The other nine policy variables remain free in their Cartesian factors.
Thus their irrelevance to this acceptance predicate is verified over all
paths, not assumed from the reduced diagram's appearance.

The result covers 8,192 numerical paths per operand/payload case, 32,768 in
total, and 1,280,000 projected-cube predicate checks. Accepted policy counts
are 511,718,750 for de3 and 685,546,875 for e73 in each payload treatment,
matching H1602. Each accepted departure-mask set also exactly matches
H1600. All 625 assignments of the four policy variables are explicitly
checked to give zero joint acceptances. Full witnesses for each individually
satisfiable operand are preserved.

The numerical verifier compares nearest-away neighbors using exact rational
distances, not H1602's half-bit implementation. It shares H1592's previously
tested arithmetic for the other policies and the same explicit operation
graph; this is independent solver/certificate logic, not independent recovery
of the hardware graph. All source evidence hashes are checked.

For every traversed path, ordinary positive RD gives C1=0. Thus C1 adds no
constraint to these two output-only acceptances. No status bit or mode is
inferred as a new hardware observation.

## Consequence and limits

Any rule that chooses one of these policies at each operation based **only
on architectural RC** must choose the same thirteen-policy vector for both
operands, because both are RD. The contradiction therefore excludes even
arbitrary RC-to-policy selection, not just H1602's RC-independent vector.
Adding an "obey architectural RC" policy cannot rescue this particular graph.

This supersedes the tentative next RC-only extension in the H1602 discussion.
It does not exclude input-dependent internal control, changed precision,
nonstandard arithmetic, forwarding/fusion, a different graph or changed
payload generation. Nor does it establish physical square or terminal cause.
A general solution remains open; the finite certificate narrows what a
successful revised mechanism must change.

## Artifacts and verification

Paths relative to `fsincos-re`:

- `experiments/h1605_same_mode_policy_core.py`, SHA-256
  `c9d22aab29589809fe884300400e35363cad2ca7cb8b273a4a4e8f2d8353a537`.
- `tmp/ledger33/current/h1605_same_mode_policy_core.json`, SHA-256
  `b936d3a3f403c7785880f290a2a69e9e194e0fb9d8834d0429cf34c704f416f1`.

```sh
python3 fsincos-re/experiments/h1605_same_mode_policy_core.py \
  --root fsincos-re --output NEW_OUTPUT_FILE
```

The script refuses existing output. A separate full replay reproduces the
report byte-for-byte. No hardware/source/default/private-ledger action was
taken; the source remains H1598's 0339 hash, speculative selectors are off,
R96 is empirical/incomplete, and the direct 45/44 and external 75/74 frontiers
are unchanged.
