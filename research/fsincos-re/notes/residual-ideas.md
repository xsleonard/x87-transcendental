# Ideas for the remaining FSIN/FCOS/FSINCOS residuals

Brainstormed 2026-08-07 against the post-Round-53 state.  Current residual
classes:

- **Standalone FSIN**: 3 result / 4 C1 differences on the frozen h377
  binary64 fixture (unbiased exponents 27, 7, 29).  Structured, dense, and
  h347 corpora are exact.
- **Standalone FCOS**: exact on all promoted corpora, but the hostile
  terminal-adder retained-state sets remain: h363 `2/2`, h372 `8/8`,
  h380 `22/28`, h384 `72/100` output/C1 differences.  Every candidate rule
  "collides on visible state while hardware chooses both outcomes."
- **Paired FSINCOS**: 794 mismatches in 1,182,264 h347 lane/mode
  observations; 515 in 6,000,000 on the balanced h349 scan; 13 structured.
  Attributed to paired state reuse in the later
  cross-product/subtract/final-add sequence.

Ordered roughly by expected information per unit effort.

## 1. Order/history dependence on the collision sets (top priority)

"Hardware chooses both outcomes on identical visible state" has two
explanations: a hidden wire outside the current feature set, or *history* —
microcode scratch state leaking from the previous instruction.  Replays
confirm per-input determinism, but if every capture runs inputs in the same
order, determinism does not rule out predecessor dependence: two colliding
inputs in a batch have different predecessors.

Test: re-capture h363/h372/h380/h384 with input order shuffled, and again
with different priming (FNINIT vs not, a preceding FSIN/FCOS on a different
operand, different stack registers).  If any residual output moves with
context, the paradox dissolves and the hidden state becomes controllable.
If nothing moves, the signal is proven input-determined and upstream of the
current features — which sharpens ideas 3 and 4.

## 2. Unused observables: PE bit, µop counts, RZ

- The exhaustive harness does not yet compare PE.  The precision-exception
  sticky bit is set by internal inexactness and may expose internal sticky
  state that C1 does not — one extra bit per observation, essentially free.
- On Skylake, retired-µop counts around a single serialized FSIN/FCOS are
  measurable with performance counters.  Data-dependent microcode branches
  (extra normalization pass, incrementer carry-out) often execute different
  µop counts; a count correlated with the hidden choice on the collision
  sets is an independent physical label exactly where result bits cannot
  discriminate.  RDTSC latency distributions are the cheap version (the
  capture kit already has bare-metal timing probes).
- RZ is redundant at final rounding (equals RD/RU by sign) but capturing it
  verifies internal operations are RC-independent; any deviation is itself
  a discovery.

## 3. Complete truth tables + exact logic synthesis

For the FCOS terminal adder: pick one colliding configuration, construct
preimages with the exact model that hold the terminal operands fixed while
sweeping upstream discarded bits, and capture the *complete* truth table of
increments-vs-not over that local space (the harness runs ~3M inputs/s, so
2^20-scale local sweeps are minutes).  With a complete table, run SAT- or
espresso-style minimization over candidate physical wires.  Crucially, if
the table is inconsistent with every enumerated wire, that is a *proof* the
discriminator lives outside the feature set (upstream or history), not just
another failed fit.  An SMT encoding of the adder with unknown block
parameters, constrained by all observations at once, yields UNSAT cores
that identify which observations mutually conflict.

## 4. Explicit carry-chain block structure in the terminal FADD

