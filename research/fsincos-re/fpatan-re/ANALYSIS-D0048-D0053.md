# D0048–D0054: algebraic tie inversion and exact local carry checks

2026-09-06. The goal remains to identify all four formerly masked additions.
The short correction addition is identified as nearest/even among the four
fixed rules by D0046; the long odd-inner, long even-inner and short odd-chain
rules are still unresolved. No new hardware, algorithm change, corpus
promotion, pseudocode edit or paper update belongs to this investigation.

## D0048: preserve the solver outcome and the parser failure separately

CVC5 returned `unknown (TIMEOUT)` after the independent 30-second checks of
the three unchanged D0047 queries. D0048's parser only accepted bare
`unknown`, so its three receipts record a parser error and preserve the
timeout text in stderr. These are not successful solver receipts and are
not UNSAT proofs. The original files and hashes remain unchanged.

## D0049: invert the halfway target algebraically

For these inner additions the magnitude of the target is
`B + T67(v*C)`, where `v = T67(u*u)` and `u = U*2^(e-63)`.
At a fixed binade, an RN64 halfway requires the truncated product to lie on
one arithmetic progression of dyadic values. For each selected product:

1. Its exact T67 multiplication interval gives an inclusive integer interval
   for the 67-bit significand of `v`, using integer division by `C`.
2. Inverting `v = T67(u*u)` gives all integer `U` preimages by integer square
   roots of the interval endpoints.
3. A separately written integer-dyadic graph checks the target and altered
   tie. Every changed-H state and external endpoint candidate also receives
   exact Fraction replay. A fixed sample of other targets receives it too.

This is a closed-form preimage construction for the specified target and
binade, **not a newly identified hardware rounding law**. D0049 samples the
target progression; D0053 below exhausts it over explicit local intervals.
All 93,678 earlier GMP targets replay correctly and are recovered by the
inverse, including their tie parity and changed-H classifications.

| Completed D0049 search | Product targets searched | Exact U ties | First outer changes | H changes | Residual preimages after H change | Kernel cut changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long odd-inner, e=-9 | 16,777,216 | 807,789 | 14 | 0 | 0 | 0 |
| Long even-inner, e=-9 | 16,777,216 | 678,254 | 16 | 1 | 6 | 0 |
| Short odd-chain, e=-13 | 67,108,864 | 4,372,358 | 4,372,358 | 379 | 1,676 | 0 |
| Short odd-chain expanded, e=-13 | 268,435,456 | 17,494,745 | 17,494,745 | 1,510 | 6,702 | 1 |

The new even-inner changed-H square is `U=8768acc7f2f6dc43`, e=-9,
odd retained parity. Its six 67-bit residual preimages are
`5d179e4d4ba603772` through `5d179e4d4ba603777`, at step -71.
All six are still endpoint-masked. This refutes the narrower idea that
even-inner tie changes always disappear before H; it does not identify the
tie rule or establish an externally visible counterexample.

The separate 268,435,456-target short odd-chain search completed and is
retained under `../tmp/fpatan-re/d0049-node2-expanded/`. Its one cut change
has 19 admissible cell/sign proposals, all endpoint-masked; see D0054 below.
Counts from different sampled runs must not be added as unique inputs.

## D0050–D0051: a sound local affine relaxation, not an exact SAT witness

D0050 replaces each varying product in a bounded integer box with
`a0*b + b0*a - a0*b0 + r`, where
`0 <= r <= (amax-a0)*(bmax-b0)`. The identity
`r = (a-a0)*(b-b0)` proves inclusion of every exact product, including signed
intervals. Additions and rounding constraints remain explicit. An UNSAT
result excludes a changed H only inside that box. SAT must be replayed
exactly and may be spurious because product remainders were relaxed.

The fixed-U even-inner positive fixture is SAT and independently exact;
the fixed-U odd-inner masked fixture is UNSAT. The three nontrivial Z3
boxes timed out at 30 seconds. D0051 fixes result parsing in a new file and
cross-checks two unchanged box queries in CVC5: both timeout at 10 seconds.
The emitted SMT2 has no set-logic directive; CVC5's default all-theories
warning is preserved. No successful exclusion or new witness is inferred.
Five signed-enclosure, rounding, fixture and parser tests pass.

## D0052: exactly where the known perturbations disappear

The exact propagation audit is `../tmp/fpatan-re/d0052-wide-masking.json`.
All 14 surviving long odd-inner outer changes also change the weighted
odd term and the pre-H sum, then disappear at RN64(H). The long even-inner
changes bypass the weighted odd term: 16 change the pre-H sum and one
changes H. This identifies the next arithmetic boundary to constrain.

