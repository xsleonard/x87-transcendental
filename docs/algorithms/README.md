# Reading the numerical programs

Each root instruction source contains its entry policy. Private arithmetic
spells out intermediate widths and rounding destinations. Keep those cuts and
operation order when changing the code: ordinary host arithmetic is not an
interchangeable implementation.

Use the [code documentation guideline](../code-documentation-guidelines.md)
when reading or updating production comments. It gives repository examples of
mathematical explanations, finite-precision contracts, boundaries and provenance.

| Family | Current program | Preserved derivation |
| --- | --- | --- |
| FSIN/FCOS | `src/trig/standalone_polynomial.c`, `table.c`, `tiny.c`, `reduce.c` | [Trig pseudocode](../../research/fsincos-re/docs/TRIG-PSEUDOCODE.md) |
| FSINCOS | `src/trig/paired_polynomial.c`, shared table/tiny/reducer | [Paired correction](../../research/fsincos-re/notes/h1717-policy2-promotion.md) |
| FPTAN | `src/fptan.c` | [Sibling pseudocode](../../research/fsincos-re/docs/SIBLING-PSEUDOCODE.md) |
| F2XM1 | `src/f2xm1.c` | [Storage correction](../../research/fsincos-re/docs/verification-expansion/f2xm1-integration.md) |
| FPATAN | `src/fpatan.c` | [Algorithm](../../research/fsincos-re/fpatan-re/ALGORITHM.md) |
| FYL2X/FYL2XP1 | `src/log/logarithm.c` | [Algorithm](../../research/fsincos-re/fyl2x-re/ALGORITHM.md) |

Standalone multiply truncates its X and Y input ports to 67 and 64 bits,
respectively. Its two interleaved coefficient chains differ from the paired
FSINCOS Horner schedule, whose products each undergo CHOP67 before RN64 addition.
The table's RN64 product is rounded from the exact port product. Reduction uses
exact division by the preserved 66-bit pi/2 constant.

The arctangent and logarithm files share exact finite values, explicitly rounded
operations and raw80 encoding in `src/arithmetic/finite.c`. FPATAN retains its
final sum until architectural quantization; logarithms retain their exact final
product. Their different tininess/exception policies remain in the instruction
kernels. See [bounds and rounding](../finite-arithmetic.md).

The source archive carries standalone algorithm descriptions in this directory;
the links above additionally connect a full checkout to the historical evidence.

The local walkthroughs cover [trigonometry](trig.md), [FPTAN and F2XM1](siblings.md),
[FPATAN](fpatan.md), and [logarithms](logarithms.md). Implementation comments
explain the numerical reasoning in place; the evidence map below preserves the
supporting derivations and tests without requiring source readers to follow links.
The [validation record](../validation.md) describes the current scope. Historical
acceptance documents retain their original scope and may describe older APIs.

| Numerical choice | Supporting evidence and its scope |
| --- | --- |
| Trig reduction and polynomial operand widths | The [residual-grid argument](../../research/fsincos-re/notes/h1627-h1629-polynomial-domain-transfer.md) bounds the significand widths reachable after reduction and explains which operand cuts can discard bits. The [shared polynomial study](../../research/fsincos-re/notes/h1630-h1632-shared-polynomial.md) gives the two coefficient chains and distinct sine/cosine terminals. The [standalone integration record](../../research/fsincos-re/notes/h1707-h1708-standalone-promotion.md) checks the combined dispatch without changing the paired schedule. |
| Trig table and tiny paths | The [table study](../../research/fsincos-re/notes/h1633-h1635-shared-table.md) shows that inserting a 67-bit chop before the RN64 product changes retained results and C1. The [tiny-path study](../../research/fsincos-re/notes/h1638-h1643-tiny-and-remaining-scope.md) tests the predecessor rule and the separate direct-input bypass. The paired correction linked above records why earlier FSINCOS product cuts also matter. |
| FSINCOS special-result C1 | [Retained state rows A008–A013](../../research/fsincos-re/tmp/ledger33/current/h1401_single_shot/raw-state-output.txt) begin with C1=0 and end with C1=0. They support that endpoint for the recorded prestates; they do not establish behavior for incoming C1=1. |
| FPTAN internal states and final quotient | The [reconstruction study](../../research/fsincos-re/notes/fptan-reconstruction.md) records the operation-class tests for chopped products/subtractions, RN64 additions, and the sine-state precision cut before division. These internal states differ from public FSIN/FCOS results. |
| F2XM1 mixed precision | The [reconstruction study](../../research/fsincos-re/notes/f2xm1-reconstruction.md) explains the 67-bit chopped products, RN64 ordinary sums and selected RN64 products, including h254's operation-class search and h258's rejection of neighboring schedules. Its later addenda and the storage correction linked above qualify the earlier NaN and subnormal-store limitations. |
| FPATAN table midpoint ownership | The [midpoint failure analysis](../../research/fsincos-re/fpatan-re/ANALYSIS-D0022.md) isolates discrepancies at the exact ratio 19/64. The [selector tests and alias proof](../../research/fsincos-re/fpatan-re/ANALYSIS-D0024-D0025.md) support the lower-tie rule while showing why lower and odd-index ties are output-equivalent within this graph. |
| FPATAN operation order and rounding | The [source-guided polynomial study](../../research/fsincos-re/fpatan-re/ANALYSIS-D0021.md) motivates interleaved coefficient chains and distinct operation classes; its full candidate was later corrected at table midpoints. The [final-rounding challenge and delivery record](../../research/fsincos-re/fpatan-re/ANALYSIS-D0026-D0027.md) and [acceptance audit](../../research/fsincos-re/fpatan-re/ACCEPTANCE.md) document the corrected program's retained and prospective tests. |
| Logarithm constants and operation classes | The [source audit](../../research/fsincos-re/paper/evidence/logarithm-public-source-audit.json) derives four corrected table words and checks exposed significand projections against another public ROM. The [operation comparisons](../../research/fsincos-re/paper/evidence/logarithm-operator-ablations.json) record differences for seven alternative rounding schedules. The [acceptance record](../../research/fsincos-re/fyl2x-re/ACCEPTANCE.md) separates corrected regression evidence from prospective validation. |

These records support numerical choices within their stated bounds. Agreement
on retained observations does not establish every-input equivalence or recover
physical circuit details.
