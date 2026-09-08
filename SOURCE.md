# Library source map

The public interface is [x87trans.h](include/x87trans/x87trans.h). Build the single
`x87trans` target and link it from callers; no source inclusion or mode defines
are needed. All numerical changes belong in the files below.

| Instruction | Entry file | Main shared implementation |
| --- | --- | --- |
| FSIN | [fsin.c](src/fsin.c) | [Sine/cosine evaluator and polynomial](src/trig/sin_cos.c), selected with `TRIG_SINE` |
| FCOS | [fcos.c](src/fcos.c) | [Same evaluator and polynomial](src/trig/sin_cos.c), selected with `TRIG_COSINE` |
| FSINCOS | [fsincos.c](src/fsincos.c) | [Paired evaluator and polynomial](src/trig/sincos.c) |
| FPTAN | [fptan.c](src/fptan.c) | Instruction-specific numerator/denominator programs and final divide |
| F2XM1 | [f2xm1.c](src/f2xm1.c) | Tiny, long and table paths, including raw80 subnormal rounding |
| FPATAN | [fpatan.c](src/fpatan.c) | Explicit finite arctangent, special operands and mask-dependent outcomes |
| FYL2X | [fyl2x.c](src/fyl2x.c) | [Shared logarithm](src/log/logarithm.c) |
| FYL2XP1 | [fyl2xp1.c](src/fyl2xp1.c) | Shared logarithm with explicit domain policy |

For sine and cosine, start with the evaluator at the top of
[sin_cos.c](src/trig/sin_cos.c). It handles special inputs and the range limit,
reduces the argument once, then selects the [tiny-result rule](src/trig/tiny.c),
the polynomial in the same file, or [table evaluation](src/trig/table.c).
The public entry files apply exception and register-update policy around that
numerical calculation. [sincos.c](src/trig/sincos.c) follows the same stages for
both outputs, using its own polynomial operation order and sharing one reduction.

The [exact reducer](src/trig/reduce.c) is shared where the numerical graphs
agree. [Wide integer arithmetic](src/arithmetic/wide.c), [software values](src/arithmetic/soft_value.c)
and [bounded finite arithmetic](src/arithmetic/finite.c) preserve each precision cut.
[Raw classification](src/raw80.c) runs before normalization.
The [common outcome policy](src/context.c) selects newly unmasked exceptions and
write suppression; final arithmetic stages construct adjusted UE/OE results.

[Constants](src/constants/) are compiled literal data; [private headers](src/internal/)
are not installed. Historical experiments and the Itanium reference remain in
[research/](research/), outside the product build.
