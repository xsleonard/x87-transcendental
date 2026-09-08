# H1502: product quotient and operand-swap symmetry are rejected

Date: 2026-09-03

Status: **exact negative quotient results; no selector promotion.**

## Question

H1501 proves that the pair-A/pair-B swap defect is exactly a function of the
ordered low-residue pair:

```text
D_j = f_j(m mod 2^j, q mod 2^j),  j in {45,46}.
```

H1502 asks whether this representation is isomorphic to either of two simpler
objects:

1. the ordinary product residue `(m*q) mod 2^j`;
2. an unordered pair of operand residues, which would make `D_j` symmetric
   under exchanging multiplicand and multiplier roles.

## Exact result

Both quotients fail at both columns.

| Column | Same-product/different-`D` query | Swapped-operands/different-`D` query |
|---:|---|---|
| 45 | SAT | SAT |
| 46 | SAT | SAT |

The same-product witnesses are:

| `j` | Left `(m,q,D)` | Right `(m,q,D)` | Shared product residue |
|---:|---|---|---|
| 45 | `400000895e7ffcf83`, `800097ebabfd15d7`, 0 | `400002b666e99f9fb`, `80001f972269ffff`, 1 | `0b9b69540605` |
| 46 | `400005fe7d73d6f47`, `8000a71c2e793eea`, 1 | `40000191ce7572fbd`, `8000e37a8dfb3fde`, 0 | `12d7f9a9e8e6` |

For the swap queries, the right input's low `m` residue equals the left low
`q` residue and vice versa, yet `D` changes.  The report retains both complete
normalized witnesses and their shared product residues.

Therefore ordinary multiplication has discarded information needed to select
between these two carry-save representations.  The defect retains both
factorization information and the asymmetric Booth roles of multiplicand and
multiplier.  It is not merely a function of the exact product bits near the
rounding boundary.

## Proof boundary

Well-definedness on the ordered residue pair is inherited exactly from
H1501: every higher free input bit is individually irrelevant, so any two
high-bit assignments can be connected by a sequence of invariant flips.  A
redundant monolithic two-copy query for the same fact timed out; no inference
is taken from that UNKNOWN.  The new product-collision and swap-collision
queries are SAT and carry explicit witnesses.

This result characterizes the two abstract surviving representations.  It
does not identify which orientation, if either, is present in Skylake.  H1488
remains `FROZEN_UNOPENED`, and no closed-form x87 selector is promoted.

## Artifacts

- `experiments/h1502_defect_quotient_audit.py`, SHA-256
  `93062c70a8048d014cc288134a1d68244b90b377bef89d2eff88612d3d1b7dea`;
- `tmp/ledger33/current/h1502_defect_quotient_audit.json`, SHA-256
  `bcea5f0fcd9dfd6fa9fcc71ca4e952cdb483faafe71894e6b0812a6dee899fe5`;
- H1501 input report, SHA-256
  `5ef2ddd6db82ce204b02b039102ddf5178ed69ab9d956f782845a333888fc610`.

The H1502 report reproduces byte-for-byte.  No x87 instruction ran, no
hardware or private-ledger label was opened, no manifest was created or
changed, and no emulator behavior/default changed.  The academic paper and
PDF were not modified.  R96 remains empirical/incomplete and the authoritative
frontier remains eleven mode rows over ten operands.