Round 52's rules — "distance ten with payload six," "distance eight with
payload seven" — look like alignment-shifter and carry-lookahead group
boundaries rather than arbitrary predicates.  Parameterize the terminal
FADD as a blocked carry structure (4/8/16-bit groups, unknown phase) where
a carry crossing a specific group boundary under specific alignment is
dropped or resolved late; enumerate that small physically motivated grid.
Ken Shirriff's die-level Pentium FPU photos may show the adder's physical
group structure directly, and the P6 FADD patents (beyond Poon '215) may
state the group width.

## 5. Triangulate the h377 survivors through multiple consumers

FSIN, FCOS, FSINCOS, and FPTAN share N and r from the same reduction but
consume them through different downstream graphs.  Capture all four on the
three surviving h377 inputs (exponents 27, 7, 29) and ±few-ulp neighbors
under all modes; a single unknown perturbation of the reduction state must
simultaneously explain all four observed outputs — interval-intersect
across instructions to pin the exact retained bits.  Also check whether the
exact-division fix resolved FPTAN's four formerly overlapping inputs.
Feeding the pre-reduced residual r directly as a |x| < π/4 argument
separates reduction error from kernel error on the same nominal r.

## 6. Paired-vs-composed diff and cross-lane features

h347 captured hardware FSIN, FCOS, and FSINCOS on the same 197,044 inputs.
Diff the paired lanes against the standalone outputs input-by-input; the
set where paired ≠ composed-standalone directly fingerprints what paired
mode reuses or schedules differently.  Then try predicting sine-lane
residuals from *cosine-lane* trace features and vice versa: if paired mode
shares an FADD carrier or scratch register between lanes, the other lane's
incrementer/sticky state is exactly the kind of hidden input single-lane
feature sets never contain.  Timing FSINCOS against FSIN+FCOS bounds how
much work is actually shared.

## 7. More silicon witnesses (lineage bisection)

Re-running just the residual discriminator sets on the Pentium II box
determines whether the retained-state behavior is original P6 logic (die
photo/patent route applies) or a later re-implementation detail.  Cheap
intermediate generations (P4, Core 2, Ivy Bridge, Atom's independently
designed FPU) bisect where each residual behavior first appears.  The
compiler-free capture kit makes this a hardware-acquisition problem only.

## Status log

- 2026-08-07: file created; beginning with ideas 6 (local h347 analysis),
  1 (shuffle capture on the Skylake box), and 5 (h377 triangulation).
- 2026-08-07, idea 6 executed: compared hardware paired FSINCOS against
  hardware standalone FSIN/FCOS.
  - h347: 0 lane differences over 591,132 observations; paired non-TOP SW
    equals standalone FCOS SW everywhere (C1 tracks the cosine lane).
  - Fresh Skylake captures (this pass) of all three instructions on the
    canonical structured sweep and dense corpora, RN/RD/RU: paired equals
    standalone on **every table-path observation** and differs only on
    polynomial-path inputs (direct and reduced; 266 structured lane/mode
    differences, all classified poly by exact reduction; dense differences
    all in the e=-3 binade, none in the e=-2/-1 table binades).
  - The AMD Zen 3 capture shows paired == standalone on its dense corpus
    too.
  - Conclusion: paired FSINCOS shares the table datapath bit-exactly with
    the standalone instructions; only polynomial behavior is
    paired-specific.  The paired model's 13/515/794 table residue is
    therefore a routing gap, fixed by computing paired table-path lanes
    with the standalone operation-class state
    (`--round54-fsincos-table-lanes`).
  - Caution for future passes: `capture-kit-captures/out/` is the AMD
    Zen 3 capture, not Skylake, and
    `data/sweeps/skylake-xeon-20260715.out.gz` is a Skylake *paired*
    sweep; fresh per-instruction Skylake streams live in the remote
    workdir `fsincos-residual-20260807-1/fresh/`.
- 2026-08-07, Round 54 ported and validated: paired FSINCOS table-path
  lanes routed through the standalone operation-class core.  Zero result
  misses on h347/h349/structured/dense (8,922,492 lane/mode observations;
  baselines 794/515/13/101).  See the Round 54 section of
  `skylake-comparison.md`.  The paired residue is solved; remaining paired
  work is the C1 derivation on polynomial paths.
- 2026-08-07, idea 1 executed: h363/h372/h380/h384 recaptured in reversed
  and two seeded shuffled orders, RN/RD/RU.  Zero per-input differences
  (281,028 inputs x 3 modes x 3 orderings).  FCOS is strictly
  input-determined; history effects are ruled out.  The collision-set
  discriminator must therefore be upstream visible state (ideas 3/4:
  complete truth tables + carry-chain block structure), not order.
- 2026-08-08, paired C1 solved (Round 54 addendum): C1 is the cosine-lane
  rounding-increment flag from the model's directed bounds; exact on all
  4,461,240 comparable paired status observations.
- 2026-08-08, idea 5 executed (h403/h404): FPTAN's 18 large-argument
  residuals are closed by the Round-53 exact-division quotient (zero
  divergence from the seed quotient on all sweep/dense inputs); F2XM1
  signaling-NaN quieting and the FPTAN NaN push rule are represented.
  Triangulating the three surviving h377 FSIN inputs against
  FCOS/FSINCOS/FPTAN proves the shared reduction is consistent and
  localizes all three to the sine producer, each a sub-ulp too high in
  the model, with a strict paired/standalone/model hidden-state ladder at
  exponents 27/29 (internal-cosine polynomial path) and an RN-midpoint
  straddle at exponent 7 (table path).  Findings in
  `fsin-exhaustive-validation.md`; next step is a carrier-interval
  boundary pass seeded with these ladder constraints.
- 2026-08-08, Round 55 (h405-h407): the exponent-7 seed is SOLVED.  Its
  sine-state FADD carries exactly the Round-51 carrier signature
  (diff 14, above-half, retained 0x8c, prefix 0xc1), and the Round-51
  leaf — dead on every promoted corpus since Round 53's exact quotient —
  was flipping it to the non-incremented sum against silicon.  The leaf
  is retired; all corpora remain exact (standalone and paired), and the
  h377 fixture improves to 2 result/3 C1.  Remaining open set:
  the exponent-27/29 internal-cosine seeds plus one window family member
  each (offsets -848/-689), one paired-poly cosine window case
  (+716 at exponent 29), and the FCOS hostile terminal-adder sets.
  Lesson recorded: single-signature empirical leaves fitted from one
  observation family are fragile — the h359 signature matched a second,
  contradictory case 2^16-to-1 against chance; prefer retirement or a
  physically-derived rule when the fitting corpus vanishes.
- 2026-08-08, Round 56 (h408-h410): the exponent-27 seed and both window
  family members are SOLVED by applying the Round-52 terminal cosine
  carrier to FSIN's odd-quadrant internal cosine (shared physical
  kernel).  Two fresh hardware-blind separators confirm; zero corpus
  regression; h377 fixture now 1 result/2 C1.  The one surviving seed
  (exponent 29, RD) shows the same visible-state-collision behavior as
  the FCOS h363/h372/h380/h384 terminal-adder sets — the remaining trig
  work is that single shared retained-carry family (ideas 3/4: complete
  local truth tables + carry-chain block modeling), plus the one paired
  legacy-polynomial window case at exponent-29 offset +716.
