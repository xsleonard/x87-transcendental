# H1593: backwards intervals and a bounded upstream-rounding exclusion

Status: analysis-only, no new selector. No hardware execution, new labels,
manifests, emulator changes, or paper/PDF changes. The authoritative report is
`tmp/ledger33/current/h1593_inverse_rounding_constraints_v3.json`; v1 and v2
are retained as superseded development outputs, not additional observations.

The strongest result is narrower than physical localization: one observed
H1587 row cannot be explained by **any faithful 64-bit rounding directions at
both final Horner additions**, even chosen separately for each input, under
the specifically fixed surrounding arithmetic below. This excludes more
than constant signed one-ulp perturbations, but does not exclude changed
precision, earlier conditional arithmetic, coupled payload generation,
forwarding, or unknown operation/control state.

## Evidence and assumptions

The bank contains exactly 26 actually observed mode/operand rows over 25
operands: the eleven H1378 historical misses over ten operands and all fifteen
H1587 observations, including both H1589 opposing-profile pairs. No other
rounding-mode label is inferred. H1378 evidence is checked against H1590;
H1587 OPENED_ONCE, score and raw capture hashes are checked. The R84-off
current C model is used only as an external trace comparator; its output is
checked against each recorded baseline before any inverse is calculated.

These are three different levels of statements:

1. The output inverse is exact **if** the final composition is positive
   `round64_RC(1-c)`, with the observed output away from a binade edge.
   It does not independently prove that silicon uses that composition.
2. Intermediate inverses additionally assume an ordinary positive-magnitude
   CHOP67 terminal subtraction, and hold the other operand, numeric payload,
   normalization binade, exponent and relevant integer lattice fixed.
   The current payload is itself derived upstream: these cuts do **not**
   constrain a coupled upstream intervention that also changes that payload,
   scale, or operation sequence.
3. The finite arithmetic-family audits test specified operation-wide
   semantics under those assumptions. A failed family is not a proof that
   no conditional upstream mechanism exists, or that a physical terminal
   carry selector must be the cause.

All tested intermediates are positive magnitudes except the signed negative
Horner arm. Its quantizers below operate on magnitude; CHOP/AWAY do not mean
architectural RD/RU for that negative value. H1592 independently reconstructs
the square, fourth power, both factors, and both products. All 182 matching
dyadic stage values (seven per observed row) are checked by H1593. Agreement
of those two implementations is not silicon equivalence.

## Exact inverse

Write observed positive `y = h * u`, where `u` is its architectural ulp.
The interval of permissible correction magnitudes is obtained by reflecting
the usual rounding interval about one:

| Mode | Values of `c` satisfying `round64(1-c)=y` |
| --- | --- |
| RN | Between `1-y-u/2` and `1-y+u/2`; both ends included iff `h` is even |
| RD / positive RZ | `(1-y-u, 1-y]` |
| RU | `[1-y, 1-y+u)` |

Intersecting this interval with the proposed correction lattice `2^ce`
gives a consecutive integer interval `[a,b]`. For a plain CHOP67 correction
in the same normalized binade, its unrounded input has the exact preimage
`[a*2^ce, (b+1)*2^ce)`. This is an interval inversion, not a SAT timeout or a
search over guessed operands.

Let `U = L + P - R`, using positive terminal product magnitudes and numeric
payload `P`. Holding `R,P` fixed shifts that interval to permissible `L`;
holding `L,P` fixed reflects it to permissible `R`. Intersecting with each
product lattice yields exact integer ranges. A second CHOP67 inverse and
division by the other positive multiplier then yields a permissible factor
interval, again conditional on that fixed cut. Every row records the full
rational endpoints, inclusion flags, product/factor integer ranges, traces,
and surrounding assumptions.

The two opposing-profile pairs illustrate how weak endpoint localization is.
The permissible correction increments relative to plain CHOP67 of `L+P-R`
are:

| Observed row | Allowed correction-integer delta |
| --- | ---: |
| RN `3ffc:f9dffffdf814cc29` | `[-255,-1]` |
| RN `3ffc:f9dfffffa971b4a5` | `[0,254]` |
| RD `3ffc:de3ffffc73d9080b` | `[-255,0]` |
| RD `3ffc:e73ffffd2c52df71` | `[1,256]` |

All four use `ce=-72`. Their identical coarse gate profiles do not make their
full arithmetic operands identical. Thousands of ordinary fixed arithmetic
schedules satisfy each pair individually, although none in the tested
family satisfies the complete 26-row bank. This does not recover a physical
mechanism; it demonstrates why a profile collision cannot by itself exclude
upstream arithmetic explanations.

