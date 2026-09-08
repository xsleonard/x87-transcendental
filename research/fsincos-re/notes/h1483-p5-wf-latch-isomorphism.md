# H1483: P5 X2-to-WF latch-isomorphism audit

Date: 2026-09-03

Status: no tested group-generate/propagate, conditional-carry,
carry-select-sum, or P5-prefix signal is functionally identical to R1475.
R1475 remains label-selected and default-off; H1477 remains unopened.

## Question

US 5,195,051 says that the X2 stage reduces the 22 Booth partial products to
131-bit sum and carry vectors, partially adds their upper 129 bits to form
group generate/propagate terms, and latches those terms for the WF-stage
summation.  It also describes a four-bit carry-select last stage:

<https://patents.google.com/patent/US5195051A/en>

H1479 had already excluded individual compressor-node and final-CPA bits as a
single-signal representation of R1475, but it did not enumerate the grouped
and conditional signals explicitly forwarded from X2 to WF.  H1483 fills that
bounded gap.

## Search

For each of the seventy arithmetic-exact P5 compressor-tree layouts retained
by H1400, H1483 reconstructs 898 Boolean features:

- group generate, propagate, carry-out for assumed carry zero and one,
  actual carry-in, and selected carry-out;
- all four conditional sum bits for both assumed carries in each four-bit
  carry-select block;
- four-, eight-, and sixteen-bit groups under P5-column, absolute-column, and
  retained-cut alignments; and
- P5-origin prefix generate/propagate and conditional-carry states around the
  retained cut.

Complements are included, for 125,720 single literals.  The truth rows are the
sixteen cached H1472 hardware labels and the established d0d0/d800 anchors.
The 22 disjoint H1476 rows are not hardware labels; their R1475 values are used
only as a functional counterexample wall.

## Result

Thirty literals fit all eighteen known labels.  None is the R1475 function:
24 fail on 13 of the 22 disjoint rows, and six fail on 14.  There are zero
exact single-signal aliases over the combined forty rows.

On the already-frozen H1477 operands, the thirty aliases collapse to four
prediction patterns.  All four were already among H1480's five precommitted
alternate-tree classes; H1483 introduces no new H1477 class.  H1480's fifth
class, `0010100001`, simply has no H1483 member.  R1475's prediction remains
the distinct vector `1100111001`.

This excludes a direct identification of R1475 with any signal in the tested
X2-to-WF grouped-state family.  It does not exclude arbitrary combinational
logic in X2, a grouping or signal outside this bounded reconstruction, or
undocumented state.  It does not validate R1475.

## Artifacts

- `experiments/h1483_p5_wf_latch_isomorphism.py`, SHA-256
  `461df61d1c6e38b98d398498698bc1ea0fa4aefafe6b822c476a5510c3f0c750`;
- `tmp/ledger33/current/h1483_p5_wf_latch_isomorphism.json`, SHA-256
  `b4dc343189b77163d7867b9e21b4739780f54e58e42deb89d7781366c56568d2`.

An independent rerun reproduced the report byte-for-byte.  No x87 instruction
ran, no private ledger or H1477 label was opened, and no emulator default or
academic paper/PDF changed.
