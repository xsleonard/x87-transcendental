# H1535 complete three-wire XOR audit

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Question

H1401 exhausts one- and two-wire Boolean gates over the unified R59 wall.
H1442 later exhausts three-input Boolean gates only for 2,392 fixed
architectural/isomorphic wire pairs.  Neither result answers the complete
three-wire parity question over all named histories.  H1535 tests that
smallest physically recognizable extension: the sum output of a 3:2
carry-save compressor,

```text
sum = a XOR b XOR c.
```

This is not an arbitrary three-input Boolean census.  It is the complete
parity/XNOR class, because both polarities of every source pattern are in the
literal universe.

## Immutable wall and reproduced H1401 boundary

The audit uses only the cached H1386 feature rows and the H1092/H1108
all-mode endpoint labels:

- H1386 features: 37,450 source rows, SHA-256
  `6769baae23840775207b4283d5227dd0bba15227481f38ff24eae1c3af318932`;
- H1092 positives, SHA-256
  `fdaec8e810bfb3e5220abc636abef5153b524cf3d9d02dcdaae753f2ddf9ed6c`;
- H1108 controls, SHA-256
  `82da3ff9751c011f202885a424c5359755302ed2e7c8f939706f69a8a6d1b006`.

There are 34,473 carry-constraining rows: nine incumbent-flip positives and
34,464 controls.  The 2,977 rows allowing either endpoint are neutral and do
not constrain a selector.

The first implementation run exposed a useful provenance distinction.  The
current helper code includes H1172's later P5-CPA features, while the
historical H1401 report predates that addition.  Removing only the `p5cpa.*`
component reproduces H1401 exactly: 6,864 named features and 7,924 distinct
literal histories.  The current universe is a strict superset with 10,456
named features and 11,240 distinct literal histories.  The final census uses
the larger universe, so its negative result includes the complete original
H1401 universe rather than silently changing the old report.

## Exact search

The expanded universe contains

```text
C(11240, 3) = 236,609,272,280
```

unordered triples of distinct truth histories.  Enumerating every triple
directly is unnecessary.  For each target truth vector, H1535 enumerates all
63,151,941 ordered-prefix pairs and looks up the required third history using
two deterministic 64-bit projections that are linear over GF(2).  If
`a XOR b XOR c` equals the full target vector, the same equality must hold in
both projections.  Therefore this filter cannot produce a false negative.
Every projected candidate is checked against the full 34,473-bit vector.

The projections produced zero candidates for both target functions.  The
full results are consequently:

| target | ones | exact distinct-pattern triples | exact direct literals |
|---|---:|---:|---:|
| required physical carry | 18,220 | 0 | 0 |
| incumbent-carry flip | 9 | 0 | 0 |

The direct-literal check also closes repeated-history triples: if two of
three inputs have the same truth history, they cancel and the circuit reduces
to its third literal.  No such literal equals either target.

## Boundary

No three-wire compressor parity over any current terminal, P5 tree, P5 CPA,
borrow, or incumbent-carry literal is the missing selector on the cached
wall.  This is a complete exclusion of that circuit class, not proof against
arbitrary three-input Boolean functions, hidden/raw control bits, or a new
observable absent from the feature bank.

No x87 instruction or hardware capture ran.  No H1488 label or private ledger
was opened.  No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1535_complete_three_wire_xor.py`, SHA-256
  `1ef58c8e20f63f812f3e847f3f35f6caa70794c6cc900e56c90de24e8be0031e`;
- `tmp/ledger33/current/h1535_complete_three_wire_xor.json`, SHA-256
  `6b9daa2069356ba4fe4a93e37283410245ea0a9e5a944e2c5e02575b05ca3dd1`.

The JSON pins all direct helper-code hashes in addition to the three input
hashes.
