# H1698–H1699: helper lemmas and whole-domain carrier bounds

2026-09-04 local date. This advances the finite-width implementation
obligation without new hardware or a new fitted rule. Production source,
candidate formulas, defaults and the academic paper/PDF are unchanged.

## What is established, and what is not

H1698 proves explicit bitvector predicates corresponding to the pinned
integer helpers: both Z3 and CVC5 return UNSAT on all1,283 counterexample
queries. A separate Python integer oracle agrees with the **actual C helpers**
on130,124 vectors for each of O0/O2/O3/UBSan, with zero diagnostics or misses.

H1699 then bounds the polynomial/table arithmetic over their stated input
domains using exact rational intervals and carrier widths, not sampled
operands. The worst conservative accumulator bound is210 bits, the maximum
alignment shift is142, and raw operation scales lie in[-327,0]. Every signed
partial sum fits below the256-bit sign boundary. Candidate add alignment and
C1 re-encoding use nonnegative shifts below256, so neither loses low bits.

This is a **source-backed, conditional arithmetic certificate**. The SMT and
interval programs are explicit manually checked transcriptions, not automatic
C/LLVM verification or a compiler proof. The established reducer/dispatcher
entry contract is an assumption here. These results do not prove silicon
implements the formula, verify every conversion/reduction/dispatch statement,
recover physical ports, complete tiny/special/control/state semantics, or
authorize production/paper promotion. No current candidate numerical miss was
found; all81 documented external incumbent-frontier outputs remain matched.

## H1698: precise helper contracts

The source is pinned to
`src/fsincos_skylake.c` SHA0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b
and the existing `ia64_sf.h`. Predicates correspond to `u128_mul_full`,
`acc_add`, `acc_add_product`, `acc_round_bits_mode` and `acc_round64_rc`.

| Query family | Queries | Contract |
| --- | ---: | --- |
| Partial-product reassembly | 1 | Four128-bit partial words combine correctly modulo2^256 |
| Add, subtract, two's-complement negate | 3 | Exact modulo2^256 carry/borrow arithmetic |
| Alignment | 511 | Every constant shift from-255 through255; right means floor division |
| Internal rounding | 512 | Every magnitude MSB0..255, precision64/67, all six internal modes and signs |
| Terminal rounding | 256 | Every magnitude MSB0..255, RC64, all four architectural modes and signs |

Each formula asserts a difference from its independent arithmetic definition.
All are UNSAT in Z3 4.15.3 and CVC5 1.3.1. Each full SMT-LIB query and both
answers are retained. The per-solver/query bound is10,000ms; no UNKNOWN or SAT
is converted to success. The MSB premises are nonempty: magnitude2^MSB and
mode0 satisfy each one. Modulo-helper queries have no input restrictions.

For multiplication, each64x64 partial product fits128 bits. Algebraically:

```text
(a0 + 2^64*a1)*(b0 + 2^64*b1)
  = a0*b0 + 2^64*(a0*b1 + a1*b0) + 2^128*a1*b1.
```

The proved reassembly is modulo2^256 for arbitrary partial words; the actual
128x128 product is below2^256, so this lifts to exact unsigned multiplication.
Signed accumulator interpretation additionally requires magnitude below2^255.
Right-shift alignment is only floor division unless the caller proves
divisibility. H1699 supplies the relevant no-overflow/nonnegative-alignment
obligations for these candidate core paths.

Rounding is checked against quotient/remainder arithmetic independently of
the C-style guard/sticky extraction. It includes tie-even, carry into the next
binade, chop, magnitude-away, odd, signed-up/down, rounding history and the
terminal64-bit increment wrap. Scale arithmetic assumes int32 does not
overflow; H1699 bounds the candidate scales far inside that range. Zero and
the minimum signed256 value are included in the compiled helper checks.

`h1698_integer_helper_driver.c` includes the unchanged source and calls the
actual static helpers; it does not substitute a second C implementation or
execute an x87 capture. The independent oracle uses Python integer
multiplication, divmod, shifts and signed-magnitude rounding. Vector counts:
4,132 multiplication;8,192 add/subtract;4,088 shifted-product accumulation;
68,064 internal rounding;45,648 terminal rounding. Four builds give520,496
software comparisons, not that many external operands or silicon observations.

## H1699: connecting the helper contracts to core graph domains

Polynomial:30 residual binades cover2^-32<=r<1/4, with two kernel branches
and normalized64-bit entry representation. Exact signed intervals propagate
through X67/Y64 cuts, products, rounded Horner adds and the distinct sine and
cosine terminals. Native coefficients are pinned; none is fitted or changed.

