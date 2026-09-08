# FYL2X and FYL2XP1: a shared logarithm engine

The portable C model evaluates the observed Skylake numerical programs for
`FYL2X` ($y\log_2x$) and `FYL2XP1` ($y\log_2(1+x)$). Ken Shirriff's published
Pentium ROM reconstruction supplies the coefficients and split table.[^ken]
The public Goldmont listing supplies an independent operation-order clue;
its transfer to Skylake is tested with frozen hardware predictions.[^listing]

This implementation models processor results, including their internal
approximations. It is not a correctly rounded mathematical logarithm library.
The C source uses GMP rational arithmetic to make every precision cut explicit.
The separately written [Python reference](model.py) uses exact fractions.
Neither implementation executes x87, calls a host logarithm, or looks up saved
input/output pairs. See [ACCEPTANCE.md](ACCEPTANCE.md) for measured coverage.

## Arithmetic notation

`T_p(a)` truncates the exact value toward zero to `p` significant bits.
`N_p(a)` rounds to nearest, ties to even. Define

$$M(a,b)=T_{67}(ab),\qquad A(a,b)=N_{64}(a+b),\qquad W(a,b)=T_{67}(a+b).$$

The direct-path square has an asymmetric input cut:

$$u=N_{64}\bigl(z\,T_{64}(z)\bigr).$$

These cuts are instruction-internal and independent of architectural PC and RC.
The final multiplication by `y` rounds to raw80 using the selected RC. Keep
that multiplication unrounded until the final raw80 conversion. In particular,
rounding the logarithm to 64 bits first can change the result.

## Direct path and cancellation avoidance

`FYL2X` uses the direct path for $7/8\leq x\leq9/8$. Form

$$z=T_{67}\left(\frac{M(2\log_2e,A(x,-1))}{W(x,1)}\right).$$

The name $\log_2e$ here denotes the **literal ROM approximation**, not an
on-demand evaluation of the mathematical constant. For `FYL2XP1`, use the
direct path for $|x|\leq1/8$ and form

$$z=T_{67}\left(\frac{M(2\log_2e,x)}{W(x,2)}\right).$$

This preserves a small input without first rounding `1+x`. At nonzero
`FYL2XP1` inputs with $\lfloor\log_2|x|\rfloor\leq-70$, bypass the rational
transform and return $M(\log_2e,x)$ as the retained logarithm.

Let `C200` through `C205` denote the six published long-path coefficients.
The exact operation order is:

```text
u    = N64(z * T64(z))
v    = M(u, u)
odd  = A(M(A(M(C205, v), C203), v), C201)
even = A(M(A(M(C204, v), C202), v), C200)
h    = A(M(odd, v), M(even, u))
g    = W(M(h, z), z)
```

Without intermediate cuts this is the odd polynomial

$$g=z+z^3(C_{200}+C_{201}z^2+\cdots+C_{205}z^{10}).$$

The polynomial identity explains the function being approximated; the listed
cuts and interleaved order define the bit-level numerical program.

## Table path

For other positive finite `FYL2X` inputs, normalize $x=m2^e$, $1\leq m<2$.
Choose one of 32 odd-centered bins:

$$i=\lfloor32(m-1)\rfloor,\qquad a_i=\frac{65+2i}{64},\quad0\leq i<32.$$

`FYL2XP1` with $|x|>1/8$ forms $W(1,x)$ and enters this same `FYL2X` path.
The wider addition is essential: substituting a 64-bit addition loses bits.

```text
n    = A(m, -a[i])
n    = A(n, n)
d    = A(m, a[i])
z    = N64(n / d)
lead = M(C195, z)                  # literal log2(e)
u    = M(z, z)
h    = A(M(A(M(C199, u), C198), u), C197)
tail = M(M(h, u), z)
low  = W(A(tail, lead), L[i])
high = A(e, H[i])
g    = W(low, high)
```

