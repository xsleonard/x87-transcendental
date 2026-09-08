# Independent FPATAN challenge — D0066 / D0067

This input-only pack contains **445,588 distinct tuples** from 110,535
admitted operand pairs, all four rounding modes and sampled PC24/53 cases.
Families are mathematical rounding-boundary brackets, exact ratio lattice
witnesses, raw-bit exponent strata and sixteen exhaustive 17x17 two-operand
windows. Selection uses neither candidate arithmetic nor hardware labels.

Observed once on Skylake `00050654:0x1` (D0066) and i7 `000506e3:0xf0`
(D0067): zero output/C1/exception mismatches and byte-identical complete raw
output streams. **Do not recapture these tuples on either recorded context.**
Audit and reserve fresh tuples before using the pack on a different context.

No numerical predictions, hardware labels or private records are packaged.
The pack is included in [CATALOG-D0066.json](../../CATALOG-D0066.json).
See the [analysis](../../../ANALYSIS-D0065-D0070.md) for construction,
conservative holds, original UNKNOWN solver results, constructive witnesses
and evidence limits. Finite independent verification is not an all-input
silicon-equivalence proof.
