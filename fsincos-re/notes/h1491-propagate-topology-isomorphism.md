# H1491: surviving propagate functions require nonlocal row relabeling

Date: 2026-09-03

Status: exact topology classification over the 28 existing hardware labels;
no physical-wiring identification, selector promotion, hardware execution,
emulator change, or paper/PDF change.

## Question

H1487 proved that the four surviving `final.propagate.-18` spellings are
exactly two Boolean functions. Each spelling uses the same abstract
six-to-three-to-two-to-one 4:2-compressor graph as Figure 7 of US 5,195,051.
H1491 asks whether that isomorphism also preserves the published left-to-right
assignment of partial-product groups, or instead depends on a nonlocal
relabeling of the six first-level compressor outputs.

## Literal published topology

Figure 7 shows six first-level 4:2 compressors. Adjacent first-level outputs
feed three second-level compressors; the first two second-level results feed a
third-level compressor, while the rightmost result is held for the final
compressor. H1491 transcribes that grouping as

```text
((0,1), (2,3), (4,5)), hold branch 2
```

At cut minus eighteen, this literal row-ordered topology disagrees with four
of the 28 existing labels, all in the same direction:

| Row | Mode | Operand | Hardware | Literal topology |
|---|---|---|---:|---:|
| L006 | RN | `3ffc:d269c229b6dbc4b8` | 0 | 1 |
| L007 | RN | `3ffc:d6c4128204d14139` | 0 | 1 |
| L003 | RD | `3ffc:cdb7de45bcbc2dcd` | 0 | 1 |
| X007 | RU | `3ffc:d3bf424dec41fc10` | 0 | 1 |

It is therefore not the exact 28-label selector.

## Exact isomorphism classification

All four H1486 survivors still have zero errors, but none preserves the
six partial-product quartet labels, their linear order, or its reversal:

| Layout | Pairing | First-level order | Crossings | Total displacement |
|---|---|---|---:|---:|
| `pair_02_14_35_hold2` | 02 / 14 / 35 | 0,2,1,4,3,5 | 2 | 4 |
| `pair_02_15_34_hold2` | 02 / 15 / 34 | 0,2,1,5,3,4 | 1 | 6 |
| `pair_03_14_25_hold2` | 03 / 14 / 25 | 0,3,1,4,2,5 | 3 | 6 |
| `pair_03_15_24_hold2` | 03 / 15 / 24 | 0,3,1,5,2,4 | 2 | 8 |

Thus the answer to the representation question is precise:

- as **unlabeled compressor graphs**, each survivor is isomorphic to the
  published tree;
- as **row-labeled or order-preserving graphs**, none is isomorphic;
- obtaining a survivor requires crossed, nonlocal reassignment of the six
  first-level partial-product quartets.

This makes the current representation less naturally supported by the public
80486-era topology, but it is not a proof against later P5 or Skylake wiring.
The patent explicitly identifies the 80486 and marks Figure 7 `PRIOR ART`.
The drawing orders the partial-product arrows visually but does not textually
number every arrow-to-compressor connection.  Later direct P5 die work confirms
the same ten-compressor count without publishing the leaf wiring.  H1491
identifies the exact relabeling assumption; it does not establish a physical
netlist.  See H1499 for the corrected provenance audit.

## Artifacts

- `experiments/h1491_propagate_topology_isomorphism.py`, SHA-256
  `d21814c98461a4bd3dbcf347824fb6de7336f4046357b65c97cfe67cbcc075d5`;
- `tmp/ledger33/current/h1491_propagate_topology_isomorphism.json`, SHA-256
  `154296d8f0d96496c8160f47e505ba7bc627458651f4d2eef7e01d9960b8394d`;
- local source copy `tmp/pdfs/US5195051.pdf`, SHA-256
  `3d83be8935b39383aa4dc6d6409a1085cf477c9c528d40d22e1ec67d298ee09e`.

An independent rerun reproduced the JSON byte-for-byte. No x87 instruction
ran, no private-ledger entry or unopened label was read, H1488 remains
`FROZEN_UNOPENED`, and the academic paper/PDF was not edited. R96 remains
empirical/incomplete and the ledger-free frontier remains eleven mode rows
over ten operands.
