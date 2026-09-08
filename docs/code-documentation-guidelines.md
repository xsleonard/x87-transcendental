# Documenting the numerical programs

Comments should explain the mathematics and the code to someone who has not
followed the research. The reader needs to know what each stage computes, why
it is needed, and where rounding changes the calculation. More accurate
arithmetic can give different result bits and C1, so those details matter.

The [algorithm index](algorithms/README.md) maps the implementations and their
supporting evidence. The [API contract](api.md) describes register updates and
exceptions; the [validation record](validation.md) describes what was tested.

## Publication boundary

Keep privately supplied technical source material and all references to it out
of the entire repository, including ignored records and generated files. Do not
include contributor identities, correspondence, source filenames or paths,
source hashes, excerpts, address maps, or source-specific inventories. A release
exclusion is not sufficient. Keep any retained restricted records outside the
repository.

Explain the implemented numerical program and the evidence from experiments.
Cite publicly available material only for claims it supports. Do not describe
a structure as independently discovered merely because a later implementation
or hardware comparison validated it. When a historical source-analysis section
cannot meet this boundary, remove the whole section rather than relabeling its
evidence as an independent experiment.

## Write ordinary technical English

Write as though you were explaining the code to another programmer. Use verbs
that name the operation: add, multiply, truncate, round, compare, return, write.
Put one main idea in each sentence, and connect the operation to its reason.

For example:

| Hard to read | Clearer |
| --- | --- |
| These products are intentional materialization points. | Round these products to 64 bits before the next multiplication. |
| The retained prevalue supplies architectural C1 metadata. | Set C1 if final rounding increases the sum's magnitude. |
| The wrapper owns exception-dependent writeback policy. | The wrapper decides whether to write the result after checking the exception masks. |
| Finite inputs enter the numerical model. | Compute the result for finite inputs in this range. |

Keep useful technical terms, but explain them when needed. For example, a
significand is the part of a floating-point value that holds its significant
bits. An exact dyadic is an integer times a power of two. Prefer an equation
or a named variable to a phrase such as “retained internal carrier state.”

Avoid strings of nouns, unnecessary abbreviations, and slash-separated lists
inside sentences. Say “round the sum, then multiply by x” rather than “perform
sum materialization and residual scaling.” Do not repeat the research history
or a general warning about hardware equivalence beside every operation.

## Start with the function and the main steps

Begin each implementation with a short explanation of:

- What it computes and which inputs it accepts.
- Which special cases it handles, including range returns and exclusions.
- How reduction, approximation and reconstruction lead to the result.
- Which identities explain those steps, and where the code rounds them.

An entry function should also explain which register receives the result and
whether the instruction pushes or pops. A shared helper should state what its
callers must provide. Keep CPU targeting, release labels and package status in
project or API documentation.

C comments must be self-contained plain text. Do not put Markdown links or
pointers to documents and research files in them. Explain the necessary
mathematics, helper behavior and reason for each choice in the code. Keep
supporting links in the algorithm and validation documentation.

**Weak overview:**

```c
/* F2XM1 approximation using the h254/h258 model. */
```

**Improved overview**, based on [f2xm1.c](../src/f2xm1.c):

```c
/* Compute 2^x-1 for -1 <= x <= 1. Handle zero and +/-1 first.
 * For 0 < |x| < 2^-68, multiply x by the stored approximation to ln(2).
 * For 2^-68 <= |x| < 1/4, use the eleven-coefficient polynomial.
 * For 1/4 <= |x| < 1, subtract a table midpoint, approximate the small
 * remainder, and combine it with the table value.
 * Most products are truncated to 67 bits. Ordinary sums and selected
 * products round to 64 bits, nearest with ties to even. The last operation
 * uses the guest rounding mode; subnormals round directly to raw80 spacing. */
```

The complete source overview also explains NaNs, unsupported encodings and
infinities. It states that finite inputs outside [-1,1] return unchanged with
PE set, because this observed behavior is separate from the function's domain.
An overview should orient the reader; put detailed branch rules beside the branch.

## Explain the identity, then the rounded calculation

Define each mathematical symbol and connect it to a code variable. Say what a
table stores: an angle, a function value, a reciprocal or a correction. Explain
its scale, how the index is formed, and which cell includes an exact boundary.
Use exact fractions or raw80 values where a decimal approximation could obscure
a comparison.

