# FSIN/FCOS closure: transfer and architecture coverage audit (h1400)

Date: 2026-09-02

This audit treats a closed-form, bit-exact Skylake emulator as the objective.
Corpus exactness, an operand-keyed overlay, a fitted selector, and a decision
tree are not closure.  R96 remains empirical and incomplete.  The current
ledger-disabled distance is 11 mode/operand rows over ten operands: the nine
R59-selector operands and the separately tracked d0d0 RD/RZ case.

No hardware was executed for h1400.  The new manifests are
`FROZEN_UNOPENED`.  Every proposed operand is absent from repository-visible
text, and all 124 proposed `(instruction, mode, operand)` keys are unique.
The private/supplemental capture ledger must still be merged and checked
locally before any capture; it must not be copied into a report or committed.

## What the existing evidence actually transfers

The following are genuine transfer results already present in the evidence:

1. **The table-path producer transfers among all three trig instructions.**
   h177/h178 observed standalone FSIN equal to the paired sine lane and
   standalone FCOS equal to the paired cosine lane on 160,000 dense table
   operands plus 21,805 table-active sweep operands under RN/RD/RU.  The h178
   reduced cases establish more than a direct-operand coincidence.  Round 62's
   separately frozen reduced-argument lane-boundary blind (N=1..3) further
   supports exact residual bit-slicing after reduction.

2. **The older FCOS terminal response transfers to standalone FSIN's internal
   cosine producer.**  h616 constructed exact M66 inverse images and found
   56,190/56,190 row-level outcome-category agreement between direct FCOS and
   odd-quadrant FSIN under three rounding modes.  This establishes a shared
   standalone cosine terminal behavior, not paired-polynomial equivalence.

3. **The high-q factor state is not an FCOS operand-identity artifact.**
   h1307-h1309 moved the same causal geometry through standalone FSIN and got
   nine one-shot legs over seven operands: three selected the wider factor and
   six the predecessor.  That is a real cross-entry localization result.  It
   predates the R1378 recurrence and cannot by itself be counted as a blind
   validation of R1378.

4. **Finite reduction and result projection transfer broadly in ordinary
   corpora.**  The four-mode suite and the near-k*pi/2 banks exercise many
   signs, quadrants, and exponents.  They strongly constrain numerical output,
   but they do not intentionally hold an internal recurrence state fixed while
   changing instruction, binade, or quotient entry.

The following stronger transfer claims are **not** supported yet:

- **R1158** is directly validated in the lower producer binade by
  51,229/51,229 discovery legs and 2,151/2,151 frozen boundary legs.  Its
  simple upper-binade phase mapping was adversarially rejected (1,088 direct
  errors; the best phase remap still missed about 14,976/37,470).  There is no
  existing R1158-specific FSINCOS or exact reduced-entry blind.
- **R1378** is ledger-free exact on the 398-leg direct union, including the
  independent 28/28 blind, and improves the matched 182,737,480-result
  ledger-off suite by eight rows with zero regressions.  The heterogeneous and
  stage-A exact walls were overlay-on; they are regression walls, not
  ledger-free proof.  No opened bank yet transports the final R1378 recurrence
  itself through paired FSINCOS or multiple exact M66 quotients.
- **The remaining R59 selector** has no closed law.  The 31/31 QX long-run and
  75/75 pre-merge-Q fresh pairs selected the incumbent, so those candidates
  are negative evidence and stay default-off.  R1382 is a useful d0d0
  diagnosis but its 4.29-billion centered scan and 12.8-billion stratified
  scan found no fresh architectural separator; it remains default-off.
- **Paired polynomial equivalence** is not established.  The code deliberately
  uses the shared standalone path only for table inputs and falls back to the
  legacy paired schedule for polynomial/tiny inputs.  Older paired residual
  decorrelation is evidence of schedule state, not permission to declare the
  paired path unknowable or to replace it with a random model.

## Requirement-to-evidence matrix

Status meanings: **covered** = direct opened evidence for the named scope;
**partial** = useful evidence exists but a stated transfer is missing;
**open/frozen** = h1400 has a frozen one-shot test but no label; **open** = no
adequate test/harness yet.

