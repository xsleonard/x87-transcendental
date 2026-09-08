# H1499: public multiplier-topology provenance audit

Date: 2026-09-03

Status: **no public source in the audited lineage identifies the H1498
partial-product-quartet orientation; source attribution corrected; no selector
promotion.**

## Question

H1498 proves that the two surviving `final.propagate.-18` functions are one
exact nine-column circuit under the coordinate swap that exchanges the
PP8..PP11 and PP12..PP15 first-level quartets.  The remaining physical question
is whether a public implementation source identifies which quartet occupies
the corresponding middle/held topology in the processor that implements the
observed Skylake behavior.

This audit rechecks the diagrams and surrounding text rather than treating an
unlabeled tree shape as a netlist.

## US 5,195,051: exact shape, no H1498 orientation

The patent explicitly identifies the described processor as the Intel 80486.
Its Figure 7 is itself marked `PRIOR ART`.  The figure shows the exact abstract
shape used by H1491: six first-level 4:2 compressors, three second-level
compressors, one third-level compressor combining the first two branches, and
a final compressor combining that result with the held rightmost branch.

The source does **not** number the 24 individual Figure 7 input arrows.  Figure
8 separately lays out `FM0PP` through `FM21PP` in radix-8 weight order, but it
does not draw or state an arrow-to-Figure-7-leaf correspondence.  Consequently
the patent supports the compressor count and unlabeled graph, not an absolute
PP-quartet assignment and not either H1498 orientation.

This corrects earlier shorthand that called Figure 7 a "public P5 drawing."
H1491's computed classification against the transcribed graph is unchanged;
only the provenance boundary is corrected.

A second high-resolution rendering confirms that the 24 arrows entering the
six first-level compressors carry no row numbers or signal names.  The related
Intel sticky-bit patent, US 5,260,889, incorporates US 5,195,051 and repeats
the 67-by-64 inputs, 22 partial products, and 4:2 tree, but only exposes
trailing-zero/sticky selection around that multiplier.  It adds no
partial-product-to-compressor leaf assignment.

Primary source:
<https://patents.google.com/patent/US5195051A/en>.  Local source copy
`tmp/pdfs/US5195051.pdf`, SHA-256
`3d83be8935b39383aa4dc6d6409a1085cf477c9c528d40d22e1ec67d298ee09e`.
Related primary source:
<https://patents.google.com/patent/US5260889A/en>.

## P5 evidence: the same count, still no leaf map

Ken Shirriff's direct die reverse engineering of the original Pentium (P5)
independently identifies radix-8 multiplication with 22 terms and a tree of
ten 4:2 carry-save adders.  That is positive P5 provenance for the broad
arithmetic shape.  The published work explicitly leaves the full multiplier
for a future article and supplies no PP0..PP21-to-compressor connectivity.
It therefore cannot choose pair A or pair B.

Source: <https://www.righto.com/2025/03/pentium-multiplier-adder-reverse-engineered.html>.

## P6 evidence: public verification omits the gate topology

Intel's Q1 1999 article, *Formerly Verifying IEEE Compliance of Floating-Point
Hardware*, reports formal verification of the Pentium Pro floating-point
execution unit against its gate-level design.  Its public FMUL Figure 2 exposes
only the algorithmic `MPY -> RND` boundary and sticky output, not the internal
partial-product tree.

The article also reports that when the structural FMUL proof was ported to a
new processor generation, microarchitectural changes forced many low-level
properties to be modified.  That is affirmative evidence against silently
transporting an 80486 or P5 row map into later P6-family or Skylake silicon.
The underlying gate-level netlist used by Intel's verification is not
published in the article.

Primary source: <https://www.intel.com/content/dam/www/public/us/en/documents/research/1999-vol03-iss-1-intel-technology-journal.pdf>.
Local source copy `tmp/pdfs/intel-technology-journal-1999-q1.pdf`, SHA-256
`65a461af7650a0945acfa72e362f39de8a93f34d9f480d850f14b3629d3a9f02`.

## US 6,615,229: detailed radix-4 example, hypothetical radix-8 extension

Intel US 6,615,229 gives a fully numbered, partitioned 33-partial-product
radix-4 Wallace tree.  Its text then says a 64-bit radix-8 version generating
22 partial products and having seven CSAs in the critical path is
"contemplated."  The drawings remain the 33-row radix-4 implementation; the
patent supplies no 22-row radix-8 connectivity and no relationship to the
Skylake x87 multiplier.

It is therefore useful evidence that Intel used materially different
partitioned tree organizations, but it cannot instantiate the H1498 swap.

Primary source: <https://patents.google.com/patent/US6615229B1/en>.  Local
source copy `tmp/pdfs/US6615229.pdf`, SHA-256
`0e51dd343974ba2e3ec60f2b761add6b3012a15b96aa5957723fda9a6f3c90af`.

## Conclusion

The public evidence separates three claims that had been conflated:

1. The six-to-three-to-two-to-one 4:2 graph is documented for the 80486-era
   design and the same ten-compressor count is independently observed on P5.
2. No audited source publishes the absolute 22-row leaf assignment required
   to evaluate H1498's PP8..PP11 versus PP12..PP15 orientation.
3. Intel's own P6 verification report warns, by direct experience, that FMUL
   structural properties changed across processor generations.

Accordingly, documentary provenance cannot promote pair A, pair B, or the
literal row-ordered patent topology.  H1488 remains the only frozen direct
orientation vote and remains `FROZEN_UNOPENED`.  Even an H1488 survivor would
be a fresh finite hardware validation of one exact representation, not a
global proof of the final R59 selector.

No x87 instruction ran, no hardware or private-ledger label was opened, no
manifest changed, and no emulator behavior/default or academic paper/PDF was
modified.  R96 remains empirical/incomplete and the authoritative frontier
remains eleven mode rows over ten operands.
