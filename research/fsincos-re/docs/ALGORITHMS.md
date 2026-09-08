# How the x87 algorithms work

The project implements FSIN, FCOS, FSINCOS, FPTAN, F2XM1, FPATAN, FYL2X
and FYL2XP1. This guide explains the main ideas and links to the full code
and pseudocode for each instruction.

Ken Shirriff's Pentium ROM analysis supplies the main constants and explains
many of the algorithms.[^ken] Those exact constants matter: substituting Taylor
coefficients or recomputing a table with a math library can change the last
bits. The source register explains how we also use the published Itanium
implementation and Goldmont material.[^sources]

## Why these methods approximate the functions

The common method is to reduce the argument, approximate the function on a
small interval, and reconstruct the answer using a table or an identity.
Harrison, Kubaska, Story and Tang describe the tradeoff: smaller intervals
allow shorter polynomials, while tables supply the larger part of the answer.[^methods]
Taylor series explain the powers and leading terms. Coefficients chosen to
reduce the worst error over the whole interval can differ from Taylor
coefficients; this is the minimax approach discussed by both Harrison et al.
and Shirriff. The stored ROM words, including their low bits, are still the
coefficients required to reproduce the processor.

There are two separate numerical questions: how closely the real polynomial
approximates the function, and how rounding each operation changes that
polynomial's value. The paper's approximation discussion connects the
identities below to the published literature. The executable specifications
then identify the precise rounding steps to implement.

## Reading the rounding notation

Think of each algorithm as exact arithmetic interrupted by explicit rounding:

- `T_p(v)` truncates magnitude to `p` significant bits, preserving sign.
- `RN64(v)` rounds to a 64-bit significand, nearest with ties to even.
- Final architectural rounding obeys RN/RD/RU/RZ and the output format's
  exponent/subnormal rules.

An addition is exact unless its operation explicitly says otherwise.
Bit widths refer to significant bits, not C object size. The number of bits in the stored value does not tell you how an intermediate
operation was rounded.

Similar-looking multiplies are not always interchangeable:

$$
M_{\mathrm{standalone\ trig}}(a,b)
  =T_{67}(T_{67}(a)T_{64}(b)),
\qquad
M_{\mathrm{FPATAN}}(a,b)=T_{67}(ab).
$$

Likewise, a multiply directly rounded to RN64 can differ from a multiply
first truncated to 67 bits and then rounded to RN64. Preserve the named
operator, operand order, and every rounding point when translating pseudocode.

## Exponential: F2XM1

The mathematical target is $2^x-1$ for $-1\leq x\leq1$. The model has a
tiny linear path, a long polynomial path, and a table-assisted path:

| Input magnitude | Calculation |
| --- | --- |
| Below $2^{-68}$ | Multiply by the stored ln(2), then round |
| $2^{-68}\leq |x|<1/4$ | Eleven-coefficient polynomial |
| $1/4\leq |x|<1$ | Table value plus a six-coefficient correction |
| $x=\pm1$ | Exact endpoints +1 and -1/2 |

For the smallest inputs, round the exact stored-ln(2) product directly to
raw80. Subnormal values have fixed spacing $2^{-16445}$. Rounding to 64
significant bits and then truncating on storage was a bug in the earlier
implementation; rounding a second time can also produce a different answer.
The corrected C and rational reference pass the targeted tests on both the
Core i7-6700 and Xeon. Their polynomials and constants are unchanged.
[Integration evidence](../paper/evidence/f2xm1-integration.json).

The table identity is

$$2^x-1=(2^b-1)+2^b\bigl(\exp((x-b)\ln2)-1\bigr).$$

For small $t$, $\exp(t)-1=t+t^2/2+t^3/6+\cdots$.[^exp-series]
The table makes $t=(x-b)\ln2$ small enough for the shorter polynomial.
Computing this difference directly also avoids losing a tiny result by
subtracting 1 from an already rounded exponential.

