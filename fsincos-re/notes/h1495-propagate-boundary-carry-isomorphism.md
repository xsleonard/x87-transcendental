# H1495: canonical boundary-carry form of the surviving functions

Date: 2026-09-03

Status: exact universal arithmetic isomorphism; pair A versus pair B remains
hardware-unresolved, no selector is promoted, and the paper/PDF is unchanged.

## Question

H1486 leaves four `final.propagate.-18` spellings exact on the 28 available
hardware labels.  H1487 proves that they are exactly two functions over every
normalized 67-by-64-bit multiplier input, and H1491 shows that their tree
drawings require nonlocal row relabeling relative to the public P5 figure.

H1495 asks whether those functions have a representation that does not depend
on treating the compressor drawing itself as the explanation.

## Closed form

Let `(S,C)` be either candidate's final redundant pair, let `P = S + C` be
the exact product, and let `j = product_cut - 18`, which is absolute column 45
or 46 in this normalized domain.  Define

```text
boundary_carry_j = ((S mod 2^j) + (C mod 2^j) >= 2^j)
selector_j       = bit_j(P) XOR boundary_carry_j
```

Then `selector_j` is exactly `bit_j(S XOR C)`, the H1486 final-propagate
signal.  Z3 4.15.3 proves the negation UNSAT for arbitrary 131-bit `S` and `C`
at both columns 45 and 46.  This lemma is independent of any sampled operand,
hardware label, or multiplier-tree topology.

The identity is ordinary binary addition: the product bit is
`S_j XOR C_j XOR boundary_carry_j`, while the propagate bit is
`S_j XOR C_j`.  Consequently pair A and pair B disagree if and only if their
two final redundant representations generate different carries across the
same lower-residue boundary.  The common exact product bit cancels.

## Exact product proof

H1495 also makes the arithmetic-exact premise explicit rather than relying on
the candidate labels:

1. The eight possible one-bit inputs to a CSA3 exhaustively satisfy
   `a+b+c = sum + 2*carry`.  A CSA42 is two such applications, so every level
   of the four-stage tree preserves its input sum modulo the word width.
2. All sixteen radix-8 Booth codes exactly equal the linear digit formula
   `b[-1] + b[0] + 2*b[1] - 4*b[2]`.
3. Summing that formula over the 22 overlapping windows gives coefficient
   `2^k` for every multiplier bit `k=0..63`; the recoded digit sum is exactly
   the unsigned 64-bit multiplier.
4. Each corrected partial row is `7*2^69 + digit*multiplicand`.  The 22 common
   scaffolds plus the extra `2^69` input sum to exactly `2^135`, hence zero
   modulo `2^131`.  The final redundant sum therefore equals the exact
   67-by-64-bit product through bit 130.

These are finite algebraic proofs, not random tests.  Together with H1487's
UNSAT within-pair and SAT cross-pair results, they establish that the four
spellings are two distinct arithmetic boundary-carry functions.

## Interpretation and remaining boundary

This supplies the isomorphic representation sought after H1486: the survivor
is not merely a 28-row decision tree or operand table.  It is a fixed carry
across an exact lower-residue boundary of a redundant product representation.
That structural statement generalizes over the complete normalized multiplier
input domain.

What remains unproved is physical selection.  Exact arithmetic permits both
pair A and pair B, and H1495 cannot identify which redundant pair, if either,
Skylake actually materializes.  H1488's two frozen disagreement rows are the
precommitted observation that distinguishes them.  Until that distinct
one-shot bank is separately authorized and opened, neither function is a
confirmed R59 selector and neither may change default emulator behavior.

## Artifacts

- `experiments/h1495_propagate_boundary_carry_isomorphism.py`, SHA-256
  `c6fdbf08811341b895a7cc15cb45ffbc59a0399168beb7b8867f6d1c8388dfbf`;
- `tmp/ledger33/current/h1495_propagate_boundary_carry_isomorphism.json`,
  SHA-256
  `2d8f5401eb47de1faeb7dea306d95dbf6d226d47539300958b1809f0a75d8717`.

The isolated solver was Z3 4.15.3.  An independent rerun is byte-identical.
No x87 instruction or hardware capture ran, no label or private ledger was
opened, and H1488 remains `FROZEN_UNOPENED`.  No emulator behavior/default or
academic paper/PDF changed.  R96 remains empirical/incomplete; the
authoritative frontier remains eleven mode rows over ten operands.