## Stronger faithful64 counterexample

For RD `3ffc:e73ffffd2c52df71`, hardware is
`3ffe:f97ff2968a37b8b1`. The plain CHOP67 correction integer is
`119907611608401530368` at exponent `-72`; hardware requires an increment
between **1 and 256**, inclusive.

With the other terminal arm and numeric payload held fixed, the negative
factor magnitude needs an integer change in `[1,19]`, or the positive factor
needs a change in `[-6151,-1]`. Yet the exact H1592 last-add inputs give only
these faithful64 neighboring choices relative to the current factors:

- Negative magnitude: floor/ceil deltas `{-1,0}`.
- Positive magnitude: floor/ceil deltas `{0,+1}`.

Both directions can only decrease `L-R`, whereas this observation needs a
larger correction. Checking all four combinations gives the following
correction deltas, for **both** omitted payload and frozen numeric payload:

| Negative magnitude | Positive magnitude | Correction delta |
| --- | --- | ---: |
| floor | floor | -13 |
| floor | ceil | -13 |
| ceil | floor | 0 |
| ceil | ceil | 0 |

None intersects `[1,256]`. Earlier values are fixed to the independently
replayed MUL67/ADD64 sequence, terminal products are CHOP67, and their
correction subtraction is CHOP67. Under exactly those conditions, *any*
conditional choice between adjacent 64-bit representables at the two last
Horner adds is excluded for this row. This includes choices supplied by an
unknown control bit, and is therefore stronger than rejecting a single
rounding direction. It does not exclude a wider retained/forwarded value or
another surrounding sequence.

The same faithful64 test fails three rows with the incumbent numeric payload
held fixed; only this e73 row fails under both tested payload variants. The
report preserves every row's allowed four-corner choices, not just failures.

## Finite operation-semantics audits

The operation choices are normalized precisions 64 through 72, with CHOP,
RN ties-even, RN ties-away, AWAY, or JAM (truncate then set the retained LSB
when inexact), plus exact forwarding: 46 choices per operation. Policies are
fixed by operation/arm across the entire bank. There are no input thresholds,
operand predicates, or fitted Boolean gates.

- Terminal audit: independently choose left-product, right-product and final
  correction semantics; omit payload or keep its current numeric value.
  **194,672 schedules, zero exact; best 20/26.** All 26 rows are individually
  reachable under some member, which is not a joint solution. The RN f9d pair
  is satisfied by 6,595 schedules and the RD de3/e73 pair by 19,389.
- Last-Horner audit: independently choose both last-add semantics from the
  exact independently reconstructed addition inputs, then use ordinary
  CHOP67 products and correction; omit/freeze payload as above.
  **4,232 schedules, zero exact; best 15/26.**

These counts concern an adversarial 26-row bank, not accuracy estimates. Best
examples are explicitly labeled non-candidates. No control-wall survival or
generalization is claimed. The tested ordinary terminal and last-add families
are excluded; conditional changes elsewhere, more complicated retention or
normalization behavior, coupled payload changes and undiscovered control
information remain open. No new selector is promoted.

## Reproduction and checks

```sh
python3 fsincos-re/experiments/h1593_inverse_rounding_constraints.py --selftest
python3 fsincos-re/experiments/h1593_inverse_rounding_constraints.py \
  --root fsincos-re \
  --model /private/tmp/h1590-arithmetic-audit.0DkC4y/models/after_O2 \
  --output NEW_REPORT_PATH
```

The pure inverse/grid selftest covers 2,556 exact cases, plus four explicit
tie/JAM cases. Each per-row single-product interval checks both admissible
endpoints and the two adjacent inadmissible lattice points. Independent
stage parity covers 182 values. The report is reproducible without hardware;
the final arithmetic version is v3. Earlier outputs are preserved, never
mistaken for fresh evidence.

SHA-256:

- H1593 script: `b544c8df030d5245b46989827bf5d4baa376ae972ee0b12f31b56fd38d1db96a`.
- Authoritative v3 report: `c2d9e1250fd32791d49b937c8aa504980d45622d426b4c0d986afe21158dad37`.
- H1592 independent spec used: `0cc55ff4c0de1f957b30a5f48f5d63939ae22f2de99936f9bb41fe8543f80c82`.
- C source: `de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.

This is evidence about the allowed arithmetic and excluded bounded classes,
not a change to the failing frontier or the full bit-exact FSIN/FCOS goal.
