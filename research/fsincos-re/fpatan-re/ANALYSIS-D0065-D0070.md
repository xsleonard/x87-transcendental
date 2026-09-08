# Independent mathematical-boundary and raw-bit challenge

2026-09-06. This campaign addresses correlated test-selection bias: earlier
internal-node tests were useful discriminators within the reconstructed
graph but could overlook a wrong graph. The new generators import neither
the candidate, its ROM, its polynomial, its table-index logic, nor any
hardware labels. The production algorithm and publication are unchanged.

## Independent selection

D0065 fixes its recipe before constructing inputs. MPFR evaluates
`tan(angle)` with directed lower/upper rounding at 192 and 384 bits. Every
384-bit enclosure nests inside its 192-bit enclosure; optimized and
address/undefined-sanitizer builds agree. Angles are independently selected
raw80 RN midpoints and directed-rounding boundaries, including normal and
subnormal output ranges. No candidate branch or output selects an angle.

For each angle, four independently generated denominator significands give
552 total certified positive-base brackets. Exact rational arithmetic finds
adjacent raw80 numerators y0,y1 satisfying

`y0 <= tan_lower(angle)*x <= tan_upper(angle)*x < y1`.

Sign/swap orbits and exactly representable common power-of-two rescalings
extend these pairs. They are tested separately; scale invariance is not
assumed from the mathematical ratio. A transformed quadrant is not claimed
to remain at the same mathematical output midpoint.

The other independent tracks are:

- A deterministic raw-significand sweep of all 32,767 finite exponent fields
  in **each operand position**, paired by an exponent permutation. It is one
  sample per exponent field, not all significands at that exponent.
- 4,096 additional full-width raw pairs with nearby exponents, to avoid
  having exponent-gap/extreme-ratio cases dominate the whole challenge.
- Sixteen complete 17-by-17 two-operand significand windows, with all eight
  sign/swap orbits: 36,992 pairs. These include subnormal, minimum-normal,
  moderate and high-exponent regions. The declared windows, not their
  surrounding binades, are exhaustive.

## SMT and exact lattice construction

The original 22 QF_LIA queries ask for two legal 64-bit significands A,B
whose ratio lies just below or above a certified mathematical target.
Let R be the target ratio normalized into [1,2), and L/2^192, H/2^192 be
outward-rounded bounds. For a below-target witness the constraints are

`0 <= L*B - 2^192*A <= H*B - 2^192*A <= 2^144`.

The above-target query reverses the subtraction. Both A and B lie in
`[2^63,2^64)`. Thus every accepted witness satisfies
`abs(A - B*R) <= 2^-48`, or normalized ratio error at most `2^-111`.
These are representation/mathematical constraints, not microcode constraints.

All original Z3 searches returned UNKNOWN at a two-second bound. Their
SMT2 files and responses are preserved exactly under
`../tmp/fpatan-re/d0065-independent-inputs/smt/`. UNKNOWN did not discard
any region.

D0068 instead enumerates continued-fraction convergents of the certified
ratio enclosure's midpoint, scales their numerator and denominator into
the external significand range, then checks the full directed bounds with
exact rational arithmetic. It finds **526 exact base witnesses** across
the mathematical targets. Concrete assignments satisfy **21 of the 22
original queries**, with independent integer replay and Z3 checking each
pinned assignment against the original unmodified constraints. That
establishes constructive SAT for those queries without rewriting the old
UNKNOWN search receipts. `a0064-below` has no constructed witness here;
it remains unresolved, not UNSAT or impossible.

The initial D0068 attempt failed an external-encoding assertion for a ratio
below the minimum normal exponent. Its failure receipt is retained in
`d0068-independent-lattice/FAILED.json`; no input pack or hardware observation
was produced. The corrected `d0068-independent-lattice-v2` lifts both
operands' common scale so their ratio remains exact and their encodings are
legal. Every resulting witness is independently decoded and checked.

