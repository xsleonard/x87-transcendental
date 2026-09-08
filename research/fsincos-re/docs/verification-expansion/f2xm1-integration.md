# F2XM1 subnormal rounding: production integration

The C implementation and exact rational reference now round the tiny F2XM1
product directly to the raw80 destination. The original investigation and
capture receipts remain unchanged. This report records the later integration
and its offline checks.

## What changed

The approximation and ROM constants are unchanged. The previous tiny path
rounded the product to 64 significant bits at an unrestricted exponent and
then truncated it when storing a subnormal. Those two steps could lose a
required increment. Rounding a second time at storage would also be wrong:
the first rounding can manufacture a halfway case.

For the smallest inputs, the output spacing is fixed at $2^{-16445}$. The
corrected implementation rounds the exact product once at that spacing. For
raw input exponent fields zero and one, its magnitude in output units is

$$
u = \frac{mL}{2^{67}},\qquad
L=\mathtt{0x58b90bfbe8e7bcd5e},
$$

where $m$ is the raw input significand and $L2^{-67}$ is the existing ROM
approximation to $\ln 2$. Quotient, remainder, sign and RC determine the final
increment. C1 describes that increment.

With round-up, input `0000:000000000000010e` now produces
`0000:00000000000000bc`, matching both saved CPU captures. The previous
implementation produced `0000:00000000000000bb`.

In `src/fsincos_skylake.c`, the new `f2xm1_tiny_raw80` helper is selected only
for finite inputs with normalized exponent at most -16382. Its shift lies in
[67, 130]; the two-word product and guarded shift cases cover that entire
range. Other F2XM1 paths retain their arithmetic. Every nonzero
binary64-derived input has normalized exponent at least -1074, so it cannot
enter the new branch.

In `docs/sibling_reference.py`, `finish_raw80` quantizes directly to
$2^{\max(-16445,\lfloor\log_2|v|\rfloor-63)}$. Only F2XM1 uses the new
finalizer. FPTAN retains its existing finalizer and numerical code.

All original comments and docstrings were preserved. The old `store()`
description is preceded by an added comment explaining its historical
context and the new F2XM1 call order.

## Checks

| Check | Result |
| --- | --- |
| Both saved new CPU captures | Zero C or rational result/C1 mismatches over 108,256 processor observations; 54,128 distinct input/RC/PC tuples |
| Address/undefined-behavior sanitizer build | Identical predictions to optimized C over the complete 54,128-tuple stream; no sanitizer diagnostics |
| Independent integer arithmetic | 42,264 software cases passed optimized and sanitized C, including every native significand 0 through 4096, normalization boundaries, both signs and all RCs |
| Historical H245/H257 C replay | Zero mismatches over 915,162 saved output comparisons; archive manifests rechecked |
| Independent rational H257 replay | Zero result/C1 mismatches over 25,650 saved comparisons |
| Historical RN precision-control groups | 6,466 groups agree across PC24, PC53 and PC64 |
| Existing paired regression | All six saved output/C1 cases pass |
| Source isolation | Removing only the F2XM1 additions and restoring its former finalizer call exactly recovers both baseline source hashes |
| Frozen evidence | All 178 pinned existing campaign/report files remain byte-for-byte unchanged |

The two new captures identify a Xeon with signature `00050654`, microcode
`0x1`, and a Core i7-6700 with signature `000506e3`, microcode `0xf0`. Both
are Skylake-family processors. Their complete saved input and output/status
streams are identical. The second stream is authenticated independently;
the same software predictions are compared with it. No hardware was
executed during integration.

The focused programmer test uses 216 verbatim saved rows covering 18
operands, both signs and all twelve RC/PC combinations per operand. It
includes the original storage failure, a real double-rounding
counterexample, native/pseudo/normal input boundaries, and a result that
rounds up to minimum normal while retaining the captured underflow flag.
The test compares result and C1; it does not claim to implement every status
flag. The C adapter derives C1 from directed internal results because the
public unary API returns the value only.

The regression rejects the original C implementation with 36 output and 30
C1 mismatches, rejects the original rational reference with the same counts,
and rejects a round64-then-raw80 mutation with 24 output and 48 C1 mismatches.
Its fixture includes both capture hashes and the original one-based line
offsets. The full integration audit checked every selected line against
both authenticated archives.

## Run the programmer regression

From the repository root:

```sh
make -C fsincos-re/src check-f2xm1-regressions
python3 fsincos-re/src/test_f2xm1.py \
  --authenticate-archives fsincos-re/tmp/verification-expansion/f2xm1
```

The first command needs only the source, public constants, and bundled
fixture. The second also requires the saved campaign archives. Both run
offline. The test files are `src/test_f2xm1.py`,
`src/test_f2xm1_driver.c`, and `src/f2xm1_regressions.json`.

The complete integration was checked with:

```sh
make -C fsincos-re/src check-f2xm1-regressions check-paired-regressions
clang -O1 -g -std=c11 -fsanitize=address,undefined \
  -fno-sanitize-recover=all -Wno-unused-const-variable \
  fsincos-re/src/test_f2xm1_driver.c -lm \
  -o fsincos-re/tmp/verification-expansion/f2xm1/integration/driver-sanitized
python3 fsincos-re/tmp/verification-expansion/f2xm1/integration/check_integration.py
python3 fsincos-re/tmp/verification-expansion/f2xm1/integration/audit_saved.py
```

The full audit scripts create new receipts and refuse to overwrite them.
The ordinary build still emits pre-existing missing-field-initializer and
unused-function warnings; no sanitizer failures occurred.

## Source and evidence records

Integrated source SHA-256 values:

```text
src/fsincos_skylake.c
14a9772d147d7a2b0c875f578a8397a3544d63f52f2e21f990edcee9cb0878fc
docs/sibling_reference.py
b06d46f2827fb5b83ad3ce17846c630fdd99f966c4a767b07e0a590dd682817f
```

`tmp/verification-expansion/f2xm1/integration/INTEGRATION.json` binds the
integrated sources, test files, this report and the new machine receipts.
`SOURCE-ISOLATION.json` records the reconstructed baseline hashes.
`FROZEN-BEFORE.json` preserves the pre-integration evidence inventory.

This integration does not extend the finite numerical contract to
unsupported encodings, arbitrary initial state or unmasked traps. Historical
duplicate exclusions still receive no new hardware pass credit. Broader
paper, guide and release assembly belongs to the publication task.
