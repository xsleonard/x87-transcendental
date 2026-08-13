# F2XM1 and FPTAN binary64-space validation

`src/sibling_exhaustive.c` compares native Skylake F2XM1 or FPTAN with the
corresponding reconstructed C entry point. It uses the same bijective
binary64 permutation, exact binary64-to-x87 conversion, RN/RD/RU modes, class
inventory, sharding, and bounded reporting as the standalone-FSIN comparator.

FPTAN comparison includes its tangent, C1, C2, unchanged input on range
return, and the value pushed in ST(0). F2XM1 comparison distinguishes its
documented finite `[-1,+1]` range from empirical out-of-range behavior.

## Reproduction

Build and run on native x86, not the Apple Silicon development host:

```sh
make -C fsincos-re/src sibling_exhaustive
fsincos-re/src/sibling_exhaustive \
  --instruction=f2xm1 --bits=24 --threads=2 --mode=all
fsincos-re/src/sibling_exhaustive \
  --instruction=fptan --bits=24 --threads=2 --mode=all
```

The 2026-07-23 Skylake build used:

```text
permutation seed  f51c05d1a64e2026
sibling_exhaustive.c
  32453b23008078d036ae64ca4ceb3ca7e8eaf26c0daf3936e2ce2b44561fa539
fsincos_skylake.c
  c8aa7491d3df09b75696fdd44b17474320c4e0af15df665da561632cde94407a
source archive
  ca4f33650cfb44848e15ff54292bca77f0bfea912ae0fc199a9f53b32247133e
Linux executable
  c458555408bf77b5258eade459c77eb64cef3c3fdb3348140da82267dcd0cde3
```

Tiny `2^4`, `2^8`, and `2^12` gates and one-/two-thread `2^16` runs agree.
Two explicit `2^23` shards also sum exactly to each complete `2^24` result.

## F2XM1 result

The `2^24` traversal covers:

```text
inputs=16777216
observations=50331648
defined finite inputs=8377427
out-of-range finite inputs=8391474
special inputs=8315
```

All 25,132,281 RN/RD/RU observations in the documented finite range have
zero result or C1 differences. All sampled finite out-of-range observations
also match the processor's empirical unchanged-input behavior.

There are 12,327 result differences, exactly three for each of the 4,109
binary64 signaling NaNs. Hardware quiets the NaN; the model currently returns
the signaling encoding unchanged. Quiet NaNs match. No infinity encoding
appears in this deterministic prefix.

The numeric F2XM1 graph is therefore substantially supported by this trial,
but the complete architectural model is not finished until signaling-NaN
handling is represented.

### F2XM1 `2^32` extension

The same executable subsequently completed the deterministic counter range
`0..2^32-1`:

```text
inputs=4294967296
observations=12884901888
defined finite inputs=2145431144
out-of-range finite inputs=2147441527
special inputs=2094625
output_misses=3134754
defined_output_misses=0
C1_misses=0
defined_C1_misses=0
elapsed=2394.655079
inputs_per_second=1793564.064
```

The documented finite range therefore has zero result or C1 differences over
6,436,293,432 RN/RD/RU observations. All sampled finite out-of-range values
also match the empirical unchanged-input behavior.

The complete mismatch total is exactly
`1,044,918 signaling NaNs * 3 modes = 3,134,754`. There are no other result
differences, C1 differences, or model-interval failures. The traversal
contains 1,049,707 quiet NaNs, all of which match. Exact zero and infinity
encodings do not occur in this deterministic prefix.

## FPTAN result

The `2^24` traversal covers:

```text
inputs=16777216
observations=50331648
defined finite inputs=8894148
finite range-return inputs=7874753
special inputs=8315
```

Range handling is exact: there are no C2 differences and every C2 return
preserves the input. Successful ordinary finite cases always push exact
`1.0`.

The defined finite range contains:

```text
output differences=25
C1 differences=18
affected inputs=18
```

Every result difference is one adjacent x87 value. The mode distribution is
11 RN, 7 RD, and 7 RU output differences; all 18 C1 differences are RN.
Separate replay through the capture binary and standalone model CLI
reproduces all 25 result and 18 C1 differences.

The 18 exact inputs are:

```text
4039 da28b87c53033000
403b c0f1dcd732738000
403b f5e5383a74aa0000
403c 8d8935f5895fa800
403c 91df36fdbaae1000
403c a1441327fdc24000
403c a5d8f19fd3df5000
403d b7fcfadbf0691800
403d c986dafe33b96800
403d d1c13506eb22e800
403d fdc9efd7eba71000
c03a 8a9c14926dce3000
c03c 8d4f7f2c28979000
c03c d9202f3036e10800
c03d abb7a5bd0276f800
c03d b1eab9beceafd000
c03d f0128b4324f76800
c03d feb53a190ad93800
```

All have unbiased exponents 58 through 62. Four are also members of the
standalone-FSIN h377 residual set. This strongly localizes the new numeric
class to large-argument range reduction or retained state immediately after
reduction, rather than a missing broad FPTAN polynomial or table term.

FPTAN special inputs expose a separate stack rule. For all 8,315 sampled NaN
encodings, hardware pushes a second copy of the quieted/preserved NaN result,
not exact `1.0`; the same occurs for infinity in a direct probe. The current
batch model always prints exact pushed one, producing 24,945 pushed-value
differences in the sampled special set. Tangent values themselves match.

The correct status is therefore:

- F2XM1 finite numeric reconstruction: no differences found in this trial.
- F2XM1 complete architectural behavior: signaling-NaN handling incomplete.
- FPTAN reconstruction: incomplete for rare large finite arguments and
  special-value push behavior.

## 2026-08-08 re-run: h403 fixes close every residual class

With the h403 changes — unconditional exact-division FPTAN quotient,
F2XM1 signaling-NaN quieting, and the NaN/indefinite FPTAN push rule in
both the batch model and this harness's expectation — the `2^24`
deterministic traversals are completely clean for both instructions:

```text
fptan : inputs=16777216 observations=50331648
        output/C1/C2/C2-output/pushed/interval misses = 0/0/0/0/0/0
f2xm1 : inputs=16777216 observations=50331648
        output/C1/C2/C2-output/pushed/interval misses = 0/0/0/0/0/0
```

This closes the FPTAN 25-result/18-C1 large-argument class (all 18 inputs
now exact under all modes), the 24,945 sampled pushed-value differences,
and the F2XM1 signaling-NaN class from the earlier trials.

```text
fsincos_skylake.c    2d72aee97a911d60e187db7e3030454ea59c92259a51a1b13eb0ab212f01aa70
sibling_exhaustive.c 2f7acce7dd447b9c7f344f022f276d56b5344efc82ddd9421418e356b14474cf
```

The `2^32` extensions completed on the capture host
(`fsincos-residual-20260807-1/h403/sibling_{f2xm1,fptan}_32.log`) with the
same result: both instructions traverse all 4,294,967,296 deterministic
counter values (12,884,901,888 RN/RD/RU observations each) with zero
output, C1, C2, C2-output, pushed-value, or model-interval differences.
For F2XM1 this removes the 3,134,754 signaling-NaN differences of the
earlier `2^32` trial; for FPTAN it is the first complete `2^32` traversal,
and it is entirely clean.