| ID | Requirement | Current evidence | Honest status and uncovered scope | h1400 transfer coverage |
|---|---|---|---|---|
| CORE-01 | Closed finite arithmetic; no operand ledger | R1158 and R1378 are structural recurrences; ledger-off suite has 11 named misses | **Partial.** R96 and the 11 rows prevent closure | Exact unresolved transfers plus explicitly non-isomorphic brackets |
| CORE-02 | R1158 across FSIN/FCOS/FSINCOS | Direct lower-binade FCOS discovery and boundary blind | **Open/frozen.** No instruction/reduction transfer was opened | 13 exact residual states, each through a standalone cosine projection and the corresponding paired lane; all standalone legs are visible R1158-vs-ablation separators |
| CORE-03 | R1158 across external binades, signs, quadrants, N paths | h1162 rejects a simple upper-binade remap | **Open/frozen.** Rejection is not an alternate transfer law | Exact N={1..9,16,17,32,35}, all four quadrants, positive and negative external inputs, external encodings through `3fff..4004` |
| CORE-04 | R1378 across FSIN/FCOS/FSINCOS | 398/398 direct union; 28/28 fresh blind; global eight-fix/no-regression wall | **Open/frozen.** Final recurrence not transported through paired schedule | Five exact points at N={1,3,4,8}; RN/RD/RU; FSIN, FCOS, and paired target lanes; every standalone leg separates R1378 from its ablation |
| CORE-05 | Remaining selector through independent entry paths | h1309 proves earlier high-q causal state transfers to FSIN; current 11 misses remain | **Open.** No closed selector. The later h1404 exact solver finds nonzero-quotient inverse states for cca0, d920, and d0d0; only d920 and d0d0 were in the opened h1400 bank | Seven anchors are globally nonrepresentable in the stated external domain. The already-opened cca0 q=5 pair remains adjacent brackets, while a distinct exact q=892177135061317282 negative-side inverse now exists in analysis only |
| CORE-06 | Exact representability of selector inverse tests | M66 integer construction used by h616 and the exact h1404 QF_BV classification | **Covered as a theorem in the stated domain.** For positive finite normal x87 operands below 2^63, three anchors are SAT and seven are UNSAT under the exact M66 equation | Manifest labels remain historically correct for the operands it froze; h1404 supersedes the earlier global claim that all eight bracketed anchors lacked any exact inverse |
| CORE-07 | Large-argument cancellation | Near-k*pi/2 and hostile corpora; B6 explicitly not exhaustive | **Open/frozen.** No dedicated worst-tail transfer wall | Eight modular-inverse M66 cases in external binades 2^8 through 2^62, with residuals selected before hardware |
| CORE-08 | Independent quotient-entry implementations | Standalone compatibility path uses centered M66 division; paired polynomial fallback uses the 128-bit 2/pi reciprocal | **Partial/frozen.** The exact recurrence and cancellation rows make both quotient computations agree while entering different schedules. When the quotients disagree by one, the M66 residual is at the ±pi/4 table edge, so Round 54's shared-table guard returns before the paired reciprocal path | Five fresh high-binade disagreement operands validate that table short-circuit; they are not mislabeled as polynomial reciprocal-entry tests |
| CORE-09 | Tiny, polynomial, table boundaries | Round 62/63 specials and reduced blinds; older structured/dense corpora | **Partial.** Strong standalone evidence; paired tiny/polynomial transfer is weaker | Exact recurrence states are polynomial; cancellation cases enter tiny/exact-residual paths; table transfer relies on existing h177/h178/R62 evidence |
| ARCH-01 | C2 at `|x| >= 2^63`, input unchanged | Dense FSIN/FCOS edge sweeps, all modes | **Covered for standalone value/C2; open for complete paired stack/status state** | Fresh paired below/at-boundary state snapshots A014-A015 |
| ARCH-02 | Signed zero | Round 63 FSIN/FCOS results | **Covered for standalone values; paired stack/status not isolated.** Only two encodings exist, so a new capture would likely violate the no-repeat rule | No new zero capture; retain existing labels and audit the private tuple ledger before proposing one |
| ARCH-03 | Subnormal and pseudo-denormal | Round 63 FSIN/FCOS value captures, all modes | **Covered for standalone values; open for paired full state** | Fresh paired subnormal and pseudo-denormal A012-A013 |
| ARCH-04 | Infinity, quiet/signaling NaN, unsupported encodings | Round 63 FSIN/FCOS masked responses; 1,408/1,408 invalid-encoding blind | **Covered for standalone values; open for paired flags/stack and exception delivery** | Fresh paired qNaN, sNaN, infinity, and unnormal A008-A011 |
| ARCH-05 | Full exception/status semantics (IE, PE, C0-C3, ES, SF) | Existing scorer checks results and C1/C2; `--status` was captured but PE/IE sequencing was not swept | **Open/frozen for masked sticky state; open for unmasked delivery** | A001-A024 snapshot complete before/after SW, including pre-seeded IE/PE cases |
| ARCH-06 | Stack TOP/tags/deeper-register preservation | Existing value harness loads one operand and pops outputs | **Open/frozen** | Replace semantics at depths 3/5/8; FSINCOS push at depths 4/7; masked full-stack overflow at depth 8 |
| ARCH-07 | Precision-control field | h172: FSIN PC24/53/64 byte-identical over 150,963 lines | **Covered for tested FSIN finite paths; open for FCOS/FSINCOS and specials** | Fresh FCOS and FSINCOS PC24/53/64 triplets A016-A021, using distinct operands to preserve tuple freshness |
| ARCH-08 | All four rounding modes | Full standalone suite uses RN/RD/RU/RZ | **Covered for captured standalone values; full paired/flag state remains partial** | Core and architecture manifests include all four modes |
| ARCH-09 | Exception-mask settings and traps | All current captures use masked exceptions | **Open.** The new state harness intentionally refuses unmasked rows; SIGFPE/ucontext recovery must be designed and frozen separately | None; do not reinterpret masked results as unmasked semantics |

