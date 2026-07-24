# FSIN binary64-space validation

`src/fsin_exhaustive.c` is an explicitly requested native-x86 comparison
harness. It embeds the standalone FSIN C model and executes hardware FSIN in
the same process.

## Input space

- The counter is transformed by a bijective SplitMix64 permutation with
  default seed `0xf51c05d1a64e2026`.
- A complete 64-bit counter traversal visits every IEEE-754 binary64 encoding
  exactly once.
- Each encoding is converted exactly to its x87 extended-register value.
  Binary64 subnormals are normalized as they are after a successful load.
- `--start` and `--count` define nonoverlapping shards. `--bits=N` is shorthand
  for `--start=0 --count=2^N`.

## Comparison

For RN, RD, and RU the harness checks:

- complete x87 result encoding;
- C2 and unchanged input on a C2 return;
- C1, derived from the model's directed bounds. The away-from-zero bound is
  the incrementing result and the toward-zero bound is not.

The harness counts every failure and prints only the first `--max-report`
records. It does not yet compare PE, IE, or other exception-status bits.

The C1 derivation has zero differences and zero interval failures against the
saved Skylake structured, dense, and h347 standalone-FSIN status captures:
`0/1,461,246` RN/RD/RU observations.

## Build and run

Build on the Debian x86 host, not the local Apple Silicon Mac:

```sh
make -C fsincos-re/src fsin_exhaustive
fsincos-re/src/fsin_exhaustive \
  --bits=16 --threads=2 --mode=all --max-report=64
```

Example explicit shard:

```sh
fsincos-re/src/fsin_exhaustive \
  --start=0x100000000 --count=0x100000000 \
  --threads=2 --mode=all --max-report=64
```

## 2026-07-22 Skylake trials

Tiny gates at `2^4`, `2^8`, and `2^12` pass with zero output, C1, C2,
C2-output, or model-interval failures. One- and two-thread `2^12` runs agree.

The requested `2^16` trial uses:

```text
start=0000000000000000
count=65536
seed=f51c05d1a64e2026
threads=2
mode_mask=7
```

It covers 65,536 inputs and 196,608 RN/RD/RU observations, including 45
binary64 subnormals, 20 quiet NaNs, and 15 signaling NaNs. All comparison
counts are zero.

Reproduction hashes:

```text
fsin_exhaustive.c  50b9121b5176c4a12f0cb5602bcc037179e93111beafcf39a869e4fa77d2c1a3
fsincos_skylake.c  c8aa7491d3df09b75696fdd44b17474320c4e0af15df665da561632cde94407a
Linux executable   021c5a9ccfaabcea52e5f493ff3f16821e17467ba0afe8cae600160135225f81
```

The subsequent `2^24` trial covers 16,777,216 inputs and 50,331,648
RN/RD/RU observations:

```text
classes=zero:0,subnormal:8259,normal:16760642,infinity:0,qnan:4206,snan:4109
output_misses=12
C1_misses=15
C2_misses=0
C2_output_misses=0
model_interval_failures=0
elapsed=5.702937
inputs_per_second=2941855.446
```

The 12 result differences occur on 12 distinct inputs. Each is one x87
representable step. Independent replay through the original capture binary
and a separate standalone-model process confirms every result difference.
The two explicit `2^23` counter shards reproduce totals of 6/8 and 6/7
result/C1 differences, respectively, so their sum also reproduces the full
12/15 result.

| Counter | Raw binary64 | Exact x87 input | Result mode | C1 mode(s) |
|---:|---:|---:|:---:|:---:|
| `065cb6` | `41adab8068cf4465` | `401a:ed5c03467a232800` | RD | RD |
| `0adb8f` | `43d023fd8101ab2b` | `403d:811fec080d595800` | RD | RN, RU |
| `0e3b12` | `43bebca7074e9540` | `403b:f5e5383a74aa0000` | RN | RN |
| `2d24ee` | `43dae47fd03a458b` | `403d:d723fe81d22c5800` | RN | RN |
| `362d21` | `43d38ef924200cf3` | `403d:9c77c92100679800` | RN | RN |
| `76528f` | `c3a15382924db9c6` | `c03a:8a9c14926dce3000` | RD | RN, RU |
| `b1a720` | `c3d576f4b7a04edf` | `c03d:abb7a5bd0276f800` | RN | RN |
| `cfe50b` | `c0614fb467db2fe2` | `c006:8a7da33ed97f1000` | RN | RN |
| `c98892` | `c1c9971526bbbbe8` | `c01c:ccb8a935dddf4000` | RD | RN, RU |
| `e46183` | `c3b9879f1319c8f9` | `c03b:cc3cf898ce47c800` | RN | RN |
| `f75cbc` | `43d47dd8218af175` | `403d:a3eec10c578ba800` | RN | RN |
| `f8e292` | `43c1b126beb12bf5` | `403c:8d8935f5895fa800` | RN | RN |

This supersedes any interpretation that the previous zero-difference corpora
proved universal standalone-FSIN parity. They remain exact, but the larger
binary64-space trial exposes another rare class. Eleven of the twelve inputs
have unbiased x87 exponents from 27 through 62; one has exponent 7. The
concentration at large reduced arguments makes range-reduction or a retained
state after reduction the first hypothesis to test. It is not evidence of a
missing broad polynomial term.

## Frozen h377 regression fixture

The 12 exact seeds are frozen separately from every earlier corpus:

```text
capture-kit/inputs/fsin_binary64_misses_h377.txt
capture-kit/inputs/fsin_binary64_misses_h377.meta.txt
capture-kit/expected/fsin_binary64_misses_h377_{rn,rd,ru}_status.txt
```

The input and golden-output hashes are checked by
`experiments/h377_fsin_binary64_residual_gate.py`. The default policy permits
scores no worse than 3 result and 4 C1 differences, so it is safe to use
while the residuals remain unsolved:

```sh
make -C fsincos-re/src check-fsin-h377
```

`--expect-baseline` requires exactly 3/4 and verifies the present
model/fixture pairing. `--require-zero` is the promotion gate for a completed
fix. The fixture is not part of the default build or test target.

The fixture originally exposed 12 result and 15 C1 differences.  Replacing the
reciprocal quotient seed with literal exact division by the 66-bit reduction
constant removes nine result and eleven C1 differences with no ordinary-corpus
regression.  The three remaining result inputs have unbiased exponents 27, 7,
and 29; every former exponent-58--62 result case is solved.  The twelve inputs
remain frozen so the resolved cases continue to guard the reduction change.

`capture-kit/run_fsin_binary64_misses_h377_prebuilt.sh` can recapture the
three status files on native x86 without a compiler. Any diagnostic
neighborhood must be stored as another corpus rather than appended to h377.
This preserves its ordering, hashes, historical counts, and role as an
immutable twelve-seed oracle.

At the full-pass rate, a `2^32` run would take about 24 minutes and a `2^40`
run about 4.3 days on this VPS if throughput remains stable. The 12 cases
should be localized before expanding the scan because they provide much
stronger diagnostic seeds than another undifferentiated mismatch count.
