# Bounded finite arithmetic

FPATAN, FYL2X and FYL2XP1 use `src/internal/finite.h` and
`src/arithmetic/finite.c` to execute the reconstructed numerical programs.
The five other kernels use their instruction-specific integer
arithmetic. There is no host floating-point calculation or external arithmetic
dependency. Evaluation uses automatic storage; only context creation allocates.

## Exact values and explicit cuts

An `fv` represents `(-1)^negative * magnitude * 2^exponent`. Its magnitude has
four little-endian 64-bit words. Nonzero magnitudes are normalized to odd integers;
zero has sign and exponent zero. The binary exponent is separate, so even a
32,000-bit operand gap does not allocate a 32,000-bit integer. The private zero
leading-exponent convention is -1.

Literal parsing, raw80 decoding, sign changes, scaling and comparisons are exact.
Multiplication accepts two magnitudes of at most 128 bits and returns their full
256-bit product using the existing integer multiplication helper. Addition and
division require an explicit precision (1 through 128 bits) and rounding mode.
RN is nearest/even; RD and RU are signed directed rounding; RZ and internal CHOP
truncate magnitude. An extra rounding stage is never implicit in an assignment.

| Kernel operation | Operand/result bound |
| --- | --- |
| Raw80 operand | 64 significant bits, leading exponent -16445 through 16383 |
| ROM literal | 67 significant bits |
| FPATAN table cross-product | 64-bit raw significand times integer at most 65: at most 71 bits |
| FPATAN reduced numerator/denominator | Explicit CHOP67 before division |
| Ordinary polynomial multiplication | At most 67 by 67, exact product at most 134 bits before its cut |
| Special FPATAN angle | 67-bit constant times 3: at most 69 bits |
| Final logarithm multiplication | At most 67 by 64: at most 131 bits, retained exactly |
| Exponents and exception adjustment | Separate signed integers; all kernel values and +/-24576 adjustments fit well within C `int` |

These are private, bounded primitives, not a general arbitrary-precision API.
Executable checks reject unsupported widths, zero divisors and accumulator
overflow even in Release builds. Public special-value dispatch prevents NaNs,
infinities and unsupported encodings from reaching the finite kernels.

## Addition with a signed remainder

The addition workspace has five 64-bit words and an independent scale. Let E be
the larger operand's leading exponent. Alignment uses scale E-318. That operand
has its leading bit at position 318, fits exactly (at most 256 bits), and leaves
bit 319 available for a same-sign carry. The other operand either fits exactly
or leaves a nonzero fractional remainder below the workspace scale.

At most one operand can leave a remainder. Equal leading exponents fit exactly;
a discarded remainder requires a leading-exponent gap of at least 64. Thus
cancellation cannot hide a large unknown prefix. Exact magnitude comparison
chooses the result sign before subtraction.

For addition, store the integer prefixes' sum and whether a positive remainder
exists. For subtraction with a discarded subtrahend remainder, subtract the
prefix **and one unit**, retaining the complementary positive remainder. For
example, `1 - tiny` must become a prefix just below 1, not exactly 1 with an
unsigned sticky bit attached. This preserves its leading exponent and directed
rounding. Exact cancellation produces canonical zero.

The resulting workspace always means an integer prefix plus a nonnegative
fraction smaller than one workspace unit. Guard, lower bits and the remainder
flag decide quantization. If a remainder was discarded, the requested cut lies
well above it: target precision is at most 128 bits, versus 319 retained leading
bits. If cancellation leaves an already exact value narrower than the requested
precision, it returns unchanged. All word shifts explicitly handle zero,
word-boundary and out-of-window counts.

## Division and final encoding

Division compares scaled integers to find the quotient's leading exponent.
Normalize the exact numerator/denominator ratio to [1,2), then generate the
requested quotient bits by binary long division. The exact remainder chooses
rounding (including ties/even); no rounded reciprocal is introduced. With the
128-bit input bound, normalized numerator/denominator need at most 129 bits and
remainder doubling fits comfortably in the same workspace.

Raw80 encoding quantizes at `max(leading_exponent, -16382)-63`. C1 records a
magnitude increment. Overflow retains the previous infinity/max-finite policy
and its C1 rule. A nonzero negative value rounded to zero preserves its sign;
architectural exact signed zeros are handled in the instruction policy.

FPATAN holds the terminal expression as two operands until its specified cut.
The direct result is `z + tail`; a table result is `CHOP67(z + tail) + anchor`.
Quadrant restoration first applies the existing CHOP67 cut, then forms the final
sum or difference with pi/2 or pi. The exact sum's leading exponent determines
tininess before architectural rounding. An unmasked tiny sum is exponent-adjusted
before encoding. A truncated stand-in for the final sum would add an unintended
rounding stage and is deliberately avoided.

Logarithms retain their final exact product. Their underflow rule tests the
64-bit rounded product with unbounded exponent; overflow and unmasked endpoint
adjustments retain their existing order. NaN selection, exception priority,
completion, writeback and push/pop metadata are unchanged by this layer.

## Validation

`tests/arithmetic/check_finite.py` compares the private C driver with Python
`Fraction` and integer `divmod`. It includes exact products/comparisons, division
remainders, cancellation, word boundaries, ties and neighbors, large signed
tails, raw80 decoding/encoding, C1 and unmasked sum adjustments. It does not
reimplement the C window or long-division algorithm.

`tools/validation/replay_binary.py` checks complete instruction results against
the retained FPATAN/logarithm hardware corpus and authenticates the capture
receipts. The test fixtures retain their capture hashes and CPU context;
[validation](validation.md) gives the commands and data requirements.
Hardware agreement remains evidence
for the selected Skylake profile, not an exhaustive proof for all operand
pairs or CPU models.
