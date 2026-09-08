# H1686: exact tiny/polynomial model join

2026-09-04 local date. This is an analytic certificate for the **specified
numerical program**, not a new physical selector or an all-input silicon
proof. No hardware, hardware labels, private ledger, default/source change,
or paper/PDF edit. The full goal remains active/unachieved.

## Result and domain

For every positive dyadic residual `2^-68 <= r <= 2^-32` with at most 64
significant bits, the fixed H1630 polynomial and the H1637 non-bypass tiny
rule give identical rounded output **and C1**, for either result sign and all
four final rounding modes. This includes exactly `r=2^-32`, where the actual
dispatcher selects polynomial rather than tiny.

This closes a model-level interface obligation with inequalities, not sampled
error-state fitting. Direct non-bypass tiny inputs meet the lower bound and
width condition. Reduced nonzero tiny inputs are `|D|*2^-65`, with at most 33
significant bits; they also meet the conditions. The existing exact quadrant
mapping supplies the sign and sine/cosine selection. The claim does not merge
external zero or the separate external exponent-below-68 bypass.

## Analytic argument

Write `T_p` for normalized p-bit truncation toward zero and `RN64` for
normalized nearest-even rounding, with unbounded exponent. The fixed operators
are `M(x,y)=T67(T67(x)*T64(y))` and `A(x,y)=RN64(x+y)`. Then:

```text
S = M(r,r)                      0 < S <= r^2 <= 2^-64
F = M(S,S)                      0 < F <= S^2 <= 2^-128
N = A(K1, M(F, A(K3,M(F,K5))))
P = A(K2, M(F, A(K4,M(F,K6))))
L = M(S,N), R = M(F,P)
pre_s = r + M(r,A(L,R))
pre_c = 1 + T67(L+R)
```

All pinned coefficient magnitudes are below 1. With `rho=65/64`, each inner
Horner value has magnitude at most `rho*(1+2^-128)<2`. The outer coefficient
perturbation therefore has magnitude below `2^-127`. The certificate computes
RN64 at both exact endpoints `K1 +/- 2^-127` and `K2 +/- 2^-127`; for each
coefficient the endpoints round identically. Monotonicity of rounding proves
N and P constant throughout the domain, not just at sampled r.

The resulting sine N lies strictly between -1/4 and -1/8. Both P values are
strictly between 0 and 1. The cosine N is exactly -1/2. Importantly, its stored
K1 is **not** -1/2: it is `-1/2 + 2^-67`. Equality holds after the bounded
Horner addition/rounding, which the certificate checks explicitly.

For sine, use `eta=63/64`, a loose lower magnitude bound for nonzero T67.
Then `eta*S/8 <= |L| < S/4` and `0<R<S^2<eta*S/8`, so `L+R<0`.
Its RN64 value h is negative with `|h|<rho*S/4<S/3`. Thus
`0 < r-pre_s < r^3/3 <= r*2^-64/3 < r*2^-65`.
For any positive exact64 r, predecessor spacing is at least `r*2^-64`,
including power-of-two binade boundaries. The sine correction is therefore
strictly below half that spacing.

For cosine, `L=-S/2` exactly because scaling a 67-bit S by -1/2 is exact.
Since `0<R<S^2<S/2`, truncation gives
`0 < 1-pre_c < S/2 <= 2^-65`. The inequality stays **strict at the upper
endpoint** because R is positive. Half the predecessor gap below 1 is 2^-65.

Both prevalues are strictly between the leading value and its nearest-even
midpoint with the predecessor. RN or away-from-zero therefore selects the
leading magnitude with C1=1; toward-zero selects its predecessor with C1=0.
There is no tie case. Sign converts RD/RU to the appropriate magnitude
direction. No fitted threshold, literal operand, hidden history or new
conditional selector enters the proof.

## Software checks and limits

`experiments/h1686_tiny_polynomial_join.py` pins the original program/ROM and
existing H1634 rational quantizer, checks all rational inequalities and rounded
interval endpoints, then runs a finite implementation regression:

| Check | Count | Outcome |
| --- | ---: | --- |
| Distinct residual magnitudes, every active overlap exponent | 6,841 | Tested |
| Graph prevalue enclosures, sine and cosine | 13,682 | All pass |
| Graph output/C1, both signs and four modes | 109,456 | All pass |
| Existing O0/O2/O3/UBSan active-dispatch output/C1 | 437,824 | All pass |
| External bypass extension negative controls | 16 | Every extension differs |

The C replay uses the actual tiny path below the threshold and actual
polynomial path at the threshold. It does **not** force the finite-limb C
polynomial into the smaller domain. That counterfactual graph is checked by
exact rational arithmetic. The universal model claim comes from the analytic
bounds; finite regression counts do not prove it. This also does not constitute
a formal verification of the quantizer implementation or finite-limb C.

The 16 negative controls use external exponent -69. The original bypass
returns the leading result with C1=0; the non-bypass/polynomial extension
differs in directed output or C1 in every tested combination. These are
expected differences of a rejected extension, **not new candidate misses**.
The bypass remains a distinct observed mechanism, not an approximation to
the polynomial or correctly rounded mathematical sin/cos.

Full exception flags, physical coefficients, all-input silicon equality and
other domain joins are outside this certificate. Several independent pieces
may be necessary for full closure. Nothing here requires one universal final
selector or authorizes production/paper promotion.

Artifacts: `tmp/ledger33/current/h1686_tiny_polynomial_join/report.json`,
`software_operands.json` and `bypass_negative_controls.json`. The report pins
the script, constants, source, prior report, four binaries and both artifacts.

SHA256 anchors:

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1686_tiny_polynomial_join.py` | `9726b54acedbd25f88725592a9d3ac14adab72521462180568cdcad5b514326b` |
| `tmp/ledger33/current/h1686_tiny_polynomial_join/report.json` | `6aab704a66472a16b424476beb253f5cf8c9d2935daa69800289b0f9bfea23df` |
| `software_operands.json` | `67f60a6016f4b663898a2a1f8f9b394475d4c4aaa5461957b7bd0188068b31f0` |
| `bypass_negative_controls.json` | `062f32d0fd193d7b419e8840efd2bc023c2aa5a9348af086dc49bd8cc49c8aa5` |
