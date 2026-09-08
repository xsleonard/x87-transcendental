# D0041–D0044: inner-addition halfways and two-CPU corpus comparison

2026-09-06. Analysis and adversarial verification only. The production C,
pseudocode, LaTeX and PDF are unchanged. The broader adversarial investigation
is not complete; this is not a universal correctness or silicon-identity proof.

## Exact external halfway construction

D0037 found no exact-halfway coverage at the earlier RN64 additions and only
one table correction-sum tie. D0041 targets four specific additions in the
fixed V7 graph. `T67` denotes truncation to 67 significant bits; the target is
the exact input to the named RN64 operation, before its rounding decision.

| Node | Targeted addition | Exact external base pairs | Even / odd retained parity | Endpoint separators |
| --- | --- | ---: | ---: | ---: |
| 0, long/direct odd inner | `C121 + T67(v*C123)` | 2,040 | 1,056 / 984 | 0 |
| 1, long/direct even inner | `C120 + T67(v*C122)` | 2,099 | 1,104 / 995 | 0 |
| 2, short/table odd chain | `C115 + T67(v*C117)` | 1,425 | 616 / 809 | 0 |
| 3, short/table correction | `T67(u*odd) + even` | 2,998 | 1,529 / 1,469 | 0 |

The C miner performs 8,192 bounded local target searches per node, 32,768
total. It finds 517, 530, 511 and 1,074 exact-halfway square targets,
respectively. Independent exact Python arithmetic inverts
`RN64(z*T64(z))` on the 67-bit residual lattice, then seeks actual raw80
operand preimages. The direct search spans square binades -14 through -9;
the table search spans -20 through -13. Local bisection is a construction
method, not a claim of global monotonicity or complete search coverage.

For table candidates, both residual signs are considered and each bounded
lift checks the actual nearest-cell reduction, not merely a desired ratio.
The successful lifts cover cells 2 through 32, with residual signs where
admissible. There are 2,671 odd-chain and 5,390 correction-sum lift attempts
still **UNKNOWN**, not proved unrepresentable. All 8,562 successful external
pairs are retained, including those with no endpoint-visible mutation.

The independent full-pool test rechecks each raw operand preimage, its exact
halfway equality and parity, the unchanged upstream trace, and the full
published Fraction pseudocode. Optimized and ASAN/UBSAN C miners reproduce
the same complete target stream and log. The three software regression tests
pass; the sanitized receipt is `d0041-inner-ties/SANITIZED-MINER.json`.

## The masking result is a limitation, not a new tie law

Each control changes nearest/even to nearest/odd at exact halfways of only
one named addition. For nodes 0, 1 and 2, the changed decision disappears
before the kernel result in every retained construction. For node 3, the
kernel changes for all 8,388 signed internal preimages, but after lifting to
2,998 actual external pairs its effect disappears by the table-anchor result.
None of the lifted base pairs separates the final output/C1 under the tested
restorations and rounding modes.

D0042 evaluates these four controls on every expanded input before native
capture. All four still have **zero endpoint separators**, including the
neighboring inputs. The frozen sparse override file is therefore empty;
an omitted input/control pair explicitly means exactly the frozen baseline,
not an uncomputed prediction. The native control score labels this outcome
as observationally indistinguishable on this batch. It does not validate
nearest/even versus nearest/odd at these hidden nodes, and it is not a proof
that their effects are globally unobservable. No alternative is promoted.

## D0042: new adversarial batch on the Skylake reference

The entire external pool is expanded through 3-by-3 both-operand neighbor
windows, eight sign/octant transformations, all four RC, and sampled PC24/53
controls. The retained set contains 616,464 distinct raw operand pairs and
**2,485,048 fresh native tuples**, with no local-history holds. It includes
2,465,856 PC64 rows and 9,596 each at PC24/53; each RC has 621,262 rows.

The frozen traces contain 147,920 node-0, 156,448 node-1, 46,312 node-2 and
97,552 node-3 exact-halfway events, with both retained parities at every
node. These are per-node observation counts, not a claim that the sum counts
distinct rows or all reachable internal states.

Both optimized and sanitized production C preflights match all 2,485,048
frozen predictions. The one-shot Skylake capture completes all rows with
**zero V7 output, C1, arithmetic-exception or pre-load-exception misses**.
All 9,596 three-PC comparison groups agree. These new moderate-ratio normal
inputs have no IE/UE events; the older corpus supplies those classes.
The four indistinguishable tie controls also have zero misses, as expected
from their identical predictions. This is not the earlier D0040 result:
D0040 rejected its different, direct correction-sum control on 708 union
rows; those were not V7 failures.