## Frozen input and capture scope

The combined pool has **110,839 distinct operand pairs**:

| Family | Pairs in independent pool | Fresh observation tuples |
| --- | ---: | ---: |
| Mathematical brackets and transforms | 24,832 | 100,104 |
| Exact lattice witnesses and transforms | 12,152 | 47,768 |
| Raw exponent permutation | 32,767 | 132,092 |
| Raw nearby-exponent pairs | 4,096 | 16,512 |
| Exhaustive two-operand windows | 36,992 | 149,112 |
| Total | 110,839 | 445,588 |

Local private/public history conservatively holds 304 pairs. No private
record is exported, and a hold does not assert that an exact pair was
previously observed. The admitted 110,535 pairs produce 445,588 tuples:
all four RC modes at PC64, plus sampled PC24/53. No admitted pair or tuple
is discarded according to the candidate's prediction.

D0066 writes and hashes `INPUTS-FROZEN.json` **before importing the
candidate**, then predicts every admitted tuple. Optimized and sanitizer C
builds both match all 445,588 frozen Python predictions. D0067 uses byte-
identical inputs and predictions on i7; its preflight receipts explicitly
reuse the same complete streams, not additional executions.

The input construction audit is
`../tmp/fpatan-re/d0069-independent-input-audit.json`,
`PASS_INDEPENDENT_INPUT_CONSTRUCTION`. It checks dependency independence,
all certified brackets, all lattice witnesses, original-query assignments,
all canonical raw encodings, complete exponent-field coverage, all declared
window members, and source/artifact hashes without candidate predictions.

## Native results

D0066 (Skylake `00050654:0x1`) and D0067 (i7 `000506e3:0xf0`) each complete
**445,588 one-shot observations**, authenticated by manifest, raw-output and
compressed-output hashes. Both host ledgers have integrity `ok` and mark
their batches `OBSERVED`. **Neither campaign may ever be captured again.**

| Check | Skylake | i7 |
| --- | ---: | ---: |
| Observations | 445,588 | 445,588 |
| Candidate output mismatches | 0 | 0 |
| Candidate C1 mismatches | 0 | 0 |
| Candidate exception mismatches | 0 | 0 |
| Candidate preload exception mismatches | 0 | 0 |
| Complete three-PC groups | 1,724 | 1,724 |
| Three-PC value/status differences | 0 | 0 |

Both complete raw output streams have the same SHA256: numerical values,
full captured status words, controls and input mappings are byte-identical.
Each context includes 14,692 observations with underflow set. All five
independent selection families pass; none is removed after seeing labels.
This is 891,176 CPU observations of 445,588 distinct new input tuples, not
891,176 additional distinct inputs.

`d0070_finalize_independent.py` independently recounts the native results,
checks receipts and unchanged publication sources, and checks the entire
append-only corpus for exact tuple duplicates. Final receipt:
`../tmp/fpatan-re/d0070-independent-verification.json`. The new input-only
pack is `corpus-v1/extensions/d0066/inputs.txt.gz`, with D0067 using the same
pack on the second context. No expected outputs or hardware labels belong
in that package.

The final receipt is `PASS_INDEPENDENT_TWO_CPU_CHALLENGE`.
[CATALOG-D0066.json](corpus-v1/CATALOG-D0066.json) contains **7,571,628 unique
tuples in 23 packs**, with zero exact cross-pack duplicates. Common two-CPU
coverage is 7,543,172 tuples; the older 28,456 tie-discriminator rows still
have Skylake-only coverage. All work in this campaign is terminal; no
background construction or capture remains.

This is finite independent evidence. Correctly rounded mathematical atan2
is used to **select** challenges, not as a bit-exact specification for x87.
Matching the hardware on these inputs cannot prove an unknown silicon graph,
exclude arbitrary isolated failures, or establish all-generation behavior.
Production C, pseudocode, LaTeX and PDF are not modified by this campaign.
