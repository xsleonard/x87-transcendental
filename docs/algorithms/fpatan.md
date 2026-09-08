# FPATAN numerical program

[fpatan.c](../../src/fpatan.c) implements the arctangent operation with the
finite arithmetic described below. The [executable pseudocode](../../tests/reference/fpatan.md)
provides an independent specification, and [validation](../validation.md) describes
the current checks and their scope. The operation order and bit widths are
constrained by Skylake observations; they do not identify the physical
implementation of hidden microcode.

## Finite nonzero inputs

Let `C67` and `C64` truncate to 67 and 64 significant bits (toward zero), and let
`N64` round to 64 significant bits, nearest/even. Both have unbounded internal
exponent range here. Architectural output rounding is separate and includes
extended-format subnormals.

Save input signs. Set `a=min(abs(y),abs(x))`, `b=max(abs(y),abs(x))`, and
`r=a/b`, retaining whether the magnitudes were swapped.

1. For `r < 2^-40`, the first-octant angle is `C67(r)`.
2. For `2^-40 <= r <= 3/64`, evaluate the direct kernel below with `z=C67(r)`.
3. Otherwise use `n=ceil(32*r-1/2)`, so `2 <= n <= 32`, and `c=n/32`.
   Set `z=C67(C67(a-c*b)/C67(b+c*a))`. The small-integer products `c*b`
   and `c*a` are complete before their sum/subtraction is cut. Compute the
   kernel, truncate that intermediate kernel sum with `C67`, then add the
   ROM value `atan(n/32)`.

The index is nearest with ties to the lower cell. D0025 proves that odd-tie
indexing is output-equivalent within this graph for every input; this does
not identify the hidden silicon selector.

The public ROM coefficients are literal exact dyadic values in the C source.
Let `M(a,b)=C67(a*b)`, `A(a,b)=N64(a+b)` and `W(a,b)=C67(a+b)`.
Both kernels use `u=N64(z*C64(z))` and `v=M(u,u)`.

The direct kernel uses ROM indices 118--123 in two interleaved chains:

```text
odd  = W(C119, M(v, A(C121, M(v, C123))))
even = W(C118, M(v, A(C120, M(v, C122))))
```

The table kernel uses ROM indices 114--117:

```text
even = W(C114, M(v, C116))
odd  = A(C115, M(v, C117))
```

For either kernel:

```text
h      = A(M(u, odd), even)
tail   = M(M(z, u), h)
kernel = z + tail
```

These are exact real sums until a specified cut or final rounding. A direct
kernel sum is not truncated merely because the table-path kernel is.

If quadrant restoration follows (magnitudes swapped, or x negative), first
truncate the first-octant angle `t` with `C67`. Restore the quadrant using
the corresponding 67-bit ROM constants:

- Swapped and x positive: `pi/2 - t`.
- Swapped and x negative: `pi/2 + t`.
- Not swapped and x negative: `pi - t`.
- Otherwise retain `t`.

Apply y's sign and perform the requested architectural rounding once. C1
indicates whether that final rounding increased magnitude. The current
underflow rule tests tininess on the retained angle **before** final rounding,
including directed rounding that produces the minimum normal output.

## Architectural classes

Signed-zero/infinity quadrants follow Intel's FPATAN result-class table.
Unsupported encodings produce the indefinite quiet NaN and IE. Signaling
NaNs are quieted and raise IE; when both operands are NaNs, the ordinary x87
quiet/signaling and significand-priority rules apply. These class/propagation
rules are specified in [Intel SDM Vol. 2A, FPATAN](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf)
and [Vol. 1, NaN handling](https://cdrdv2-public.intel.com/874241/253665-090-sdm-vol-1.pdf).

An exponent-zero nonzero operand raises DE on a non-NaN/unsupported path,
including a pseudo-denormal with its explicit integer bit set. Its numerical
value nevertheless uses effective exponent 1. A zero result from an exact
zero/infinity special path does not raise PE; an ordinary nonzero finite
transcendental path does. Undefined condition bits are outside this contract.

## What this does not establish

These are not mathematically correctly rounded atan2 results: the CPU's
retained-width arithmetic measurably differs from that function. The evidence
does not prove universal accuracy across every raw80 pair or CPU revision.
The independent Goldmont operation listing supports the interleaved polynomial
structure and distinct operation classes, but not a physical Skylake decode.
