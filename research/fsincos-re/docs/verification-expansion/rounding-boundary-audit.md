# Rounding and storage boundary review

The F2XM1 discovery justified checking the rest of the suite. This bounded
review found **no additional numerical defect** in the reviewed instruction
paths. The important distinction is whether a value still needs rounding
when it reaches the raw80 store. F2XM1 did; the other shared-helper paths
either carry an already representable tiny input or produce normal results.
FPATAN and the logarithms use separate packers that round at raw80 spacing.

The review used a source snapshot taken before the authorized F2XM1
integration. It made no shared-source or paper changes and ran no hardware
instructions. The FPTAN unsupported-encoding patch was not applied. The
[source snapshot](../../tmp/verification-expansion/coverage/storage-audit/SOURCE-SNAPSHOT.json)
and [local checks](../../tmp/verification-expansion/coverage/storage-audit/CHECKS.json)
keep the findings reproducible while integration proceeds elsewhere.

## What the shared helper actually promises

`sf_t` has a 64-bit significand and an extended internal exponent range.
`sf_to_x87` right-shifts a subnormal result and discards the shifted bits.
It has no RC argument, guard/sticky output, C1 result or general overflow
handling. It is therefore a conversion for values whose callers have already
settled those questions, rather than a general architectural rounder.

For a true raw80 subnormal with integer significand `m`, normalization shifts
`m` left by `64 - bit_length(m)`. Conversion shifts it right by exactly the
same amount. All discarded bits are zero. A pseudo-denormal is canonicalized
to exponent field one without changing its value; its original encoding must
still be retained for exception classification. Signed zero has a separate
sign-preserving path.

The audit inventories all **15 call sites** in the current `src` tree:

| Callers | Storage premise |
| --- | --- |
| `general_standalone_ref`, `h1638_tiny_entry` | Extreme-tiny sine returns its input; cosine returns one. Other results are normal. |
| `general_paired_ref`, `general_paired_polynomial` | Same exact tiny transfers; polynomial/table lanes are bounded away from zero. NaNs and signed zero take explicit branches. |
| Historical bodies of `fsin_ref`, `fcos_ref`, `fsincos_ref` | Retained alternate paths; promoted defaults dispatch before these bodies. Their shared tiny bypass also returns the input or one. |
| `fptan_ref` | Extreme-tiny input transfer; every non-bypass quotient is normal and finite under the fixed reduction contract. |
| `f2xm1_ref` | The known failing caller: a newly computed tiny product previously reached a truncating store. Its correction is being integrated separately. |
| `dump2`, `run_fma_test`, `run_kernel_test` | Diagnostics can accept or display general internal carriers. They are not general raw80 arithmetic emulators. |

Exact locations refer to the snapshot and are recorded in `CHECKS.json`.
The diagnostic modes remain a reuse hazard: a future caller can reproduce
the same truncation mistake if it assumes this helper performs final rounding.
This is not another demonstrated defect in one of the eight instructions.

## Why the other trig paths cannot reach the same failure

FSIN, FCOS and FSINCOS separate the external `exponent < -68` bypass from
ordinary tiny arguments. The bypass returns `x` or `1`, with known tiny C1
equal to zero. Normal/pseudo-denormal inputs remain normal. Non-bypass tiny
sine uses the leading value or its representable 64-bit predecessor; its
input is far above the subnormal range.

The existing H1647 exact interval certificate was rerun in the audit directory
and passed. It bounds the promoted standalone polynomial, table and tiny
paths away from underflow. The exact M66 reducer produces a nonzero residual
that is an integer multiple of `2^-65`; its odd 66-bit divisor cannot divide
a nonzero 64-bit significand times a power of two. Reduction therefore cannot
silently create a residual near `2^-16382` or an exact zero.

The paired polynomial uses a different operation sequence. This review bounds
its actual six-coefficient Horner chain separately. All coefficient magnitudes
are below one. With square at most `1/16`, a conservative rounding factor of
`65/64` bounds the chain below `9/8`. Sine's relative correction and cosine's
absolute correction are each below `1/8`. The final lanes remain above half
their leading magnitudes. The shared table correction remains below `1/8`
against a leading value above `1/4`.

The same bounds cover FPTAN's numerator and denominator, including their
67-bit cuts. In its polynomial region, their magnitudes satisfy
`|s| > |r|/2`, `|c| > 1/2`, and both are below two. A non-bypass residual has
`|r| >= 2^-68`; quadrant rotation only exchanges the two lanes and signs.
After final rounding, the quotient's magnitude is strictly between
`2^-71` and `2^71`. The table quotient is more tightly bounded between
`1/64` and `64`. Neither path approaches raw80 underflow or overflow.

