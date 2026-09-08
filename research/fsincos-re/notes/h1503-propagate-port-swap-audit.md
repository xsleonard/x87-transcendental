# H1503: individual propagate support and operand-port swap audit

Date: 2026-09-03

Status: **exact support theorem; operand-port isomorphism rejected; no selector
promotion.**

## Exact support of the individual functions

H1501 proves that the pair-A/pair-B defect `D_j=F_A,j XOR F_B,j` depends on
both operand residues modulo `2^j`.  H1503 applies the same normalized-domain
sensitivity proof to `F_A,j` and `F_B,j` separately.

For both surviving functions:

```text
F_*,45(m,q) = g_*,45(m mod 2^46, q mod 2^46)
F_*,46(m,q) = g_*,46(m mod 2^47, q mod 2^47).
```

Every displayed bit is essential.  Pair A and pair B each have 92 essential
free operand bits at column 45 and 94 at column 46.  Each essential coordinate
has an explicit SAT sensitivity witness; higher syntactic coordinates have
UNSAT sensitivity queries or are structurally absent.

Together with H1501, this identifies an exact cancellation: each individual
propagate function needs the operand bit at the boundary column, while their
XOR does not.  The topology defect removes precisely that highest residue bit
from both operands.

## Operand-port swap is not the missing isomorphism

H1503 next exchanges every low operand coordinate on which either compared
function semantically depends.  At each column it tests all four mappings:

```text
A -> A, A -> B, B -> A, B -> B.
```

For every mapping, one SAT query finds swapped operands for which the two
outputs differ, and a second SAT query finds swapped operands for which they
agree.  Thus all eight mappings have `no_constant_xor_relation`: none is
universal equality and none is universal complement.

This rules out the idea that pair A and pair B are merely the same function
seen after exchanging multiplicand and multiplier ports.  The only exact
coordinate action currently known between them remains H1498's internal
PP8..PP11 versus PP12..PP15 quartet swap.

## Claim boundary

The support and port-swap results hold over the complete normalized 67-by-64
Booth domain.  They do not identify which internal quartet orientation, if
either, is implemented in Skylake.  H1488 remains the precommitted direct
orientation vote and remains `FROZEN_UNOPENED`; no closed-form x87 selector is
promoted.

## Artifacts

- `experiments/h1503_propagate_port_swap_audit.py`, SHA-256
  `30cb183a8531eb8de287519fa05ff21c87c9733ca500a89f62d5149bcac94d57`;
- `tmp/ledger33/current/h1503_propagate_port_swap_audit.json`, SHA-256
  `35d4635917439812b0244f9c5a8139574485e3e5c25b2803d2d2a68390aba7e2`;
- H1501 input report, SHA-256
  `5ef2ddd6db82ce204b02b039102ddf5178ed69ab9d956f782845a333888fc610`;
- H1502 input report, SHA-256
  `bcea5f0fcd9dfd6fa9fcc71ca4e952cdb483faafe71894e6b0812a6dee899fe5`.

The report reproduces byte-for-byte.  No x87 instruction ran, no hardware or
private-ledger label was opened, no manifest was created or changed, and no
emulator behavior/default changed.  The academic paper and PDF were not
modified.  R96 remains empirical/incomplete and the authoritative frontier
remains eleven mode rows over ten operands.
