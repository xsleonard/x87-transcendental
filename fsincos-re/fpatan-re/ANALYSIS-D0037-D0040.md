# D0037–D0040: polynomial-node census and inverse correction-sum ties

2026-09-06. **956,608 fresh observations, zero V7 misses.** The frozen
opposite-halfway control fails on 708 output-or-C1 rows. No numerical
implementation, pseudocode or paper change. The broader goal remains active.

## D0037: all explicit polynomial rounders in the retained corpus

The input-only census authenticates all sixteen packs in CATALOG-D0036:
3,655,928 observations, 526,510 normalized finite cores, including 419,936
polynomial cores and 106,574 tiny-path cores. The exact-rational named-node
trace independently matches the published kernel for every polynomial core.
The census reads inputs, not hardware result labels.

There are 508 exact RN64 halfway events across those cores: 138 direct
squares, 366 table squares, three direct correction sums and one table
correction sum. The earlier RN64 polynomial additions have no exact-tie
examples in this corpus. Only the 73 already-known direct-square witnesses
expose an opposite tie decision at an observed endpoint. None of the four
correction-sum ties does. Counts describe coverage, not unreachability.

Source: `d0037_polynomial_node_census.py`. Evidence:
`../tmp/fpatan-re/d0037-polynomial-node-census/REPORT.json`.

## D0038: an exact numerator-width bound, not another capture target

Normalize finite nonzero magnitudes as a=M_a*2^(E_a-63) and
b=M_b*2^(E_b-63), with 2^63 <= M < 2^64. Exact normalization also covers
subnormals and pseudo-denormals. Magnitude ordering gives a<=b. The table
path requires 3/64<a/b<=1, so d=E_b-E_a lies in 0..5.

Write the nearest table index n=odd*2^t and put j=max(d,5-t)<=5. The
completed numerator is a power of two times the integer

```text
N = M_a * 2^(j-d) - odd * M_b * 2^(j-(5-t)).
```

Nearest-cell selection implies |a-(n/32)b|<=b/64. Therefore
|N|<=M_b*2^(j-6)<2^63. The completed numerator needs at most **63 significant
bits**, so its CHOP67 operation cannot discard a nonzero remainder in this
graph. Searching for that discarded event would target an empty bucket.

An independent exact-rational polygon certificate checks all 186
cell/exponent regions (66 nonempty) after relaxing strict boundaries outward.
Its maximum agrees with the bound. A valid cell-2 witness proves sharpness:
y=`3ffa:f000000000000001`, x=`3fff:a000000000000000` has a 63-significant-bit
numerator retained exactly by T63 but changed by T62.

This is a theorem of the **completed numerator in the specified graph**.
It does not permit truncating the individual products before cancellation,
identify silicon widths, or prove native equivalence. The certificate was
rerun exactly; a first receipt comparison needed tuple/list JSON
normalization, not a mathematical or source correction.

Source: `d0038_numerator_width_certificate.py`. Evidence:
`../tmp/fpatan-re/d0038-numerator-width-certificate.json`.

## D0039: construct the correction tie backward

The direct kernel's pre-RN64 correction sum depends on the retained square
u. Instead of hoping random operands hit a tie, the miner chooses an exact
half-ULP target for that sum and searches the 64-bit u lattice. The bounded
domain uses square exponents -10 and -9, with u capped at (3/64)^2. A local
bisection produces candidates; it is not used to claim global monotonicity
or the absence of witnesses elsewhere.

For each exact hit, the miner enumerates the 67-bit z lattice near the
integer-square-root inverse and checks the actual asymmetric operation
RN64(z*T64(z)). It then tries up to 64 exact external denominators, checking
representable numerator neighbors and T67(y/x)==z. The public raw operands,
not an unattested internal state, are what enter the candidate pool.

The 65,536 target searches yielded 7,089 correction ties and 28,803 checked
square preimages. Four bounded external lifts failed and remain **UNKNOWN**,
not unreachable. All **28,799 successfully lifted external pairs** are
retained, including the non-visible controls. Their tie parities are 14,457
even and 14,342 odd. **32 pairs** expose the opposite halfway decision in
at least one of the sixteen positive-restoration/RC output-or-C1 endpoints.

Every retained row was independently reproduced with exact Fraction
arithmetic, the published pseudocode, and the named-node trace. This checks
the external reduction, square, exact tie, parity and complete endpoint
difference mask. The C miner also checks every positive restoration and RC
through the complete unchanged production graph. No native labels were read.

