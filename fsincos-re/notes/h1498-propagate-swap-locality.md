# H1498: canonical swap-local form of the surviving propagate functions

Date: 2026-09-03

Status: **exact structural isomorphism; physical quartet orientation remains
unresolved; no selector promotion.**

## Result

The four H1487 layouts are not four unrelated formulas.  They are the orbit
of one canonical 4:2-compressor template under two first-level quartet swaps.
Using the canonical layout `pair_02_14_35_hold2`:

| Coordinate action | Resulting layout |
|---|---|
| identity | `pair_02_14_35_hold2` |
| swap quartets 4 and 5 | `pair_02_15_34_hold2` |
| swap quartets 2 and 3 | `pair_03_14_25_hold2` |
| both swaps | `pair_03_15_24_hold2` |

Four QF_BV counterexample queries are UNSAT for arbitrary 24-word compressor
inputs, not merely Booth products or known labels.  Each transformed template
reconstructs both final redundant output words of the named layout exactly.

H1487 supplies the quotient on the normalized 67-by-64-bit Booth domain at
absolute columns 45 and 46:

- the quartet-4/5 action is trivial there (UNSAT within pair A and within
  pair B);
- the quartet-2/3 action is nontrivial (SAT across pair A and pair B).

Thus the two surviving functions are one function in two coordinate
orientations: whether the PP8..PP11 or PP12..PP15 first-level quartet occupies
the corresponding middle/held topology.

## Exact local cone

A CSA3 carry moves information upward by one column.  Each reconstructed
CSA42 is two serial CSA3s, so one tree level can move information upward by at
most two columns.  There are four CSA42 levels.  H1498 proves the resulting
bound directly rather than relying only on that argument:

```text
F_j depends only on physical compressor-input columns j-8 through j.
```

All eight counterexample queries—four layouts at `j=45` and `j=46`—are
UNSAT for arbitrary 64-bit input words.  SAT witnesses for representatives of
both pair A and pair B show that replacing the nine-column window by
`j-7..j` can change the output at `j=45`; radius eight is tight on the
unconstrained compressor-input domain.

This is an exact finite gate cone, not an operand decision tree.  The apparent
globality of H1495's lower-residue carry is a consequence of representing the
same local propagate bit through the final binary sum.

H1500 subsequently imposes the radix-8 row shifts on the swap defect itself.
It proves that the common current-column payload cancels: `D_j` has exact
support only in `j-8..j-1`, with radius eight still tight on that shifted-row
superset.

H1501 then imposes the complete normalized Booth constraints and gives the
operand-residue isomorphism `D_j=f_j(m mod 2^j,q mod 2^j)` at `j=45,46`.
Every bit of both low residues is individually essential on that domain.

## Swap-defect form

Let `F_A,j(x)` be the canonical template's propagate bit and let `sigma`
exchange first-level quartets 2 and 3.  Then

```text
F_B,j(x) = F_A,j(sigma(x))
D_j(x)   = F_A,j(x) XOR F_A,j(sigma(x))
         = F_A,j(x) XOR F_B,j(x).
```

At both absolute columns, six further QF_BV queries prove:

1. `D_j` is invariant under applying `sigma` again;
2. `D_j=0` whenever the two exchanged quartets are equal;
3. because both final redundant pairs preserve the same total, `D_j` equals
   the XOR of their two H1495 lower-residue boundary carries.

Therefore pair disagreement is exactly a local nine-column swap defect.  It
is not an independently fitted classifier and needs no operand constants.

## Evidence reconciliation

- All 28 hardware-labeled H1486 rows have `D=0`: fourteen pattern `0000` and
  fourteen `1111`.  They validate the common function value but cannot reveal
  quartet orientation.
- H1496's 63 fresh software rows contain seven `D=1` cases and 56 `D=0`
  controls.  Its selected eight-row wall is balanced four/four.
- The unchanged H1488 freeze contains exactly two `D=1` pair discriminators
  and four `D=0` unanimous controls.  It remains `FROZEN_UNOPENED`.

The theorem covers these finite banks a priori; the counts document why the
opened labels do not choose an orientation and why the two unopened H1488
rows would.

## Claim boundary

H1498 gives the requested alternative representation: the two functions are
one exact local circuit under a named PP-quartet coordinate swap.  It does not
identify which quartet is physically wired to the held branch in Skylake.
The public 80486-era drawing and the available P5/P6 descriptions still lack
the absolute row-to-input mapping needed to choose that orientation, and the
unopened H1488 labels are not inferred.  See H1499 for the provenance audit.

## Artifacts

- `experiments/h1498_propagate_swap_locality.py`, SHA-256
  `bad2ec071a73fc4091adf2254764d4a45cb04ea2f2d805c541f9ac18ea0e25fd`;
- `tmp/ledger33/current/h1498_propagate_swap_locality.json`, SHA-256
  `96a20527c1ff576f1705eabf63cd84aac44b4e0d46fad44175a34b781ffcb721`.

Z3 4.15.3 discharged 18 UNSAT obligations; two tightness queries are SAT.
The report reproduces byte-for-byte.  No x87 hardware ran, no hardware or
private-ledger label was opened, no manifest was created or changed, and no
emulator behavior/default changed.  The academic paper and PDF were not
modified.  R96 remains empirical/incomplete and the authoritative frontier
remains eleven mode rows over ten operands.
