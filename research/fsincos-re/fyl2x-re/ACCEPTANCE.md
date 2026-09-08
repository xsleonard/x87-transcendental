# Logarithm acceptance and reproduction

**FYL2X and FYL2XP1 are implemented.** The final fixed C program has no known
mismatch in the retained reference evidence and passed the **420,212-case
L0005 prospective challenge** with identical frozen source: 185,212 FYL2X
and 235,000 FYL2XP1 observations, all four rounding modes and selected PC24,
PC53 and PC64 cases. Results, C1, arithmetic exceptions, preload flags,
control words and stack-pop transitions were checked.

The target is the recorded Skylake Xeon context with signature `00050654`
and reported microcode `0x1`; the context reports a hypervisor. This is
observed context identity, not independent physical microcode attestation.
A second processor was not required and was not used for this extension.

## Retained evidence and discovery history

All five packs contain distinct instruction/control/ordered-operand tuples.
The final C and independent exact-rational reference are authenticated against
**941,808** saved observations (400,552 FYL2X and 541,256 FYL2XP1).
The [machine-readable replay](../paper/evidence/logarithm-replay.json)
records all checked fields, hashes, controls and per-instruction counts.
The source-identical L0005 rows are prospective validation; the other packs
are regression evidence after correction. No earlier failed prediction is
rewritten or relabeled as an original pass.

| Pack | Hardware observations | Rows missed by its frozen predecessor |
| --- | ---: | ---: |
| L0001 | 8,896 | 306 |
| L0002 | 145,116 | 0 |
| L0003 | 174,480 | 780 |
| L0004 | 193,104 | 1,206 |
| L0005 | 420,212 | 0 |

L0001 tested a direct transfer from the public ROM/listing. Its 306 mismatched
rows led to the four independently derived table corrections and FYL2XP1's
wide-add table entry. L0002 then passed without a mismatch. L0003 exposed
780 underflow-flag differences while all result/C1 bits matched. L0004's
frozen stored-result/inexact hypothesis missed 1,206 status rows. The final
rule tests the 64-bit rounded value with unbounded exponent and retains the
kernel's inexact indication, including exact final products. It resolves
both earlier status failures with a general arithmetic rule. L0005 is the
fresh confirmation of that final source.

## Independent support and scope

- [Public source audit](../paper/evidence/logarithm-public-source-audit.json):
  77 ROM payload projections, independently derived splits at decimal
  precisions 128 and 192, and addressed direct/table/tiny instruction slices.
- [Operation ablations](../paper/evidence/logarithm-operator-ablations.json):
  the retained data distinguish all seven tested alternative arithmetic
  policies, including both simpler square rules and the quotient widths.
- [Implementation checks](../paper/evidence/logarithm-implementation-checks.json):
  public C API parity and address/undefined-behavior sanitizer replays.
- `make check`: 854 bundled hardware witnesses through the C CLI, C API
  and rational reference, API error atomicity and exact domain endpoint proof.

The normalized table selector always has `0 <= i <= 31`. Finite positive
raw80 inputs have exponents from -16445 to 16383 after normalization, so
exponent restoration is a bounded integer operation. Direct denominators
are bounded away from zero; tiny FYL2XP1 inputs use the explicit linear
branch. Both coefficient families have a symbolic polynomial interpretation,
but the named precision cuts and evaluation order define the numerical result.
All branches use arithmetic and public constants; there are no operand-specific
corrections, fitted selectors, saved-result tables or private-source code.

The final challenge combines independent full-significand/exponent strata,
independent samples throughout the upper FYL2XP1 interval, all table joins,
near-one inputs, tiny-path joins, signed exceptional classes, equal-payload
NaNs, exact subnormal products and inverse rounding-surface constructions.
Model-guided boundary tests are identified as such; the independent strata
are selected without candidate arithmetic. History exclusions are recorded
as holds and are not counted as tested cases or complete windows.

The numerical wrapper assumes masked exceptions, clear initial latches and
valid two-deep stack entries loaded as raw80. It does not emulate arbitrary
incoming state, unmasked traps, pointer registers or undefined condition bits.
FYL2XP1 finite `x` is restricted to Intel's documented
`|x| <= 1-sqrt(1/2)` interval; its exact raw80 endpoint is enforced by the API.
This is strong finite validation of a general program, not exhaustive raw80
pair enumeration or a uniquely recovered physical circuit.

## Reproduce without executing hardware

```sh
make -C fsincos-re/fyl2x-re check PYTHON=python3
python3 fsincos-re/fyl2x-re/verify_archive.py \
  fsincos-re/tmp/fyl2x-re/l000{1,2,3,4,5} \
  --candidate fsincos-re/fyl2x-re/build/x87-log \
  --python-stride 1 --out /tmp/logarithm-replay.json
```

The small check needs only bundled files. The full replay requires the named
saved research packs and validates every source/input/output hash before
comparison. It never executes the native capture harness. The capture files
are retained for provenance; executing them again is forbidden by the permanent
no-repeat ledger, including any started or uncertain request.

Final source pins:

- C: `2c35028920bb3603cc157974b0be7f935329e0ff32ea61ecf18e7698074b6f7b`
- Independent rational reference: `6ea14e017ee11eb5a1c3e5d462ecf2fc2c4db43906e008935845a66a75782584`

Original-work licensing remains undecided; no public upload was performed.