These are exact bounds on the specified arithmetic, conditional on the
inspected dispatch, width and reduction contracts. They do not prove that
every processor implements that arithmetic.

- [Replayed H1647 certificate](../../tmp/verification-expansion/coverage/storage-audit/h1647-replay/report.json)
- [New paired/FPTAN bounds and software checks](../../tmp/verification-expansion/coverage/storage-audit/check_storage.py)

## FPATAN and logarithms already use destination spacing

Both GMP `encode` functions choose the final quantum before rounding:

```text
step = 2^max(floor(log2(abs(value))) - 63, -16445)
```

They retain the exact rational carrier until that rounding, preserve the sign
when a negative value rounds to zero, and calculate C1 from the actual final
magnitude increment. The logarithm packer also handles mode-dependent
overflow to infinity or the largest finite value. Neither calls `sf_to_x87`.

This matters for reachable values. FPATAN can have a ratio much smaller than
the least raw80 subnormal even when both operands are normal. FYL2X and
FYL2XP1 can produce products far below the least raw80 subnormal through
their final multiplication by `y`. Their packers explicitly handle those
cases. FYL2XP1's tiny logarithm branch still retains its specified internal
67-bit cut before the final exact product and raw80 rounding.

The FPTAN rational reference still uses `finish` followed by `store`. Its
subnormal bypass skips `finish` and transfers the exactly representable input;
the range bounds above keep every other finite result normal. The F2XM1
reference requires the separately reviewed destination-spacing correction.
Moving all callers onto one generic rounding/flag rule would erase real
instruction differences.

## C1 and underflow need separate reasoning

An instruction can set UE while the stored result is minimum normal. This
was already investigated for FPATAN and the logarithms; the F2XM1 result
does not newly discover that phenomenon for those instructions.

The saved hardware streams and their completion/score hashes were
reauthenticated. This inventory found:

| Saved pack | Rows with UE | UE with stored minimum normal |
| --- | ---: | ---: |
| FPATAN D0007 | 36,864 | 1,092 |
| FPATAN D0067 | 14,692 | 42 |
| Logarithms L0005 | 44,446 | 852 |

FPATAN tests tininess on its retained angle before final rounding. The
logarithms test the 64-bit rounded value with an unbounded exponent before
raw80 storage and retain the kernel's inexact indication, including exact
final products. Earlier logarithm hypotheses failed on those distinctions;
the corrected rule passed L0005 and the later i7 confirmation. For the
F2XM1 tiny-product arithmetic, before-rounding and post-64-bit predicates
are equivalent; its new observations cannot distinguish them.

The trig tiny transfer has C1 zero even though a finite nonzero instruction
can report PE, and an original true subnormal can report UE/DE. Exact output
copying therefore does not imply clear exception flags. Raw encoding,
internal approximation and final rounding remain separate inputs to the
status rules. The existing partial trig state work retains those distinctions;
this review does not extend it to arbitrary incoming state.

[Authenticated saved-flag inventory](../../tmp/verification-expansion/coverage/storage-audit/SAVED-FLAGS.json).
Original discovery labels are preserved. This audit did not rerun those
numerical scorers or count their rows as new observations.

## Checks and useful follow-up

The software checks exercised 11,618 raw tiny operands over all four RC
settings through FSIN, FCOS, FSINCOS and FPTAN: 185,888 instruction-result
checks per optimized/sanitized build, with zero differences. They cover small
subnormal significands, every leading-bit position, both signs, signed zero,
pseudo-denormals and the minimum-normal boundary. Known tiny trig C1 bits
also pass. Common history-held inputs were used only as software values.

The actual FPATAN and logarithm C packers each pass 5,816 independent
integer-lattice expectations around zero, exact values, halfways, both sides
of halfways and the subnormal/normal boundary. Another 80 logarithm checks
cover maximum-finite rounding, overflow, saturation and C1. These tests are
local implementation evidence, not additional hardware validation.

The most useful next work is to make the store helper's caller requirements
explicit and preserve regression tests at destination-format boundaries.
Any new arithmetic caller should establish that its output is already
representable or use a destination-aware packer. Keep underflow predicates
instruction-specific. F2XM1's confirmed correction is the only new numerical
fix required by this review.

Remaining coverage questions concern historical held inputs, complete
RC/PC/processor boundary groups, arbitrary incoming state, and other processor
generations. The known FPTAN unsupported-encoding issue concerns classification
before normalization; it is separate from rounding-to-storage and remains an
isolated patch. No new hardware campaign is proposed by this report.
