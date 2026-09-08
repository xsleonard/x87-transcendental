# D0045–D0046: exposing a previously masked RN64 tie decision

2026-09-06. The objective is to identify the correct tie rule at all four
D0041 additions. It is not satisfied merely by another passing corpus.
Production C, pseudocode, LaTeX and PDF remain unchanged.

## D0045: target propagation, not just the occurrence of a tie

D0041 spread its search over several square binades and attempted only two
table cells per candidate. D0045 concentrates on larger admitted residuals,
then checks every table cell permitted by the exact inverse ratio. The
search separately records a change in the rounded correction H, a change
after the 67-bit kernel cut, and a change in the architectural output/C1.
The final cell-specific external lift must still reproduce the actual
separately truncated reduction; the inverse ratio alone is not accepted.

The production graph supplies the expressions and ROM constants, but all
targets and retained preimages are independently checked with exact Fraction
arithmetic. Target records are preserved even when changing the tie is
masked. These internal square targets are not automatically external raw80
preimages, and counts below must not be described as hardware observations.

| Target | Square binade | Searches | Verified internal halfways | H changes | Pre-anchor cut changes | External endpoint separators |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long odd inner | -9 | 262,144 | 12,727 | 0 | 0 | 0 |
| Long even inner | -9 | 262,144 | 10,515 | 0 | 0 | 0 |
| Short odd chain | -13 | 1,048,576 | 70,436 | 8 | 0 | 0 |
| Short correction | -13 | 262,144 | 35,748 | 35,748 | 85 | 76 |

For the short odd-chain target, eight changed-H square states have 49
67-bit residual preimages; every effect still disappears by the pre-anchor
cut. This is measured masking, not a proof of global equivalence.

For the short correction, there are 163,571 verified square preimages.
Eighty-five cross the pre-anchor cut. Checking every admissible cell/sign
yields 1,711 cell proposals, of which 76 change an output or C1. All 76 have
exact external raw80 preimages, with no bounded lift failures: 49 have even
retained parity and 27 odd. The complete optimized and ASAN/UBSAN target
streams and logs match byte-for-byte; the independently verified witnesses
also match. Synthetic scorer tests detect the opposite hardware outcomes
at both parities. No native instruction runs during these checks.

Artifacts under `../tmp/fpatan-re/` are `d0045-node0-upper/`,
`d0045-node1-upper/`, `d0045-node2-upper/`, `d0045-node3-upper/` and
`d0045-node3-sanitized/`, plus separate small pilot runs. Each preserves
the source/binary pins, exact target stream, progress log and report.
The pilots are separate bounded searches, not additional native captures.

## D0046: a frozen four-rule hardware discriminator

All 76 external witnesses are expanded through 3-by-3 both-operand
neighborhoods, eight sign/octant transformations, all four RC and sampled
PC24/53 controls. All 5,472 operand pairs pass the local public/private/prior
history checks: **22,064 fresh tuples**, no holds. This is an additive
challenge, not a repetition of D0042 or its i7 transfer.

The frozen batch has 1,568 even-parity and 872 odd-parity exact correction
ties. Of these, 224 and 142 rows, respectively, distinguish opposite tie
decisions. The other cases remain in the input pack as ordinary model and
neighborhood checks. The short odd-chain addition has no ties in this batch.

The predictions distinguish four fixed half rules while changing only this
one addition. At even retained parity, nearest/even agrees with ties-zero
and nearest/odd agrees with ties-away; at odd parity those relationships
reverse. Consequently, if hardware follows the unchanged nearest/even graph,
the expected union mismatch counts are:

| Rule at short correction RN64 | Expected disagreements with nearest/even |
| --- | ---: |
| Nearest/even | 0 |
| Nearest/odd | 366 |
| Ties away from zero | 224 |
| Ties toward zero | 142 |