- 2026-08-08, h411-h421 characterization of that family (no port): the
  terminal-correction full-state trace has ZERO collision groups — a
  deterministic rule exists; all 104 hostile-set misses are
  payload-valued with support |lane-byte - payload| <= 2 and mixed
  directions; carry-suppressed merge semantics reproduce 76/104 misses
  but break exacts, so the merge is gated by an enabling condition
  invisible in the terminal state; no consistent predicate exists over
  17 fine features.  Next decisive data: idea-3 constructed truth-table
  captures sweeping only upstream discarded bits at one near-collision
  cell, and idea-2 uop/timing side channels on miss-vs-matched pairs.
  See the h411-h421 section of `skylake-comparison.md`.
- 2026-08-08, h422-h424: fresh 541-row hardware-blind informative corpus
  (mirrored to `capture-kit-captures/skylake-fcos-h422/`).  Silicon
  shows at least THREE reachable micro-behaviors at near-collision —
  arithmetic add (181 exclusive rows), carry-suppressed merge (46), and
  lane capture (33; all 27 "neither" rows consistent with payload rising
  to the lane byte) — interleaved within single coarse cells.  The gate
  is not a function of any output-derived feature tried.  Idea 2
  (retired-uop counts / latency on behavior-classified pairs) is now the
  highest-value experiment: it observes the executed path directly.
  The family remains the sole open trig item, shared between the
  exponent-29 FSIN seed and the FCOS hostile sets.
- 2026-08-08, h425: idea 2 executed on the VPS — negative there.  Timing
  is repeatable (all rows ~278 cycles) but class differences were a
  run-order artifact (always interleave classes in one run), and the KVM
  guest exposes no PMU.  The side channel needs BARE METAL: run the
  capture kit's timing/PMU probes on a physical Skylake or the
  Pentium II witness with the h425 class files.  Hardware access is the
  blocking item; everything else (classified corpus, scripts, analysis)
  is ready to go.
