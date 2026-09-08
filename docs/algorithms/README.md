# Reading the numerical programs

Each root instruction source contains its entry policy. Private arithmetic
spells out intermediate widths and rounding destinations. Keep those cuts and
operation order when changing the code: ordinary host arithmetic is not an
interchangeable implementation.

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
