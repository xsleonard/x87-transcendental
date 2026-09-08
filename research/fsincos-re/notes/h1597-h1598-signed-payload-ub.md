# H1597–H1598: broader encoding audit and signed payload scaling

Date: 2026-09-04. Implementation repair, not a new arithmetic selector or a
silicon solution. No hardware execution or new ground-truth observation.

## Discovery

H1597 generates 86,952 unique software encodings: both signs at all 32,768
exponent fields, selected exceptional encodings and domain boundaries,
16,384 unrestricted deterministic bit patterns, and 4,352 denser reduction-
domain cases. It compares the H1590 hash-locked O2 and O2+UBSan models under
both standalone instructions and all four architectural rounding modes.
The bank has no hardware labels and does not prove any output correct.

All 695,616 instruction/mode/encoding legs agree, but each of the eight
sanitized invocations reports a negative left shift at old source line 3444,
`S += (__int128)payload << dp`. This extends the earlier H1590 audit, which
did not cover this failure in its cached row bank. Eight diagnostic lines
are not a count of affected operands.

H1598 uses diagnostic-driven bisection of the software input bank to preserve
a single witness: `3ffb:808699bc7415d7c9`, FCOS/RN. Its trace has distance 12,
payload -1, left exponent -75 and right exponent -87. Thus `dp=4`; the
intended aligned payload is -16, but C's negative signed shift is undefined.
The emulator output is `3ffe:ff7efd166ebf7de5`; it is a software prediction,
not a newly captured hardware value.

## Exact repair and scope

Five signed payload scalings are changed to multiplication by a positive
power of two: the R59 site, R75 site, two R96RES2045 sites and R96M12 site.
The latter analysis branches retain their previous enable defaults. One
comment explains negative-payload scaling. No branch, coefficient, selector,
default, existing comment or historical evidence is removed or changed.

For the default R59 scope, the admitted distances are at most twelve and
the payload shift is in 0..4. A signed int32 payload times 2^4 fits well
inside int128. At the four analogous sites, explicit guards give
`8 < dl <= 40`, hence `1 <= dl-8 <= 32`; the product magnitude is at most
2^63. The positive power-of-two shift and signed multiplication therefore
express the intended scaling without overflow. The materialized positive
67-bit product scaled by at most forty positions also fits in int128.
This argument does not establish safety of arbitrary experimental wide-scope
configurations, all integer operations elsewhere, or the physical model.

## Before/after checks

The complete before source and repaired candidate are preserved separately.
H1598 asserts that their entire textual difference is exactly the five
substitutions and explanatory comment. Each is compiled at O0, O2, O3 and
O2+UBSan, with R84 disabled, giving eight programs.

Every program is checked on both banks:

- All 149,898 H1590 cached legs, including 134 named frontier/defining/alias
  observations. Their baseline streams exactly reproduce H1590's saved O2
  output streams; source/input hashes are checked.
- All 695,616 software legs from H1597's 86,952 encodings. These include
  ordinary outputs and C2 range-rejection statuses.

All eight programs produce identical output streams; there are zero changes.
The two banks are counted separately and are not asserted disjoint. The old
UBSan program reports eight diagnostics in the software bank and none in the
cached bank. The repaired UBSan program reports none in either bank. This
finite result does not prove global UB freedom. It leaves H1590's 75 observed
external misses unchanged, and does not add any new hardware failure count.

The tested candidate is byte-identical to the updated canonical C source.
The normal build and `--selftest` pass, as do Python syntax and whitespace
checks. The normal build still reports 93 warnings, principally pre-existing
initializers and unused analysis functions; it is not warning-free.

An independent full replay reproduces every stdout/stderr hash, witness and
result field. Only the two O0 executable identity hashes differ: a binary
load-command audit confines every changed byte to Mach-O `LC_UUID` and
`LC_CODE_SIGNATURE` ranges. Code/data outside those metadata ranges are
identical. The O2/O3/UBSan executable hashes also reproduce. Consequently the
whole JSON is not claimed byte-identical, although all behavioral evidence is.

## Artifacts and replay

- `experiments/h1597_broad_encoding_ub_audit.py` and
  `tmp/ledger33/current/h1597_broad_encoding_ub_audit/` preserve the generated
  inputs, raw output/diagnostic streams and original broad-audit report.
  Report SHA-256:
  `bdaa2e7bd91c133d52f11abb1a8ee56fb1d15df59a6a897f21ce5f1d924abd42`.
- `experiments/h1598_signed_payload_ub_audit.py`, SHA-256
  `a6920734ff9fdfc42fe3210c756853ba5a0d1c6737a0e00aafb1a24fb96f99ab`.
- `tmp/ledger33/current/h1598_signed_payload_ub_audit/report.json`, SHA-256
  `14a1f50903c5f0008e2b310f687c68de9d610694502ed18ce5be5841cebd7aa9`.
  The same directory preserves all eight model executables, fifteen job
  streams per model, and `witness_trace.txt`; individual hashes are recorded.
- Before source: `tmp/ledger33/current/h1598_source_before.c`, SHA-256
  `de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.
- Candidate snapshot: `tmp/ledger33/current/h1598_source_candidate.c`, and
  updated canonical `src/fsincos_skylake.c`, both SHA-256
  `0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.

```sh
python3 fsincos-re/experiments/h1598_signed_payload_ub_audit.py \
  --root fsincos-re --output-dir NEW_EVIDENCE_DIRECTORY
```

H1598 replays its explicit immutable before/candidate source snapshots and
refuses an existing output directory. Older audits that require the de04
source must use that historical snapshot/replay environment; their hashes
must not be rewritten to the new canonical hash. H1595 supports an explicit
`--source-snapshot fsincos-re/tmp/ledger33/current/h1598_source_before.c`.
H1590's still older 8fe4 source snapshot is retained too. No prior report,
SAT/UNSAT/UNKNOWN artifact, manuscript or PDF is altered by this repair.

The direct residual frontier remains 45 failing mode rows over 44 operands;
known exact aliases make the external frontier 75/74. R96 remains empirical
and incomplete. The full bit-exact emulation goal is still open.