The mathematical reduction is

$$\log_2x=e+\log_2a_i+
  2\log_2(\mathrm{e})\operatorname{atanh}\!\left(\frac{m-a_i}{m+a_i}\right).$$

The literal split is $H_i=\mathrm{RN}_{40}(\log_2a_i)$, followed by a
signed 67-bit approximation $L_i$ to the residual. The short coefficients
approximate the cubic, fifth- and seventh-degree corrections for the doubled
ratio `z`. The implementation preserves both table pieces through restoration.

## Literal provenance and corrections

`log_model.c` contains all 77 required literal records, including their
published row numbers and binary scales. The original public TSV is preserved.
Four words in that transcription differ from the independently derived split:

| P5 row | Original significand | Corrected significand |
| --- | --- | --- |
| 207 | `43ace37e8a8000000` | `43ace27e8a8000000` |
| 245 | `6f66cc899b64303f7` | `6f66cc899b64b03f7` |
| 259 | `5c833d56efe4338fe` | `5c813d56efe4338fe` |
| 268 | `4a83eb6e0f93f7a64` | `4a83eb6e0f93f7a44` |

`source_audit.py` recomputes every split at two independent decimal precisions
and checks the upper 64 bits against the pinned public Goldmont ROM.[^rom]
All **77** logarithm-related projections agree after these four corrections.
The projection does not expose the low three significand bits, exponents or
signs; the mathematical derivation supplies the split-table correction values.
Goldmont source structure is not a recovered Skylake microcode listing.

## Architectural wrapper

The [C API](log_library.h) returns raw80 result bits, C1 and the six arithmetic
exception flags for masked exceptions and a valid two-deep stack with initially
clear latches. The calling emulator performs the architectural stack pop.
PC settings 24, 53 and 64 are accepted; the internal precisions stay fixed.
Signed zeros, subnormals, pseudo-denormals, NaN selection and unsupported
encodings are handled before the ordinary finite graph as appropriate.

The nonzero finite path sets PE. UE is determined from the 64-significant-bit
result rounded with **unbounded exponent**, before final subnormal storage
rounding. The retained inexact indication applies even to an exact final
product. Thus a stored minimum normal may or may not set UE, depending on
which side of the unbounded-rounding threshold its prevalue occupies. This
uses Intel's definition of tininess and the observed logarithm-kernel flags;
classifying only the stored raw80 result is insufficient.


For `FYL2XP1`, Intel guarantees $|x|\leq1-\sqrt{1/2}$.[^intel]
The largest positive raw80 member is `3ffd:95f619980c4336f7`. The endpoint
check is exact: for $N=2^{65}$ and this integer significand $S$,
$2(N-S)^2\geq N^2$ while $2(N-S-1)^2<N^2$. Larger finite magnitudes and
infinite `x` return `X87_LOG_OUTSIDE_SCOPE`; the API does not imply an Intel
guarantee for architecturally undefined inputs. NaN/unsupported encodings use
their instruction-level handling. `FYL2X` covers its defined negative, zero,
infinite and NaN cases in addition to positive finite arguments.

[^ken]: Ken Shirriff, [Pi in the Pentium: reverse-engineering the constants in its floating-point unit](https://www.righto.com/2025/01/pentium-floating-point-ROM.html), January 2025.
[^listing]: [Public Goldmont operation listing](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/ucode/ucode_glm.txt), pinned commit `ffc9070233a6e7a26dbabe723289259f087ee20b`; relevant blocks `U6cb5..U6ce2`, `U6e8c..U6ec2`, `U5b64..U5b72`.
[^rom]: [Public Goldmont FP-ROM projection](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt), pinned commit `4237524fe7545c66e42dd986113f220662c06f6a`.
[^intel]: Intel, [Intel 64 and IA-32 Architectures Software Developer's Manual, volume 2A](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf), FYL2X and FYL2XP1 instruction entries.
