# H1701: conversion and exact bypass-grid contract

2026-09-04 local date. This advances implementation-boundary verification,
not the academic paper or a claim of universal hardware equality. No numerical
formula, production source/default, ROM or paper/PDF is changed.

## Result

Both Z3 4.15.3 and CVC5 1.3.1 prove all 198 positive predicates and return SAT
for the two deliberately false generalizations. Every query and answer is
retained; neither SAT negative control is counted as a proof or candidate miss.
The actual C decoder, encoder, raw invalid gate and unchanged H1638 tiny entry
match 544,876 independently computed rows per O0/O2/O3/UBSan build, including
the full expected tiny trace. No unexplained diagnostics or failed processes.

These are manually transcribed source-backed predicates plus compiled tests,
not automatic C/LLVM or compiler verification. They establish the conversion
contract of the specified program, not unseen silicon behavior, architectural
flags from numerical equality, complete entry dispatch/state composition, or
generic correctly rounded underflow. The full standalone FSIN/FCOS goal is
still unachieved; all 81 known external incumbent-frontier outputs remain
candidate-matched and no new candidate numerical miss is known.

## Normalization and exact subnormal store

Let E be the original 15-bit exponent field and s a nonzero raw significand.
For finite decode, k=63-floor(log2(s)) is in 0..63. The helper returns

```text
normalized significand = s * 2^k
internal exponent = max(E,1) - 16383 - k
```

The loop predicates prove for every highest-bit position and every permitted
intermediate iteration that the shift is lossless and bit63 is first reached
exactly at iteration k. Exponents stay in [-16445,16383]. For valid normal
encodings E>0, J=1 implies k=0 and the finite exponent/significand roundtrip
is exact. Zero preserves sign. Infinity and NaN helper branches are separately
exercised; the helper itself does not quiet signaling NaNs.

For a true denormal, E=0 and 1<=k<=63. The store computes
`sh = 1-(internal_exp+16383) = k` and divides the normalized significand by
exactly 2^k. Every removed low bit is zero. Thus the unchanged truncating store
returns exactly the original significand for every true-denormal encoding,
not merely the sampled small values. The case artifact's `discarded_bits=0`
means no information/significand bits lost; it does not mean the right shift
has length zero.

For a pseudo-denormal, E=0 and J=1, so k=0. It stores with E=1 and unchanged
sign/significand: numerical value is preserved, raw encoding/class is not.
The original E/J must remain available separately to status handling. The
H1645/H1652/H1660 state functions take original `se,sig`; do not reconstruct
exception class from the normalized `sf_t` or canonical output encoding.

The unchanged H1638 direct entry selects its bypass for every valid nonzero
E=0 input and normal E<16315 (unbiased exponent<-68). It performs no predecessor
step, returns the exact input magnitude/sign for FSIN and +1 for FCOS, and
reports C1=0 independent of RC. All these values are below the direct-reduction
cutoff. Combined with the exact grid identity above, the store cannot introduce
an additional rounding on this bypass. H1647's earlier graph enclosure places
the other numerical paths above the subnormal boundary under their contracts;
that is a model result, not a recovered physical exception generator.

## Necessary exclusions, demonstrated by negative controls

1. Generic correctly rounded underflow is false for `sf_to_x87`. At internal
   sign0, exponent-16383, significand8000000000000003, its store is
   `0000:4000000000000001`; nearest-even on the subnormal grid would be
   `0000:4000000000000002`. The former truncates an odd halfway quotient. This
   internal value is outside the exact decoded bypass grid; it is not a new
   FSIN/FCOS counterexample.
2. The decoder is not an architectural raw classifier. A nonzero exponent
   with zero significand returns helper zero because its zero branch is first,
   but the public invalid-encoding guard rejects it. The SAT model supplies
   E=7fff, s=0. Other unsupported unnormals can likewise normalize into ordinary
   finite helper values. Never remove or move the raw guard after decode.

Arbitrary invalid internal exponents/overflow, unmasked scaled-underflow
selection, complete special condition bits and physical state histories are
not certified here. Original-class retention inside `sf_t` is explicitly not
claimed. This work does not resolve H1700's separate legacy `wv.rh` dataflow
obligation.

