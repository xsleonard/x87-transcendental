# Short-odd boundary discrimination and long-odd acceleration

2026-09-06. **All four formerly masked RN64 additions now have direct
both-parity hardware evidence identifying nearest/even among four fixed
rules in the recorded Skylake context.** D0061 identifies short odd-chain;
D0063 identifies long odd-inner, joining D0046's short correction and
D0057's long even-inner. D0064 independently reconstructs all four results
from 28,456 raw hardware rows and the exact counterfactual graph. Production
C, pseudocode, LaTeX and PDF remain unchanged. No rule is transferred to an
unobserved node by association, and no universal silicon proof is claimed.

## D0058: rejected exclusion, preserved counterexample

The first short-odd filter correctly enclosed the **raw** weighted products
but incorrectly required those raw products to straddle the next rounding
grid. Independent replay of earlier, unfiltered searches falsified that
necessary condition at square `fb05b105f1817315`, exponent -13, block width
128. Both raw products lie above a grid point. The smaller product truncates
exactly onto it; H's RN equality/parity decision then differs from the
above-boundary decision. This is a missing truncation allowance, not an
emulator miss or a hardware observation.

`../tmp/fpatan-re/d0058-filter-failure.json` records
`FAIL_FALSE_NEGATIVE_EXCLUSION`. The original source, verifier and both
completed pilots are retained unchanged. Their retained arithmetic states
are valid, but their discarded-index exclusion is **not certified**. Do not
read their historical `VERIFIED_*` search status as a valid exclusion proof.

## D0059: corrected necessary condition

Let T be the exact truncated product producing the target halfway, B the
positive odd base coefficient, C its positive fourth-power coefficient,
and u the internal square. The smooth weighted-odd center is

`f(T) = sqrt(T/C) * (B+T)`.

The exact inverse bounds give `T <= C*v < T+ulp_T` and
`v <= u*u < v+ulp_v`. Both inner decisions are `B+T +/- half_inner`.
A certified rational square-root bracket, a linear Taylor enclosure and a
bounded negative second derivative enclose f on each target-index block.
Fixed-point coefficient flooring is separately bounded. **D0059 also
subtracts the maximum weighted-product T67 ulp from the lower bound.**

The even addend lies on g=2^-68, and H's halfways lie on 4g in the tested
domain. A changed H therefore requires the closed interval between the
two **truncated** weighted products to include a multiple of g, including
endpoint equality. Exact floor sums enumerate only candidates admitted by
that conservative condition. This is arithmetic-derived search pruning,
not fitting a hardware selector.

Independent tests check 11,279 complete forward product cases, the frozen
false-negative regression, and all 5,151 H carries from three earlier
unfiltered searches at four block sizes. The corrected exclusion includes
every saved carry. Receipt: `d0059-filter-verification.json` under the tmp
directory, `PASS_CORRECTED_SHORT_ODD_FILTER_AUDIT`.

The completed `d0059-short-wide` search covers 1,073,741,824 sampled
target-index occurrences, including possible block overlap. It retains
2,986,597 boundary candidates, 185,026 distinct U ties and 6,673 changed-H
states. Their 30,557 residual preimages produce 24 kernel-cut changes,
294 admissible cell/sign proposals and **ten exact external endpoint
separators**, six at even retained parity and four at odd parity. All lifts
succeed. This is not an exhaustive domain search.

`d0059-short-wide-replay/REPORT.json` independently replays every retained
tie through both optimized and sanitizer-built C, every Z/W record through
the Fraction kernel, and all ten exact external witnesses. All pass. The
2,995-tie pilot also has a complete independent replay receipt.

## D0060: exact native residue enumeration

The long-odd D0056 sampled search is terminal: 274,877,906,944 target-index
occurrences, 342,188 retained ties, 224,129 outer changes, 31 H changes and
157 residual preimages, **zero endpoint separators**. The complete retained
stream has independent C/sanitizer/propagation replay in
`d0060-prior-long-replay/REPORT.json`. It is not a global masking proof.

D0060 replaces only D0056's exact floor-sum residue enumeration with bounded
unsigned-128 C. Guards require `n <= 2^20`, `0 < modulus < 2^108`, and
`modulus*(n+1) < 2^128`; reduced coefficients and clamped margins preserve
the intermediate bounds. Python, shared-library C, optimized CLI and
sanitized CLI agree on 2,790 cases with 4,500,186 selected indices. The
comparison includes both actual long-filter domains and integer-boundary
cases. All three builds pass strict warnings. Receipt:
`d0060-offsets-verification/REPORT.json`.