For rounding notation in these examples, RN64 means nearest with ties to even
at 64 significant bits; RN67 uses 67 bits. CHOP67 truncates to 67 significant
bits toward zero. RC is the guest rounding mode. PC is the guest precision
control; accepting PC24 or PC53 does not make internal operations use those widths.

**Weak reconstruction comment:**

```c
/* Get the table value and combine it with the polynomial. */
```

**Improved reconstruction**, for the F2XM1 table path:

```c
/* Let c be the table midpoint, r=x-c, and d=2^c-1. Then
 *     2^x-1 = d + (1+d)*(2^r-1).
 * lookup stores d rounded to RN67. Compute residual=RN64(x-c), then
 * z=RN64(L*residual), where L is the stored approximation to ln(2).
 * polynomial approximates exp(z)-1, with each operation rounded separately.
 * Round 1+lookup to RN64, multiply by polynomial and chop to 67 bits,
 * then add lookup using guest RC. Rearranging the identity would change
 * where the code rounds and could change the final result. */
```

In this function, `lane` selects one of 16 equal cells in each magnitude
interval, [1/4,1/2) and [1/2,1). For exponent -2, the midpoint magnitude is
`(33+2*lane)/128`; for exponent -1, it is `(66+4*lane)/128`. Each cell includes
its lower boundary and excludes its upper one. Rows 0–15 cover positive
exponent -1 inputs, rows 16–31 cover positive exponent -2 inputs, and adding
32 selects the corresponding negative midpoint. This explains why the code
can choose a cell from the top four fraction bits.

## Describe each rounding step precisely

Distinguish truncating an operand from rounding the result of an operation.
State the number of significant bits and the rounding mode. Explain when a
value is narrowed before its next use and why keeping extra bits would change
the calculation.

**Weak precision comment:**

```c
/* Compute z squared at high precision. */
```

**Improved precision comment**, for F2XM1's long polynomial:

```c
/* Let L be stored ln(2) and z=L*x. Compute L*x twice: tmp1 uses CHOP67
 * and tmp2 uses RN64.
 * Multiply them, chop the product to 67 bits, and keep it in tmp2.
 * Both coefficient chains use this product as their approximation to z^2.
 * Squaring either rounded value instead would give a different calculation.
 * Later, round the two products in tmp5 and tmp6 to RN64 before their
 * next multiplication; keeping 67 bits there can change the later sums. */
```

Explain numbered temporaries without renaming them: `tmp5` collects terms for
the odd powers, `tmp6` collects terms for the even powers, and `tmp3` starts
with the quadratic term. Distinguish coefficient count from polynomial degree.
F2XM1's six short coefficients multiply z² through z⁷, in addition to the leading z.

Read helpers before describing them. In shared trig code,
`mul_x67_y64_rn64` first truncates X to 67 bits and Y to 64 bits, then rounds
their exact product directly to RN64. Rounding a CHOP67 product to RN64 can
give a different answer. Plain `wide_mul` instead uses its inputs as stored
and rounds only the product. The width of a C type does not tell you which of
these operations takes place.

The same rule applies to whole instructions. FPTAN divides its internal sine
and cosine approximations before final rounding. It does not divide the public
FSIN and FCOS results. FSINCOS also has a different polynomial calculation
from the two standalone instructions.

## Explain boundaries and exceptions where they occur

Say which side includes equality. Preserve the distinction between classifying
raw80 bits and normalizing their value. Explain why a special case returns its
particular value and which exceptions it raises.

C1 usually records whether final rounding increased the magnitude. It does not
measure the approximation's error, and C1=0 does not mean the calculation was
exact. Identify which operation sets C1; for FSINCOS, it comes from cosine.
Explain the special cases and which condition bits are known on a C2 return.

**Weak boundary comment:**

```c
/* Handle tiny values and store. */
```

**Improved boundary comment**, for F2XM1:

```c
/* For finite nonzero x with normalized exponent <= -16382, multiply by
 * the stored ln(2) exactly, then round to multiples of 2^-16445 using RC.
 * Test for underflow before rounding: even a result rounded up to the
 * smallest normal value can raise UE. If the product is tiny and UE is
 * unmasked, multiply it by 2^24576 before rounding. Scaling an already rounded
 * zero would lose the result that must be written to the register. */
```

