# Numerical research tools

These modules support offline floating-point experiments and saved-capture
comparisons.

- `p6_value.py` defines the packed numerical value and validates its fields.
- `p6_arithmetic.py` implements exact values, configurable quantization,
  arithmetic, and x87 value conversion.
- `p6_fadd.py` evaluates alignment, sticky-bit, and retained-carrier hypotheses.
- `p6_constants.py` reads the named cosine coefficients from the public
  `tests/data/sibling-constants.json` fixture at the repository root.
- `numerical_capture.py` reads x87 capture rows for the experiments.

Run each of the four `p6_` modules directly with Python for its embedded checks.
