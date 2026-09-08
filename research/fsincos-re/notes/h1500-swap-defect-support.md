# H1500: exact shifted-row support of the H1498 swap defect

Date: 2026-09-03

Status: **exact radix-8 shift-geometry support; no selector promotion.**

## Question

H1498 proves that each surviving final-propagate function at absolute column
`j` has a tight nine-column cone `j-8..j` on arbitrary compressor inputs.  It
also identifies their disagreement as the swap defect

```text
D_j = pair_A.final.propagate[j] XOR pair_B.final.propagate[j].
```

H1500 asks which coordinates remain genuinely essential after imposing the
physical shift geometry of the 22 radix-8 partial-product rows.

## Model

The experiment reconstructs the same four-level Boolean CSA42 network used by
H1498 for pair A (`pair_02_14_35_hold2`) and pair B
(`pair_03_14_25_hold2`).  Before constructing `D_j`, it imposes:

- partial-product row `r` is zero below absolute column `3*r`;
- the independent negative-row correction routed into row `r+1` may occur at
  column `3*r`;
- the two scaffold compressor inputs are constant in the relevant windows.

Live row payload bits remain independent.  Booth-code selection, common
multiplicand multiples, and the correlation between a row's sign and its
correction bit are deliberately not imposed.  The result is therefore a
universal theorem on the shifted-row superset, not a fit to known operands.

## Exact result

At both target columns, `D_j` has no essential coordinate at relative column
zero.  Its effective support is exactly the eight preceding columns
`j-8..j-1`, and radius eight remains tight.

| `j` | Syntactic live coordinates | Essential (SAT) | Inessential (UNSAT) | Essential PP | Essential corrections |
|---:|---:|---:|---:|---:|---:|
| 45 | 128 | 106 | 22 | 104 | 2 |
| 46 | 131 | 111 | 20 | 108 | 3 |

The essential-coordinate group counts are:

```text
j=45: groups 0/1/2/3 = 31/27/31/17
j=46: groups 0/1/2/3/4 = 31/27/31/21/1
```

At `j=45`, the only essential negate-correction coordinates are rows 14 and
15 at columns 39 and 42.  At `j=46`, those same coordinates remain essential
and row 16's correction at column 45 becomes the sole essential group-4
coordinate.  No group-5 coordinate can reach either defect.

For every syntactic coordinate, the script substitutes its complement while
holding every other Boolean input shared and asks whether `D_j` can change.
SAT is a concrete sensitivity witness; UNSAT proves algebraic irrelevance.
Four additional UNSAT queries prove that both Boolean output words equal an
independently constructed nine-bit bit-vector CSA42 network at both columns.
All queries resolved under Z3 4.15.3.  An independent execution produced the
same JSON byte-for-byte.

## Interpretation and boundary

The pair ambiguity has a smaller exact representation than either propagate
function separately: an eight-column shifted-row circuit whose current-column
payload cancels.  This strengthens the structural answer to the decision-tree
concern, but it still does not identify the Skylake physical quartet
orientation.  The model intentionally over-approximates valid Booth rows, so
it is not yet a closed-form selector over external x87 operands.  H1488
remains the precommitted direct orientation vote and remains
`FROZEN_UNOPENED`.

## Artifacts

- `experiments/h1500_swap_defect_support.py`, SHA-256
  `cb5bcb2146377f21c8340dc3df74ed378c00a07731b8a9874ecd452a7f4cff9b`;
- `tmp/ledger33/current/h1500_swap_defect_support.json`, SHA-256
  `f332ddabd40773eb61399ba073b7dcc47fd089ee726f951394dc5f33c8bfbe16`;
- H1498 input report, SHA-256
  `96a20527c1ff576f1705eabf63cd84aac44b4e0d46fad44175a34b781ffcb721`.

No x87 instruction ran, no hardware or private-ledger label was opened, no
manifest was created or changed, and no emulator behavior/default changed.
The academic paper and PDF were not modified.  R96 remains
empirical/incomplete and the authoritative frontier remains eleven mode rows
over ten operands.
