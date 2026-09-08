# F2XM1 and FPTAN: executable numerical specification

The canonical program is [sibling_reference.py](../../tests/reference/sibling_reference.py), using
Python's exact `Fraction` arithmetic. It defines every numerical operation,
constant lookup and rounding point without calling the production C program
or a host transcendental function. The paper mechanically includes that same
source. The literal data is [sibling-constants.json](../../tests/data/sibling-constants.json).

Both instructions build on the published Pentium ROM material.[^ken]
The current programs also specify the inferred rounding schedule, exact
dispatch and reduction, and the corrections established by the project.
The data file identifies each source ROM row and preserves the original
literal alongside each corrected value.

## How to read the program

`quantize(v, p, rc)` performs one rounding to `p` significant bits with an
unbounded exponent. `T67` means truncate toward zero; `N64` means nearest,
ties to even. `M(a,b)=T67(a*b)` and `A(a,b)=N64(a+b)`. Here `W(a,b)` is a
truncated subtraction, `T67(a-b)`; the FPATAN document uses a separately
defined sum operator. Operator names are local to each specification.

For F2XM1, read `f2xm1_long` and `f2xm1_table`, then the F2XM1 branch of
`evaluate`. The eleven-element coefficient array is zero-based. The long
path deliberately computes two differently rounded versions of ln(2)*x;
replacing them with one temporary changes the program. The table path
includes rounding in the reconstruction of `1 + lookup`.

The final `finish_raw80` step rounds directly to the destination format.
For a subnormal result, its spacing is $2^{-16445}$: do not round to a
64-bit significand first and then truncate during storage. That sequence
lost result bits and C1 in the original F2XM1 implementation. The corrected
tiny path uses the same ROM constant and changes only this final rounding.

For FPTAN, read `reduce_angle`, `horner`, the two kernel functions and
`fptan_ratio`. Table selection uses exact rational comparisons and floors.
The kernels produce retained internal numerator/denominator values; the
architectural result is one rounding of their exact ratio. This is not
division of the separately rounded FSIN and FCOS instruction outputs.

The shared entry function returns `(result, pushed, C1, C2)`. Each raw
value is a `(sign_exponent, significand)` pair; `pushed=None` means no
second value. C2 returns preserve the input. Ordinary FPTAN completion
pushes +1; NaN/indefinite paths push a second copy of the special result.

## Precise scope

The reference accepts ordinary raw80 values, signed zeros, subnormals and
pseudo-denormals, infinities and valid NaNs. Unsupported encodings raise an
error because their general hardware behavior has not been established for
these sibling wrappers. No full x87 stack, trap or exception-latch emulator
is supplied by this reference.

The production library adds the operand policy and arithmetic outcomes described
in [the API contract](../api.md), including masked unsupported encodings and
unmasked completion. F2XM1 infinities are outside its accepted numerical scope.
The reference above remains a numerical oracle for its stated domain.

`store` encodes a supplied value and can truncate during subnormal storage;
it is not a general rounding operation. F2XM1 now calls `finish_raw80`
before it, so the value is already an exact multiple of the destination
spacing. The older helper commentary is retained as implementation history.

F2XM1's unchanged-input policy outside [-1,1] is explicitly empirical,
not an architectural promise. Its numerical specification is centered on
the documented domain. Special-path C1 values in the program are the
reference convention; the replay establishes only the fields/classes present
in its identified observations.

## Verification

The corrected F2XM1 program matches **54,128** newly captured cases on each
of the Core i7-6700 and Xeon, including native raw80 subnormals, all four RC
settings and selected complete PC24/PC53/PC64 groups. The C correction and
its predictions were fixed before capture. The old program missed 8,658
results and 3,177 C1 predictions per processor; direct raw80 rounding fixes
all of them. The corrected independent program also matches all **25,650**
saved H257 observations under RN/RD/RU in result and C1. Historical holds
still leave some proposed neighborhoods incomplete.

The FPTAN program matches all **495,432** saved
T0002 observations and all **495,432** T0003 observations under RN/RD/RU/RZ
in result, pushed value, C1 and C2. The latter campaign contains normal finite
inputs, including range returns. The verifier checks raw input mapping,
hashes, control words and stack transitions, and authenticates both complete
hardware streams.

The [F2XM1 integration record](../../research/fsincos-re/paper/evidence/f2xm1-integration.json)
connects the corrected source, the new hardware challenge and the saved-data
regressions. The H257 and T0002/T0003 checks are software replays of existing
observations. The [current H257 receipt](../../research/fsincos-re/paper/evidence/f2xm1-current-replay.json)
and [FPTAN receipt](../../research/fsincos-re/paper/evidence/fptan-pseudocode-replay.json) bind the
specification, constants and verifier hashes. The original F2XM1 receipt is
preserved separately. The integration check establishes that the shared
reference's FPTAN arithmetic is unchanged.

On the research workspace with the retained capture artifacts:

```sh
python3 fsincos-re/paper/verify_siblings.py --instruction f2xm1 --out /tmp/f2xm1-new-replay.json
python3 fsincos-re/paper/verify_siblings.py --instruction fptan --out /tmp/fptan-new-replay.json
```

Use new output paths. Replays preserve existing reports and never execute
native hardware. The curated release additionally includes bounded public
witnesses for an offline smoke check without the large research archive.

[^ken]: Ken Shirriff, [Pi in the Pentium: reverse-engineering the constants in its floating-point unit](https://www.righto.com/2025/01/pentium-floating-point-ROM.html), January 2025. The project's saved ROM table is the source edition used for literal row comparisons.
