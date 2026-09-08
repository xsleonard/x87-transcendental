# D0031–D0033: exact-square-tie adversarial verification

2026-09-06. **D0033 observed once and scored: zero V7 misses.** This is
additional adversarial evidence, not universal closure. The numerical C
program, pseudocode and paper are unchanged.

## Measured gap in the original corpus

D0031 authenticates all 2,783,208 original observations' input and hardware
file hashes, then classifies the saved inputs without opening output labels.
There are 2,691,816 finite-nonzero observations and 423,316 distinct normalized
magnitude cores after factoring out exact common powers of two. The cores
divide into 86,501 tiny, 128,345 direct and 208,470 table cases.

The selected-node census covers reduction cuts, the asymmetric square, and
the four magnitude restorations. It is **not** a certificate for every
polynomial node. Only 56 cores reach an exact square-rounding halfway, all
on the direct path and all with even retained parity. None distinguishes
square ties-even from square ties-away at any restored output/C1 endpoint.
There are no table-path square ties in this original set. This means the
original saved corpus cannot distinguish these two square tie rules within
the otherwise fixed V7 graph; it does not identify the silicon rule.

The census also finds 18,210 additional normalized cores sharing an existing
retained reduction state; 8,548 differ from that group's first core in the
reduction-cut remainders. These are input-side coverage facts. They are not
new native captures, and no discarded-history selector is inferred from them.

Report: `../tmp/fpatan-re/d0031-internal-rounding-coverage.json`.

## Constructive external preimages

Choose odd `2^32 < v < sqrt(2^65)` and `z = v*2^(E-32)`. The square is
`z*z`, because this z is already exactly representable at 64 bits. At its
RN64 cut, the scaled significand is `v*v/2`: an exact halfway. Since an odd
square is 1 modulo 8, its retained integer `(v*v-1)/2` is even. The direct
external preimage is `(a,b)=(v,2^(32-E))`.

For a table cell `c=n/32`, sign `s`, and `L=32-E`, take integer operands

```text
a = n*2^L + 32*s*v
b = 32*2^L - n*s*v
a-c*b = s*v*(1024+n*n)/32
b+c*a = (1024+n*n)*2^(L-5)
(a-c*b)/(b+c*a) = s*v*2^-L
```

The selected parameter bounds make both operands exactly raw80-representable
and both completed reduction sums exactly C67-representable. The generator
checks those claims, the dispatch/cell, the sign, the residual and the exact
halfway remainder for every admitted base pair. Constructions outside their
intended cell are counted and excluded, not called unreachable. Suitable odd
integer multipliers also preserve the exact residual while changing the
external significands. No solver, host arctangent or hardware labels select v.

D0032 attempted 146,944 base constructions: **145,315 passed the exact
construction checks**, and 1,629 were outside the intended dispatch.
There are **73 endpoint-visible base witnesses**, all on the direct path,
with 197 differing positive-restoration/RC endpoints. The table constructions
add reachable exact ties, even where this particular mutation is invisible.
The full 145,315-pair pool is retained, not just its successful discriminators.

Report and pool: `../tmp/fpatan-re/d0032-square-tie-mining/`.
The pool itself is software-certified, **not** entirely freshness-cleared or
captured. Its complete sign/swap/four-RC expansion at PC64 is bounded by
4,650,080 rows before history exclusions; these are not extra observations.

## Frozen first challenge and one-shot observation

D0033 selected all 73 visible witnesses with a 3x3 neighborhood in the two
external operands, exact table-tie controls, three-member same-z integer-scale
groups, all sign/octant/four-RC orbits, and 512 independent full-exponent
controls. PC24/53 supplement PC64 on a bounded subset. All 8,712 generated
pairs cleared the local private/public/corpus and prior-tuple exclusions.
The final manifest contains **35,120 observations**.

Both the unchanged V7 predictions and the deliberately different square
ties-away predictions were frozen before dispatch. The latter changes only
the RN64 asymmetric-square tie decision, never the implementation default.
The local C preflight matches every frozen baseline prediction. The remote
prior-use audit and permanent per-tuple reservation guard passed; only generic
capture code and cleared public inputs were uploaded. No private records or
numerical model went to the host. The existing unary trig campaign was left
untouched.

One local preparation attempt stopped before writing any input row because
its first denominator neighbor crossed a power-of-two binade. The corrected
generator uses actual adjacent raw80 encodings across that boundary and has
a regression test. The empty attempt and source snapshots remain in
`../tmp/fpatan-re/d0033-freeze-attempt-1/`. No manifest was frozen, no remote
job staged, and no hardware run occurred in that attempt.

Observed reference: guest-reported Skylake Xeon, CPUID `00050654`, microcode
`0x1`, using the established masked/clear/two-deep capture contract. As in
the paper, these are guest-visible identifiers, not physical attestation.

| D0033 result | Count |
|---|---:|
| Observations | 35,120 |
| V7 output / C1 / exception / pre-load misses | 0 / 0 / 0 / 0 |
| Square ties-away output misses | 308 |
| Square ties-away C1 misses | 176 |
| Square ties-away union misses | 394 |
| Exact square-tie observations | 14,208 |
| Direct / table exact-tie observations | 2,408 / 11,800 |
| Three-member same-z groups / hardware splits | 3,904 / 0 |
| Complete three-PC groups / differences | 136 / 0 |
| Underflow observations | 148 |

The table ties cover every used cell, n=2..32. Each RC has 8,780 observations;
PC24/53 each have 136, and PC64 has 34,848. The output and C1 miss counts for
the control overlap and must not be summed. The hardware rejects this precise
ties-away alternative; it does not prove arbitrary internal tie behavior or
every table-path tie implementation. Same-z groups here test exactly
representable reduction sums, not the census's differing-cut-remainder groups.

Artifacts are in `../tmp/fpatan-re/d0033/`: `MANIFEST.json`,
`STRUCTURAL-HYPOTHESIS.json`, `C-PREFLIGHT.json`, `STARTED.json`,
`COMPLETE.json`, `SCORE.json`, `SQUARE-CONTROL-SCORE.json`, and
`LEDGER-AUDIT.json`. The remote ledger reports integrity `ok` and D0033
`OBSERVED`. Sanitized C replay also matches all 35,120 saved rows.
Never repeat any tuple from this job on that capture context.

## Corpus and remaining work

[corpus-v1](corpus-v1/README.md) now carries all **2,818,328 distinct retained
observation tuples across fifteen input packs**, with zero cross-pack
duplicates. Its approximately 88 MiB includes the full provisional D0032 pool.
It carries inputs only: native outputs, predictions and private history remain
separate. Original delivery/paper counts remain valid historical snapshots.
The unchanged V7's prospective total is now 659,432 observations.

The active adversarial goal remains open. Strong next work is independently
mining final-rounding boundaries in each restored quadrant, and constructing
fresh same-z groups with **different nonzero reduction-cut remainders**, not
only exact-sum scale variants. Extend the census to the remaining polynomial
RN64/C67 nodes and reachable intersections. The broader D0032 pool also needs
history admission and bounded batches before it can count as hardware-tested.
Do not substitute an undirected large random run or another square ties-away
fit for these missing tests. No new selector or paper revision is warranted.