| Predicate family | Positive queries |
| --- | ---: |
| Normalization loop, every highest bit and intermediate iteration | 64 |
| E=0 exact grid roundtrip, every highest bit | 64 |
| Subnormal quotient/remainder and exactness condition, shifts1..63 | 63 |
| Store quotient zero for shifts>=64 | 1 |
| Decode exponent bounds, E=0 store shift, normal exponent roundtrip | 3 |
| Raw invalid partition, sign/exponent packing, bypass result sign | 3 |

All positive premises have nonempty domains. Two further negative queries
return SAT, for 200 total queries. The timeout is 10,000ms per solver/query;
there is no UNKNOWN result or hidden timeout.

## Software checks and reproducibility

The driver directly includes pinned production C and the unchanged isolated
tiny header. R84 is OFF. Calls to the decoder intentionally include unsupported
raw inputs as helper tests, not architectural output predictions. The tiny
entry tests its existing guard. Original input structs remain unchanged.
The independent oracle uses bit lengths, multiplication and exact integer
division rather than the C normalization loop or store branches.

Each build checks 269,544 decoder rows, 2,148 direct stores and 273,184 tiny-entry
rows. The decoder bank spans all 32,768 exponent fields, both signs and J states;
this is not exhaustive significand sampling. Tiny rows include 271,968 bypass
hits, 256 non-bypass controls and 960 nonhits. Every expected HTINY field matches
exactly. Total across four builds is 2,179,504 software comparisons, not hardware
observations, fresh tuple clearance or a unique-input count.

Paths below are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1701_conversion_certificate.py` | `a79c4d32c8b42fe9e7bc323be3f2755034dd5783b602b874b8b859f6737cee1c` |
| `experiments/h1701_conversion_driver.c` | `da431b60952bfdd85869b1805199e2bae8937baba4e9dbfe56987341b24db71e` |
| `tmp/ledger33/current/h1701_conversion_certificate/report.json` | `f1ac755d778a09c46ab076bdcf1c7c99591157c318136d111ba06b32b690200c` |
| `tmp/ledger33/current/h1701_conversion_certificate/solver_results.json` | `753912b6564a8ca7f3aa934094493f97fe381a255af124cd05f7ae5c8aa933b8` |

The report retains executable/input/oracle/output/metadata hashes. The query
directory retains all 200 SMT-LIB files and answers, including SAT models from
Z3. InputSHAd5aef7ae5ef1e9db02939593f7418c75a7f28e79a7ca04042d11a988bea2e793;
oracle and all C outputs SHA207e3b3301001b5ad678a7637f92134275f3626a6734178fd42fb09f578c2bdd;
trace SHA c085c88c309ad7604a0d74745e945bda50466ffc1f571a2df6da94ca30a66e40.

Replay `/private/tmp/h1701-replay.61KsAv/h1701` reproduces all query/answer/
numerical-output/metadata bytes and O2/O3/UBSan executables. O0 differs only in
47 Mach-O UUID/signature bytes within [1288,1304) and [237392,239376), verified
by load-command parsing with zero code/data differences. Original O0
SHA5fd4ef8c94a858529ca22f6baf038d9cbb2152fab80dd28b70f178c0be5f494a and replay
SHA8faaf347793058d2e4aedb1c8640c5e6c1aa88141ca40bf3b16e4ca0588fe662 remain
preserved; only that binary hash differs in O0/top-level reports. Do not claim
full-directory byte identity.

Python syntax, canonical build, both selftests and diff/whitespace checks pass.
Source0339a7d6/headera5e9d085/ROM2189e006 and paper802fb3b6/README8096a84f anchors
remain unchanged. Sessions33065/37916 are terminal. No hardware, remote action,
private-ledger access, labels, source/default promotion or paper/PDF edit.

## Next compositional boundary

Verify the actual configured candidate's route selection and dataflow through
raw guard, special/range return, tiny override, exact reducer and polynomial/
table hooks. Establish that all finite in-range inputs reach the intended
numerical graph, no legacy fitted fallback remains reachable, and legacy
rounding-history metadata is not consumed by the candidate path. Keep this
distinct from full control/state and universal physical fidelity.

H1697 private possible matches remain unresolved; no small-complement capture
is cleared. H1688 reservations stand, all opened campaigns stay closed, H1685
paused and H1670 held. Goal active/unachieved; concrete implementation-boundary
progress, not a global blocker or an all-input silicon claim.
