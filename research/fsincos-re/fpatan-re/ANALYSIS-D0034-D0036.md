# D0034–D0036: restored boundaries and nonzero discarded-history tests

2026-09-06. **837,600 fresh observations, zero V7 misses.** The unchanged
implementation survives this next adversarial campaign. This is not an
exhaustive proof; the broader investigation remains active. No numerical
change, new selector, pseudocode edit or paper revision was made.

## Independently mined restored-quadrant boundaries

D0034 mines each of `t`, `pi-t`, `pi/2-t` and `pi/2+t` separately, for RN
and RD. It does not assume that sign/swap expansion of a first-octant
boundary remains boundary-adjacent after restoration. RN targets include
the ordered pair `(positive raw result, 1-C1)`: a rounded-up flag can change
without a change in result bits. All RC and both signs are tested later.

Bisection maintains a local predicate bracket, not an assumed global
monotonicity theorem. Every accepted bracket retains the two adjacent raw80
values and a complete nine-point neighborhood. The published exact-rational
pseudocode independently reproduces every C-mined endpoint and C1 bit and
checks actual external adjacency, including exponent-binade changes.

Of 4,096 attempts, **3,649 local brackets** were verified, with **32,841
neighbor rows**, **707 C1-only transitions**, and no local reversals in the
checked windows. Another 447 attempts had their low endpoint already at or
beyond the selected target and were skipped; that is not an impossibility
proof. There were no failed high-end brackets. The retained windows include
tiny, direct and table paths in every restoration/mode combination.

Sources: `d0034_quadrant_boundary_miner.c` and
`d0034_quadrant_boundary_mining.py`. Evidence:
`../tmp/fpatan-re/d0034-quadrant-boundaries/`.

## Same retained state with different nonzero cut histories

D0035 uses exactly representable dyadic ratios `m/2^K` near table centers.
Choose `d=-floor(log2(m/2^K))`, and bounded integers B such that both
significands below have their integer bit set and fit in 64 bits:

```text
y_significand = m*B             y_exponent = 16383-d
x_significand = B*2^(K-d)       x_exponent = 16383
```

The exact external ratio is fixed, while the denominator's CHOP67 remainder
can change with B. **Ratio equality does not admit a group:** the script
separately verifies equal nonzero retained z, the selected table cell, and
three distinct nonzero denominator-cut remainders. All numerators in this
family are exactly retained. Independent full published-graph calls confirm
the equal angle for every selected member.

The 31,232-pair scan yielded 486 nonzero-cut retained-state groups; 124 lacked
three distinct nonzero remainders and were not selected. The retained
**362 three-member groups** cover 28 table cells. Cells 16, 24 and 32 do not
meet this bounded family's three-remainder selection criterion; no general
unreachability claim follows. Unlike D0033's exact-sum integer-scale groups,
these groups deliberately vary a discarded, nonzero reduction remainder.
The entire candidate pool, including unselected cases, is preserved.

Source: `d0035_cut_history_groups.py`. Evidence:
`../tmp/fpatan-re/d0035-cut-history-groups/`.

## Frozen prospective campaign

D0036 retains every D0034 nine-point window, crosses it with three adjacent
denominator values, and tests both y signs and all four RC. The D0035 members
receive all sign/octant orbits. There are also 2,048 independently selected
full-exponent pairs and a bounded PC24/53 subset. All **207,782 generated
pairs** cleared the local private/public/corpus and prior-tuple checks.
The resulting manifest contains **837,600 observations**.

Two deliberately different controls were frozen before dispatch: use CHOP64
instead of CHOP67 immediately before nontrivial quadrant restoration, or omit
that cut. No other operation changes. These are test controls, not promoted
program variants or caller-selected implementation flags. Optimized and
address/undefined-behavior-sanitized C builds match all frozen V7 predictions.

The public prior-use audit passed. The remote guard checked its existing
tuple ledger, reserved the entire fresh batch durably, and executed the batch
once on the established guest-reported Skylake reference (`00050654`, reported
microcode `0x1`). No model or private records were uploaded. Results were
fetched and authenticated; the ledger reports integrity `ok`, D0036 `OBSERVED`.
All D0036 process handles are terminal. Never recapture these tuples there.

## Results

| Result | Count |
|---|---:|
| Observations | 837,600 |
| V7 output / C1 / exception / pre-load misses | 0 / 0 / 0 / 0 |
| CHOP64-before-restoration control: output / C1 / union misses | 56,099 / 40,423 / 80,701 |
| Omitted-precut control: output / C1 / union misses | 8,046 / 8,046 / 13,604 |
| Three-member equal-z, different-nonzero-cut groups | 11,584 |
| Hardware output/flag splits in those groups | 0 |
| Complete three-PC groups / differences | 3,236 / 0 |
| Underflow observations | 500 |

Output and C1 control misses overlap; do not sum them. Every RC has 209,400
rows. PC24/53 each have 3,236 rows; PC64 has 831,128. The observed families
are 794,320 quadrant-boundary rows, 35,024 nonzero-cut-history rows, and 8,256
independent controls. An additional 272 history-group RC/PC keys have only
one observed member and are **not** counted as group-agreement checks.

The results reject these two precise alternative pre-restoration operations
and reveal no discarded-history split in the selected groups. They do not
identify all physical micro-operations, establish universal retained-state
sufficiency, or prove transfer to another CPU.

Evidence in `../tmp/fpatan-re/d0036/`: `MANIFEST.json`,
`STRUCTURAL-HYPOTHESIS.json`, `C-PREFLIGHT.json`,
`C-SANITIZED-PREFLIGHT.json`, dispatch/start/completion receipts, `SCORE.json`,
`RESTORATION-CONTROL-SCORE.json`, and `LEDGER-AUDIT.json`.

## Corpus and next work

The append-only [D0036 corpus extension](corpus-v1/extensions/d0036/README.md)
brings the combined catalog to **3,655,928 distinct tuples across sixteen
packs**, independently checked for duplicates. The original corpus manifest
and packs remain unchanged. Construction-input pools are preserved without
model output predictions. Native labels remain separate. The input package
is approximately 112 MiB. The unchanged V7's prospective total is now
1,497,032 observations; original paper counts are historical snapshots.

Next, extend the census to the polynomial's remaining RN64 additions and
CHOP67 products/sums. Derive exact reachability/precision bounds before
trying to populate impossible event buckets, and target joint internal/final
boundaries rather than arbitrary feature fits. The broader provisional
D0032/D0035 pools still require history admission and bounded testing. No
day-scale FPATAN campaign or complete adversarial-plan closure is claimed.
