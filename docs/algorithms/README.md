# Reading the numerical programs

Start with an instruction's pseudocode to see its numerical steps, then follow
the C implementation. The walkthroughs explain the mathematics, branch choices
and rounding operations. Python specifications use exact fractions and explicit
precision cuts; the C implementations use integer arithmetic.

| Instruction | Pseudocode | C implementation | Walkthrough |
| --- | --- | --- | --- |
| FSIN | [Sine/cosine](trig.md) | [sin_cos.c](../../src/trig/sin_cos.c) | [Reduction and approximation](trig.md) |
| FCOS | [Sine/cosine](trig.md) | [sin_cos.c](../../src/trig/sin_cos.c) | [Reduction and approximation](trig.md) |
| FSINCOS | [Paired sine/cosine](trig.md) | [sincos.c](../../src/trig/sincos.c) | [Reduction and approximation](trig.md) |
| FPTAN | [Executable Python](../../tests/reference/sibling_reference.py) | [fptan.c](../../src/fptan.c) | [Tangent and exponential](siblings.md) |
| F2XM1 | [Executable Python](../../tests/reference/sibling_reference.py) | [f2xm1.c](../../src/f2xm1.c) | [Tangent and exponential](siblings.md) |
| FPATAN | [Arctangent](../../tests/reference/fpatan.md) | [fpatan.c](../../src/fpatan.c) | [Arctangent](fpatan.md) |
| FYL2X | [Executable Python](../../tests/reference/log_reference.py) | [logarithm.c](../../src/log/logarithm.c) | [Logarithms](logarithms.md) |
| FYL2XP1 | [Executable Python](../../tests/reference/log_reference.py) | [logarithm.c](../../src/log/logarithm.c) | [Logarithms](logarithms.md) |

## Following the C code

The C links lead to the numerical implementations. Each root instruction source
also contains its public entry policy; [SOURCE.md](../../SOURCE.md) maps those
entry points and the shared helpers. Private arithmetic spells out intermediate
widths and rounding destinations. Keep those cuts and operation order when
changing the code: ordinary host arithmetic is not an interchangeable implementation.

Each trig evaluator presents classification, one argument reduction and the
tiny/polynomial/table choice in order. Its polynomial follows in the same file.
Shared precision operations live in [wide.c](../../src/arithmetic/wide.c).

For tangent, start at `x87t_internal_fptan_core`; for the exponential, start at
`x87t_internal_f2xm1_core`. Their polynomial, table and final-rounding helpers
are in the same respective files. For arctangent, `fpatan_candidate` computes
the finite angle and `x87t_fpatan` handles the public instruction contract.
For both logarithm instructions, `logarithm` computes the retained logarithm
and `x87t_internal_evaluate_log` applies the operand policy, final multiplication
and result handling.

FSIN/FCOS multiplication truncates its X and Y input ports to 67 and 64 bits,
respectively. Its two interleaved coefficient chains differ from the paired
FSINCOS Horner schedule, whose products each undergo CHOP67 before RN64 addition.
The table's RN64 product is rounded from the exact port product. Reduction uses
exact division by the preserved 66-bit pi/2 constant.

The arctangent and logarithm files share exact finite values, explicitly rounded
operations and raw80 encoding in `src/arithmetic/finite.c`. FPATAN retains its
final sum until architectural quantization; logarithms retain their exact final
product. Their different tininess/exception policies remain in the instruction
kernels. See [bounds and rounding](../finite-arithmetic.md).

Use the [code documentation guideline](../code-documentation-guidelines.md)
when updating numerical explanations. The source archive includes the pseudocode,
walkthroughs and C programs linked above.

## Supporting evidence

The [validation record](../validation.md) describes the current checks and their
scope. The evidence map below links the supporting numerical studies. Historical
acceptance documents retain their original scope and may describe older APIs.

| Numerical choice | Supporting evidence and its scope |
| --- | --- |
| Trig reduction and polynomial operand widths | The [residual-grid argument](../../research/fsincos-re/notes/h1627-h1629-polynomial-domain-transfer.md) bounds the significand widths reachable after reduction and explains which operand cuts can discard bits. The [shared polynomial study](../../research/fsincos-re/notes/h1630-h1632-shared-polynomial.md) gives the two coefficient chains and distinct sine/cosine terminals. The [standalone integration record](../../research/fsincos-re/notes/h1707-h1708-standalone-promotion.md) checks the combined dispatch without changing the paired schedule. |
| Trig table and tiny paths | The [table study](../../research/fsincos-re/notes/h1633-h1635-shared-table.md) shows that inserting a 67-bit chop before the RN64 product changes retained results and C1. The [tiny-path study](../../research/fsincos-re/notes/h1638-h1643-tiny-and-remaining-scope.md) tests the predecessor rule and the separate direct-input bypass. The [paired correction](../../research/fsincos-re/notes/h1717-policy2-promotion.md) records why earlier FSINCOS product cuts also matter. |
| FSINCOS special-result C1 | [Retained state rows A008–A013](../../research/fsincos-re/tmp/ledger33/current/h1401_single_shot/raw-state-output.txt) begin with C1=0 and end with C1=0. They support that endpoint for the recorded prestates; they do not establish behavior for incoming C1=1. |
| FPTAN internal states and final quotient | The [reconstruction study](../../research/fsincos-re/notes/fptan-reconstruction.md) records the operation-class tests for chopped products/subtractions, RN64 additions, and the sine-state precision cut before division. These internal states differ from public FSIN/FCOS results. |
| F2XM1 mixed precision | The [reconstruction study](../../research/fsincos-re/notes/f2xm1-reconstruction.md) explains the 67-bit chopped products, RN64 ordinary sums and selected RN64 products, including h254's operation-class search and h258's rejection of neighboring schedules. Its later addenda and the storage correction linked above qualify the earlier NaN and subnormal-store limitations. |
| FPATAN table midpoint ownership | The [midpoint failure analysis](../../research/fsincos-re/fpatan-re/ANALYSIS-D0022.md) isolates discrepancies at the exact ratio 19/64. The [selector tests and alias proof](../../research/fsincos-re/fpatan-re/ANALYSIS-D0024-D0025.md) support the lower-tie rule while showing why lower and odd-index ties are output-equivalent within this graph. |
| FPATAN operation order and rounding | The [source-guided polynomial study](../../research/fsincos-re/fpatan-re/ANALYSIS-D0021.md) motivates interleaved coefficient chains and distinct operation classes; its full candidate was later corrected at table midpoints. The [final-rounding challenge and delivery record](../../research/fsincos-re/fpatan-re/ANALYSIS-D0026-D0027.md) and [acceptance audit](../../research/fsincos-re/fpatan-re/ACCEPTANCE.md) document the corrected program's retained and prospective tests. |
| Logarithm constants and operation classes | The [source audit](../../research/fsincos-re/paper/evidence/logarithm-public-source-audit.json) derives four corrected table words and checks exposed significand projections against another public ROM. The [operation comparisons](../../research/fsincos-re/paper/evidence/logarithm-operator-ablations.json) record differences for seven alternative rounding schedules. The [acceptance record](../../research/fsincos-re/fyl2x-re/ACCEPTANCE.md) separates corrected regression evidence from prospective validation. |

These records support numerical choices within their stated bounds. Agreement
on retained observations does not establish every-input equivalence or recover
physical circuit details.
