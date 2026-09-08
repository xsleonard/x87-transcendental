# fsincos-re — reverse-engineering the Intel x87 FSINCOS

Current suite delivery (2026-09-06): all eight transcendental instructions
have executable models. The new [FYL2X/FYL2XP1 implementation](fyl2x-re/README.md)
provides a C API, exact pseudocode and [validated evidence](fyl2x-re/ACCEPTANCE.md).
Read the [root programmer README](../README.md) and
[unified manuscript](paper/README.md) for the current release. The research
history below is preserved, including older scope and completion statements.

September 7 update: the verified F2XM1 subnormal-rounding correction is
integrated in the C model and exact reference. It rounds the tiny-path
product directly to raw80; the polynomial and constants are unchanged.
See the [integration record](paper/evidence/f2xm1-integration.json) and
[storage-boundary review](docs/verification-expansion/rounding-boundary-audit.md).

For the current suite and programmer entry points, start with the
[library README](../../README.md), [programmer guide](docs/PROGRAMMER-GUIDE.md)
and [suite algorithm guide](docs/ALGORITHMS.md).

## Current algorithm and programmer's pseudocode

The default Skylake implementation now uses the validated general numerical
programs for standalone `FSIN`/`FCOS` and paired `FSINCOS`. Start with the
[programmer's pseudocode in the repository README](../README.md#programmers-pseudocode)
or Appendix A of the [LaTeX paper](paper/skylake-x87.tex).
The [paper status](paper/README.md) records the H1708/H1717 validation and
evidence limits. The earlier models and mismatch counts below are historical.

## Historical outcome and research chronology

Two independent, portable, host-FP-free reconstructions of Intel
`FSIN`/`FCOS`/`FSINCOS`, plus the empirical findings that connect them:

### 1. `src/fsincos_itanium.c` — FROZEN bit-exact reference
The Itanium IA-32-compat / double-extended-libm algorithm (Harrison,
FMCAD 2000).  The "lost" Intel assembly source was found intact in glibc's
ia64 port (`data/glibc-ia64-fpu/`, preserved from glibc-2.38 — removed
upstream in 2.39) and transcribed op-for-op onto a soft IA-64 arithmetic
engine (`src/ia64_sf.h`, verified against exact rational arithmetic on 11k
vectors).  Every constant the literature called unpublished is in
`data/constants-decoded.md`.  Verification statement in the file header.

### 2. `src/fsincos_skylake.c` — behavioral model of modern Intel silicon
The historical no-flag baseline is **99.360% bit-exact against Skylake
FSINCOS over a 50k structured sweep**.  The independently validated
Round-18 polynomial refinement raises that to **99.470%** with
`--round18-poly` (zero gross mismatches; every miss is 1 ulp on one output).
Adding the Round-21 paired-tomography table-state refinement raises it to
**99.610%** with `--round18-poly --round21-table-bias` after extending the
validated Pentium polynomial path through the small region.  The Round-29
refinement reaches **99.660%** (49,868/50,038 exact) with:

```text
--round18-poly --round21-table-bias
--round23-narrow-coefficient --round24-table-delta-rn67
--round29-p5-fmul-route
```

The Round-37 four-term refinement reaches **99.906%**
(49,991/50,038 exact); all 47 remaining differences are one-ulp cases.
The numerical algorithm:

- **Range reduction** (proven bit-exact on 3971/3971 + 3467/3467 probes):
  `r+c = x − N·trunc66(π/2)` — the famous "66-bit internal π", computed as
  an exact wide difference, `N = nearest(x·2/π)`; identical for the whole
  range π/4 ≤ |x| < 2^63.  `|x| ≥ 2^63` sets C2 (operand unchanged).
- **Kernel = the 1993 Pentium FPU algorithm, still running today**:
  - |r| < 1/4: the Pentium ROM 6-term sin/cos polynomials.  Random inputs
    below 2^-3 happen to coincide with the Itanium small kernel, but four
    boundary/deep discriminators prove that silicon retains the Pentium
    evaluation path through at least exponent -32;
  - 1/4 ≤ |r| ≤ π/4: table reconstruction
    `sin(b+a) = sinT·cos(a) + cosT·sin(a)` with bit-dispatched cells
    (b ∈ {18,22,26,30}/64 narrow, {36,44,52}/64 wide).  The model uses the same four-term FPROM polynomials for every cell and a
    **wide-fused combine**; the earlier six-term wide model was an effective
    black-box proxy for this operation graph.
  - Table/polynomial constants from Ken Shirriff's 2025 physical decode of
    the Pentium constant ROM (`data/pentium-rom/`), including **two
    silicon-verified single-bit corrections to the published appendix**
    (`notes/rom-errata.md`).

### Headline findings
- The Skylake FSINCOS model combines the Pentium (1993)
  table+polynomial kernel with the documented 66-bit-π reduction.
  Intel's formally-verified
  replacement (Itanium, 2000) never displaced it in x86 silicon.  Their
  small-input outputs usually coincide, but targeted boundary inputs now
  distinguish them and select the Pentium path.
- The published Pentium ROM appendix contains two single-bit hex
  transcription errors, recoverable from Skylake behavior alone.
- The Round-16 RN/RD/RU constraint pass found a validated four-term narrow
  table-tail improvement.  Round 17 resolved its remaining width class:
  `m=RN69(P*a²)`, `u=chop68(1+m)`, `S=RN64(a*u)`,
  `t=chop66(Q*a²)`.  The explicit 66/68/69-bit implementation is available
  in `src/fsincos_skylake.c` as `--round16-narrow`; the old model remains the
  no-flag baseline for controlled comparisons.
- Rounds 18 and 20 identify the six-term polynomial datapath:
  `a²=chop67(a·a)`, native 67-bit ROM constants, and fused RN64 Horner
  steps, with the final cosine-Horner product materialized as
  `chop67(q·a²)` before adding C1.  Its output-specific finals reduce a
  fresh 2,000-input model-selected discriminator from 2,692 directed-mode
  misses to zero out of 12,000.  Two independent 64-input discriminator
  captures also score zero.  The exact-integer C port is available as
  `--round18-poly`.
- Round 19 tests transfer of that producer into the wide table kernel.
  Only the cosine-polynomial (`q`) chain survives cross-validation: it
  improves the complete direct-table, h59, and h67 RN/RD/RU evidence, but
  loses one whole-input match on the generic RN master sweep.  It therefore
  remains an explicit experiment as `--round19-wide-q`, not a default
  refinement.
- Round 21 pairs one exactly represented residual across every table cell in
  its polynomial family.  Exact RN/RD/RU inequality intersections localize
  the systematic error to the shared `S=sin(a)` state, not `U=1+t`.
  Family corrections of 4/32 and 5/32 local S ulp toward zero improve every
  dense/targeted validation family and remove 60 net failures from the master
  sweep.  The exact C state representation is available as
  `--round21-table-bias`; the still-unknown item is the physical producer
  operation that creates those low state bits.
- Rounds 22–24 close two more structural gaps.  h83/h85/h87/h89 prove the
  six-term Pentium path below 2^-3 (11,304/11,304 C/Python output-mode
  checks).  h97/h107 support an explicit +7168 equivalent correction to the
  narrow row-169 coefficient under `--round23-narrow-coefficient`; it is not
  claimed as a ROM erratum.  Final-partial search identifies the plausible
  shared operation
  `T1 + RN67(T1*t ± T2*S)`, ported as
  `--round24-table-delta-rn67`.  It improves every selected and complete
  validation family and removes 18 more master failures.  Exact C/Python
  parity covers 581,505 table results under RN/RD/RU.
- h108 independently probes the exact 65-bit reduced-residual path.  Its
  fresh Skylake separators reject the much better-looking master-only
  direct/reduced bias split, so that split is not ported; the robust model
  remains at 170 one-ulp table cases rather than claiming an overfit gain.
- Round 28 tests Tang's literal published reconstruction
  `Sj + r*Cj + (Sj*q+Cj*p)`.  Uniform materializations fail validation, but
  independently materializing the narrow `Cj*p` product away from zero at
  64 bits improves standalone dense mode/input misses by one, improves the
  independent Pentium-II dense FSINCOS capture by one, and leaves the master
  unchanged.  Exact C/Python parity covers 271,278 narrow table results;
  the port is selected by `--round28-tang-narrow`.  A wide `Sj*q=odd67`
  candidate is rejected because it regresses the master.
- Round 29 maps that narrow product onto the documented asymmetric P5
  multiplier: direct `p->X67,Cj->Y64,RU64`, reduced
  `Cj->X67,p->Y64,RD64`.  A fresh five-input Skylake discriminator improves
  from 5 to 2 mode misses; complete narrow coverage improves by one with
  exact C/Python parity and no master regression.  The port is
  `--round29-p5-fmul-route`.
- Round 30 resolves one piece of FSIN's odd-quadrant internal-cosine
  producer.  Its square keeps 68 bits in the lower P5 FMUL normalization
  case and 67 bits in the upper case.  Two new hardware-blind captures
  validate the split; the full standalone sweep improves by two mode results.
  The port is `--round30-fsin-cosine-square`.
- Round 31 independently validates a conditional low-bit materialization
  of the same producer's final polynomial product: retain chop71 when the
  exact product's 72-bit low retained bit is one, otherwise retain away72.
  It improves all three fresh internal-cosine captures without changing or
  regressing the old full sweep.  The port is
  `--round31-fsin-cosine-tail`.
- Round 32 uses a second hardware-blind capture to validate the preceding
  Horner edge: retain a chop65 fifth sum in the low product-normalization
  case when sticky is nonzero.  It removes two old full-sweep mode/input
  misses and is ported as `--round32-fsin-cosine-horner`.
- Round 33 rejects a post-hoc extension of that sum rule, then uses a new
  hardware-blind product discriminator to localize the secondary low-bit
  signal one operation earlier.  A conditional sticky-preserving 67-bit
  fifth-product carrier improves both fresh captures without changing the
  old sweep and is ported as `--round33-fsin-cosine-product`.  A 30-million
  input constructive width scan finds one architectural separator; Skylake
  rejects 72-bit RN while the 67-bit carrier and exact state remain tied.
- A post-Round-33 tomography/operation pass confirms the remaining 44
  affected internal-cosine inputs need mixed corrections.  A fresh
  six-mechanism h168 capture rejects every adjacent one-operation,
  two-predicate candidate componentwise; none is ported.
- A separate h169-h171 table pass localizes the 226 affected table inputs to
  small mixed-direction offsets around the RN67 reconstruction carrier.
  Fresh separators reject all six surviving conditional final-correction
  widths, so no table rule is ported; operation order and carrier-selection
  gates remain.
- h172 verifies that PC24, PC53, and PC64 produce byte-identical standalone
  FSIN values and status on the structured sweep and h171 separators.
  Architectural precision control cannot expose the hidden carrier.
- h173-h176 test 1,183 Tang/FADD addition schedules globally and behind
  structural direct/reduced, narrow/wide, and lane gates.  A fresh
  243-input capture falsifies every survivor under complete cross-validation;
  no alternate FADD topology is ported.
- h177-h183 prove the table values are shared exactly across
  FSIN/FCOS/FSINCOS, then use both lanes to constrain the P/Q producer.
  The remaining joint errors are balanced between P-like and Q-like state;
  every individual wide-Q Horner edge and terminal producer candidate is
  rejected, including a fresh two-lane carrier capture.
- h184-h186 complete the lookup/FIRC low-bit pass.  A fresh 38-input
  two-lane capture selects RN64 materialization of the ROM constant before
  the wide `cross*p` product.  Round 34 ports it and removes two dense sine
  mode/input misses without changing the structured sweep headline.
- h187 rejects all nine complete-corpus profiles produced by a bounded
  one-P-edge/one-Q-edge coordinated search.  The remaining multi-edge target
  is a stage-local coefficient/product/sum schedule whose individual pieces
  can be architecturally latent.
- h188-h190 find and validate that latent schedule at the terminal wide-P
  stage.  A fresh 37-input pairwise capture selects away64 materialization
  of the last coefficient followed by a chopped 65-bit sum.  Round 35 ports
  only that P route and improves the complete standalone-sine and paired-
  cosine metrics without changing the structured sweep.
- h191-h192 apply the same full 64..72-bit pair grid to the immediately
  preceding P and Q stages.  All 7,920 schedules fail the first
  componentwise joint-lane gate.  The Round-35 mechanism is terminal-
  specific on current evidence; no further route or capture is promoted.
- h193-h195 complete the higher-payoff global residual pass.  The 323
  outside wide-sweep joint states have 28 correction signatures at the
  coarse 2^-67 scale, no dominant P/Q axis, and no useful train/held
  physical predicate.  Of 1,378 propagated single-site counterfactuals,
  three improve the complete sweep; all three and their combinations fail
  the 80,000-point dense gate.  No global operation, C change, or fresh
  capture is promoted; remaining table work is coordinated multi-stage
  schedule recovery.
- h196-h198 finish the stage-local fallback.  Exact Round-35 replay now
  supports every nonterminal P/Q stage; all 31,680 two-operation schedules
  across stages 1--4 fail the first joint-lane gate.  Across all 39,600
  stage-local schedules including h188's terminal grid, the only survivor
  is the already-ported terminal-P route.  The next justified family is an
  adjacent sum-carrier/product-consumer pair across a stage boundary.
- h199 closes that adjacent family: all eight P/Q boundaries reject all
  10,656 sum(k)/product(k+1) schedules at the first componentwise gate.
  In total, 50,256 physically local two-edge schedules have been tested;
  Round 35 remains the only survivor.  Higher-order triples and arbitrary
  nonadjacent pairs are not evidence-driven next steps.
- h200-h205 replace the polynomial-producer FADD representatives with the P5
  patent's explicit 68-bit alignment, subtraction, normalization, and sticky
  carrier.
  All measured Horner additions use its unlike-sign far path.  Four bounded
  readings of the separate shifted-mantissa/sticky wires are tested globally,
  behind direct/reduced gates, in the internal-cosine polynomial, and in a
  coherent FMUL/FADD route grid.  h205 additionally separates FRND's
  normalization-on/rounding-off and normalization-off/rounding-off controls.
  Several reduce aggregate misses, but every one regresses an independent
  lane, half, or focused capture; no literal carrier profile survives and no
  C rule is ported.
- h206-h210 complete the end-to-end literal pass that h200-h205 did not
  cover.  h206 adds like-sign addition, near subtraction, overflow, arbitrary
  cancellation normalization, and explicit FADD J/GRS to FMUL X67 routing.
  h207 replays all three additions in all seven Tang reconstruction trees;
  all 16,128 schedules fail the componentwise sample gate.  h208's explicit
  producer-to-FMUL grid leaves 409 sample survivors in 40 profiles, but none
  passes the complete sweep.  h209 crosses those profiles with 20,160
  coherent full-reconstruction schedules and again finds zero sample
  survivors.  h210 reference-checks all FADD paths in 50,000 exact cases.
  Literal FADD/FIRC sequencing is now a strong negative result, not a C-model
  improvement.
- h211-h225 test data-dependent FIRC microcontrol rather than another fixed
  schedule.  All 34,560 unconditional four-term programs are closed; an
  arbitrary fixed-`jam-sub` lane selector can nevertheless reach every
  measured residual.  Complete/fresh CEGIS and h216 select one physical leaf:
  after `linear+p`, exponent distance 14, raw exponent phase zero modulo four,
  and FAMUBUS bit 3 select odd64 for that first result followed by odd67 adds.
  Round 36 ports the leaf as `--round36-table-fadd-microcontrol`.  Exact
  C/Python parity covers 7,056 results on all 588 complete-corpus base states.
  Full Debian dense/sweep replay changes only one paired dense RD line and one
  paired dense RU line.
  Complete paired-cosine mode/input/C1 misses improve
  1,514/1,303/805 -> 1,512/1,302/804; the structured sweep is unchanged.
  Three later hardware-blind captures (h221/h223/h224, 190 total inputs)
  exhaust the surviving sibling decision-tree branches: every proposed
  second leaf ultimately regresses fresh Skylake data.  h225 finds no
  carry/borrow/sticky alias for bit 3 beyond the exact bus representation
  identity `normalized X2 bit 4 = FAMUBUS bit 3`.
- Full experiment log: `notes/skylake-comparison.md` (rounds 1–37);
  falsification-tested against dense 240k RN/RD/RU rounding-mode captures.

### 3. Standalone FSIN sibling path

The Skylake model now has a separately implemented and validated
single-output `--fsin-standalone` path.  Pentium II and Skylake RN outputs are identical
on all 240,000 dense inputs; new Skylake RN/RD/RU status captures constrain
three distinct polynomial entries: direct sine, reduced-entry sine, and the
odd-quadrant internal cosine producer.  The 50,038-input directed sweep is
bit-exact in 149,784/150,114 mode results (330 one-ulp misses), with 280
inputs differing.  Of those misses, 74 are polynomial cases and 256 are the
already-unresolved shared FSINCOS table cases; the recovered tiny-input rule
is exact.  h135 additionally resolves a standalone table-carrier detail:
direct narrow/wide P terminal coefficients use chop64/away64, while the wide
Q terminal coefficient uses away64 on both direct and reduced entry.  Fresh
Skylake separators validate the path split; it removes seven dense mode
misses and five dense input misses.  Round 28's Tang grouping and Round 29's
physical X67/Y64 route each remove one more dense mode/input miss.  Round 30
then removes two internal-cosine mode misses and one affected input.  Round
31 leaves that historical sweep unchanged while improving three independent
fresh internal-cosine captures.  Round 32 then removes two old
internal-cosine mode/input misses.  Round 33 leaves the historical sweep
unchanged but improves h161 from 186 to 184 mode misses and the independent
h163 product capture from 27 to 14.
Round 34 leaves the historical structured sweep unchanged while improving
the complete dense wide-table sine score by two modes/inputs and the fresh
h185 paired cosine score from 13/12/11 to 7/6/1 mode/input/C1 misses.
Round 35 also leaves the structured sweep at 330/280.  On the complete
wide-table corpus it improves standalone sine from 1,515/1,309/828 to
1,513/1,308/827 and paired cosine from 1,515/1,304/807 to
1,514/1,303/805 mode/input/C1 misses.  On the fresh h189 standalone subset
the improvement is 21/12/13 to 12/7/7.
Round 36 again leaves the structured sweep at 330/280, but improves complete
paired-cosine mode/input/C1 misses from 1,514/1,303/805 to
1,512/1,302/804.  Its independent h216 standalone-FSIN score improves from
8/5/3 to 4/3/1.  The complete literal grammar can reach every remaining
measured table lane conditionally, but h221-h224 reject every tested second
microcontrol leaf; only the h216-selected bit-3 leaf is ported.
Round 37 replaces the empirical wide six-term producer with the
four-term graph and its adjusted highest-degree sine coefficient.  It also
uses the complete shared `sin(a)` state in the two table products, for both
narrow and wide cells.
h230 tests the
`a*a` operation with a chopped 67-bit carrier, plus two smaller
sine-side retained carriers.  Exact C/Python parity covers 1,090,830
lane/mode results.  On the 50,038-input FSIN sweep this reduces the remaining
differences from 330/280 to 126 mode results on 106 inputs, all by one ulp.
The standalone-FCOS dense score improves from 3,678 to 2,540 mode misses;
its 2,161 direct-polynomial misses are unchanged, while other misses fall
from 1,517 to 379.  The paired FSINCOS RN master improves from 49,868 to
49,991 exact inputs.
Round 38 then evaluates standalone FCOS's six-term polynomial in the two
interleaved chains of the model.  It reduces the dense FCOS
score from 2,540 to 769 mode misses and from 1,919 to 764 affected inputs;
the direct-polynomial component falls from 2,161 to 390.
Round 39 adds standalone FCOS's captured tiny-input directed-rounding rule.
On the independent 50,038-input sweep it removes 1,289 further mode misses
without regression, leaving 89 mode misses on 84 inputs.
Round 40 applies the corresponding captured tiny rules to both lanes of
paired FSINCOS.  Across RN/RD/RU it removes 2,578 lane/mode misses without
regression, leaving 110 misses on 110 inputs; every remaining paired sweep
miss is in a table path.
Round 41 reuses the two-chain cosine graph for standalone FSIN's odd-quadrant
internal cosine.  Independent boundary fitting reduces that class from 62 to
10 mode misses and the complete FSIN sweep from 126 misses on 106 inputs to 74
on 72 inputs.
Round 42 evaluates standalone sine-producing polynomial paths as two
interleaved chains.  It is exact on all 278,946 promoted FSIN/FCOS observations
and leaves the structured sweeps at 62/62 FSIN and 74/74 FCOS mode/input
misses.  Paired FSINCOS retains its separate, already-exact polynomial path.
The h243 table-wire pass then proves the existing eight cell addresses,
midpoint anchors, and residuals on all 181,805 table-path observations and
independently regenerates every lookup value as RN67 `sin(b)` or `cos(b)`.
No table-selection or lookup-word correction remains.
The h245--h276 sibling pass adds compiler-free FPTAN/F2XM1 capture.  F2XM1's
shared chop67 multiply rule reveals that FPTAN must read its 69-bit complete
sine carrier through an RN64 input materialization.  With chop67 reconstruction
multiplies and subtractions, the FPTAN table path falls from 23,667 mode misses
to four on two inputs.  A one-million-input follow-up finds five more rare
residuals and localizes all seven to the shared P/Q state producer.  Applying
the same chop67 ordinary-FMUL class to its Horner and terminal products closes
all seven, the complete dense table set, and the structured sweep.  The
transferred six-term polynomial graph plus the
independently selected exponent -69 tiny bypass is exact on all 108,231
polynomial inputs.  The C `--fptan` path has zero result misses over 870,114
dense/sweep RN/RD/RU comparisons and zero over the one-million-input RD scan.
See
`notes/fptan-reconstruction.md`.
The Debian GCC build passes selftest and exactly replays the saved Skylake
streams.
The h251--h259 F2XM1 pass is complete: a linear/long-polynomial/table graph,
uniform chop67 FMUL plus RN64 FADD and multiply-class operations, and the
exponent -68 path boundary match all existing and fresh RN/RD/RU results and
C1 observations.  The C port has 0 misses over 915,162 result comparisons and
passes a fresh Debian/Skylake replay.  See `notes/f2xm1-reconstruction.md`.

A later deterministic `2^24` binary64-space trial initially found F2XM1
missing signaling-NaN quieting and FPTAN missing 25 results/18 C1 on 18
large arguments plus the special-value push rule.  The h403 pass closes all
three classes: FPTAN now uses the same literal exact-division quotient as
the Round-53 operation-class reduction (the reciprocal seed diverges from
it on none of the sweep/dense inputs and on exactly the failing large-
argument class), F2XM1 quiets signaling NaNs, and NaN/indefinite FPTAN
results push a copy of the result.  Re-run `2^24` and full `2^32`
traversals are completely clean for both instructions — zero output, C1,
C2, pushed-value, or interval differences, the `2^32` runs covering
12,884,901,888 RN/RD/RU observations each.  See
`notes/sibling-exhaustive-validation.md`.

The subsequent F2XM1 `2^32` extension has zero result or C1 differences over
6,436,293,432 documented-range RN/RD/RU observations. All 3,134,754 aggregate
differences are exactly the 1,044,918 sampled signaling NaNs under three modes;
there is no second residual class.

The h277--h324 carrier pass then returns to the remaining trig table residue.
A scalar operation-class completion and an unconditional literal final FADD
are rejected.  Propagated unit tests instead trace 719 of 730 frozen residual
lanes through the complete shared-sine state.  Rounds 43--48 replace the old
single wide/narrow sub-ulp proxies at five representation-independent
residual-exponent/FADD-alignment coordinates.  Six hardware-blind Skylake
captures independently validate the wide direct/reduced and narrow leaves,
including their fractional 1/256-ulp boundaries.  C/Python parity is exact on
1,094,382 lane/mode checks, and the structured master counts improve from
62/74/110 to 49/57/80 for FSIN/FCOS/FSINCOS.

h325--h345 collapse those fitted fractions into one carrier-interval rule.
Every proxy materializes as `RN64<<3 - 1`; treating the low suffix as an open
producer-to-FMUL interval reduces the dense paired objective from 632/377/627
to 101/63/96 and the structured paired residue from 80 to 13 without
component regression.  The three independent narrow discriminator captures
become exact for results and C1.  Round 49 has exact C/Python parity on
1,094,382 lane/mode checks and leaves structured FSIN/FCOS/FSINCOS totals of
15/24/13.  Only 5 sine and 8 cosine paired table lanes remain; follow-up
operation-class, Q-producer, exact-carrier, and literal-FADD tests show that
they are rare retained carry/borrow effects rather than another polynomial or
lookup-table error.

h346--h359 add an adversarial 197,044-input residual-neighborhood capture and
a balanced one-million-input paired scan, then execute the finite
standalone-FSIN operation graph instead of fitting its stages independently.
Round 50 uses chop67 ordinary multiply/subtract, RN64 ordinary add and
multiply-class operations, and architectural rounding only at final
writeback. Round 51 isolates one rarer non-incrementing sine-state addition
by its retained-bit signature. The C standalone-FSIN result now has zero
misses in 1,461,246 RN/RD/RU observations spanning the structured, dense, and
new focused validation corpora. Directed-bound C1 reconstruction also has
zero differences on those 1,461,246 saved status observations. This is exact
result/status parity on those Skylake corpora, not a claim that every hidden
adder state or P6 revision is proved. A later deterministic `2^24`
binary64-space trial finds 12 one-step result differences and 15 C1
differences in 50,331,648 RN/RD/RU observations, with no C2 or interval
failures. Standalone FSIN is therefore original-corpus-exact, not universally
solved. The native hardware/model comparator, independent replay check, and
trial record are documented in `notes/fsin-exhaustive-validation.md`.

The same Round-51 sine state is shared with paired FSINCOS. It fixes four
focused paired residuals without regressions, changing the adversarial score
from 798 to 794 misses in 1,182,264 lane/mode observations. It does not fire
in the balanced million-input scan, which remains at 515 misses in 6,000,000
observations.

Round 54 closes that paired residue.  Direct hardware-vs-hardware
comparison of per-instruction Skylake captures (saved h347 plus fresh
structured-sweep and dense streams for all three instructions) proves that
paired FSINCOS shares the table datapath bit-exactly with the standalone
instructions and differs only on polynomial-path inputs.  The paired table
residue was therefore a model routing gap:
`--round54-fsincos-table-lanes` computes each paired lane's table-path
input as its standalone instruction (Rounds 50/53) while polynomial and
tiny inputs keep the legacy paired model.  The paired model now has zero
result misses on all four Skylake corpora — h347, h349, the structured
sweep, and the dense corpus — 8,922,492 lane/mode observations in total,
versus 794/515/13/101 baseline misses.  Paired C1 is the cosine-lane
(last-pushed) rounding-increment flag derived from the model's directed
bounds; the rule has zero differences on all 4,461,240 comparable paired
status observations.

Run the model with:

```text
--fsin-standalone --round18-poly --round21-table-bias
--round23-narrow-coefficient --round24-table-delta-rn67
--round29-p5-fmul-route --round30-fsin-cosine-square
--round31-fsin-cosine-tail
--round32-fsin-cosine-horner
--round33-fsin-cosine-product
--round34-table-lookup-firc
--round35-table-p-terminal
--round36-table-fadd-microcontrol
--round37-p6-four-term
--round41-fsin-cosine-split
--round42-p6-sine-split
--round43-p6-sine-bias
--round44-p6-sine-bias
--round45-p6-sine-fraction
--round46-p6-narrow-sine-fraction
--round47-p6-narrow-sine-fraction
--round48-p6-narrow-sine-fraction
--round49-p6-carrier-interval
--round50-fsin-operation-classes
--round51-fsin-fadd-signature
```

Round 55 (h405-h407) retires the Round-51 signature leaf: it was dead on
every promoted corpus after Round 53's exact-division quotient and
misfired on one of the three remaining h377 inputs, whose sine-state FADD
carries the identical carrier signature but keeps the ordinary RN64
result on silicon.  The flag is still accepted but inert in the
operation-class path; the retired-leaf source is exact on every corpus
(h347, h349, structured, dense; standalone and paired) and the h377
fixture improves to 2 result/3 C1 differences, both remaining inputs
being reduced odd-quadrant internal-cosine polynomial cases.

Round 56 (h408-h410) then applies the Round-52 terminal cosine carrier to
FSIN's odd-quadrant internal cosine — the same physical kernel.  Add
`--round56-fsin-cosine-carrier` to the standalone-FSIN flags.  It fixes
the exponent-27 seed and both window family members, and both fresh
hardware-blind h409 separators, with zero corpus regression.  The h377
fixture now scores 1 result/2 C1: the single remaining input
(`c01c:ccb8a935dddf4000`, exponent 29) belongs to the same rare
retained-carry collision family as the outstanding FCOS terminal-adder
sets, unifying the two open problems into one.

Rounds 50 and 51 affect standalone FSIN. Round 51 also selects the same
shared sine-state behavior in paired FSINCOS when Round 37 is enabled.

For standalone FCOS, use `--fcos-standalone` in place of
`--fsin-standalone`, then add `--round38-p6-cosine-split` and
`--round39-fcos-tiny --round42-p6-sine-split`.
For paired FSINCOS, add `--round40-fsincos-tiny
--round38-p6-cosine-split --round53-fcos-operation-classes
--round54-fsincos-table-lanes`.
Use `--f2xm1` or `--fptan` for the reconstructed sibling instruction entry
points; they do not require the numbered FSIN/FCOS compatibility flags.

The direct and reduced operation graphs, validation splits, rejected
alternatives, and reproduction commands are in
`notes/fsin-reconstruction.md`.  The capture kit includes a compiler-free
static i686/x86-64 standalone runner with instruction-local status, full
sweep, tiny-boundary, and bare-metal timing probes.

## Layout

- `src/` — both implementations, shared engine, capture harness
  (`x87_capture.c`), sweep/compare tooling, tests (`make test`).
- `experiments/` — the hypothesis-testing scripts (h1..h324), kept as the
  audit trail of how each conclusion was reached.
- `notes/` — algorithm spec, op-level extraction of the Itanium assembly,
  the Skylake comparison log, ROM errata.
- `data/` — preserved Intel sources (glibc ia64), Pentium ROM decode,
  decoded constants, papers, archived silicon captures (`sweeps/`).

## Hardware ground truth

Intel Xeon Skylake (`GenuineIntel`), captures under RN/RD/RU rounding
modes via `src/x87_capture.c` (CW-pinned), plus AMD Zen 3 and Pentium II
Deschutes capture-kit witnesses.  Pentium II and Skylake are byte-identical
on 1,250,038 existing instruction executions.  The capture kit includes the
h59 narrow survivor, h62 width, h65/h71/h74 polynomial, and h67
wide-producer discriminators plus h78 and the h83-h108 small-path,
tomography, coefficient, RN67-parameter, and reduced-path sets;
returned directories or tarballs are verified and scored by
`h61_ingest_capture.py`.
