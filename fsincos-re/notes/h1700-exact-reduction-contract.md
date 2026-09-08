# H1700: exact reduction boundary contract

2026-09-04 local date. Software-only implementation evidence, not an academic
paper update or a claim of complete silicon equivalence. The fixed candidate,
production source/defaults, ROM and paper/PDF are unchanged.

## Result and trust boundary

Z3 4.15.3 and CVC5 1.3.1 each return UNSAT for all 140 counterexample queries.
The actual pinned C reduction helpers also match an independent Fraction-based
oracle on 90,504 cases per O0/O2/O3/UBSan build, with zero misses, diagnostics
or failed processes. Those 362,016 comparisons are software checks, not new
hardware observations or unique external operands.

The predicates are manually transcribed from the C implementation. Together
with the integer bounds and explicit modular-inverse certificates, they
establish its numerical reduction contract conditional on that correspondence
and ordinary C/compiler semantics. This is not automatic C/LLVM verification,
a compiler proof, physical recovery of the silicon reducer, complete entry
dispatch/conversion/state verification, or an all-input hardware proof.

No candidate numerical miss was found. All 81 previously documented external
incumbent-frontier outputs remain candidate-matched; they are not 81 remaining
candidate misses. The full standalone FSIN/FCOS goal remains unachieved.

## Exact contract

Domain: normalized 64-bit significand s, unbiased exponent e=-1..62, either
input sign, and instruction phase 0/1. The domain deliberately includes some
e=-1 operands below the real reduction cutoff, a safe mathematical superset.

```text
M = 0x3243f6a8885a308d3
H = floor(M/2)
A = s * 2^(e+2)
N = floor((A+H)/M)
D = A - N*M
signed residual = (-1)^input_sign * D * 2^-65
```

The reference A+H is an unbounded-integer expression; it is NOT substituted
into the 128-bit C implementation, where that addition could overflow. The
source uses quotient/remainder and increments exactly when twice the
remainder exceeds M. Odd M excludes half ties, so the two definitions agree.

The dividend fits 128 bits. N+1 is below 2^63, so signed quotient negation
and phase addition are safe. N*M fits 129 bits and the three-limb product
construction is exact. Unsigned limb comparison and borrow subtraction are
proved modulo 2^192; the product/dividend bounds and choice of the larger
operand lift the selected subtraction to the exact magnitude.

The centered difference obeys |D|<=H<2^65. It cannot be zero: for each shift
k=1..64 the artifact verifies an explicit inverse u satisfying
u*2^k=1+v*M. If M divided s*2^k, this identity would imply M divides s,
contradicting 0<s<2^64<M. These are 64 exact arithmetic certificates, not a
sampled search for nonzero residuals.

For |D| below 2^64, the highest-bit partition proves normalization exact with
shifts 0..63. For 65-bit |D|, the split drops only its low bit, rounds ties
to even, and cannot overflow the retained word under the centered bound.
The leading part has exponent -1, while c is zero or signed 2^-65. Therefore
`wv_from_rc` reconstructs the exact signed D*2^-65 through either the original
normalized word or `2*r.sig +/- 1` at scale 2^-65.

The existing `wv_from_rc` leaves legacy `rh` metadata uninitialized. This
certificate checks numerical fields only and deliberately never reads that
field. It does not claim that field is zero, initialized, or semantically
irrelevant at every possible caller. Full caller/dataflow verification is a
separate obligation.

| Predicate family | Queries |
| --- | ---: |
| Integer quotient, centered bound, signed-width, doubled remainder, no half tie | 5 |
| Dividend construction, all shifts 1..64 | 64 |
| Product limb merge, unsigned compare, borrow subtraction | 3 |
| Exact normalization, every low-word highest-bit position | 64 |
| RN64 split, no retained-word overflow, fold identity, correction magnitude | 4 |

All premises have nonempty domains. Each complete SMT-LIB formula and both
solver answers are retained. The bound is 10,000 ms per solver/query; no SAT
or UNKNOWN result is treated as proof.

## Compiled checks and reproduction

The driver includes unchanged `src/fsincos_skylake.c` and calls
`fsincos_compat_reduce_n_exact`, `sky_reduce_rc` and `wv_from_rc` directly.
R84 is disabled. There is no x87 capture. Its output includes quotient,
leading/correction fields, exact numerical wide reconstruction and signed
phase/quadrant bits. The independent oracle uses exact integer division and
Fraction rounding, not the C limb or guard-bit implementation.

The bank contains 22,626 exponent/significand pairs, both signs and both
phases, for 90,504 rows. All 64 exponents are represented. It includes input
endpoints, deterministic random values, neighbors of quotient half boundaries
and 285 generated exact-residual target preimages before deduplication. Those
are software test constructions, not fresh-capture eligibility or labels.

Paths below are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1700_exact_reduction_certificate.py` | `ac6ece113c44b2dc6d172a0eaacb9082c61e09c68d44dbef2b8e71902a9d0802` |
| `experiments/h1700_reduction_driver.c` | `5d49ab3f913d113abd93b286ad2aefdfd594e3db4ca33b539aac8707925eef1d` |
| `tmp/ledger33/current/h1700_exact_reduction_certificate/report.json` | `bd2f4b8d2a5449058b67feb827fcfa19392470ff8d9d0f5de3ca003dbe1f4b3a` |
| `tmp/ledger33/current/h1700_exact_reduction_certificate/solver_results.json` | `67c7e1b2be46d96bdfe4c2da5d03e050565b3af0b49110acc42b629cca2fa831` |

The report pins all four executables, the input stream and the independent
oracle/C output hashes. The query directory retains all 140 formulas/results.
Input SHA33934b91bcb57ee3a5f6136984fe167e110976594f2425f5968ffab50c970506;
oracle and every C output SHA4993c04c9642ec1135fd769a37f6060b38b46c658b05dd7ac62a6cc0e2cfa7e1.

Replay under `/private/tmp/h1700-replay.sT5Eco/h1700` reproduces every query,
answer, numerical output and O2/O3/UBSan executable exactly. O0 differs in 48
bytes within Mach-O LC_UUID [1288,1304) and code-signature [237328,239312)
regions only; a load-command parse verifies zero differing code/data bytes.
The original O0 SHA612dc476ccdb39970a873ce1bed89a1fb501c045e99f428dcd22c1f2d8953cef
and replay SHA71de060a6e131cd0f5f07f65983eeefa99765f4b1f9f2a2b2f98b08655204eb4
are preserved. The O0/top-level reports differ only in that binary hash;
do not describe the entire directory as byte-identical.

Python syntax, canonical build, both emulator selftests and diff/whitespace
checks pass. Source0339a7d6, headera5e9d085, ROM2189e006, paper802fb3b6 and
paperREADME8096a84f anchors are unchanged. Original session26960 and replay
session76638 are terminal; no capture or solver remains running.

## Next boundary

Check raw-to-internal normalization and output conversion, including the
invalid-encoding guard, original E/J preservation, subnormal store exactness
on the actual bypass grid, and special/range routing. `sf_to_x87` uses
truncating denormalization; do not claim generic correctly rounded underflow
from an exact roundtrip on the relevant grid. Retain the manual translation,
compiler, caller metadata and physical-fidelity obligations separately.

H1697 private possible matches remain unresolved, so no small-complement
capture is cleared. H1688 reservations stand; all opened campaigns remain
closed, H1685 paused and H1670 held. There was no private-ledger access,
remote action, new label, production/default change or paper/PDF update.
Confirmed host map: i7 `142.132.217.24`, Skylake Xeon `45.32.204.118`;
standing research-campaign authorization remains valid.