## D0043/D0044: compare the same corpus on i7

The earlier address `142.132.217.24` times out. The existing H1725 campaign
configuration specifies `142.132.217.243`; live inspection verifies that
host as an i7-6700, CPUID `000506e3`, microcode `0xf0`. The reference host
`45.32.204.118` reports CPUID `00050654`, microcode `0x1`, and a hypervisor.
These are recorded execution contexts, not physical-host attestation or
evidence that every x87 generation has identical transcendental behavior.

D0043 captures the previous complete 17-pack corpus, 4,612,536 tuples, on
i7 exactly once. Its frozen reference uses the authenticated saved Skylake
outputs, not obsolete candidate predictions from early discovery campaigns.
Full optimized and sanitized current-C replays also match this reference.
There are zero differences in output, C1, arithmetic exceptions, pre-load
exceptions, or either complete captured status word. All 105,976 three-PC
groups agree; this set includes 50,688 IE and 55,484 UE observations.

D0044 adds only the nonoverlapping D0042 extension to i7; D0043 is never
recaptured. The D0042 optimized/sanitized preflight receipts are reused
because the complete input and prediction streams are byte-identical;
this reuse is not reported as another C execution.

**D0044 is complete and authenticated.** All 2,485,048 rows match V7 and
Skylake: zero output, C1, arithmetic-exception or pre-load-exception misses.
The independent line-by-line comparison also finds zero differences in
either complete captured status word, including the separately reported
undefined condition bits. The entire result stream has the same SHA256 on
both contexts. All 9,596 three-PC groups agree. The remote ledger is `ok`
and records both D0043 and D0044 `OBSERVED`; all capture/fetch/score/finalizer
handles are terminal. Never repeat these tuples.

Thus **all 7,097,584 current corpus tuples have been tested on both recorded
contexts**, with no numerical, C1, exception or full-status differences.
This comparison does not establish transfer to other CPU IDs or generations.

## Corpus, provenance and capture discipline

The append-only input catalog is `corpus-v1/CATALOG-D0042.json`: **7,097,584
unique tuples in 18 packs**, with zero exact cross-pack duplicates. It contains
1,774,396 observations in each RC; PC24 and PC53 each have 115,572 rows and
PC64 has 6,866,440. The Skylake total includes 4,938,688 prospective tests of
unchanged V7. CPU repetitions are additional observations of the same corpus,
not additional distinct input tuples.

`corpus-v1/extensions/d0042/` includes the native input pack and all 8,562
constructive raw operand pairs, stripped of numerical predictions and internal
trace labels. Older input packs, manifests and catalogs remain unchanged.
The construction pool is not itself a native capture-protocol pack.

Private supplemental history is checked locally. Only cleared public inputs
and generic capture/guard helpers are uploaded; no model, predictions or
private records leave this machine. Public remote history audits and the
per-context tuple ledger complement the local checks. Each capture is
one-shot, without warmups; reservations and uncertain tuples must never be
retried. Native completion, stream hashes, source pins, scores and ledger
audits are retained separately from the CPU-independent input package.

Evidence lives under `../tmp/fpatan-re/`:

- `d0041-inner-ties/`: target stream, full constructive pool, report and
  sanitizer replay receipt, including bounded UNKNOWN counts.
- `d0042/`: frozen manifest and controls, preflights, native completion,
  result stream, baseline/control scores and ledger audit.
- `d0043/` and `d0044/`: per-host manifests, reference pins, one-shot receipts,
  native streams and completed full raw-status cross-CPU comparisons.
- `d0041-d0044-verification.json`: final combined audit receipt, **PASS**;
  it checks exact pack coverage on both contexts, source/artifact hashes,
  preflights, ledger states, construction/guard/scoring tests and all frozen
  publication files. It records no model/transfer differences and leaves
  the broader investigation incomplete.

## Remaining theory-led work

The new inputs fill measured event-coverage gaps but do not resolve their
masked internal tie semantics. Useful next constructions couple an exact
inner tie with the downstream truncation/anchor and architectural rounding
boundary, or prove that a proposed separation is impossible within a sharply
specified domain. Joint table-cut/final-boundary cases and the larger D0032
and D0035 provisional pools also remain open. More random volume would not
by itself settle these questions. No complete theoretical adversarial corpus,
day-scale FPATAN run or universal cross-generation agreement is claimed.