This identity explains the arrangement, but does not define its rounding.
The model uses particular literal constants, CHOP67 ordinary products,
RN64 additions, specific products rounded to RN64 and final architectural rounding.
Positive midpoint numerators over 128 are odd 33 through 63 below 1/2,
and 66,70,...,126 above; signed table selection handles negative inputs.

Read the [F2XM1 reconstruction](../notes/f2xm1-reconstruction.md), including
its final signaling-NaN addendum, then `f2xm1_long_path`, `f2xm1_table_path`
and `f2xm1_core` in [the C source](../src/fsincos_skylake.c). Constants are
in [f2xm1_constants.h](../src/f2xm1_constants.h). The complete
[executable specification](SIBLING-PSEUDOCODE.md) includes every operation
and has been checked independently against saved hardware results.
Behavior observed outside [-1,1] is not guaranteed by Intel.

## Sine and cosine: FSIN, FCOS and FSINCOS

Reduction by multiples of $\pi/2$ leaves a small angle and a quadrant to
restore. The series have the forms $\sin r=r+r^3S(r^2)$ and
$\cos r=1+r^2C(r^2)$, which explain why both use a square but finish the calculation differently.[^trig-series]
For a table center $\theta$, the identity
$\sin(\theta+a)=\sin\theta\cos a+\cos\theta\sin a$ reduces the remaining
work to small corrections around $a=0$.[^trig-identities]
The processor model uses a finite approximation to $\pi/2$, so exact integer
reduction with that constant still differs from reduction with mathematical $\pi/2$.

The processing sequence is:

```text
classify the raw80 operand
handle specials, tiny external inputs and range rejection
reduce the angle using the fixed integer reduction constant
select the tiny-input method, polynomial or table from the residual
restore the quadrant and sign
round each output and determine C1 where defined
```

The [complete trig pseudocode](TRIG-PSEUDOCODE.md) specifies those steps.
It uses exact integer quotient/remainder reduction, then instruction-specific
polynomials. Standalone sine/cosine group odd and even coefficient indices;
paired FSINCOS uses two Horner chains sharing one square. Both paired chains truncate each product to 67 bits before adding the next
coefficient and rounding to RN64.

FSINCOS is therefore its own numerical program. Replacing it with calls to
the standalone functions can change observable bits. C1 describes rounding of the returned cosine, even when the quadrant makes
the internal sine calculation supply that result.

## Tangent: FPTAN

FPTAN shares reduction and coefficient material with the trig family, but
constructs its own internal numerator and denominator. Its final result is

$$\operatorname{round}_{\mathrm{RC}}(N/D),$$

where $N$ and $D$ are retained internal values. They are not generally the
already rounded architectural FSIN and FCOS results. In particular, forming
`FSIN(x) / FCOS(x)` inserts rounding steps that the FPTAN program does not use.
Near a tangent pole, cosine is close to zero. Dividing by that small value
amplifies errors in the internal pair, so their precision matters.

The table path distinguishes 67-bit constants, an RN64 cosine-tail read,
and a wider intermediate sine value rounded to RN64. Ordinary products and
reconstruction subtractions have explicit CHOP67 cuts. Quadrant restoration
precedes the final division. For ordinary finite outputs the instruction
pushes +1; its modeled special-value push behavior is also explicit.

Read the [FPTAN reconstruction](../notes/fptan-reconstruction.md), including
the exact-quotient/push-rule addendum, and `fptan_polynomial_values`,
`fptan_table_values`, `fptan_final_divide` and `fptan_core` in
[the C source](../src/fsincos_skylake.c). The independently checked
[FPTAN pseudocode](SIBLING-PSEUDOCODE.md) is included in the unified appendix.

## Arctangent: FPATAN

FPATAN consumes ordered operands y=ST(1) and x=ST(0). For finite nonzero
inputs it first works in an octant:

$$r=\frac{\min(|y|,|x|)}{\max(|y|,|x|)}.$$

For larger ratios it uses a center $c=n/32$ and the identity

$$\arctan(r)=\arctan(c)+\arctan\!\left(\frac{r-c}{1+rc}\right).$$

