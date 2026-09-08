# Library source map

The public interface is [x87trans.h](include/x87trans/x87trans.h). Build the single
`x87trans` target and link it from callers; no source inclusion or mode defines
are needed. All numerical changes belong in the files below.

| Instruction | Entry file | Main shared implementation |
| --- | --- | --- |
| FSIN | [fsin.c](src/fsin.c) | [Standalone dispatch](src/trig/standalone.c), [polynomial](src/trig/standalone_polynomial.c), [table](src/trig/table.c), [tiny](src/trig/tiny.c) |
| FCOS | [fcos.c](src/fcos.c) | Same standalone machinery with the cosine phase |
| FSINCOS | [fsincos.c](src/fsincos.c) | [Paired polynomial](src/trig/paired_polynomial.c); shared table and tiny arithmetic |
| FPTAN | [fptan.c](src/fptan.c) | Instruction-specific numerator/denominator programs and final divide |
| F2XM1 | [f2xm1.c](src/f2xm1.c) | Tiny, long and table paths, including raw80 subnormal rounding |
| FPATAN | [fpatan.c](src/fpatan.c) | Explicit finite arctangent, special operands and mask-dependent outcomes |
| FYL2X | [fyl2x.c](src/fyl2x.c) | [Shared logarithm](src/log/logarithm.c) |
| FYL2XP1 | [fyl2xp1.c](src/fyl2xp1.c) | Shared logarithm with explicit domain policy |

The [exact reducer](src/trig/reduce.c) is shared where the numerical graphs
agree. [Wide integer arithmetic](src/arithmetic/wide.c), [software values](src/arithmetic/soft_value.c)
and [bounded finite arithmetic](src/arithmetic/finite.c) preserve each precision cut.
[Raw classification](src/raw80.c) runs before normalization.
The [common outcome policy](src/context.c) selects newly unmasked exceptions and
write suppression; final arithmetic stages construct adjusted UE/OE results.

[Constants](src/constants/) are compiled literal data; [private headers](src/internal/)
are not installed. The [extraction map](docs/extracted-source.json) connects
historical symbols to the new implementation. Historical experiments and the
Itanium reference remain in [research/](research/), outside the product build.
