# H1496: fresh boundary-carry adversarial surface

Date: 2026-09-03

Status: **63 fresh software separators; balanced eight-row structural wall;
the selected wall was later opened as H1566 and falsifies pair A; no selector
promotion.**

## Purpose

H1495 proves that each of H1487's two surviving functions is an exact
lower-residue boundary carry for one arithmetic-exact final carry-save pair.
That identity applies over every normalized 67-by-64-bit product, but it does
not identify which carry-save pairing, if either, exists in Skylake. H1496
therefore constructs an independent adversarial surface rather than fitting
another predicate to the 28 known labels.

The H1470 exact modular-lattice scanner was rebuilt from current source and
run for 30,000,000 deterministic plateau samples with new seed
`0x4f1bbcdc676e4f35`. Operands present in the H1471, H1476, or H1485 banks,
the H1486 report, and the established d0d0/d800 anchors were excluded before
model evaluation. A repository-wide fixed-string audit found zero remaining
collisions before the report was written.

## Exact replay and observed software surface

The scan produced 123 exact external preimages. Independent current-source
incumbent and default-off R1382 builds classify 63 as architectural endpoint
separators and 60 as endpoint-invisible. Every retained row passes:

- both chopped-square inverse equalities;
- exact right-product low-72-bit replay;
- the required `s4=66`, `theta=0`, `low3=3` parent state;
- H1487's within-pair equalities; and
- H1495's closed form separately for all four final pairs:

```text
selector_j = bit_j(exact_product)
             XOR (((S mod 2^j) + (C mod 2^j)) >= 2^j)
```

Across all 63 visible rows, the pair-A/pair-B selector patterns are:

| Pattern | Rows |
|---|---:|
| `0000` | 35 |
| `0011` | 2 |
| `1100` | 5 |
| `1111` | 21 |

Thus both disagreement directions occur out of sample. The two `0011` rows
are the limiting stratum. H1496 selects two rows from each of the four
patterns, producing an eight-row wall with pair A balanced 4/4 and pair B
balanced 4/4. It includes three RD, one RN, and four RU tuples. The selector
patterns, exact product bits, lower-residue carries, carry-save residues,
Booth digits, and compact terminal state are retained in the JSON so later
work can challenge the representation without reconstructing the selection.

## Boundary and consequence

All 63 visible rows use absolute target column 46 and the same compact R1382
control state. The selected rows contain seven exact-product-bit ones and one
zero; their pair-A and pair-B boundary carries are each split five zeros to
three ones. H1496 therefore does not supply the other generally possible
column 45 or a balanced exact-product-bit sample. That is a limitation of
this endpoint-visible R1382 lattice, not evidence that column 45 is globally
unreachable.

No x87 instruction ran, no hardware label was read, and the private
supplemental ledger was not needed because no capture manifest was frozen.
H1488 remains the already precommitted `FROZEN_UNOPENED` hardware
discriminator. H1496 does not validate either physical-pair hypothesis and
does not justify an emulator change. The paper/PDF remains untouched, R96
remains empirical/incomplete, and the authoritative ledger-free frontier
remains eleven mode rows over ten operands.

## Artifacts

- `experiments/h1496_boundary_carry_adversarial_surface.py`, SHA-256
  `c0f225b1000f2338840682ef41eb35c27e398fa4ff16d49b0f3374823d363c29`;
- `tmp/ledger33/current/h1496_boundary_carry_adversarial_surface.json`,
  SHA-256
  `1fdb66d79e32602afe64f7026155ffe224b7672d141155135c2f9ee1f213d773`.

An independent rerun at `/tmp/h1496-rerun2-20260903.json` is byte-identical
to the repository report. The failed first reproducibility attempt reached
the final collision guard and stopped because the newly written repository
report itself contained all 63 operands; the narrow `--collision-exclude`
option exists only to exclude that prior copy on a reproducibility run.

Postscript: H1566 froze the unchanged selected eight-row wall after a fresh
repository/private-ledger audit and opened it exactly once on the Skylake Xeon
oracle.  H1567 scores pair A 6/8 and pair B 4/8, with zero other endpoints.
The raw result and claim boundary are in
`notes/h1566-h1567-pair-a-adversarial.md`.