The [storage correction record](../research/fsincos-re/docs/verification-expansion/f2xm1-integration.md)
explains the failure and its regression cases. The `sf_to_x87` helper simply
truncates when shifting a subnormal; it does not use RC or save sticky bits.
The caller must round to the required spacing before using that helper.

Explain exception handling separately from numerical rounding. F2XM1 reports
PE for finite nonzero inputs even at ±1, where the answer is exact.
`result_finish` chooses the first new unmasked exception. IE, DE or ZE prevents
register writes, pushes and pops, clears C1, and suppresses later flags. OE, UE
or PE can allow the write with an exception pending. The numerical routine must
have scaled the result first if unmasked OE or UE requires it. The emulator
then updates registers and handles stack faults and exception delivery.

## State what helpers store and what callers must guarantee

**Weak helper comment:**

```c
/* Add two wide values exactly. */
```

**Improved helper comment**, for [wide.c](../src/arithmetic/wide.c):

```c
/* A wv_t stores (-1)^sign * sig * 2^e2; sig need not be normalized.
 * Use the smaller e2 as the common scale, add the integers, then round
 * to the requested number of significant bits. Both aligned operands
 * and their sum must fit signed 256-bit storage, with no lost bits.
 * Ignore the input rh fields; the returned rh records this sum's rounding
 * direction. The caller handles raw80 exponent limits and exception flags. */
```

“Exact” needs a bound. `acc_add_product` can right-shift without saving sticky
information, so a caller needing exact arithmetic must ensure that every bit
shifted out is zero. A 256-bit accumulator cannot hold an exact sum with an
arbitrary gap between exponents. The [finite arithmetic helpers](finite-arithmetic.md)
use a different method to preserve the effect of a distant, small operand.

Those helpers use `fv`: an exact integer times a power of two. Four little-endian
64-bit words store the magnitude; normalization moves trailing zeros into the
exponent. Assignment does not round. `fmul` accepts magnitudes of at most 128
bits each and keeps their exact product. `fadd`, `fdiv` and `fround` take an
explicit output width. FPATAN keeps its final sum until encoding; the logarithms
keep their final product. Their underflow tests also differ and must be described
at the relevant call sites.

## Keep the conclusion in the comment and the evidence in documentation

Preserve existing explanations, experiment identifiers and attribution. Add a
local correction when an older comment describes behavior that has changed.
When removing a document pointer, keep its useful explanation in the comment
and move the reference into the algorithm documentation. Do not rewrite the
research archives.

**Weak research comment:**

```c
/* h254/h258 ordinary-multiply class. */
```

**Improved addition beside that preserved comment:**

```c
/* h254 tested the rounding rules shared by the polynomial operations.
 * Products chopped to 67 bits, sums rounded to RN64, and separate RN64
 * scaling products matched the observations. h258 checked those choices
 * at boundaries. Keeping more bits changed some results and C1 values. */
```

The [F2XM1 reconstruction record](../research/fsincos-re/notes/f2xm1-reconstruction.md)
supports this example. Put links like this in documentation, outside C comments
and comment examples. Describe what the evidence establishes. Agreement with
a retained test set does not prove agreement for every operand or processor.
A comparison with an earlier model and a comparison with hardware answer
different questions. Neither justifies an unsupported accuracy bound or a guess
about the circuit design.

## Review and validation

Read each new comment as a sentence, without relying on the code to repair its
grammar. Check that it explains a reason, calculation or requirement. Remove
repetition, and replace abstract wording with the actual operation.

Before finishing:

1. Check every technical statement against the current code, constants and
   helpers. Verify signs, scales, widths, rounding modes and equality cases.
2. Preserve existing numerical explanations and permitted public attribution.
   Apply the publication boundary above to all references. Check that C comments contain
   no Markdown links or document pointers and can be understood without the
   experiment history. Check documentation links separately.
3. Compare C tokens before and after with a comment-aware lexer. Preserve
   strings, character literals, preprocessing directives and token boundaries.
   Compare unchanged constant files byte-for-byte. Simply erasing whitespace
   can hide a change from two tokens to one.
4. Run `make check`. Further
   offline replays are described in [validation.md](validation.md). Do not make
   new native hardware captures for a comment edit.
5. Report what was documented and checked, and any remaining limits. Comments
   can move source lines and debug locations; executable tokens, interfaces,
   constants and arithmetic order must stay unchanged.
