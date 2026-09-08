# D0010–D0011: exact endpoint constraints and terminal exclusions

This is analysis-only evidence, **not a new FPATAN solution**. The main C
candidate and library remain V4; V4 and V5 are both falsified. No hardware
was executed, no tuple was repeated, and no paper or trig code was changed.
The last hardware checkpoint is D0009: 1,640,392 total observations; V5 has
470 output and 324 C1 differences in its 171,920 fresh observations.

## D0010: what the saved outputs constrain

`d0010_full_interval_audit.py` authenticates all nine manifests, input files,
hardware hashes and mapped rows. All 357,092 complete PC64 four-RC groups
with finite outputs have a nonempty common prevalue interval. There are
9,319 singleton groups; many are ordinary tiny/architectural cases, not new
kernel discriminators. Excluded from this interval grouping are 188,984
non-PC64 rows and 23,040 nonfinite-output rows. Zero/subnormal outputs are
handled explicitly. These are feasibility results, not proof that silicon
has RC-independent internal arithmetic.

`d0010_causal_intervals.py` applies exact inverse architectural rounding and
C1 constraints to the 285-group D0008/9 frontier. Five groups agree with V5;
280 do not. There are nine unique positive, unrotated direct groups whose
observed prevalue interval is a singleton. Their tails are consequently exact
constraints **conditional on the candidate's CHOP67 divided lead**.
Bounded per-stage ULP perturbations are causal reachability diagnostics only.

The following fixed-program families have no direct-frontier survivor:

| Audit | Programs | Scope |
| --- | ---: | --- |
| Consumer reads | 11,664 | Separate retained producers and tail operand reads |
| Split powers | 11,250 | Separate Horner/tail square choices in the stated family |
| Width synthesis | 2,278,125 | CHOP/RN widths 64–70 and exact, three tail orders |
| Quotient carrier | 42,588 | Separate polynomial ratio reads; divided lead fixed |
| Terminal graph | 250,563 | Last Horner multiply/add and tail operation widths |
| Static expression trees | 280,665 + 374,220 | 10,395 canonical trees, fixed operand-port/power policies |

Width synthesis admits 810 programs on the nine singleton targets; all 810
fail the same additional direct control, case ID
`08ce5bff27423f86bc060e645d66aaae874d1ff3` (ratio about 0.00724173858).
`d0010-width-synthesis-counterexamples.json` retains every recipe and its
actual counterexample. The original aggregate report is also preserved.
Other small screens cover signed cuts, control-word-dependent arithmetic,
the standalone-FSIN even/odd tree, and add-producer/consumer combinations.
They are negative bounded screens, not an impossibility proof for FPATAN.

All D0010 artifacts are in `../tmp/fpatan-re/d0010-*.json`. The corresponding
named scripts reproduce the main audits. Small initial screens are retained
as parameterized reports; do not mistake them for exhaustive graph searches.

## D0011: V5 cannot be rescued by changing coefficients alone

`d0011_terminal_preimage.py` inverts the terminal multiplications exactly,
freeing the entire Horner result rather than perturbing it by a few ULPs.
Among 137 distinct unrotated direct `(z, interval)` constraints:

- V5's terminal graph cannot reach nine, for **any** negative 64-bit Horner
  result. V4's corresponding graph cannot reach seven.
- One V5 case cannot be reached for any Horner precision or coefficient bank:
  its required first-product interval contains no 67-bit number.
- The expanded 243 terminal/precision recipes leave 70 with inputwise
  feasible arbitrary Horner values. This is not evidence for a common
  polynomial program.

The strongest single-case certificate is independently reproduced in
`d0011_terminal_certificate.py`, using the original authenticated D0009
capture, not the derived frontier or the model's rounding helpers:

```text
y = 5aeb:d8233ece2695fae0
x = 5af1:f72cbc2401e70d7a
```

All four RC outputs are the same raw value. With `z=CHOP67(y/x)`, the map
`p -> CHOP67(p * CHOP64(z))` jumps from one tail ULP below the required tail
to one tail ULP above it at consecutive 67-bit `p` values. Monotonicity
excludes every other `p`. This is a conditional mathematical obstruction to
that terminal graph, independent of how `p` was produced. It does **not**
prove that the real hardware lead, adder, or retained product has this form.
See `d0011-terminal-certificate.json` for exact rationals and original rows.

## Relaxed feasibility is not a fixed algorithm