Those disagreement counts were frozen before capture. Every input is evaluated;
omitted sparse input/node overrides explicitly equal the baseline. The
manifest and complete control predictions are pinned before dispatch.
Both optimized and sanitized production-C preflights match all 22,064
predictions. The public remote history audit finds no unmanaged FPATAN
history; the generic guard independently checks managed tuple reservations.
Only cleared inputs and generic capture helpers are uploaded, never model
code, predictions or private supplemental history.

**Native result: nearest/even passes; all three alternative fixed rules are
rejected.** The one-shot capture completed and authenticated all 22,064 rows
on CPUID `00050654`, microcode `0x1`. V7 has zero output, C1, exception or
pre-load misses. All 88 three-PC groups agree. The remote ledger is `ok`,
D0046 is `OBSERVED`, and capture/fetch/score handles are terminal.

The actual union mismatch counts equal the frozen table above: nearest/odd
366, ties-away 224, ties-zero 142. Their output and C1 mismatch counts are
respectively 246/246, 152/152 and 94/94; these counts overlap and must not be
summed. Both retained parity classes discriminate nearest/even from the
alternatives. This is positive identification among these four fixed rules
for **the short correction addition**, not an inference from a masked test.

The input-only append-only extension is `corpus-v1/extensions/d0046/`, with
all 22,064 tuples and the 76 constructive base pairs. The completed
`CATALOG-D0046.json` has 7,119,648 unique tuples in 19 packs, with zero exact
cross-pack duplicates.
The previous 7,097,584-tuple snapshot was verified on both CPUs; **this new
D0046 extension has not yet been run on i7**. Do not describe the enlarged
catalog as already tested on both contexts. All native results remain outside
the reusable corpus, and the original catalogs/packs are unchanged.

## D0047: exact carry constraints for the three unresolved additions

`d0047_tie_carry_smt.py` builds operation-specific-width QF_BV constraints
for an RN64 square input, the exact target halfway and a changed correction
H. Signed magnitudes and every normalization interval are explicit. The
reference-derived normalization/sign template is part of the query's domain;
it is not assumed to cover the entire polynomial domain. The square is a
relaxed input: any new SAT result would still need a 67-bit residual and
external raw80 preimage, then an endpoint-visible effect.

Each concrete template replays every symbolic intermediate against exact
Fraction values. For the short odd chain, the template is deliberately one
of D0045's already known changed-H states; thus surviving H carries there
are known possible independently of the free search. Z3 4.15.3 returned
**UNKNOWN after 30,000 ms** for all three free searches, with no new witness.
Their original SMT2 files, hashes and reports are preserved under
`d0047-node0-carry/`, `d0047-node1-carry/` and `d0047-node2-carry/`.
These timeouts prove neither global nor template-local unreachability.

The final combined receipt `../tmp/fpatan-re/d0045-d0046-verification.json`
passes the evidence audit: native and control scores, both C preflights,
the full sanitized miner replay, exact witness and synthetic scorer tests,
source/artifact hashes, corpus uniqueness receipt, preserved D0047 queries
and unchanged C/pseudocode/LaTeX/PDF. It explicitly records the three
unresolved additions and `goal_complete: false`.

## What would and would not finish the objective

The zero-miss nearest/even result together with rejection of all three
alternatives at both parity classes identifies the short correction's fixed
half rule within this operation graph and recorded CPU context. It does not
identify the two long inner additions or the short odd-chain addition.
Nor does it rule out arbitrary untested, state-dependent rules; finite
discrimination must not be presented as a universal silicon proof.

The full objective therefore remains open after this one-node challenge.
The next useful work for the remaining additions is an exact joint
constraint on the target halfway and a downstream carry/rounding boundary,
followed by a real 67-bit residual and external raw80 preimage. The existing
zero-separator searches are neither UNSAT proofs nor grounds for assigning
nearest/even to those hidden nodes by association. Shared-operation lineage
would require its own evidence before being used as a transfer argument.