## Frozen manifests

`transfer-tests/h1400/FREEZE.json` is the authority.  It hashes all 15
literal input/manifest files, the three software binaries used to lock
predictions, the three source evidence banks, and the architecture harness.

The 100 core legs are 50 paired transfer points:

| Family | Points | Legs | Purpose |
|---|---:|---:|---|
| `r1158_exact` | 13 | 26 | Exact recurrence transfer; standalone vs paired |
| `r1378_exact` | 5 | 10 | Exact attached-X67/Y64 transfer; standalone vs paired |
| `unresolved_exact` | 3 | 6 | Exact reduced preimages for d920 RN and d0d0 RD/RZ |
| `unresolved_bracket` | 16 | 32 | Lower/upper representable neighbors for eight nonrepresentable R59 anchors; not exact isomorphs |
| `large_cancellation` | 8 | 16 | Distant-binade M66-grid cancellation |
| `quotient_disagreement_guard` | 5 | 10 | High-binade quotient disagreement at which the shared table guard should dominate both paired and standalone lanes |

The architecture manifest adds 24 unique one-shot keys.  Its companion
`capture-kit/x87_state_capture.c` does one target instruction per row and
uses FXSAVE snapshots without popping.  It supports only masked exceptions;
that limitation is enforced, not hidden.

## Capture gate and scoring protocol

Do not open the bank until all of these conditions hold:

1. Verify the literal freeze with
   `python3 experiments/h1400_freeze_transfer_manifests.py --verify`.
2. Privately merge the supplemental/master capture ledger and reject any
   repeated `(instruction, mode, operand)` key.  Do not commit or publish the
   merged ledger or contact material.
3. Copy each `core-inputs/<instruction>_<mode>.txt` to exactly one hardware
   invocation of `x87_capture`, with `--status` allowed but `--timing`
   forbidden.  A failed/partial invocation is not evidence and must not be
   silently retried on already observed tuples.
4. Run `x87_state_capture` once over `architecture-state-inputs.txt`.
5. Score core results with `experiments/h1400_score_transfer_capture.py`.
   The scorer requires exact row counts, refuses to overwrite prior reports,
   and reports paired-vs-standalone transfer separately from
   incumbent-vs-ablation accuracy.

The decisive readout is per family, not a pooled accuracy percentage.  An
R1158 or R1378 law transfers only if the exact standalone separators select
the recurrence and the corresponding paired lanes exhibit the declared
relationship.  Bracket rows can localize a support boundary but cannot close
an odd-low-bit R59 anchor.  Large-cancellation and quotient-disagreement rows
test reduction; they must not be used to refit the terminal selector.

## Remaining work after h1400

- Open h1400 only after the private duplicate audit.  No existing law should
  be promoted or weakened before those labels are scored.
- If paired exact-isomorphs differ from standalone, reconstruct the paired
  polynomial schedule as deterministic finite arithmetic.  The old
  statistical description is evidence about missing state, not a final
  emulator mechanism.
- Build a separate frozen SIGFPE/ucontext experiment for unmasked invalid,
  precision, and stack exceptions.  Do not add those rows to the masked state
  harness.
- The seven globally nonrepresentable selector anchors still require a
  different way to create the same internal state—e.g. a genuinely
  independent microcode entry or a proved state equivalence—not a boundary
  fit to their two brackets.  The opened cca0 q=5 rows remain brackets, but
  h1404 supplies a separate exact high-q negative-side preimage that has not
  been sent to hardware.
- Keep R1382, QX-run, pre-merge-Q, and other speculative mechanisms
  default-off.  The QX and pre-merge-Q campaigns are falsifications, not weak
  positive support.