`d0011_relaxed_horner.py` retains every reachable exact value while allowing
operation formats to vary freely at every node and separately for every
input. That deliberately enlarged family can exclude fixed programs, but
its local witnesses must never be used as input-conditioned selectors.

With the square fixed to CHOP67(z*z), none of the 70 terminal recipes admits
all inputs even under this relaxation. With square production also relaxed,
only three of 441 terminal recipes admit every input: full-z, CHOP67 products
in the three multiplication orders. Requiring one common square recipe then
leaves only an operand-swap-equivalent pair:

```text
u = RN64(z * CHOP64(z))
tail = CHOP67(CHOP67(z*u) * h)
```

This is an inputwise feasibility discriminator, **not a validated square
law**. The normal RN64 Horner recurrence still fails 31 of 279 direct raw
frontier groups. Fixed uniform (324), split-last-role (104,976), and static
regrouped-polynomial (102,060) programs also all fail.

`d0011_fixed_role_solve.py` uses exact finite-state backwards intersection to
test all 108^5 = 14,693,280,768 independently chosen but globally fixed Horner
role schedules in its stated format family. None satisfies the 137 ratio
groups / 279 direct raw groups. This is symbolic schedule enumeration, not
14 billion hardware observations. The rejection occurs at the final role;
earlier operations cannot remove the following two-point conflict:

| Positive original operands (y; x) | Required final add within this family |
| --- | --- |
| `19ce:8f9f0be97151620e`; `19d4:847382db9ecb02cb` | RN64 |
| `0aae:c26cc1ed8a830b7b`; `0ab3:bf51ece14c3cf311` | CHOP64 |

Each input has four possible earlier h119 carriers under the relaxed graph.
All 18 accepted final-policy variants for the first require RN64; all 18 for
the second require CHOP64. There is no shared last policy.
`d0011_verify_role_certificate.py` independently regenerates these carrier
sets with another integer rounder and authenticates the 16 original signed
RC observations. The conflict persists when C1 is ignored: this is a
numerical-output obstruction, not just a flag interpretation issue.
`d0011-role-output-only-verification.json` retains that independent check.

## Coefficient transfer remains unproven, not disproved in general

The public physical ROM source is P5, not this Skylake CPU. Its arctan
range-reduction identity is described as a hypothesis by the source author.
Neither the source nor a large discovery-set match establishes exact P5→P6
coefficient/schedule transfer. See the original provenance in `HANDOFF.md`.

The terminal gap already rules out coefficient-only repair of V5. Separate
bounded checks also reject a shared A118 change in three feasible fixed-square
terminal graphs. For the asymmetric-RN64-square / cubic-first graph,
`d0011_two_rom_constraints.py` varies A118 on a 69-bit grid over ±16 P5 ULPs
(129 values), inverts A119 without a prior magnitude bound, and asks for one
shared 69-bit A119 while A120–123 remain fixed. No two-constant hypothesis
survives. This does not exclude a different coefficient bank or other graph.

`d0011_auxiliary_audits.py` also retains 390 final-sum CHOP/RN width controls
(64–128 bits on V4, V5 and the MR-square template) and 18 fixed split-square
controls with ordinary RN64 Horner adds. None survives the direct frontier.
These small controls do not exhaust coupled power production or final-adder
semantics.

## Next work and acceptance boundary

Do not mine an RN64/CHOP64 selector from the two-point conflict. The combined
assumptions being tested are incomplete: divided lead, polynomial dataflow,
coefficient transfer, ordinary retained-value representation and final
addition. Investigation must expose a new arithmetic mechanism or independent
provenance, not choose local relaxed witnesses according to the observed miss.
The table-path failure is separate and remains unresolved.

No new hardware campaign is justified by these rejected programs. Reuse the
saved corpus; a genuinely new structural candidate must first pass all nine
jobs, then face a newly frozen, one-shot adversarial challenge. None of these
exclusions supplies the requested general C solution. The goal remains active.

## Local verification

`python3 -m compileall -q fsincos-re/fpatan-re`, `test_d0011.py` (three test
groups, including small-width exhaustive preimage checks and an independent
rounder crosscheck), the arithmetic/protocol selftests, and `git diff --check`
pass. Fresh Clang C11 `-Wall -Wextra -Werror` builds with address/undefined
behavior sanitizers pass both the candidate selftest and library API tests.
The main candidate source is byte-identical to D0009's frozen snapshot.
These build/API checks establish implementation stability, not numerical
closure. Temporary build products are retained in
`/private/tmp/fpatan-d0011-check.XyQrsI/`; no files were deleted.
