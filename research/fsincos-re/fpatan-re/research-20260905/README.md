# FPATAN source research: provenance, index construction, and verification

Prepared by the side conversation at the user's request on 2026-09-05.
This is a research brief, not a model change or a promotion recommendation.
No hardware, private ledgers, frozen predictions, handoff, or paper were changed.

## Read this before acting

The live session advanced during this research. Its D0024-D0025 note records
261,056 clean prospective V7 observations, 2,419,952 total saved observations,
rejection of the tested reciprocal index constructions, and a certified
lower-tie/odd-tie endpoint equivalence within the candidate graph. See
[the current analysis](../ANALYSIS-D0024-D0025.md). Do not restart that resolved
alias search based on this side conversation's earlier, now-stale status.
The active session's receipts and later notes remain authoritative.

The strongest new reading targets are the Story/Tang compatibility-instruction
paper, Tang/Harrison's integer-rounding patent, and the verification papers.
The already audited Goldmont listing remains more direct structural evidence
than any generic patent. None of these sources establishes the complete
Skylake FPATAN operation semantics or proves V7 against silicon.

## 1. Highest-value algorithm provenance: Story and Tang, ARITH 1999

Shane Story and Ping Tak Peter Tang, *New Algorithms for Improved
Transcendental Functions on IA-64*, ARITH 1999, pp. 4-11.
[DOI](https://doi.org/10.1109/ARITH.1999.762822),
[conference paper PDF](https://www.acsel-lab.com/arithmetic/arith14/papers/ARITH14_Story.pdf).

Read Section 4, PDF page 7, and Section 5, PDF page 8. The authors explicitly
discuss IA-32 compatibility FPATAN on IA-64: magnitude ordering, an initial
quotient plus correction, a direct polynomial below 1/8, and a table-reduced
atan above it. The table residual uses `(v-B*u)/(u+B*v)` and the final result
combines a split atan(B) constant, polynomial correction, and quadrant angle.
The paper also distinguishes measured error from estimated bounds and warns
that directed-rounding results need not bracket the true transcendental.

Use: establish documented Intel algorithm ancestry and compare the producer,
table selection, cancellation, and reconstruction stages.
Limit: IA-64 has FMA and different precision support; its cutoff, coefficient
counts, table spacing, and correction terms differ from the current Skylake
candidate. Do not substitute this algorithm or its claimed error bounds.

## 2. Important non-equivalence: Intel Technology Journal, Q4 1999

John Harrison, Ted Kubaska, Shane Story, and Peter Tang,
*The Computation of Transcendental Functions on the IA-64 Architecture*.
[Author publication page](https://www.cl.cam.ac.uk/~jrh13/papers/itj.html),
[author-hosted PDF](https://www.cl.cam.ac.uk/~jrh13/papers/itj.pdf).

This is a **separate software math-library design**, not the compatibility
FPATAN algorithm in item 1. Table 1 (PDF page 4) gives atan no lookup table;
the Atan subsection (PDF page 6) uses long polynomials and reciprocal-based
reconstruction. The polynomial-scheduling section (PDF pages 4-5) discusses
parallel decomposition and automated schedule exploration.

Use: architectural rationale for non-Horner schedules and a useful warning
against conflating every Intel atan publication with x87 microcode.
Limit: its atan implementation is not a source for the candidate's n/32
table, 64/67-bit operation classes, or lower-tie selection.

## 3. Focused mechanism lead: Tang/Harrison integer-rounding patent

Ping T. Tang and John R. Harrison, US20040254973A1,
*Rounding mode insensitive method and apparatus for integer rounding*;
filed 2003-06-13, published 2004-12-16.
[Patent text](https://patents.justia.com/patent/20040254973),
[alternate record](https://patents.google.com/patent/US20040254973A1/en).

Read paragraphs [0035]-[0045] and claims 1-12. The described construction
adds a carefully chosen bias, clears low bits, and extracts an integer or
subtracts a second bias. Its purpose includes forming table indices without
changing the ambient rounding mode. The worked implementation discusses
Pentium 4 and contrasts its rounding-mode costs with Itanium.

Use: a concrete, independently published family to compare with Goldmont's
float/integer moves, exponent adjustments, masks, and correction operations.
Limit: software/ISA-level mechanism, not a decoded FPATAN micro-operation.
Its existence does not imply the chip uses lower ties, nor rehabilitate a
reciprocal construction rejected by D0024.

Access qualification: Justia's indexed primary patent text exposed the named
paragraphs, claims, and inventor metadata; direct page fetch and the alternate
Google record failed in this pass. No local full-text snapshot is claimed.

## 4. Lower-priority rounding-instruction patent

US20130290685A1, *Floating point rounding processors, methods, systems, and
instructions*, published 2013-10-31; the record shows assignment to Intel in
2014. [Patent text](https://patents.google.com/patent/US20130290685A1/en).

The description accompanying Figure 3 discusses rounding to a specified
number of fractional bits and explicitly names table indexing as a use.
It also describes decoding to lower-level operations.

Use: vocabulary and possible operation-family parallels when classifying
opaque rounding/conversion operations. Limit: a later architectural rounding
instruction disclosure; no FPATAN-specific schedule or connection to the
opaque Goldmont opcodes was found. Rank below item 3 and the actual listing.

## 5. Existing strongest static evidence: pinned Goldmont source and FP-ROM

[Goldmont listing at ffc9070233a6e7a26dbabe723289259f087ee20b](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt)
and [FP-ROM projection at 4237524fe7545c66e42dd986113f220662c06f6a](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt).

These are already inventoried and locally audited, not new discoveries:
[D0021](../ANALYSIS-D0021.md),
[lineage audit](../../goldmont-lineage/README.md).

- Listing SHA256: `46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e`.
- FP-ROM SHA256: `87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db`.
- Relevant control/index block: `U7099..U70c1`.
- Long polynomial: `U70ca..U70e4`; short polynomial: `U6d1e..U6d32`.
- Table-index consumer: `U6d34..U6d35`.

Suggested read-only provenance work: compare other uses of `0x6a7` and
`0x69d` with their producers/consumers; map only semantics actually supported
by those contexts. Public names, register aliases, and a matching constant
projection are not by themselves full numerical definitions. Goldmont is
not Skylake, and the dump exposes only 64 payload bits of each FP-ROM entry.

## 6. Physical constant provenance: Ken Shirriff, January 2025

*Pi in the Pentium: reverse-engineering the constants in its floating-point
unit*. [Original research article](https://www.righto.com/2025/01/pentium-floating-point-ROM.html).

The physical ROM decode supplies atan polynomial and lookup constants. Its
arctangent footnote proposes nearest n/32 table reduction using the tangent
subtraction identity. The author labels the reduction interpretation as a
hypothesis: the physical constants are stronger evidence than a recovered
execution schedule or exact tie rule.

Use: coefficient/table provenance. Limit: P5 physical data is not a proof of
Skylake operation order, operand precision, or rounding. This source and its
local copy were already known; do not count it as independent fresh testing.

## 7. Verification method: Harrison, TPHOLs 2000

John Harrison, *Formal verification of IA-64 division algorithms*,
LNCS 1869, pp. 234-251.
[Author page](https://www.cl.cam.ac.uk/~jrh13/papers/hol00.html),
[author-hosted PDF](https://www.cl.cam.ac.uk/~jrh13/papers/hol00.pdf).

Section 2.3 (PDF pages 6-7) treats exclusion zones around representable values
and rounding midpoints; later sections refine quotient and residual-correction
proofs. The conclusion explicitly retains implementation-validation tests
despite formal proofs, including difficult cases used in the proofs.

Use: a template for independently certifying exact quotient/cut helpers,
identifying difficult rational ratios, and checking underflow separately.
Limit: these theorems concern division under specified arithmetic semantics,
not the full atan approximation. A proof of the candidate's helper still
requires hardware evidence that the helper models the target stage.

## 8. Verification method: Lefevre and Muller, ARITH 2001

Vincent Lefevre and Jean-Michel Muller, *Worst Cases for Correct Rounding of
the Elementary Functions in Double Precision*, ARITH 2001, pp. 111-118.
[DOI](https://doi.org/10.1109/ARITH.2001.930110),
[author-hosted PDF](https://www.vinc17.net/research/papers/arith15.pdf).

The paper reports searches for values near rounding breakpoints, explicitly
limits the covered trigonometric domains, and includes atan cases in Table 11
(PDF page 8). The author's [test-library page](https://www.vinc17.org/research/testlibm/index.en.html)
also warns that inverse-function-derived cases need care when the logarithmic
derivative magnifies the transformation.

Use: methods and seed ideas for hard-rounding challenges, not just uniform
random inputs. Limit: binary64 mathematical-atan cases are not an exhaustive
raw80 two-input FPATAN suite. Target the candidate's retained prevalues and
64-bit output/C1 boundaries; use true atan only as a diagnostic. Apply the
session's local/private and remote one-shot clearance before any capture.

## 9. Alternative design context: Markstein, ARITH 2005

Peter Markstein, *A Fast-Start Method for Computing the Inverse Tangent*.
[Conference paper PDF](https://www.acsel-lab.com/arithmetic/arith17/papers/ARITH17_Markstein.pdf).

Section 2 compares existing reduction schemes, including Story/Tang; Section
3 develops a different scheme using an inverse-square-root and arcsin-based
reduction to overlap arithmetic with table access. The paper includes an
atan2 extension and performance/error analyses.

Use: explain why mathematically equivalent atan representations may differ
in scheduling and intermediate rounding. Limit: an HP/Itanium alternative,
not evidence that Skylake FPATAN uses arcsin or reciprocal square root. Do not
replace a surviving source-guided candidate just because another design is
algebraically attractive.

## 10. Historical lead pending direct scan inspection

Tim Coe, Terje Mathisen, Cleve Moler, and Vaughan Pratt,
*Computational Aspects of the Pentium Affair*, IEEE Computational Science
and Engineering 2(1), pp. 18-30, 1995.
[DOI](https://doi.org/10.1109/99.372929),
[scanned paper](https://people.cs.vt.edu/~naren/Courses/CS3414/assignments/pentium.pdf),
[coauthor's context page](https://boole.stanford.edu/pentium.html).

The physical-ROM article points here for the interaction between FPATAN's
internal division and the old FDIV defect. This is historical P5 material,
not a Skylake defect claim. The web PDF extractor returned no text and did
not expose usable screenshot images; direct inspection is still pending.
No precise FPATAN formula from this scan is asserted here.

## Suggested use by the active session

1. Keep D0024's reciprocal falsifications and D0025's all-input model-level
   alias identity intact; no more lower-versus-odd hardware discrimination
   is warranted under the proven graph.
2. Compare item 1 with the candidate stage by stage, documenting differences
   rather than transferring an IA-64 recipe wholesale.
3. Use items 7-8 to strengthen hard-rounding and quotient-boundary coverage,
   in conjunction with final independent C/library/full-corpus checks.
4. Treat items 3-4 as optional static-opcode provenance leads, not prerequisites
   that expand the completion contract to recovering every physical wire.
5. Keep all unresolved hypotheses in research/handoff material. Nothing in
   this brief authorizes a new selector, default change, or paper claim.