## Post-opening addendum (2026-09-02)

The frozen bank was subsequently found already opened on the established
bare-metal oracle.  Its 124 rows reconcile exactly with the frozen identities:
100 core legs and 24 architecture rows.  No tuple was recaptured.  The raw
state output has SHA-256
`1d937f8f3775aeecd01fb88cc7277dfb6cba4020ec79c46d341821dd3a2b0c1d`;
the identity manifest has SHA-256
`404770c1db4be96909c23ee1d0b0332a5963ed1a50e196b801180c30330a49df`.
`experiments/h1405_score_single_shot_state.py` (SHA-256
`ce680d7e3711cc111803feb16455ecef8bf37c2b2e24fe99a09831fe2e5becd2`)
records the authoritative score in `h1405b_single_shot_report.txt` (SHA-256
`bc5853a3da8723b5edc2c8f399c12b63376eccc37ce7e8881696ab38bcd21016`).

The core results preserve the claim boundary rather than closing it:

- R1158 is 26/26 exact; its ablation splits 13 exact and 13 miss.
- R1378 is 10/10 exact; its ablation splits 5 exact and 5 miss.
- Large-cancellation, quotient-disagreement, and unresolved-bracket legs are
  16/16, 10/10, and 32/32 exact under the incumbent.
- The three exact unresolved legs all miss the incumbent, as expected.  The
  d920 inverse reproduces the anomalous endpoint through standalone FSIN but
  not through paired FSINCOS, localizing that endpoint choice to the
  standalone cosine schedule rather than proving a cross-schedule selector.
  The d0d0 inverse reaches its anchor in both standalone FCOS and paired
  FSINCOS; this is localization evidence, not a general law.

All 24 declared post-instruction architecture relations pass.  Three intended
pre-existing-PE checks (A002, A005, and A024) are invalid because the original
AT&T `fdivp` seed loaded its operands in the wrong order and computed the exact
value 3/1.  The harness load order is corrected for any future distinct
campaign, but these three frozen observations are not retroactively relabeled
or repeated.  The corrected harness has SHA-256
`1b2df713deeb44576169c7f75e86a1365f92b6315da284280e8c76437588980b`.

Accordingly, the historical `FROZEN_UNOPENED` labels above describe the state
at freeze time only.  The bank is now opened, immutable evidence.  It confirms
the scoped R1158/R1378 transfers and schedule localization, but it leaves the
ledger-free frontier at 11 rows over ten operands and supplies no new selector.

## Exact-preimage correction (h1404, reconciled 2026-09-03)

The earlier global statement that eight unresolved anchors had no exact
nonzero-quotient inverse was too strong.  The exact finite-domain constraint

```text
sig << (se - 0x3ffc) = 2*q*M66 +/- residual, q > 0
```

is SAT for cca0, d920, and d0d0, and UNSAT for the other seven anchors over
positive finite normal x87 operands below 2^63.  The cca0 witness is
`403b 9b96fed99478343c`, q=892177135061317282, side=-1.  This does not relabel
or replace the already-opened q=5 cca0 bracket rows; it corrects the theorem's
scope and provides a new analysis-only exact inverse.

The original interpretation of the d920 q=0/q=1 pair was corrected by H1412.
The apparent RN split in the current C model is the default-on R84 literal
operand ledger overwriting direct FCOS after the common arithmetic pipeline;
it is not caused by consuming the M66 reduction carry. With `G_ROUND84=0`,
the direct FCOS anchor and its q=1 FSIN preimage agree in all four modes and
through `DI_FIN`, excluding the ASLR-dependent address token. Neither
`sky_reduce_rc` nor `wv_from_rc` retains quotient/carry history. The differing
carry is therefore `correlated_not_consumed`, only a silicon hypothesis, and
this pair does not prove the exposed post-reduction selector coordinates
insufficient. No hardware was run for H1404 and no new tuple was frozen.

The correction's authority is `notes/h1412-reduction-collision-causal-audit.json`,
SHA-256 `27604f15e62f095d81d6a9ba88419bbe3c5a7db8885957ea76f63df20fd65039`.
H1408 and all original SAT/UNSAT/UNKNOWN artifacts are unchanged. H1571 later
adds 24/24 fresh ledger-off exact-preimage hardware transfers, consistent with
the corrected interpretation, not a resurrected carry64 law.

The complete proof artifacts and the independently bounded d0d0
second-witness result are documented in `notes/h1404-exact-preimage-smt.md`.
After excluding d0d0, both Z3 and CVC5 reached 300-second bounds, so that query
is UNKNOWN, not UNSAT.
