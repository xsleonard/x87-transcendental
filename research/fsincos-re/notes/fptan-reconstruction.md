# FPTAN reconstruction

## Current independent validation checkpoint (2026-09-06)

The unchanged authoritative FPTAN implementation matches **495,432 fresh
observations on each of Skylake and i7**, with zero tangent, pushed-value,
C1 or C2 misses. All four rounding modes are covered; PC24/PC53 are sampled
alongside complete PC64 coverage. The full captured output/status streams
are byte-identical across the two recorded CPU contexts.

These inputs were selected independently of candidate arithmetic using
mathematical output boundaries, poles/zeros, exact residue/SMT witnesses,
raw-significand strata and adjacent windows. See
[T0001–T0003](../fptan-re/ANALYSIS-T0001-T0003.md) and the
[reusable corpus v1](../fptan-re/corpus-v1/README.md).
Exception words are captured and cross-compared, not predicted by the
numerical adapter. This is finite validation, not all-input closure.
No algorithm or paper changes were made for this campaign.

## Historical reconstruction result (before the h403 addendum below)

The reconstructed Skylake FPTAN model covers the direct-tiny, six-coefficient
polynomial, table, range-reduction/quadrant, final-division, and pushed-one
paths.  Across the 240,000-input dense set and 50,038-input structured sweep:

- polynomial path: 0 result and 0 C1 misses on 108,231 inputs under RN/RD/RU;
- table path: 0 result and 0 C1 misses across 181,805 inputs under RN/RD/RU;
- C `--fptan` path: 0 result misses in 870,114 complete mode comparisons.

A deterministic 1,000,002-input scan of the two formerly failing structural
classes found five new legacy-model failures plus the two old controls.  The
final model matches all one million Skylake RD results.  A focused recapture
of all seven residuals also matches RN/RD/RU results and C1 exactly.

A fresh Debian GCC build passes selftest.  The remote one-million-input replay
reports `0/1000002` differences and produces an empty mismatch file.

A later deterministic `2^24` binary64-space trial shows that this was
corpus-exact rather than universal. Among 8,894,148 valid finite inputs under
RN/RD/RU, 18 large arguments produce 25 adjacent-value result differences and
18 C1 differences. All have unbiased exponents 58--62, and four overlap the
standalone-FSIN h377 residuals, making range reduction or its immediately
retained state the leading shared cause. In addition, NaN and infinity paths
push a second copy of their special result rather than exact `1.0`, which the
current batch model does not represent. See
`notes/sibling-exhaustive-validation.md`.

## Arithmetic graph

The table reconstruction consumes three distinct operand widths: the lookup
constants are 67 bits, the cosine tail is 64 bits, and the complete sine
analysis carrier is 69 bits.  Reading that sine carrier through RN64 before
the multiplier resolves the earlier apparent operation-class conflict.

The surviving table rules are:

- every ordinary P/Q state-producer FMUL: magnitude chop67;
- every ordinary P/Q state-producer FADD: RN64;
- distinct cosine-tail multiply-class operation: RN64;
- complete sine input read: RN64;
- every ordinary reconstruction FMUL: magnitude chop67;
- every reconstruction FSUB: magnitude chop67;
- final quotient: exact ratio followed by architectural RN/RD/RU rounding.

This changes the complete table score from 23,667 misses for the exact graph,
and 799 for the superseded away67-product proxy, to zero.  Uniform 66-bit
divide-input formatting produces over 31,000 misses.  The literal P5
alignment/sticky/borrow add bus produces over 35,000 and is not the validated rule.

The polynomial path uses the six sine and cosine coefficients and transfers
the independently constrained shared classes directly:

- ordinary FMUL: magnitude chop67;
- ordinary FADD: RN64;
- multiply-class sine scaling: RN64;
- ordinary FSUB: magnitude chop67.

Direct inputs at exponent -69 or below bypass the polynomial and return the
operand.  Cutoff -70 leaves 54 inputs wrong; cutoff -68 leaves 37; cutoff -69
is exact.

## Final operation-class closure

h267 first captured every adjacent x87 significand through distance 4096
around the two old residuals.  Each failure was isolated to its seed.  h269
then sampled one million direct/reduced negative cell-36 arguments and found
five more residuals.  Their required corrections had both signs, falsifying
the earlier one-direction final-numerator interpretation.

h273 propagated signed retained-unit perturbations through every named FPTAN
node.  All seven failures were reachable by a one-unit change at the RN64 read
of the shared sine state.  h274 localized that state difference to the final
P-Horner sum or its downstream P products.  Those sites still used empirical
RN64/away67/chop65 product representatives from before F2XM1 solved the shared
ordinary-FMUL class.

h275 changes only the four ordinary multiply sites to chop67: P/Q Horner
products, P times square, and that product times the residual.  It closes all
seven focused failures, the complete dense table corpus, and the structured
sweep.  It is componentwise no worse on every frozen shared table partition
and improves two focused lane metrics.  The master FSIN/FCOS/FSINCOS sweep
counts remain unchanged at 62/74/110 mode misses, so the change introduces no
trig regression.

## Reproduction

```sh
python3 experiments/h260_fptan_multiplier_input_format.py
python3 experiments/h261_fptan_divide_input_format.py
python3 experiments/h262_fptan_literal_subtract.py
python3 experiments/h263_fptan_residual_node_search.py
python3 experiments/h264_fptan_polynomial_transfer.py
python3 experiments/h268_fptan_residual_neighborhood.py
python3 experiments/h271_fptan_scan_residuals.py
python3 experiments/h272_fptan_sibling_intervals.py
python3 experiments/h273_fptan_unit_causal_localization.py
python3 experiments/h274_fptan_shared_sine_localization.py
python3 experiments/h275_shared_fmul_class_transfer.py --section dense
python3 experiments/h275_shared_fmul_class_transfer.py --section sweep
python3 experiments/h275_shared_fmul_class_transfer.py --section residuals
make -C src fsincos_skylake
python3 experiments/h265_fptan_c_parity.py src/fsincos_skylake
python3 experiments/h276_fptan_shared_fmul_c_parity.py src/fsincos_skylake
```

## h403 addendum (2026-08-08): exact-division quotient and push rule

- The 18 large-argument residual inputs from the binary64-space trial are
  closed by replacing the reciprocal-seed `N` with the same literal exact
  division by the 66-bit reduction constant that Round 53 selected for the
  FSIN/FCOS operation-class path.  A model-vs-model scan shows the two
  quotients diverge on zero of the 290,038 sweep/dense inputs under all
  three modes, and the exact quotient removes all 25 result differences on
  the 18 inputs; it is now unconditional in `fptan_core`.
- The special-value push rule is represented: NaN/indefinite tangents push
  a second copy of the result rather than exact one, in both the batch
  entry and `sibling_exhaustive`'s expectation.
- See `experiments/h403_fptan_and_h377.sh` and
  `notes/sibling-exhaustive-validation.md` for the re-run trial results.
