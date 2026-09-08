# Independent FPTAN validation

This directory challenges the existing **FPTAN (tangent)** implementation,
not FPATAN (two-argument arctangent). The numerical implementation remains
`../src/fsincos_skylake.c`, through its unchanged `fptan_ref` entry point.
`predict.c` is a local validation adapter, not another numerical policy.

T0001–T0003 completed with **zero tangent, pushed-value, C1 or C2 misses
on 495,432 fresh observations per CPU**, covering all four rounding modes.
Skylake and i7 full output/status streams are byte-identical. The reusable
[FPTAN corpus v1](corpus-v1/README.md) contains these 495,432 unique tuples.
See [the analysis](ANALYSIS-T0001-T0003.md) for the construction and coverage limits.
No paper or numerical algorithm is changed here.

## Independent input construction

`independent_inputs.py` constructs operands without importing the candidate:

- directed MPFR bounds for `atan(output boundary) + k*pi`;
- adjacent external operands around mathematical zeros and poles;
- exact modular-residue counts and binary subdivision to find external
  operands particularly close to mathematical rounding boundaries;
- deterministic full-significand samples across every normal exponent
  field, active-range samples, and large-argument samples;
- complete generated windows of 257 adjacent significands with both signs.

The mathematical bounds select tests. They are **not** substituted for the
hardware's expected result: an x87 reconstruction need not equal a
correctly rounded mathematical tangent. Binary subdivision searches exact
residue conditions, not an assumed monotonic pattern of hardware misses.

The initial pool has 123,838 distinct signed normal finite operands and
2,054 certified adjacent mathematical-boundary brackets. Exact arithmetic
constructs 106 external witnesses satisfying 29 of 30 bounded SMT queries.
All 30 original unconstrained Z3 attempts timed out at 500 ms. Their query
and UNKNOWN artifacts are retained; pinned witnesses establish SAT for
29 queries. `a0051-e16` remains unresolved, not UNSAT or unreachable.

`audit_inputs.py` independently rechecks the brackets, witnesses, hashes,
normal-exponent strata and complete generated windows. `audit_coverage.py`
separately accounts for coverage remaining after history exclusions.
The new pool does not cover subnormals, zeros, infinities, NaNs, unsupported
encodings, arbitrary incoming stack state or unmasked exceptions.

## Freeze and one-shot protocol

`campaign.py` has separate local-clearance, history, freeze, stage, capture
and fetch commands. Do not run those commands blindly: paths and job IDs
are exclusive, and dispatched/reserved hardware work must never be retried.

Before prediction or capture, exclude local private/public history, known
generator domains, the old binary64-significand domain, and intersections
with visible public histories on both hosts. Unknown generator seeds and
unavailable records remain an explicit history-visibility limitation.
The same cleared stream is used on both CPUs.

All operands receive RN/RD/RU/RZ at PC64; a deterministic sample also gets
PC24/PC53. Each line starts from FNINIT, masked exceptions and one loaded
operand. Capture records both stack outputs, CW, and status before FPTAN,
after FPTAN and after stores. C2 returns must leave the operand in place
without pushing. Successful calls must push, then leave the stack balanced
after both results are saved.

The durable guard reserves every tuple before execution. A failed or
uncertain capture remains reserved. Only public inputs, hash manifests and
generic capture/guard code are uploaded. Candidate sources, predictions,
local history and source snapshots stay local.

`score.py` checks tangent, pushed value, C1, C2 and stack transitions. The
full captured status is also compared between CPUs, but **exception-latch
behavior is not predicted by this numerical adapter**. Agreement on finite
tests does not prove agreement for all inputs or all CPU generations.

## Local checks

```sh
cd fsincos-re/fptan-re
python3 -m unittest test_validation.py
```

Tests include brute-force checks of the exact residue arithmetic, protocol
and scorer mutation tests, and a synthetic (no hardware FPTAN) durable-guard
test covering success, duplicate rejection, failure reservation and no retry.
Optimized and ASan/UBSan numerical adapters are compared on the entire frozen
pack before any hardware execution.
