# F2XM1 reconstruction

Current integration, September 7: the tiny path now rounds its exact
stored-ln(2) product directly to raw80, correcting the former subnormal-store
truncation. The C and exact reference match the 54,128-case challenge on each
of the Core i7-6700 and Xeon, including RZ and selected full PC groups.
See the [integration evidence](../paper/evidence/f2xm1-integration.json).
The reconstruction and discovery chronology below retains its original
scope and predictions; later addenda supersede earlier limitations.

The Skylake finite-value output path is reconstructed bit-exactly
for all current RN/RD/RU captures. A later deterministic `2^24` binary64-space
trial adds zero result or C1 differences over 25,132,281 observations in the
documented finite range. The complete architectural model is not yet exact:
all 4,109 sampled signaling NaNs are returned unquieted by the model, producing
12,327 mode differences. A subsequent `2^32` traversal raises the clean finite
evidence to 6,436,293,432 RN/RD/RU observations. Its 3,134,754 differences are
exactly the 1,044,918 sampled signaling NaNs under three modes; no other result
or C1 difference occurs.

## Numeric graph

- `|x| > 1`: outside the documented input range; sampled Skylake behavior
  preserves the operand unchanged.
- `x = +1`: return `+1`; `x = -1`: return `-1/2`.
- input exponent below `-68`: final multiply/writeback of `ln(2) * x`.
- exponent `-68` through the value immediately below `1/4`: an eleven-
  coefficient polynomial in `z = ln(2)*x`.
- `1/4 <= |x| < 1`: reduce around a midpoint `b`, evaluate a six-coefficient
  polynomial in `z = ln(2)*(x-b)`, then form
  `(2^b-1) + 2^b*expm1(z)`.

For `1/4 <= |x| < 1/2`, the midpoint numerators are odd values `33..63`
over 128.  For `1/2 <= |x| < 1`, they are `66,70,...126` over 128.  The
lookup payloads are RN67 values of `2^b-1`.

Every ordinary multiply in both polynomial paths uses magnitude chop at 67
bits.  Every ordinary add uses RN64.  The distinct multiply-class operation
used for `ln(2)` scaling and two long-path products uses RN64.  The terminal
add or multiply performs architectural RN/RD/RU rounding.

The independently regenerated `b=-57/128` lookup payload is
`0x43fcb5810d1604f33`.  It scores 0 misses on 2,563 selected cell inputs;
the older published `...4f37` payload produces 3,869 mode misses on every
one of those inputs.

## Validation

- Exact mathematical baseline (h251): every in-domain processor result is
  correctly rounded or one adjacent x87 value away.
- Existing dense/sweep/target Python model: 0 result or C1 misses over
  889,512 instruction/mode observations.
- Fresh h257 hardware-blind boundary/class capture: 0 result or C1 misses
  over 25,650 observations.  Neighboring cutoffs and eight operation-class
  alternatives fail independently.
- C model: 0 misses over 915,162 result comparisons.
- Fresh Debian GCC build: byte-identical h257 RN/RD/RU output on the remote
  Skylake host; selftest passes.
- Deterministic `2^24` binary64 traversal: zero result/C1 differences over
  8,377,427 documented-range inputs under RN/RD/RU. The only differences are
  the signaling-NaN quieting class described above. See
  `notes/sibling-exhaustive-validation.md`.
- Deterministic `2^32` extension: zero result/C1 differences over
  2,145,431,144 documented-range inputs and 6,436,293,432 mode observations.
  Runtime on the two-vCPU Skylake VPS was 2,394.655 seconds.

## Reproduction

```sh
python3 experiments/h251_f2xm1_exact_baseline.py
python3 experiments/h252_f2xm1_literal_graph.py
python3 experiments/h253_f2xm1_path_threshold.py
python3 experiments/h254_f2xm1_operation_search.py
python3 experiments/h255_f2xm1_table_word.py
python3 experiments/h256_f2xm1_long_transfer.py
python3 experiments/h258_f2xm1_validation.py
make -C src fsincos_skylake
python3 experiments/h259_f2xm1_c_parity.py src/fsincos_skylake
```

Run the C model with `--batch --f2xm1 --rc=rn|rd|ru`.

## h403 addendum (2026-08-08): signaling-NaN quieting

`f2xm1_core` now quiets signaling NaNs (sets the quiet bit, preserving the
payload) before the finite dispatch, matching hardware.  This closes the
only residual class of the earlier `2^24`/`2^32` binary64-space trials;
see `notes/sibling-exhaustive-validation.md` for the re-run.