For the closest even-inner residual, the changed kernel value moves by
`3/512` of a 67-bit cut unit but is `199/1024` units from the boundary in
that direction: 199/6 times the perturbation, so no cut changes.
For the closest short odd-chain residual in the 67-million-target search,
the perturbation is `1/1024` cut unit and the boundary is `11/8192` away:
11/8 times the perturbation. This is a near miss, not a separator and not
evidence for a global lower bound. Distances are exact rational values,
not a statistical independence assumption.

## D0053: exhaustive local inverses decide the boxes that timed out

D0053 clips the algebraic preimage domains to an explicit inclusive U box,
checks that the target binade remains fixed, and enumerates every halfway
product and every integer U preimage. The boxes correspond exactly to the
nontrivial D0050 queries; the old UNKNOWN receipts are preserved.

| Node and inclusive U interval | Halfway targets enumerated | Exact U ties | First outer changes | H changes |
| --- | ---: | ---: | ---: | ---: |
| Odd-inner `8f2ede97a33447a8` … `8f2ede97c33447a6` | 5,603 | 256 | 1 | 0 |
| Odd-inner `8f2ede87b33447a8` … `8f2edea7b33447a6` | 1,434,139 | 65,447 | 2 | 0 |
| Even-inner `8768acb7f2f6dc44` … `8768acd7f2f6dc42` | 806,729 | 32,697 | 2 | 1 |

Thus the two odd-inner boxes contain no exact changed-H witness. The
even-inner box contains exactly the already-known changed-H square, whose
six residual preimages remain endpoint-masked. These are finite-box facts,
not full-domain proofs. Forward enumeration tests verify inverse completeness
on narrow intervals around known targets, inclusive endpoints, and a fourth-
power normalization boundary. No new hardware discriminator is asserted.

## D0054: the first short odd-chain kernel-cut change is still masked

The expanded run reaches a genuinely new intermediate boundary:
`U=cbbbd15084120294`, e=-13, even tie parity, and residual
`72303091d4576d17f * 2^-73`. Its kernel perturbation is 11/16384 of a
67-bit cut unit, and the boundary is only 1/16384 away. The cut changes
from `722e4bf5af98163f6` to `722e4bf5af98163f7` common units of `2^-73`.

That changes low residues 2 to 3 modulo four. Every admissible table anchor
is a multiple of four common units. The next 67-bit cut, and every RN64
half/integer boundary for direct t, are also multiples of four or a coarser
grid. Neither the positive interval (residues 2..3) nor negative interval
(residues 1..2) crosses such a boundary. The pi restorations consume the
unchanged next 67-bit cut. Thus all 19 admissible cell/sign cases have
identical output/C1 predictions, established both by exact replay and this
dyadic alignment argument. This is not a fitted selector or a global proof.

`../tmp/fpatan-re/d0054-cut-grid-proof.json` is
**PASS_EXACT_CUT_GRID_MASKING_PROOF**. It authenticates the expanded
propagation audit and the combined **PASS_SEARCH_AND_LOCAL_BOX_AUDIT**
receipt `../tmp/fpatan-re/d0048-d0053-verification.json`. The latter checks
all search streams, fully re-enumerates the exact local inverses, replays
all local ties with Fraction arithmetic, passes eight tests, preserves
UNKNOWN/error evidence, and verifies unchanged publication/corpus files.
No new external endpoint witness, hardware run or tie identification results.

## Continuation requirements

Keep the three unresolved rules open. Preserve all streams, positive
fixtures, parser failures and UNKNOWN queries; do not rewrite a timeout as
UNSAT. Use the exact local inverse to avoid repeating unsuccessful SMT
searches on boxes it can already enumerate. The remaining joint constraints
are odd-inner tie + outer carry + H boundary, and (for even-inner/short odd)
tie + changed H + final kernel cut. Any proposed hardware test must first
have an exact external preimage and an output/C1 difference, with both tie
parities needed to distinguish all four fixed rules. Nothing here warrants
editing the confirmed-only paper or production algorithm.

A new bounded 536,870,912-target short odd-chain search has been launched
at `../tmp/fpatan-re/d0049-node2-next/`. Its seed differs because the target
count is part of the frozen sampling seed. This is a new software search,
not another hardware observation or a repeat claim for unique inputs.
Check the existing process handle and terminal REPORT.json; do not restart
from a missing completion file alone. The complete expanded run and the
new running search are separate evidence sets.