Table:61 offset-binade intervals cover2^-65<=|a|<=1/16, with both offset
signs and all seven reachable cell constants. Zero offset is separate.
The raw offset uses residual grids e2=-65/-64. At exactly1/16 its raw integer
magnitude can need62 bits despite much smaller odd-part precision; the proof
does not confuse raw width with the earlier<=61-bit precision theorem.
The established S4 coefficient subtraction2^-25 is retained exactly.
The direct RN64 multiply is kept distinct from RN64(CHOP67(product)).

This yields921 interval-domain cases (60 polynomial,861 table) and51,888
operation-bound checks. Table cell/sign combinations can be unreachable;
including them is a safe overapproximation, not coverage credit. In particular
b52 zero offset is checked as a helper case without claiming it has an
external preimage. Interval upper endpoints may likewise be supersets of
representable inputs. Quantizers are monotone; fixed-sign interval bounds
exclude uncontrolled cancellation through zero. No empirical minimum exponent
is substituted when an interval would cross zero: the checker would fail.

For each addition, every aligned term and the sum of magnitudes fit below
2^255. Products fit as well; all shifts executed for nonzero terms stay below
256. The largest conservative bound,210 bits/shift142, occurs at a polynomial
positive-chain middle add. The spare45 bits below the sign bit are a proved
bound, not a measured margin on samples. Scale extrema plus normalization
shifts stay safely inside int32.

Final prevalues remain positive. The comparison re-encoding used for C1 has
nonnegative alignment and fits the accumulator, so comparing stored magnitude
with the prevalue is not silently altered by truncation or wrapping. Final
result sign remains separate from this magnitude comparison.

## Reproduction and artifacts

The existing local SMT dependencies are used via
`PYTHONPATH=/private/tmp/fsincos-smt-deps`; no package installation or remote
action was needed. All result paths below are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1698_integer_helper_certificate.py` | `3e63c781102952af2ee6d5e8a73b69d5689f427a97b5921d7b45c2af7c8baf07` |
| `experiments/h1698_integer_helper_driver.c` | `e5912ec40e182b9b13120c951b8c8dd27772ef6fd196bff79c3084742a6d2af1` |
| `tmp/ledger33/current/h1698_integer_helper_certificate/report.json` | `40d5102d5d1914c9fb98770a2d2c217ff6ffc2dcf80745b9fb93e43eb012540f` |
| `tmp/ledger33/current/h1698_integer_helper_certificate/solver_results.json` | `e976d700584401a9471e89d1ca5ac30c5509522c55f4f86a959c06e989ca2241` |
| `experiments/h1699_candidate_carrier_bounds.py` | `e57d40a61317197a90a1cd1c2fd39e85380a6c52b90776a702404a812cc9844e` |
| `tmp/ledger33/current/h1699_candidate_carrier_bounds/report.json` | `7bd2c46608510d99c1eaeac2119339243a8e3b91e1b6090e983928d0eb964648` |
| `tmp/ledger33/current/h1699_candidate_carrier_bounds/cases.json` | `b2aa8acca607a03d985c419f87480facee499cf65b791f2e3a7e05f5fb7f642d` |

H1698's queries directory preserves every SMT-LIB query and result; its report
pins actual C binaries and exact input/oracle/output hashes. H1699 retains all
domain cases and operation bounds. Replays are under
`/private/tmp/h1698-h1699-replay.lYQv2m`. All SMT queries/answers, vector counts,
oracle/C output hashes and H1699 artifacts reproduce exactly. O2/O3/UBSan
binaries are byte-identical. O0 differs only in47 bytes inside its Mach-O
LC_UUID and code-signature regions: zero-based half-open[1288,1304) and
[237344,239320). A binary load-command parse verifies equal regions/length
and zero differing bytes outside them; executable code/data are unchanged.
The original O0 SHA2c22073b80675fd49c88a2a33eebd67bf2974ed9f5e153754bd4a865bf34edb9
and replay SHAc4b7d84791e7c661cd7efe61b761623259ebffe1038a10430520fbdce39d2ad5
are both preserved, not normalized or overwritten. Consequently the O0 and
top-level replay reports differ in that binary hash only; do not claim the
entire H1698 directory is byte-identical.

Canonical build, both emulator selftests, Python syntax and final
diff/whitespace checks pass; source/paper/README anchors
0339a7d6/802fb3b6/8096a84f remain unchanged. All command sessions are terminal;
no capture, solver or replay process remains running.

## Next compositional step

Establish the entry contracts at the C boundary: exact quotient, three-limb
reduction/subtraction, RN split and `wv_from_rc` reconstruction, including
all exponent/shift limits, and raw-to-internal/output conversions. Keep the
source-to-predicate trust boundary explicit; do not rename this a complete C
or silicon proof. H1697's private possible matches remain unresolved and no
small-complement capture is cleared. H1688 reservations stand; H1694/all
opened campaigns stay closed, H1685 paused and H1670 held. Complete state,
unsupported controls and universal hardware fidelity remain obligations.
Full goal active/unachieved; concrete implementation-proof progress, not a
global blocker or promotion.
