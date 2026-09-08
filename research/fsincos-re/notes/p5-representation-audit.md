# P5 multiplier/compressor representation audit

Date: 2026-09-02

## Result

No transferable closed-form carry recurrence was found.  Arithmetic-
isomorphic P5 layouts can fit all nine current R59-selector operands, but
every such fit fails existing cached controls and/or already-frozen one-shot
adversaries.  This is negative evidence against the tested representation
family, not proof that the physical Skylake netlist has been identified or
that no other compact recurrence exists.

The result does not change the standing model boundary.  R1158 and R1378
remain the strongest structural recurrences.  R96 remains an empirical,
incomplete selector, and the ledger-disabled full suite still has 11 failing
mode/operand rows over ten operands: nine R59-selector operands plus d0d0 in
RD and RZ.

## Audit design

`experiments/h1400_p5_representation_audit.py` enumerates 255 bounded,
physically plausible alternatives around the public P5 patent transcription.
The census is factorized as one-axis perturbations, not the full Cartesian
product and not a claim to exhaust every possible layout:

- all 45 pair/held-branch choices for the six first-level compressor outputs;
- natural and five alternate first-level row groupings;
- uniform, stage-local, and rotating distinguished-D placements in the four
  4:2 levels;
- Booth negative correction in the following row, source row, one correction
  bus, or split correction buses;
- all 24 first-level slots for the square's external low radix-8 digit, plus
  post-tree 3:2/4:2, add-to-sum/add-to-carry, and materialized-core/full-product
  merges;
- stage widths 127 through 136; and
- carry endpoints one column below, at, or one column above the normalized
  product cut, with absolute, P5-column-2, or cut-relative reset alignment.

Every representation was subjected to an arithmetic gate before its hardware
labels were mined.  The gate checked deterministic edge cases and all 37,556
cached rows, requiring the final redundant words to sum to the exact product.
The rows comprise nine targets, 34,464 carry-constraining controls, 2,977 neutral
controls, and 106 prior Q/QX adversarial pairs.  No x87 instruction or
hardware capture was executed.

The mined recurrence is deliberately more permissive than a literal final
CPA: widths 1--64, fixed reset zero/one, three alignments, three normalization
attachments, and eight fixed direct/set/drop/toggle projections.  It contains
no operand identity, operand threshold, cell table, or learned boundary.

## Arithmetic gate

249/255 representations reconstructed exact arithmetic.  Six were rejected
before label mining:

- square-tree stage widths 127--130 lose exact product bits;
- normalizing/chopping the 67-bit core before the low-digit merge loses the
  discarded core tail; and
- chopping the full square to 67 bits likewise fails exact reconstruction.

Widths 131--136 are exact for the 67x64 core because its full product fits
131 bits; the subsequent three-bit square attachment preserves the complete
134-bit square.  Alternative correction routing, compressor ordering and
grouping, and exact low-digit merges all remained arithmetic-isomorphic, as
required.  They produced many different redundant encodings, so exact
arithmetic alone does not select a physical layout.

## Carry-recurrence wall

The nine targets admitted 11,937 raw target-exact aliases (4,696 recurrence
equivalence classes were scored).  This large multiplicity is itself a
warning: the remaining operands are too small a set to identify a physical
representation.

No scored equivalence class was exact on the combined target, control, and
adversarial wall.  The best target-exact alias used a QX post-tree 4:2 merge
with the low digit in distinguished slot 2, an endpoint one column above the
normalized cut, a 16-column cut-relative recurrence seeded with carry one,
and a fixed XOR projection.  It repaired 9/9 targets but contradicted 13,675
carry-constraining cached controls and 75/106 adversarial pairs.  It is a
small-set alias, not a candidate mechanism.

This agrees with the stronger prior blind falsifiers.  The long-propagate QX
hypothesis lost 31/31 fresh pairs to the incumbent (4/4 at the first minimum
and 27/27 at the stronger minimum); the distinct pre-low-digit Q hypothesis
lost 75/75.  Those captures were each performed once per fresh mode/operand
pair after their manifests were frozen.  h1400 only reuses their cached
labels.

## Separately tracked d0d0 row

d0d0 RD/RZ is not evidence for the R59 carry recurrence above.  Disabling
R1270 changes its hard-3x merge from the rounded-up `rd3` word back to the
pre-merge word and fixes both modes.  The natural R1382 interpretation—attach
R1270/R1272 only when the fourth-product normalization has `s4=67`—also
preserves the cached d800 repair, changes none of the 398 direct high-q legs,
none of the 56,393,031 stage-A rows, none of the 51,229 lower-binade legs, and
none of the 2,151 frozen lower-boundary legs.

That is still not transferable closure.  Software scans over a contiguous
4,294,967,295-input neighborhood and 64 disjoint 200,000,001-input strata
(12,800,000,064 more inputs) found no fresh architectural current/candidate
separator to freeze.  This is evidence of sparsity, not validation of the
`s4=67` attachment.  R1382 therefore remains default off and should continue
to be described as an unvalidated boundary refinement.

## Artifacts and claim boundary

- Reproducer: `experiments/h1400_p5_representation_audit.py`
- Machine-readable report: `tmp/ledger33/current/h1400_p5_representation_audit.txt`
- Report SHA-256: `861fb3c62d3bb96571320927bcd682547ca431f1b97cfe9a306741b3892bebf1`

The audit falsifies the enumerated one-axis P5 representations paired with
the stated fixed-width recurrence grammar.  It does not justify promoting a
new selector, changing the emulator, or taking another hardware sample.
Further hardware work would require a software-frozen separator that
distinguishes a new arithmetic mechanism from the incumbent; none is
currently available.