Sources: `d0039_correction_tie_miner.c`, `d0039_correction_tie_mining.py`.
Evidence: `../tmp/fpatan-re/d0039-correction-ties/`, including the full pool,
start receipt, process log and independently verified report. Deterministic
seed and bounded unsuccessful searches are preserved in the pinned sources.

## D0040: prospective protocol

The entire 28,799-pair pool receives all eight sign/octant orbits and all
four RC. All 32 endpoint-visible witnesses additionally receive 5x5
both-operand neighborhoods and common power-of-two transports to both
normal exponent limits and an intermediate scale. PC24 and PC53 are sampled
alongside PC64. There are 237,304 unique generated pairs, all admitted after
local private/public/corpus and prior-tuple checks, yielding **956,608 fresh
observation tuples**. No possible-history hold was bypassed.

One deliberately different control is frozen before dispatch: flip only
exact-halfway decisions at the direct correction_sum node from nearest/even
to nearest/odd. All other graph operations remain identical. Frozen
predictions contain 708 union separators: 540 output differences and 300 C1
differences, with overlap. There are 933,808 exact-tie observation rows,
including both retained parities, plus 22,800 non-tie neighbors.

Optimized C and address/undefined-behavior-sanitized C independently match
all frozen predictions. The four software construction regressions pass.
Public remote history auditing passes, staging confirms the reported
Skylake signature, and the one-shot guard reserved and executed the complete
batch once. Only cleared inputs and generic capture infrastructure were
uploaded; model and private data remain local. Results were fetched and
authenticated. The ledger reports integrity `ok` and D0040 `OBSERVED`.
All D0040 process handles are terminal. **Never recapture these tuples on
that reference.**

## Native results and retained corpus

| Check | Result |
|---|---:|
| Fresh observations | 956,608 |
| V7 output / C1 / exception / pre-load misses | 0 / 0 / 0 / 0 |
| Opposite-halfway control: output / C1 / union misses | 540 / 300 / 708 |
| Control separators with even / odd retained parity | 386 / 322 |
| Three-member exact normal-scale groups / hardware splits | 1,024 / 0 |
| Complete three-PC groups / differences | 3,696 / 0 |

Output and C1 differences overlap; their sum is not a distinct-row count.
The 708 control separators comprise 260 RN, 152 RD, 152 RU and 144 RZ rows.
Every RC has 239,152 observations. PC24 and PC53 each have 3,696 rows;
PC64 has 949,216. Families comprise 928,744 full-pool rows, 24,768 visible
neighbor rows and 3,096 extreme/intermediate normal-scale rows. Another 24
scale-group mode keys have only one observation and are not counted as
invariance checks. No invalid or underflow flags occur in this normal,
moderate-ratio campaign; those classes remain covered by earlier packs.

The control changes just one exact-half decision. Its rejection on both
parities is discriminating evidence for this node, not a universal proof
of the graph or a new selector. Of the 32 independently verified base
separators, 31 expose the first-octant endpoint; one exposes the swapped
pi/2-t endpoint. Merely checking one quadrant would miss that latter case.

The append-only [D0040 extension](corpus-v1/extensions/d0040/README.md) and
[combined catalog](corpus-v1/CATALOG-D0040.json) contain **4,612,536 distinct
tested tuples across seventeen packs**, independently checked for duplicates.
The unchanged V7 now has **2,453,640 prospective observations**. The full
28,799-pair construction-input pool is also retained without internal state,
model predictions, hardware labels or private data. Earlier manifests,
catalogs and packs remain byte-identical. The package is approximately
140 MiB; original paper/delivery counts remain fixed publication snapshots.

Evidence in `../tmp/fpatan-re/d0040/`: frozen manifest/control, both C
preflights, dispatch/start/completion receipts, `SCORE.json`,
`CORRECTION-CONTROL-SCORE.json` and `LEDGER-AUDIT.json`. The final
`../tmp/fpatan-re/d0040-adversarial-verification.json` is **PASS**. It
authenticates the evidence chain and source pins, repeats the exact D0038
certificate and four construction tests, checks the corpus and all seventeen
paper/source evidence pins, and verifies the PDF/C program are unchanged.

## Remaining scope

D0040 does not close coverage of the earlier inner RN64 additions or the
short table correction; those need independent reachable/exposed constructions. The inverse
search here covers only a bounded upper part of the direct domain. Remaining
CHOP-node/final-boundary intersections and larger provisional pools are not
exhausted. No all-input hardware proof, cross-CPU transfer, complete
theoretical corpus or day-scale FPATAN campaign is claimed.