A 4,096-block sequential pilot compares **every** block's native candidate
list with Python, and Fraction-replays all 5,689 retained ties. It has one
H change, five masked preimages and no endpoint separator. A following
non-overlapping sequential run begins at block 4,096 and is intended to
cover the rest of the highest square binade. After the hardware
discrimination succeeded, the optional sweep was stopped with a normal
interrupt. Its partial streams are authenticated in `STOPPED.json`:
1,444,360 recorded blocks, 2,017,923 ties, 139 H changes, 790 preimages,
eight kernel-cut changes and three endpoint states. Those three states
are represented by D0063. The last recorded block has an independent exact
candidate/target replay. **The whole domain was not searched**; no full
REPORT.json is fabricated. An initial oversized block-count
invocation was rejected before any search; its empty-run `REJECTED.json`
is retained separately, and the corrected run uses a new path.

## D0062: authenticating a useful live-stream prefix

`d0062_freeze_long_prefix.py` snapshots a newline-terminated prefix without
stopping or relabelling the ongoing search. It verifies that the source
prefix remains byte-identical, replays selected endpoint records using
independent Fraction and optimized/sanitized C, and constructs exact raw80
preimages independently of the running process's in-memory witness list.
It explicitly makes **no scan-completion claim**.

`d0062-long-prefix1/REPORT.json` has one exact odd-parity long odd-inner
endpoint witness: U=`801d7b4f75f0477f`, exponent -9,
z=`5a8ce560f753d10c8 * 2^-71`, endpoint mask `000f`.
This breaks the long odd-inner masking barrier for that state, but one
parity alone does not distinguish all four fixed rules. The second prefix,
`d0062-long-prefix2`, adds two even-parity external witnesses at
U=`80c149e0a2c2e641`, with z significands `5ac6b65d3c86413db` and
`5ac6b65d3c86413df` at step -71. Its complete three-witness set covers both
parities and underlies D0063. The subsequently stopped scan has no full
completion claim. Its original partial streams remain intact.

## D0061 hardware challenge

The ten D0059 witnesses generate 720 distinct neighboring/sign/octant pairs
and 2,904 fresh tuples across all RCs, with sampled PC24/53 groups. Local
private/public/prior exclusions hold no pair or tuple. Both unchanged-C
preflights pass, and the remote public history audit and staging pass.
Frozen predictions contain 18 even-parity and 14 odd-parity short-chain
separators. The one-shot capture, authenticated fetch, baseline/four-rule
scoring and ledger audit are complete: **zero baseline misses** in output,
C1, exception or pre-load flags. Nearest/odd fails on 32 union rows,
ties-away on 18 and ties-zero on 14 (output/C1 counts can overlap).
All twelve three-PC groups agree. Ledger integrity is `ok`, D0061 is
`OBSERVED`, and it must never be captured again.

This identifies **nearest/even at short odd-chain among the four fixed
rules**. D0061's complete input-only pack is appended to corpus v1, with
its terminal authenticated audit in `d0061-verification.json`.

## D0063 final-node challenge

The three authenticated D0062 prefix witnesses expand to 216 distinct
neighboring/sign/octant pairs and 872 fresh all-RC tuples, including sampled
PC24/53. Both unchanged-C preflights and the remote history/staging checks
pass. Frozen controls contain ten even-parity and eight odd-parity
separators. The one-shot capture, authenticated fetch, scoring and ledger
audit are complete: **zero baseline output/C1/exception/pre-load misses**.
Nearest/odd fails on 18 union rows, ties-away on ten and ties-zero on eight.
All four three-PC groups agree. Ledger integrity is `ok`, D0063 is
`OBSERVED`, and it must never be recaptured. This independently identifies
**nearest/even for the final long odd-inner addition among the four rules**.

## D0064 final independent audit and delivery

`d0064-all-four-tie-rules.json` is
`PASS_ALL_FOUR_FIXED_TIE_RULES_IDENTIFIED`. It regenerates each targeted
alternative from the exact numerical graph for every captured row, checks
the frozen sparse control predictions, parses authenticated native results,
and independently reproduces all rule scores. It also checks both retained
parities, all RC modes, C preflight receipts, capture contexts, corpus
membership, regression tests and unchanged publication hashes. It does not
merely trust the earlier PASS statuses.

| Addition | Rows | Nearest/even misses | Nearest/odd | Ties-away | Ties-zero |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long odd-inner | 872 | 0 | 18 | 10 | 8 |
| Long even-inner | 2,616 | 0 | 36 | 2 | 34 |
| Short odd-chain | 2,904 | 0 | 32 | 18 | 14 |
| Short correction | 22,064 | 0 | 366 | 224 | 142 |

The input-only [CATALOG-D0063.json](corpus-v1/CATALOG-D0063.json) has
7,126,040 unique tuples in 22 packs, with zero exact cross-pack duplicates.
It includes all D0061/D0063 seeds and challenge tuples. All current packs
have saved Skylake observations. The 28,456 rows from these four campaigns
have not run on i7; two-context coverage remains 7,097,584. All campaign,
verification and mining handles are terminal; no background work remains.

No model predictions or private ledger were uploaded. These experiments
distinguish four fixed local tie rules within the frozen arithmetic graph;
they do not prove arbitrary state-dependent silicon rules or cross-CPU
transfer of these new observations.