For a nearest center spaced by $1/32$, the residual has magnitude at most
$1/64$. Its series $\arctan t=t-t^3/3+t^5/5-\cdots$ then needs fewer terms
than a polynomial applied to the original ratio.[^atan-series]

The code computes the reduced input directly from the original magnitudes,
evaluates two interleaved polynomial chains, then restores the quadrant and
sign. The pseudocode shows every rounding step. An exact check finds that
two table-index tie rules give the same final answer in this algorithm.
Hardware tests distinguish the tested rounding alternatives at four RN64 additions.

Use the [executable FPATAN pseudocode](../fpatan-re/PSEUDOCODE.md) and
[algorithm specification](../fpatan-re/ALGORITHM.md). The
[current evidence](../paper/evidence/fpatan-pseudocode-current.json) replays
the same pseudocode against all 7,571,628 retained catalog observations;
the original paper's smaller replay remains a separate historical snapshot.

## Logarithms: FYL2X and FYL2XP1

FYL2X, $y\log_2(x)$, and FYL2XP1, $y\log_2(1+x)$, first compute an internal
logarithm and then multiply by `y`.[^intel] A direct transformed
atanh polynomial handles inputs near one (FYL2X) or zero (FYL2XP1); a 32-bin
split table handles the rest of the specified domain. The internal sum,
product, quotient and asymmetric-square cuts are explicit.

For $v>0$, putting $t=(v-1)/(v+1)$ gives
$\ln v=2(t+t^3/3+t^5/5+\cdots)$.[^log-series]
Normalization and table anchors make $v$ close to 1, so the odd powers decay
quickly. FYL2XP1 uses $t=x/(2+x)$ near zero, preserving an increment that an
early rounded addition of $1+x$ could erase.

The [complete logarithm pseudocode](../fyl2x-re/ALGORITHM.md) explains the
schedule, four independently derived table corrections, the exact FYL2XP1
input bound and final exception rounding. The [C library](../fyl2x-re/log_library.h)
and [independent Python reference](../fyl2x-re/model.py) implement the same
algorithm. [Acceptance evidence](../fyl2x-re/ACCEPTANCE.md)
distinguishes tests used during development from the final hardware test,
whose code and predictions were fixed in advance.

The separate [Itanium model](../src/fsincos_itanium.c) transcribes a public
Intel algorithm associated with Harrison's verification work.[^harrison]
It is useful historical and numerical context, with its own arithmetic
tests. It is not the Skylake instruction implementation.

[^ken]: Ken Shirriff, [Pi in the Pentium: reverse-engineering the constants in its floating-point unit](https://www.righto.com/2025/01/pentium-floating-point-ROM.html), January 2025. Corrections are tied to the saved published table edition in the project records.
[^sources]: See the [source register](../paper/SOURCES.md) and [Goldmont lineage audit](../goldmont-lineage/README.md) for separate source roles, revisions and interpretation limits.
[^intel]: Intel, [Software Developer's Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), transcendental instruction inventory and individual instruction entries.
[^harrison]: John Harrison, [Formal verification of floating point trigonometric functions](https://www.cl.cam.ac.uk/~jrh13/papers/fmcad00.html), FMCAD 2000, pp. 217-233.
[^methods]: John Harrison, Ted Kubaska, Shane Story and Ping Tak Peter Tang, [The Computation of Transcendental Functions on the IA-64 Architecture](https://www.cl.cam.ac.uk/~jrh13/papers/itj.pdf), Intel Technology Journal, Q4 1999, pp. 1-3.
[^exp-series]: NIST DLMF, [the exponential series, Section 4.2](https://dlmf.nist.gov/4.2#E19).
[^trig-series]: NIST DLMF, [sine and cosine series, Section 4.19](https://dlmf.nist.gov/4.19).
[^trig-identities]: NIST DLMF, [trigonometric identities, Section 4.21](https://dlmf.nist.gov/4.21).
[^atan-series]: NIST DLMF, [arctangent series and addition identities, Section 4.24](https://dlmf.nist.gov/4.24).
[^log-series]: NIST DLMF, [the transformed logarithm series, Section 4.6](https://dlmf.nist.gov/4.6#E4).
