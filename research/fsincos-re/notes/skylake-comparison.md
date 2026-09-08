# Skylake FSINCOS vs the Itanium algorithm — first comparison

2026-07-15. Hardware: Intel Xeon (Skylake, IBRS) VPS, `GenuineIntel`, x86-64,
CW pinned 0x037F, RN.  Sweep: 50,038 structured inputs (`src/gen_sweep.py`,
deterministic seed), real `FSINCOS` captured by `src/x87_capture.c`; reference
= `src/fsincos_ref.c` (bit-exact Itanium algorithm).  Raw hardware output
archived in `../data/sweeps/skylake-xeon-20260715.out.gz` (inputs regenerate
from gen_sweep.py; ref regenerates from fsincos_ref --batch).

## Results by path

| path                | n     | bit-exact | note |
|---------------------|-------|-----------|------|
| quick-small (<2^-3) | 4004  | **100.00%** | S_1..S_5 / C_1..C_5 kernel + op order identical |
| quick-normal        | 6010  | 94.83%    | ALL mismatches exactly 1 ulp (sin 196, cos 118) |
| moderate (pi/4..2^24)| 24018| 7.34%     | diffs grow with |x|; >64-ulp bucket dominates |
| large (2^24..2^63)  | 16004 | 0.00%     | pre-reduction wholly different |
| C2 range (>=2^63)   | 2     | 100%      | C2 set on both |

## Interpretation

1. **The polynomial kernels survived into Skylake microcode.**  The
   quick-small path (r = x, c = 0, degree-11/10 kernels) matches bit-for-bit
   on all 4004 samples — coefficient values AND evaluation order (a different
   order would show occasional 1-ulp rounding differences).
2. **quick-normal**: same r on both sides (r = x exactly), all diffs exactly
   1 ulp, ~5% incidence -> the degree-17/16 kernel agrees except for a detail.
   Prime suspect: the U_hi/U_lo leading-term split.  Itanium uses
   r_hi = frcpa(frcpa(r)) (architectural table); x87 silicon has no frcpa,
   so presumably truncates r's significand (the FMCAD00 paper itself says
   "explicit bit-level operations ... r_hi has only 10 significant bits").
   -> HYPOTHESIS H1: r_hi = r truncated to k significand bits (k ~ 10);
   grid-test k and re-score.
3. **moderate/large**: the reduction differs.  Known from the Intel SDM
   (vol 1, FPU transcendental accuracy): hardware reduces with a **66-bit
   internal pi**.  The Itanium algorithm reduces with pi/2 to ~198 bits
   (P_1+P_2+P_3) — hence divergence that grows with N, exactly as observed
   (diffs at the tail for x ~ 2*10^4, top-30-bits-only agreement by
   x ~ 2*10^14).
   -> HYPOTHESIS H2: hardware r (+c?) comes from x - N*P66 with
   P66 = pi/2 truncated to 66 significand bits, plausibly computed exactly in
   a wide accumulator; N presumably nearest-int of x*(2/pi approx).
   Conventions to grid-search: N rounding source, r rounding (RN64 vs exact),
   c = 0 vs c = residual, P66 trunc vs RN.
4. C2 boundary at 2^63 exact on both sides.

## Consequence for the project goal

The target ("algorithm with parity against modern x87 fsincos") is now
plausibly REACHABLE: modern microcode looks like this same algorithm family
with (a) a truncation-based r_hi and (b) a shorter-pi reduction.  Both are
finite, testable micro-hypotheses rather than an unknown algorithm.

## Next experiments

1. H1: add a --rhi=trunc<k> mode to fsincos_ref's normal_r; find k that takes
   quick-normal to 100%.
2. H2: add a kernel-entry test mode (feed r, c, N_Inc directly); in Python,
   compute candidate (r, c) per reduction convention exactly; find the
   convention that reproduces hardware on the moderate mismatches; then
   port it into fsincos_ref as --skylake reduction and re-score everything.
3. Re-run the full sweep; iterate on residual mismatch clusters.
4. Later: second hardware source (different Intel generation, and an AMD box)
   to map the family tree.

## Experiment round 2 (2026-07-15): quick-normal 1-ulp mismatch hunt

Baseline: 311/6010 line mismatches (sin 196, cos 118 outputs; all exactly
1 ulp).  Falsified hypotheses:

- **r_hi rule (H1)**: frcpa vs truncation vs RN at k=8..16 — mismatch count
  flat (311-313).  The exact-split design makes the result insensitive to
  the split point; r_hi cannot be identified from outputs, nor explain
  the mismatches.
- **non-fused datapath (H1c)**: modeling every real multiply as separate
  FMUL-round + FADD-round produced ZERO bit differences vs fused on all
  6010 quick-normal inputs (engine verified on a crafted double-rounding
  case).  The dataflow is numerically self-protected: all split-sensitive
  sites have tiny downstream weight.  Fusedness is unobservable here; it
  neither explains the mismatches nor distinguishes silicon.
- **naive kernel (H1d, no U_hi/U_lo split)**: all variants WORSE
  (cos 115 -> ~420 mismatches).  Silicon cos is more Itanium-like than
  naive.

Accuracy forensics (h1b): at the 314 mismatched outputs, reference is
correctly rounded 301 times, hardware 13.  An equal-accuracy alternative
implementation would split ~50/50 -> hardware's kernel has a LARGER
pre-rounding error budget than the Itanium chain (but still well under
1 ulp).  Mismatch rate grows with |r| (0.1-0.4% below 0.25 to ~6% near 0.7)
and is higher for sin than cos.

Interpretation: Skylake's normal-range kernel is a DIFFERENT member of the
same function family — most plausibly a descendant of the Pentium (1993)
table-assisted design (1/64 breakpoints + short polys + angle-addition
reconstruction), whose small-argument limit (b=0, pure polynomial) would
naturally coincide bit-for-bit with the S/C kernels — exactly what we see
at |r| < 2^-3.  Two sub-ulp implementations agree except where their small
errors straddle an RN boundary (~2-6%, growing with r): matches
observations.

Next: obtain the 2025 Pentium FPU constant-ROM decode (Ken Shirriff),
implement the Pentium-style kernel, score vs Skylake; densify the
quick-normal capture for fitting power.

## Round 3 (2026-07-15): REDUCTION IDENTIFIED (moderate range) — 66-bit pi
measured directly from silicon

Trick: for inputs within ~2^-20 of k*(pi/2) with quadrant N mod 4 in {0,2},
FSINCOS's sin output ~= the internal reduced argument itself -> the
hardware's reduction is directly readable from output bits.

1. Internal modulus scan (h2_pi_probe.py): candidates pi/2 @ {64,65,66,67,
   68,72,80,128} bits, trunc and RN.  Result: 66/67/68-bit variants explain
   3971/3971 probes (identical because pi/2 bits 67-68 are 00); 64, 65, and
   >=72-bit variants explain ZERO.  => modulus = pi/2 truncated to 66 bits
   (THE documented "66-bit internal pi", now empirically pinned).
2. Bit-exact test (h2_exact.py): hw sin == RN64_exact(x - N*M66) on
   **3971/3971** moderate-range probes (pi/4 <= |x| < 2^24), N = nearest
   integer of x*2/pi.  Single rounding of an exactly-computed wide
   difference.  MODERATE-RANGE REDUCTION FULLY IDENTIFIED.
3. Large range (2^24..2^63): NOT the single-step formula (436/1001 exact).
   Top ~40 bits of hw r always agree with the M66 model (so M66 governs
   there too), but low bits carry a second truncation artifact — their
   large-arg pre-reduction has additional limited-precision structure
   (analogous to the Itanium P_0 pre-reduction step).  OPEN.

Skylake model so far:
  |x| < 2^-3     : S/C kernels, bit-exact Itanium         [PROVEN 4004/4004]
  2^-3..pi/4     : same-family kernel, ~97.4% agree, hw ~1ulp weaker [OPEN]
  pi/4..2^24     : r = RN64(x - N*trunc66(pi/2)), then kernels [REDUCTION
                   PROVEN bit-exact on near-multiple probes]
  2^24..2^63     : M66 + unknown pre-reduction detail            [OPEN]
  >= 2^63        : C2, operand unchanged                        [PROVEN]

Note for the original CoD use-case: game angle math lives entirely in the
moderate range, which is now the solved part (kernel-entry tail differences
pending).

## Round 4 (2026-07-15): source split + M66 model lands 96.5%

Restructure: fsincos_itanium.c is now the FROZEN reference (verification
statement in its header; experiment scaffolding removed); fsincos_skylake.c
is the working silicon model (M66 reduction + experiment flags).  Frozen
binary verified bit-identical to the pre-split reference on the full sweep.

Skylake model = Itanium kernels + r+c = x - N*trunc66(pi/2) (exact 192-bit
subtract, r = RN64, c = one-bit residual; N = RN(x * 2/pi_128)).  Scored
against the 50k Skylake capture:

  TOTAL 96.537% bit-exact (was 22.9% with pure Itanium)
  quick-small 100% | quick-normal 94.83% | moderate 96.49% | large 96.38%
  ZERO gross mismatches: every miss is exactly 1 ulp on one output.

New insight: the large range ALSO follows the single-step M66 semantics in
general position; the hardware's extra pre-reduction artifact only exceeds
ulp(r) for near-multiple (deep cancellation) inputs — the class-F probes.
So the remaining unknowns are exactly two:
  (a) the ~2-3% kernel-tail 1-ulp flips (all ranges, r-magnitude dependent),
  (b) the large-range near-multiple reduction artifact (tiny-r cases only).

## Round 5 (2026-07-15, overnight): large-range "artifact" was a probe error

Scheme grids S2/S3/S4 (limited-width product, split-N two-step, FPREM-style)
all dead; constant-modulus interval intersection collapses (no constant
M_hw).  Root cause found: the h2_exact large-range probe compared hw sin
against r alone, neglecting sin(r) ~= r - r^3/6 — large-range near-multiple
r's (~ N*tau66) are big enough that the cubic is visible.  Scoring the FULL
C model (kernel included) on the same lines: **3467/3467 = 100.00%**.

=> There is NO second reduction artifact.  The single-step M66 reduction
   (r+c = x - N*trunc66(pi/2), exact wide subtract, r=RN64, c=residual)
   is COMPLETE AND PROVEN for the whole range pi/4 <= |x| < 2^63.

Remaining unknown (the only one): normal_r kernel tail — 1-ulp flips at
~2-6% when |r| >= 2^-3 (quick-normal 94.83%, large general-position 95.37%,
moderate 96.49% — all the same phenomenon at different r distributions).

## Round 6 (2026-07-15, overnight): KERNEL STRUCTURE IDENTIFIED = Pentium FPU

Delta(r) forensics (h5/h6/h7): noise-level below r=1/4; piecewise lobes with
sign flips at 20/64, 24/64, 28/64, 40/64, 48/64 = Voronoi midpoints of the
PENTIUM trig table b in {18,22,26,30,36,44,52,60}/64.  Ken Shirriff's ROM
decode (righto.com 2025-01, saved in data/pentium-rom/ + full 304-constant
table parsed to rom-constants.tsv) provides: 6-term sin/cos polys (rows
157-168), 4-term Remez sin/cos polys (169-176), 16 table constants (177-192),
68-bit significands.

Prototype scoring (experiments/h8_pent_model.py, exact-integer soft x87,
one-RN64-per-op) vs dense Skylake RN capture:
- POLY REGION (2^-3 <= r < 1/4): P5 6-term polynomials, 64-bit-truncated
  coefficients, plain Horner + r+p*r^3 / 1+q*r^2 assembly:
  **~99% bit-exact on first attempt** (11 sin + 23 cos misses / ~1560).
  The 6-term-poly hypothesis is effectively confirmed; residual = evaluation
  detail (op order / a coefficient bit / rounding mode of some op).
- TABLE REGION (r >= 1/4): structure right (~50% exact after variants:
  RN64 table entries + delta-form combine sin = sinT + (sinT*(C4-1) +
  cosT*S4) beats direct form).  Remaining search space: wider internal
  datapath (P5 FPU had extra bits), truncating instead of RN intermediate
  ops, multi-input adds, exact-vs-rounded sinT*t products, tie rule at cell
  edges.

Open items to finish the kernel:
1. Poly region: chase the last ~1% via op-order/rounding variants (cheap).
2. Table region: variant search over {internal precision 64..68, trunc/RN
   per op class, combine shapes}; if no exact hit, SOLVE per-cell table
   entries + per-op semantics jointly from the Delta-interval data
   (constraints are abundant: ~10k per cell).
3. Then: port winning kernel into fsincos_skylake.c, rescore full 50k sweep
   (reduction already proven -> expect ~100%), regenerate all artifacts.

## Round 7 (2026-07-15, overnight): per-cell solve state

h10 per-cell regression of hw-minus-model (P=68 wide datapath, delta-combine,
ROM 68-bit constants):
- cells 22,26,30,36/64: ESSENTIALLY PERFECT (meanD ~ 0.00 output-ulps).
- cos(18/64): clean constant offset ~ -512 ulp => Skylake's entry differs
  from the P5 ROM value by one bit (bit ~55) OR a transcription nit; apply
  delta and verify.
- cells 44,52/64 (the 8/64-spaced cells, |a| up to 1/16): gross model error
  ~2^-24 scale growing with |a| => 4-term poly coefficient decode issue or
  different poly/scaling for wide-|a| cells (P5 may use the 6-term poly
  there, or a different a-scaling).  ONE debug print of a single cell-44
  input (model S4/C4 vs true sin/cos(a)) will pinpoint it.
- KNOWN BUG in gen_dense_qn.py: the pi/4 cap `0x8000..| (sig>>1)` maps into
  [0.89,1.0) instead of [0.5,0.75) — ~22% of binade -1 inputs exceed pi/4
  (they reduced through N=1 in hw; harmless for other analyses but they
  polluted "cell 60" stats and slightly thin the [0.5,0.785) coverage).
  Fix to `sig = (sig >> 1) | (1<<63)` is IDENTICAL — real fix: resample into
  [0x8000.., PI4SIG).  Regenerate + recapture for the final validation run.

STATE: kernel = P5 structure with wide (~68-bit) internal datapath is
CONFIRMED for poly region + 4 of 6 reachable table cells.  Remaining:
(1) cell 44/52 coefficient/poly question (one debug away), (2) exact entry
deltas for cos18 (+ verify others at +-1 ulp), (3) poly-region last few
per-thousand (op-order micro-variant, P~70 nearly closes it), (4) regenerate
dense sweep with fixed generator, recapture, iterate to 100%, port to C.

## Round 8: table region 33% -> 0.58% — three fixes

1. ROM appendix transcription errors CONFIRMED and error-corrected from
   silicon: cos(18/64) sig bit 12, cos(44/64) sig bit 43 (the article's own
   decimal columns match true cos; the hex fields carry single-bit errors).
   My first fix attempt was 2x too large (sig-unit is 2^-67 for exp=0fffe
   rows, not 2^-68) — spot-check vs truth caught it.
2. Combine is WIDE-FUSED: sin = one rounding of (sinT*(1+t) + cosT*S);
   per-op-64 combine scores 8x worse. Consistent with the 69-bit datapath.
3. Cell dispatch is BIT-BASED, not Voronoi: narrow cells [16,20,24,28)/64
   (b=18,22,26,30), wide cells [32,40),[40,48),[48,56)/64 (b=36,44,52),
   split exactly at r=0.5.  (The cell-30-edge cluster at [0.5,33/64) gave
   it away.)

Best model now: 35/6000 = 0.58% (insensitive to poly op precision 64-vs-
wide).  Residuals sit within <=0.03 ulp of rounding boundaries = hardware's
internal ~69-bit poly-op noise, next to hunt via entry/coefficient storage
precision under the fused combine.

## Round 9: full model ported to C — 99.185% on the master sweep

fsincos_skylake.c now implements the complete discovered algorithm:
M66 reduction (proven) + P5 kernel (6-term polys [2^-3,1/4), bit-dispatched
table cells + 4/6-term polys + wide-FUSED combine [1/4, pi/4]) + Itanium
small_r below 2^-3 (bit-proven) + first-order c-injection for reduced
arguments (sin += c*cosT, cos -= c*sinT as extra fused-accumulator terms).
ROM constants live in src/p5_rom_constants.h with the two silicon-verified
bit corrections documented.

Master 50k sweep vs Skylake: 99.185% bit-exact
  quick-small 100% | quick-normal 98.72% | moderate 99.22% | large 99.10%
  C2 100% | zero gross | all misses 1 ulp on one output.
(was 96.54% with the Itanium-kernel stand-in, 22.9% with pure Itanium.)

Residual ~0.8%: hardware's internal op-rounding noise (measured amplitude
~+-2^-70.5) — matching it bit-for-bit requires the exact micro-op residue
pattern; black-box variant search has hit diminishing returns there
(uniform/mixed precisions, double rounding, storage widths, dispatch, and
combine shapes all tested; survivors sit within <=0.03 ulp of boundaries).

## Round 10: forensics, falsifications, and a new instrument

Survivor-Delta forensics (h27/h28, after fixing an RD-interval sign bug for
negative values that briefly masqueraded as a constant offset — caught by
sign-splitting): the model's internal values sit within ~2^-71 of silicon
mid-cell; at cell edges there is a small antisymmetric-in-a deviation
(~5*2^-72 at |a|=1/32) with sensitivity ratio kappa_sin/kappa_cos ~
cosT/sinT — i.e. a systematic *relative* perturbation of S. Mechanistic
candidates ALL falsified by scoring: chopped S/t/Horner/asq, factored
S = a*(1+a^2 P) (x4 rounding variants), S/t materialization at 65-68 bits,
product widths, delta-u, sequential-accumulation shapes. The carrier of the
edge bias remains unidentified; it drives most of the remaining ~0.5%.

NEW INSTRUMENT — instruction-variant captures (x87_capture now takes
sin|cos|sincos): **FSIN and FCOS take a DIFFERENT microcode path than
FSINCOS in the polynomial region (r < 1/4): 208 sin + 779 cos bit
differences on 240k inputs, ALL in the poly region; in the table region the
three instructions agree bit-for-bit (0 diffs).** Our model matches the
FSINCOS path better (339 vs 415 / 816 vs 1121). First direct evidence of
multiple internal paths; the instruction-diff input set is a window into
the differing op.

Also: first-principles audit (h26) corrected the ROM-errata evidence chain
before sending: the article's decimal column is derived from the hex (row
186's decimal is itself wrong vs true cos(0.6875) at the 7th decimal —
hand-checkable); row 189's deviation is sub-display-precision. Errata note
and Shirriff draft rewritten accordingly with a reviewer checklist.

## Round 11: fused finals in the polynomial region

Instruction-diff dissection (h32): FSIN-vs-FSINCOS sin diffs are direction-
balanced and CR-split 50/50 (two equally-good paths); FSINCOS-cos is MORE
accurate than standalone FCOS (CR 554:225).  Diff rates grow toward r=1/4.

Shape hunt (h33-h36): Itanium-shaped split eval with P5 coeffs: falsified.
WINNERS — the last operation of each output is a single fused rounding:
    sin = RN( r + w*r + c ),   w = RN64(P(rsq)*rsq), Horner @64
    cos = RN( 1 + Q(rsq)*rsq - c*r )   (Q*rsq unrounded into the fusion)
Poly-region outputs vs FSINCOS: sin 0.42% -> 0.201%, cos 1.02% -> 0.630%.
Deeper fusion (folding the last Horner add) and wider Horner: worse.
Table-region S-fusing: insensitive (absorbed by the fused combine).

C model v3 (fused poly finals + c folded into the same rounding):
dense poly-region line-miss 1.44% -> 0.83%; MASTER SWEEP 99.185% -> 99.239%.

Still open: the table-region antisymmetric edge bias (sin-heavy: 0.81% vs
cos 0.36% outputs), carrier unidentified after 12+ falsifications.

## Round 12: wide-a validated for reduced arguments

- h38 (table region): S-chain associativity x chop/RN per op — ALL variants
  identical (absorbed below S's rounding grid at feasible sample sizes);
  chopped final S worse.  The antisym edge-bias carrier remains beyond
  black-box resolution in this region for now.
- h39 (leak inputs = genuine reduced args, N=1): TRUE WIDE-A (the exact
  65-bit reduced argument through a=r_wide-b, asq, and the fused finals)
  vs first-order c-injection:  sin 1.387% -> 0.640%, cos 1.257% -> 0.724%.
  Wide-a is the correct reduced-path design; C implementation pending
  (sky_reduce_rc already computes the exact wide D limbs — plumb a wv_t
  into p5_kernel instead of (r64, c)).

## Round 12b: wide-a in C — master sweep 99.360%

fsincos_skylake.c now reconstructs the exact wide reduced argument inside
p5_kernel from (r, c) — by the M66 reducer's construction, c != 0 only when
|r| >= 0.5 and is then exactly +-1 unit of 2^-65, so rw = (r.sig<<1) +- 1 at
scale 2^-65.  The wide argument flows through a = rw - b (exact), asq =
RN64(aw^2), the w-chain, S = RN64(aw + w*aw), and the fused finals; the
first-order c-injection terms are gone.

Scores: dense leak 2.63% -> 1.36%; master sweep 99.239% -> 99.360%
(moderate 99.46%, large 99.21%, quick-normal 98.95%, small 100%, C2 100%,
zero gross, all misses 1 ulp).

## Round 13: directed-rounding validation + the tiebreaker instrument

- Model scored vs the RD/RU captures: same rates as RN (poly 0.82-0.87%,
  table 1.15%) => the model's directed-rounding final is correct AND
  hardware's INTERMEDIATES are RC-independent (only the final rounding
  follows the control word) — a real microcode fact.
- NEW INSTRUMENT: synthesized "tiebreaker" inputs (model value within
  2^-8 ulp of an RN boundary, found by Newton-hopping the exact model;
  4790 captured).  Each reads sign(hw - model) directly.  The sign field:
  sin P(+) sweeps 95%->5% crossing 50% AT a=0 in all four narrow cells
  (cos mirrored, weaker) — confirming the antisymmetric carrier and giving
  per-input phase discrimination that flip-rates could not.
- Per-input sign prediction (h42): "factored S = a*u with u = 1+p*asq
  CHOPPED, S chopped" predicts sin signs at 83.3% (base model 64.2%);
  cos still favors base (86.2%) => composite carrier: dS from
  factored-chop, dt ~ unbiased; per-point phases not yet exact.
  Next: grid u/t formation variants (width x mode) under sign-prediction
  scoring on an enlarged tiebreaker set; verify winner improves RN flips.

## Round 13b: u-grid — a structural paradox as the next clue

Sign-prediction grid over u/m/S formation (h43): sin's best remains
u64-chopped + S-chopped (83.3%); cos's best remains base-S (86.2%);
m-width/mode invisible.  Since sin and cos SHARE S in the modeled combine,
no single S satisfies both => either (a) the hardware computes sin(a)
DIFFERENTLY for the two outputs (sequential microcode paths), or (b) the
cos path contains a compensating term the current combine shape lacks.
This is a sharp, testable structural fork — next round: enlarge the
tiebreaker set (incl. cos-focused points, wide cells, poly region) and fit
the two outputs' carriers independently to settle (a)-vs-(b).

## Round 14: fork resolved; carrier identified at mechanism level; phase open

- Tiebreaker set v2: 12.8k points, both outputs, full table region, exact
  per-point thresholds (window 2^-6 ulp; SHARP subset |d|<=2^-8 ulp is the
  discriminating instrument — the wide window dilutes toward "base").
- The sin/cos "structural fork" was a phase artifact: in the WIDE cells both
  outputs prefer factored-chopped S; narrow-cos prefers base only because
  its dS weight (sinT) is ~3x smaller, so imperfect chop-phase costs more
  than the correct mean gains.  ONE mechanism: hardware computes S in
  factored form a*(1 + p*a^2) with TRUNCATION — sign-prediction 82.5% vs
  base 64.2% (random 50%).
- Phase hunt exhausted the local op-graph space at the 82.5/76.2 ceiling:
  u/m widths+modes, Horner chop, t/q chop, asq chop, fused-single-chop
  (trades sin for cos: 76.0/80.6), ROM flag bit (all trig rows flag=0).
- NOT PORTED: the winner worsens RN flip score (phase mismatch penalty >
  mean gain) — model stays at 99.360%.
- Ideas bank for the phase: coefficient pre-scaling conventions; S/t
  shared partials; per-cell empirical phase-LUT (quantify remaining
  structure); solve the FSIN standalone path first (different, possibly
  simpler phase) and triangulate.

## Round 15 (final for this campaign): the wall, characterized precisely

Instrument saturation checks (h49-h57):
- P(hw_up) vs frac(u), frac(S) in own ulp, S on fixed grids 2^-64..67,
  a's sub-grid bits: ALL FLAT — no phase information in any model-computable
  quantity's fractional position.
- Scale bookkeeping corrected: the true residual deviation is ~2^-71
  (h27's earlier "2^-66" was mis-scaled by ~2^5); flip-rate dimensional
  analysis and sharp-point statistics agree: mean -sign(a)*mu, mu ~= 1.04
  sigma, |mu| ~ 2^-71 — i.e. HALF-ULP-OF-S scale (chop-of-S family), but
  the chop's phase decorrelates from every reconstruction of S we can
  build (their chain differs somewhere at the same 2^-71 scale — the
  difference IS the signal, circularly).
- Fixed-grid truncation of S (2^-64..67): catastrophically worse — grid
  hypotheses dead.
- Poly region (h54-h57, dedicated tiebreaker set, 8.3k): sin already at
  0.15% flips; apparent frac(w*r)-step turned out to be a selection
  artifact (frac correlates with the boundary side); disagreements
  concentrate at frac(wr)~0 = razor points where sub-2^-72 upstream chain
  differences decide — same wall shape as the table region.  Correction-
  product materialization widths 64-68/trunc: all worse or equal.

WALL STATEMENT: the remaining ~0.5% of 1-ulp differences are driven by
rounding-position details of the silicon's internal S-chains at the
2^-70..2^-72 level.  Outputs quantize observations at 2^-65 (ulp/2);
boundary-hugging probes read signs at ~2^-72 but cannot be densified in
the conditioning variable (the hug condition and the a-grid fight); and
~40 historically-plausible op-graph placements have been falsified.
Black-box refinement below this level is obstructed, not merely
unexplored.  Final model: 99.360% bit-exact, all misses 1 ulp, mean
residual bias characterized per side/cell.  Further progress would need
non-black-box information (microcode) or a different silicon generation
to triangulate (capture kit ready).

## Round 16: Pentium II constraints expose a narrow-kernel survivor

- Pentium II Deschutes and Skylake are byte-identical on the 50,038-input
  sweep and all five 240,000-input dense channels: 1,250,038 instruction
  executions.  The Pentium II capture therefore validates the P5 lineage
  but is not an independent numerical oracle.
- `h58_constraint_search.py` converts RN/RD/RU observations into exact
  integer candidate tests and systematically searches 64..69-bit RN/chop
  sites.  The baseline reproduces the full table-region counts exactly:
  4,361/752,778 directed-mode misses, 3,377/250,926 constrained-output
  misses, and 1,463/250,926 RN misses.
- A global fitted producer/tail survivor was falsified by a fresh
  model-selected Skylake discriminator (4,163 misses vs 3,525 baseline).
  Splitting the four-term narrow and six-term wide kernels exposed the
  signal hidden by that aggregate.
- Narrow survivor, representative of a small precision-equivalence class:
  `m=RN68(P*a^2)`, `u=chop68(1+m)`, `S=RN64(a*u)`,
  `t=chop66(Q*a^2)`.  On the full Pentium II capture it improves all four
  narrow cells and reduces directed misses 2,477 -> 2,374, constrained
  output misses 1,905 -> 1,835, and RN misses 829 -> 792.
  Keeping the wide baseline gives full-table totals 4,361 -> 4,258,
  3,377 -> 3,307, and 1,463 -> 1,426 respectively.
- Fresh Skylake discriminator (`h59`, 2,000 inputs selected only because
  baseline and survivor differ): directed misses 1,945 -> 1,154,
  constrained output misses 1,316 -> 782, RN misses 636 -> 359.  Every
  narrow cell improves independently.  AMD moves slightly in the same
  direction (15,663 -> 15,628 directed misses), consistent with an
  ancestral table-tail detail.
- Wide `t=chop64(Q*a^2)` improved the fitted capture slightly but failed
  its independent Skylake discriminator (1,518 -> 1,579); it is rejected
  as a shared wide-kernel change.  Its opposite sine/cosine effects remain
  possible evidence of output-specific internal materialization.
- The narrow schedule is not ported yet: several `m` widths are
  observationally equivalent, and fitting alternate schedules directly
  to the selected discriminator overfits the complete capture.  A targeted
  Pentium II replay of `narrow_inputs.txt` would now be useful; Pentium 4
  work is not indicated.
- Carrying rule: score this narrow candidate against every subsequent
  capture and port its best-supported representative into
  `fsincos_skylake.c` using explicit 66/68-bit intermediates.  Do not let a
  new generic sweep replace the h59 discriminator.  The capture kit now
  includes the h59 inputs in full runs and provides
  `run_constraints_prebuilt.sh` for a short targeted replay.
- Generation triage: a Pentium 4 that is identical to Skylake on h59 adds
  lineage evidence (the sensitive behavior survived NetBurst) but no new
  numerical inequalities, so it does not resolve the equivalent widths.
  A difference would make P4 an independent oracle.  Use the short h59
  replay before considering the cost of another complete P4 capture.

## Round 17: C port, reduced-path proof, and m=RN69 width resolution

- The Round-16 narrow schedule is ported to `fsincos_skylake.c` behind
  `--round16-narrow` with exact 66/68/69-bit integer carriers.  The canonical
  schedule is now `m=RN69(P*a^2)`, `u=chop68(1+m)`, `S=RN64(a*u)`,
  `t=chop66(Q*a^2)`.  Omitting the option preserves the old baseline.
- `h60_round16_parity.py` exhaustively checked the 240,000-input dense set
  plus 50,038-input sweep: 271,278/271,278 candidate-path C results equal
  the exact Python oracle, and 598,836/598,836 inactive mode-results remain
  byte-identical to the baseline.  All 39,322 observed nonzero 65th-bit
  reduction residuals dispatch to the unchanged wide six-term path.
- A fresh Linux build and live x87 replay on the remote Skylake reproduced
  the h59 hashes exactly.  The targeted score remains baseline 1,945 ->
  candidate 1,154 directed misses, 1,316 -> 782 constrained outputs, and
  636 -> 359 RN misses.  On the complete PII-equivalent direct-table
  capture the hybrid totals remain 4,361 -> 4,258, 3,377 -> 3,307, and
  1,463 -> 1,426.
- The old dense and h59 sets could not distinguish `m=RN68`, `m=RN69`, and
  `m=chop69`.  `h62_mwidth_discriminator.py` scanned raw x87 significands
  host-FP-free and found 19 final-bit separators without consulting hardware.
  Skylake selects RN69: 8/114 directed misses, 4/38 constrained-output
  misses, and 0/38 RN misses, versus 23/114, 15/38, and 7/38 for both RN68
  and chop69.  The versioned input concatenates seeds `0xf620..0xf623`
  (one result each, 10M caps) and `0xf624..0xf627` (4,4,3,4 results,
  30M caps), preserving each seed's output order.
- The generic 50,038-input RN sweep is nearly neutral and loses four
  whole-input exact matches with the refinement (49,718 -> 49,714), while
  the deliberately discriminating h59/h62 evidence improves strongly.
  Therefore the refinement stays explicit rather than silently replacing the
  historical baseline until a returned PII replay adds generation evidence.
- The full and prebuilt capture runners now include h59 plus the 19-input
  h62 replay.  `h61_ingest_capture.py` reads a returned directory or tarball
  without extraction, verifies its checksum manifest, compares legacy
  channels, identifies Skylake-equal target hashes, and scores baseline,
  RN69, RN68, and chop69 schedules.

## Round 18: six-term polynomial schedule isolated and ported

- `h63_crossvalidate_tail.py` split the complete 80,000-input narrow
  direct-table set deterministically and searched output-specific
  64..69-bit schedules with observational-equivalence collapse.  The h59-only
  optimum overfits badly (1,154 -> 1,070 h59 misses but 2,374 -> 4,012 on
  the complete capture).  No schedule improves heldout, complete, and h59
  evidence together; Round 17's RN69 narrow schedule remains canonical.
- `h64_poly_constraints.py` applies RN/RD/RU hidden-value constraints to all
  80,000 direct polynomial inputs.  The unique useful producer is
  `a²=chop67(a*a)` followed by fused `RN64(acc*a² + coefficient)` Horner
  steps using the native 67-bit ROM constants.  Output-specific finals are:
  sine `m=RN64(P*a²)`, `correction=chop67(m*a)`, hidden value
  `a+correction`; cosine `tail=chop67(Q*a²)`, hidden value `1+tail`.
  It has zero misses in 480,000 captured output/mode comparisons used for
  discovery and deterministic cross-validation.
- Fresh h65 discriminator: 2,000 inputs selected from 106,777 random raw
  polynomial inputs without consulting hardware.  Baseline -> Round 18:
  2,692 -> 3 directed-mode misses, 2,003 -> 2 constrained-output misses,
  and 912 -> 1 RN misses.  The three remaining events belong to two cosine
  inputs and recapture deterministically.  Widths 64..72, RN/chop,
  double-rounding, fixed-point grids, round-to-odd, coefficient-LSB changes,
  per-Horner substitutions, and negative-direction variants do not improve
  them.
- The exact-integer C implementation is behind `--round18-poly`.
  `h66_round18_parity.py` proves 264,993 active C result pairs equal the
  Python oracle and 611,121 inactive result pairs equal the no-flag model.
  A fresh Debian release and UBSan build passed selftests and parity, and a
  live Skylake replay reproduced all h65 hashes.
- On the 50,038-input master RN sweep, Round 18 improves 49,718 -> 49,773
  exact whole-input matches (99.360% -> 99.470%), with no gross mismatch.
  It is the strongest broad model improvement in this pass.

## Round 19: wide q-chain transfer is useful but remains experimental

- The wide table cells use the same six cosine coefficients, so h67 selected
  2,000 inputs where the historical producer and Round-18 producer disagree.
  A live Skylake RN/RD/RU capture separates the chains: changing the sine
  (`p`) producer is rejected; changing only cosine (`q`) improves baseline
  1,577 -> 1,502 directed misses, 1,177 -> 1,135 constrained outputs, and
  521 -> 512 RN misses.
- The q-only transfer also improves the complete 45,463-input direct-wide
  capture (1,884 -> 1,883 directed, 1,472 -> 1,469 output, 634 -> 629 RN)
  and the independent h59 wide set (1,518 -> 1,498, 1,126 -> 1,112,
  492 -> 484).  Per-mode cosine regressions inside h67 remain, even though
  all three aggregate metrics improve.
- `h69_wide_q_crossvalidate.py` exhausts 72 combinations: baseline versus
  Round-18 q-Horner, baseline versus chop67 final square, and RN/chop
  tail materialization at 64..72 bits.  Only three schedules are jointly
  non-worse on complete-wide, h59, and h67; the full
  `q=Round18, square=chop67, tail=RN64` schedule is best.  This rejects a
  precision-equivalence explanation for the transfer.
- The C implementation is behind `--round19-wide-q`.
  `h68_round19_parity.py` includes the exact 65-bit reduced argument and
  proves 280,101 active result pairs equal Python while 596,013 inactive
  result pairs remain byte-identical to baseline.
- The generic master RN sweep loses one exact whole-input match with Round
  19 (49,718 -> 49,717 alone; 49,773 -> 49,772 with Round 18).  It remains
  an explicit hypothesis rather than a default model change.  A Pentium-II
  h67 replay would classify lineage, but an identical result would add no
  new numerical constraints.
- Range reduction is not an outstanding dependency: Round 5 already proved
  the exact single-step M66 reduction across the full
  `pi/4 <= |x| < 2^63` range.  At this stage the two rare h65 cosine events
  remained alongside the table-kernel micro-op residue.

## Round 20: polynomial q-product materialization closes the residual

- `h70_poly_outlier_forensics.py` traces the two h65 cosine inputs.  At the
  final q-Horner edge their exact fused sums lie only 0.000306 and 0.000128
  local ulp above the negative half-way boundary.  Final-tail precision and
  sticky variants cannot explain the hardware.  Double-rounding the complete
  sum away from zero at 75 bits happens to fix h65 and the complete
  80,000-input direct-polynomial capture.
- The hardware-independent h71 generator selected 64 architectural
  separators from 8,220,700 random inputs with seed `0xf710`.  Live Skylake
  RN/RD/RU scores are: direct fused RN64 90/192 directed misses; whole-sum
  away75 2/192.  `h72_poly_rounding_crossvalidate.py` finds no whole-sum
  width/mode/placement schedule that removes those two exceptions.
- `h73_poly_product_crossvalidate.py` tests the physical product-before-add
  alternative.  Materializing the last product gives
  `q=RN64(chop67(q*a²)+C1)` and scores zero on the complete 80,000-input
  capture, h65, and h71.  Applying the same rule at every q-Horner edge is
  observationally equivalent on those sets.
- h74 independently validates the mechanism after its discovery: seed
  `0xf740` selected 64 new separators from 4,956,997 inputs without consulting
  hardware.  Direct fused RN64 misses 88/192 directed results; both final-only
  and every-edge chop67 product schedules miss 0/192.  The C implementation
  uses the minimum-change final-edge representative under `--round18-poly`.
  Updated C/Python parity covers 265,377 active result pairs, including
  h65/h71/h74, while 611,121 inactive pairs remain baseline-identical.
- The same mechanism does not generalize indiscriminately.  h75 finds no
  jointly non-worse product-before-add schedule in either four-term narrow
  chain.  h76 finds only a two-directed-miss improvement in the wide q chain,
  with no RN gain.  A fresh h77 scan sees 70 internal q differences but zero
  architectural separators in 1,000,000 random wide inputs (seed `0xf770`);
  the wide transfer is therefore not promoted.
- The direct six-term polynomial path now has zero mismatches across the
  complete capture and three independently selected discriminator sets.
  The only unresolved polynomial detail is whether the 67-bit product
  materialization occurs only at the final q edge or at every edge; current
  outputs cannot distinguish them.  The remaining numerical reconstruction
  gap is in the table-assisted kernel, not an unknown polynomial operation.

## Round 21: paired-cell tomography resolves a large table-state component

- `h78_paired_table_tomography.py` reuses one exactly represented residual
  `a` across all four narrow cells or all three common wide cells.  Each
  RN/RD/RU sine/cosine result becomes a differently oriented exact
  inequality on the same hidden `(U=1+t, S)` state.  A hardware-independent
  seed `0xf781` selected 512 groups per family with at least two projections
  within 2^-8 ulp of an RN midpoint: 3,584 inputs and 10,752 executions.
- The shared-state model is feasible for 1,021/1,024 groups.  Median polygon
  widths are about 2^-67 in narrow and 2^-66 in wide; the best decile reaches
  about 2^-69.  In the groups tight on both axes at 2^-68, mean `dU` is only
  -0.0015/-0.0052 local ulp while `dS` is +0.0978/+0.1425 local ulp toward
  zero (narrow/wide).  The systematic carrier is therefore `S`, not a
  compensating cosine-tail error.
- The obvious 64..69-bit table-tail DAGs fit the midpoint-conditioned set but
  regress the complete dense capture and are rejected.  Direct replay of the
  master sweep's reduced residuals proves all 141 exactly representable
  narrow/wide failures reproduce in the direct kernel; 21/64 wide residuals
  with a 65th bit also reproduce.  These are intrinsic table-kernel failures,
  not missing reduction sequencing.
- `h79_table_state_bias.py` cross-validates exact sub-ulp S states.  The
  family representatives are 4/32 ulp toward zero in narrow and 5/32 in
  wide.  Directed misses improve: dense narrow 2,477 -> 1,722; h59 narrow
  1,945 -> 1,531; paired narrow 301 -> 136; dense wide 1,884 -> 1,606; h59
  wide 1,518 -> 777; h67 wide 1,577 -> 805; paired wide 484 -> 306.
  Binary corrections on `U` fail cross-validation or regress the master and
  are rejected.
- The C port is explicit as `--round21-table-bias`.  `h80_round21_parity.py`
  proves 557,415 direct/reduced candidate results equal the exact Python
  oracle under RN/RD/RU, including the 65th reduction bit; 324,699 inactive
  results remain byte-identical.  Combined with Round 18, the master sweep
  improves 49,773 -> 49,833 exact inputs (99.470% -> 99.590%): 119 old
  failures are repaired and 59 new boundary flips are introduced, a net
  reduction of 60.
- `h81` fits single retained/discarded-bit phase rules on half the dense
  capture and rejects them against heldout dense, h59/h67, paired h78, and
  finally the master in `h82`: none improves the constant family state.
  The state-level correction is supported and useful; the exact physical
  multiply/add/truncation event that produces its low bits remains open.
  The remaining master gap is 205 inputs: 195 table-kernel boundary cases
  plus the separate 10-case reduced-small RN boundary behavior.

## Round 22: small-input silicon uses the Pentium polynomial path

- h83 extracts the 10 reduced-small Round-21 master failures.  The Itanium
  `small_r` path misses RN once on every input but matches RD/RU.
- h85 (503 inputs), h87 (987), and h89 (384, exponents -7 through -9)
  independently separate small-path width/chop candidates.  Extending the
  solved Pentium six-term Round-18 polynomial below 2^-3 matches all four
  captures under RN/RD/RU: 11,304/11,304 output-mode checks.  Itanium misses
  1,114 of those checks.
- The exact-integer C port now routes Round-18 direct/reduced small inputs
  through the Pentium path down through exponent -32.  h66 proves 299,262
  active C/Python results and 581,736 inactive results; h90 proves the four
  small discriminators.  The 50,038-input master improves 49,833 -> 49,843,
  leaving 195 table cases and no small-path failures.

## Round 23: local tomography exposes the narrow row-169 direction

- h93 replays all 195 table residuals under RN/RD/RU and pairs every directly
  representable state across its family cells.  All original failures are
  pure RN midpoint events.  h95 densifies 195 local states into 776 paired
  groups / 2,284 inputs.  Together with h78 they reinforce a systematic
  shared-S correction while dU remains near zero.
- h96 finds no stable retained/discarded-bit phase rule.  Increasing the
  magnitude of the narrow four-term leading sine coefficient (ROM row 169)
  is the first residual-dependent mechanism to improve selected datasets
  and the untouched master.
- h97 independently selects 1,536 coefficient separators.  With Round 21,
  +7168 ROM-significand units cuts h97 directed misses 1,147 -> 686 and
  master table failures 195 -> 188.  h98-h101 reject joint bias tuning,
  pre-Horner materialization, and every 64..69-bit downstream S topology as
  replacements.  The explicit C flag is
  `--round23-narrow-coefficient`; +7168 is an equivalent correction, not a
  claimed ROM transcription error.  h102 proves 291,006 active C/Python
  results and 607,320 unchanged results.

## Round 24: the table rotation has a 67-bit correction accumulator

- h104 searches 545 final-partial schedules at 64..80 bits with RN, chop,
  away, and odd materialization.  The cross-validated topology is:

  `result = architectural_round(T1 + RN67(T1*t +/- T2*S))`

  Round 21's equivalent S correction is included inside the RN67 sum.
  Against the current state, narrow master failures fall 55 -> 39 and wide
  failures 133 -> 131.  The same candidate improves complete dense and every
  h59/h67/h78/h95/h97 selected set.
- The exact-integer implementation is
  `--round24-table-delta-rn67`.  h105 proves 581,505 direct/reduced table
  results equal Python under RN/RD/RU and 324,699 non-table results remain
  identical to Round 23.
- h106 shows the RN67 transfer changes fitted parameter surfaces: selected
  captures favor smaller narrow deltas, while the untouched master and h97
  retain +7168; a master-only wide 7/32 bias would overfit the selected data.
  h107 therefore generates 1,024 new separators per family without hardware.
  Fresh Skylake results select +7168 on total directed misses (527 versus
  531 at +6144 and 924 uncorrected) and retain wide 5/32 (593 versus 595 at
  4/32, 604 at 6/32, and 643 at 7/32).
- Combined Rounds 18/21/23/24 score 49,868/50,038 exact (99.660%).  The 170
  remaining differences are all one-ulp table-boundary events; quick-small
  is 4,004/4,004 and there are no gross or C2 differences.

## Round 25: reduced-path parameter split falsified

- Follow-up searches reject two apparent extensions of RN67.  Quantizing
  the correction on a fixed grid relative to the leading table entry loses
  on the selected captures, and RN67 remains the selected-data winner in
  every table cell except a three-mode-miss tie-scale fluctuation in cell
  52 that fails complete/fresh validation.  There is no supported
  cell-specific accumulator width.
- Fine 1/256-ulp scans find shallow direct-data optima near the current
  proxies, but those values trade wins between h59/h78/h95/h97/h107, the
  complete direct capture, and the master.  No fine replacement dominates
  the explicit 4/32 narrow and 5/32 wide state corrections.
- h108 selects 512 fresh large operands per family without reading hardware;
  every operand reduces through M66 to an exact 65-bit table residual.
  Fresh Skylake RN/RD/RU ranks narrow 36/256 over 32/256 by 171 versus 181
  directed-mode misses, and wide 48/256 over 32/256 and 40/256 by 272 versus
  274 and 280.  By contrast, fitting separate reduced biases directly to
  the master prefers 24/256 narrow and 56/256 wide and would superficially
  improve 170 to 156 failures.  h108 rejects both master-only values
  (224 narrow and 303 wide mode misses), proving that gain is selection
  overfit.  No C change is made.
- h108 input SHA-256 is
  `d48d3427601aaece690b3eb7ab04f2c250818600983f052128b04b9b12f13a21`;
  its metadata SHA-256 is
  `e7001fc885ef6d017eaf46fe9994dba7c17d2b9000808dcdb6528cc49fe33129`.
  The x86-64 and static i686 capture binaries produce byte-identical
  RN/RD/RU output on the set.
- h109 crosses the wide six-term final sine coefficient (ROM row 157) with
  RN67 and biases 0..10/32.  Row 157 is nearly identical to narrow row 169,
  so it was the strongest untested coefficient transfer.  All nonzero
  deltas lose sharply: on the joint selected sets, delta 0/bias 4 scores
  2,884 mode misses, while the nearest +1024 candidate scores 2,951 and
  raises complete-wide misses 1,525 -> 1,910.  The supported narrow
  equivalent correction therefore does not transfer to the wide family.

## Round 26: standalone FSIN split and directed tiny boundary

- The capture harness now emits instruction-local status and repeated-minimum
  timing while preserving its default format.  Static i686/x86-64 Debian 12
  prebuilts are byte-identical on default and status captures.  Skylake FSIN
  RN is identical to Pentium II on all 240,000 dense inputs; C1 is consistent
  on all 478,278 directed FSIN comparisons.  The final runner also records
  matched FSINCOS status: standalone/paired FSIN differs on 26 RN, 44 RD,
  and 37 RU full-sweep results.
- h110's directed/C1 search produces the standalone direct-sine graph in
  `notes/fsin-reconstruction.md`: 420/240,000 one-ulp mode misses and
  303/80,000 inputs.  Constant bias, coefficient deltas, and factored finals
  fail independent halves.
- h117 identifies the exponent -68/-69 transition and validates the C tiny
  rule on 1,080/1,080 RN/RD/RU results.
- h118 maps all 26 full-sweep RN differences between FSIN and FSINCOS to the
  polynomial kernel.  h119 constrains standalone FCOS; h121 then selects an
  FSIN-specific odd-quadrant cosine variant over 12,249 residuals.  h122
  independently selects a reduced-entry sine variant over 5,684 residuals.
  Exact C/Python parity holds for all 53,799 directed reduced-subpath results.
- The final standalone C path scores 334/150,114 mode misses on the complete
  sweep, affecting 283/50,038 inputs; every error is one ulp.  h125 partitions
  the residual into 78 polynomial and 256 inherited table cases, with zero
  tiny-input misses.
- KVM timing classifications fail repeatability and are rejected as
  algorithm evidence.  The probe remains useful for a future bare-metal
  capture.

## Round 27: standalone FSIN table terminal materialization

- h126-h129 exhaust raw-carrier, 64..80-bit width, exact-Horner, and wide
  coefficient searches.  The only apparent polynomial gain is a one-boundary
  reduced-sine `-256` effective coefficient correction.  h130 selects 512
  fresh large operands without reading hardware; Skylake rejects the change
  by 415 versus 341 mode misses, so it is not ported.
- Standalone FSIN table C1 enables a separate hidden-carrier search.  h131
  rejects all 545 h104 final combines; h132 rejects fine shared `S`, `U`, and
  row-169 replacements; h133 rejects uniform 64..72-bit producer/tail
  changes.  h134's per-edge search leaves only terminal coefficient
  materializations.
- h135 selects 80 fresh direct/reduced separators without hardware.  Skylake
  validates direct narrow P chop64, direct wide P away64, and wide Q away64
  on both direct and reduced entry; it rejects carrying either P rule into
  reduction.  Exact C/Python parity covers 1,090,830 table results and
  324,699 inactive results.
- The default standalone C model improves the 160,000 dense table inputs
  from 2,119 to 2,112 mode misses and 1,806 to 1,801 input misses.  The
  complete sweep remains 334/150,114 mode misses and 283/50,038 inputs.
  Six master boundary results change: three become exact and three formerly
  exact results move by one ulp.

## Round 28: Tang reconstruction grouping

- Tang's published table graph is
  `Sj + r*Cj + (Sj*q+Cj*p)`.  h104's earlier 545 variants did not split
  `Cj*(r+p)` into `Cj*r+Cj*p`.  h136 tests 121 uniform 64/67/69-bit
  materializations; none transfers across standalone train/held/fresh
  gates.
- h137 searches the three products and two sums independently.  Narrow
  `Cj*p=away64` improves the standalone dense table score from 2,112 to
  2,111 mode misses and 1,801 to 1,800 input misses; C1 misses fall from
  1,125 to 1,123.  Pentium-II dense FSINCOS narrow improves from 967 to 966
  mode misses and 813 to 812 output misses; the master is unchanged.
- Wide `Sj*q=odd67` improves dense FSINCOS by two but regresses the master
  from 186 to 187, so it is rejected.  h138 proves C/Python parity on all
  271,278 narrow standalone table results and proves 598,836 other results
  unchanged.  The validated rule is ported as `--round28-tang-narrow`; the
  complete 50,038-input FSIN sweep remains 334 mode misses.

## Round 29: the Tang product maps onto asymmetric P5 FMUL routes

- h139 replaces Round 28's aggregate `away64(Cj*p)` proxy with explicit
  67-bit multiplicand and 64-bit multiplier buses.  Old aggregate captures
  select RN-formatted inputs but cannot distinguish RN64 from away64 output.
- h140 generates five final-result separators with seed `0xf140c5` after
  1,000,000 scans.  A compiler-free Skylake FSIN capture under RN/RD/RU
  selects reduced RD64 or round-to-odd over RN64/away64 and contains one
  direct orientation separator.  Input SHA-256 is
  `1595654e466fe1bcc784af59730739098da339caf9da39aa08177da699896abb`;
  RN/RD/RU output hashes are respectively
  `d85d9e65ea7e1b96a35642adec2c9b7ad4c91abd8a0609da9a3c93520b104de`,
  `20bca5d6d2fd16059873e43b31486b28ca301bf315208331027c345e82ce586a`,
  and
  `5557a0a12f4ba526494dadd04266a2ebeb50f60809558c2864e40db899c41831`.
- h141-h142 jointly gate path-specific output modes and bus orientation.
  The selected physical representative is direct
  `p->X67,Cj->Y64,RU64` and reduced `Cj->X67,p->Y64,RD64`.
  Round-to-odd remains tied with reduced RD64, but the documented P5
  multiplier implements IEEE directed modes and provides no round-to-odd
  result mode.
- The exact-integer C port is `--round29-p5-fmul-route`.  h143 proves all
  271,278 complete narrow RN/RD/RU results equal Python, with 598,836
  non-narrow results unchanged.  It changes one complete result from Round
  28 and fixes it: narrow misses fall 850 -> 849.  The independent h140 set
  improves 5 -> 2 mode misses; dense Pentium-II FSINCOS improves by one;
  the untouched master and 334-miss standalone full sweep do not change.
- h144 then rejects every normalized/raw fixed-grid interpretation at the
  13 internal-cosine square/Horner/tail/final sites.  h145 rejects all 1,728
  X67/Y64 terminal-product routes at output widths 64..72.  The remaining
  66 internal-cosine mode misses require a conditional low-bit rule or an
  earlier producer operation, not one terminal multiply replacement.

## Round 30: FSIN internal cosine follows FMUL normalization

- h146 synthesizes only over normalization, guard/sticky, retained LSB,
  trailing-zero, low operand bits, sign, and path predicates.  Its best old
  split candidate changes the fifth cosine-Horner sum from chop66 to chop65
  when the 66-bit guard is set, reducing 66 -> 62 mode misses.
- h147 independently selects 128 architectural/C1 separators with seed
  `0xf147c5`.  Skylake rejects that rule: mode misses regress 93 -> 100 and
  affected inputs regress 66 -> 69.  The candidate is not ported.
- h148 selects 441 inputs with seed `0xf148c5`, balanced to 64 separators
  for each of twelve remaining predicate families.  The transferable rule
  is tied directly to the P5 multiplier's two normalization cases:
  retain `away68(a*a)` when the exact 64x64 square has 127 bits, otherwise
  retain h121's `away67(a*a)`.  It improves the old split 66 -> 64, h147
  93 -> 90, and pooled h148 329 -> 310 mode misses; output and C1 counts
  improve on every set.
- h149 proves the `--round30-fsin-cosine-square` C port over all 36,747 old
  internal-cosine mode results and proves no output outside that subpath
  changes.  The full standalone FSIN sweep improves from 334 to 332 mode
  misses and from 283 to 282 inputs; all errors remain one ulp.  Polynomial
  residue falls 78 -> 76 while table residue remains 256.
- Fresh macOS arm64 and Debian x86-64 builds pass selftest and have identical
  full-sweep hashes:
  RN `20693f07dae6273b64c421b9d57c45814262275f35c90e49b7d5ed5cca0d94bb`,
  RD `37d5284fbe940d4e9dbeeb23db5affb25ed542d7bcfbe9a4750fe1806d920eb5`,
  RU `5386489050c6a71d35500332fb49545bcdd26c9e9e71f824d1b61e68c6918c01`.

## Round 31: independently captured internal-cosine tail selector

- h150 repeats the physically constrained one-coordinate search after Round
  30 and requires old train/heldout, h147, and h148 to be componentwise no
  worse.  It leaves low-bit/trailing-zero candidates at the final `q*a2`
  product.
- h151 selects 538 architectural inputs from 8,219,043 deterministic scans
  with seed `0xf151c5`, balanced to 128 prediction separators for each of
  six predeclared mechanisms.  The committed static capture binary records
  RN/RD/RU on the Debian Skylake host without compilation.
- Four candidates fail once mode, affected-input, and C1 counts are enforced
  componentwise.  The predeclared rule `tail=chop71(q*a2)` when the exact
  product's retained 72-bit LSB is one survives.  h152's complete tail grid
  confirms it on old train/heldout, h147, h148, and every h151 targeted
  subset.
- h153 retries every one of the 1,728 X67/Y64 terminal routes after Round 30
  and finds no survivor.  h154 tests 208 fixed-grid and fused `1+q*a2`
  forms and likewise finds none.  The selected low-bit rule is therefore an
  equivalent carrier representative, not evidence for a standard FMUL
  writeback or a simple fused operation.
- h155 tomography finds the old 46 affected residual inputs need mixed
  corrections (33 hidden cosine values up, 13 down).  All 286 outside h151
  cases need an upward correction.  This explains why the new selector
  improves fresh captures while leaving the old sweep unchanged.
- h156 proves the `--round31-fsin-cosine-tail` C port exactly matches Python
  on all 36,747 old internal-cosine results plus h147/h148/h151.  Mode misses
  improve 90 -> 85, 310 -> 304, and 489 -> 471 respectively; h151 affected
  inputs improve 331 -> 324 and C1 misses 254 -> 227.  The full sweep remains
  332/150,114 mode misses and 282/50,038 inputs, so its RN/RD/RU hashes remain
  the Round 30 hashes above.

## Round 32: product normalization and sticky select the fifth sum

- h155 shows the remaining old internal-cosine residuals need mixed
  correction directions.  h157 therefore searches conjunctions of two
  physical trace predicates while requiring old train/heldout, h147, h148,
  h151, and all h151 targeted subsets to be componentwise no worse.
- h158 declares six old-improving fifth-Horner rules, then selects 634
  hardware-blind architectural separators from 5,321,078 deterministic
  scans with seed `0xf158c5`.  The compiler-free Skylake capture rejects all
  three chop64 rules and validates all three chop65 rules on their targeted
  subsets.
- h159 evaluates the individual survivors and simple unions on every old
  and fresh gate, including all six h158 targeted subsets.  The conservative
  transferable rule is the only single candidate that improves both old
  halves: use chop65 for the fifth sum when its exact incoming product lacks
  the high normalization bit and has nonzero sticky below the 65-bit guard.
  Better post-hoc unions are not promoted.
- The first C parity run exposes an interaction with Round 31: changing the
  sum can flip the later 72-bit tail LSB.  The corrected Python graph
  recomputes that selector, and h160 then proves exact C/Python parity on all
  36,747 old results and h147/h148/h151/h158.
- The `--round32-fsin-cosine-horner` port improves old internal-cosine
  mode/input misses 64/46 -> 62/44.  The full standalone sweep improves
  332/282 -> 330/280; polynomial misses fall 76 -> 74 and table misses
  remain 256.  Fresh mode misses improve h148 304 -> 278, h151 471 -> 446,
  and h158 474 -> 429.  All errors remain one ulp.

## Round 33: the secondary state belongs to product 5

- h161 selects 256 hardware-blind cases where Round 32 and the post-hoc
  `D OR E` fifth-sum composition differ.  The composition fails
  componentwise: mode/input misses change 186/132 -> 188/138, although C1
  improves 78 -> 54.  The second selector is therefore not another sum
  materialization.
- h162 searches all 1,157 existing single and paired materializations on
  independent h161 halves.  No `sum65 plus ...` candidate survives.  A
  product-5 carrier improves h161 186/132/78 -> 184/131/77 and is no worse
  on every old and fresh gate; coefficient-5 grids are weaker equivalents.
- h163 constructs large architectural inputs from randomized odd reduction
  quotients.  Its 33 hardware-blind inputs give 16 separators for each of
  39 predeclared product/coefficient grids.  All product representatives
  transfer; the best class improves 27/20/9 -> 14/10/4, versus 22/15/9 for
  coefficient changes.
- Round 33 chooses the physically constrained representative: retain
  round-to-odd 67 bits for product 5 when its retained 65-bit LSB is zero,
  the square low three bits are three, and the Round-32 normalization/sticky
  condition is false.  The width matches Intel's documented normalized
  multiplier carrier and odd retains discarded sticky information.
- h164 proves exact C/Python parity and scope over 42,837 old/fresh results.
  Round 33 changes two h161 and 41 h163 architectural mode results, no older
  capture result, and no full-sweep result.  The headline remains
  330/150,114 modes and 280/50,038 inputs, partitioned 74 polynomial and
  256 table.
- h165 scans 30,000,000 constructed architectural inputs for pairwise
  differences inside h163's best class.  Only one separator exists.  Its
  compiler-free Skylake capture rejects product5=RN72 (one mode/input miss);
  away64/65, odd66..71, odd67, and exact all match 3/3 modes and C1.  The
  documented odd67 representative survives the strongest available width
  discriminator.

## Post-Round-33 adjacent-operation falsification

- h166 freezes Rounds 30--33 and reinverts all 12,249 old internal-cosine
  inputs.  There are 12,205 inside states, 31 need-up states, and 13
  need-down states.  No adjacent one- or two-bit partition isolates a
  direction without selecting many correct controls.
- h167 jointly searches 146 product-5, sum-5, tail, and final-sum
  materializations with one- and two-predicate selectors.  It requires
  componentwise non-regression on old train/heldout and
  h147/h148/h151/h158/h161/h163/h165.  Thirty-one rules survive existing
  data; the leader predicts old mode/input/C1 improvement
  62/44/22 -> 58/42/20.
- h168 predeclares six distinct mechanisms and constructs 363
  hardware-blind inputs, balanced to 64 architectural separators per rule.
  Compiler-free Skylake rejects all six componentwise.  The leading sum
  rule changes 52/33/25 -> 51/34/17; its mode/C1 gain does not justify the
  new affected input.  The tail rules create 8--16 extra affected inputs
  and some also regress C1.  No rule is ported.

## Post-Round-33 table-correction falsification

- h169 inverts all 21,805 table-active sweep inputs through the solved
  Tang/P5 graph.  It finds 21,579 inside states, 129 residuals needing
  greater hidden magnitude, and 97 needing smaller magnitude.  The offsets
  cluster within a few units at the RN67 correction scale.
- h170 searches conditional 64..72-bit/exact materialization of the final
  correction accumulator over dense and sweep train/heldout plus h135 and
  h140.  Six distinct mechanisms survive the existing gates.
- h171 freezes those mechanisms and selects 283 hardware-blind direct and
  M66-reduced separators.  Fresh Skylake RN/RD/RU data rejects all six
  componentwise.  The leading cell/quadrant rule improves mode/input misses
  37/37 -> 35/31 but regresses C1 22 -> 24.  No correction rule is ported;
  the next table pass must test operation order, carrier formation, or
  path/promotion gates.
- h172 adds PC24/PC53/PC64 control to the static capture binary.  All 50,038
  structured sweep inputs and 283 h171 separators return byte-identical RN
  results and status words under all three settings.  Architectural
  precision control does not reach standalone FSIN; the carrier width is
  microcode-selected.
- h173 tests 1,183 global Tang addition trees with exact or 64/67/69-bit
  FADD carriers; none survives sweep train/heldout and h171.
- h174 gates the same schedules only by direct/reduced, narrow/wide, and
  sine/cosine lane.  Ten schedules survive all existing data, so h175
  constructs 243 fresh table-interval inputs balanced to 64 separators for
  six distinct rules.
- Three h175 rules improve their own targeted subsets.  h176 checks each
  against the complete h175 capture and all other targeted subsets; all
  regress at least one independent subset.  No FADD topology or structural
  path gate is ported.

## Shared table sibling triangulation

- h177 recaptures paired FSINCOS over the dense set.  All 160,000
  table-active inputs match standalone FSIN/FCOS lane values under RN/RD/RU;
  FCOS and paired C1 match in 480,000/480,000 cases.  h178 finds the same
  zero-difference result on all 21,805 table-active sweep inputs.
- Dense paired FSINCOS hashes are RN
  `508a5f199148507d715c7921bca6257da1c4d3a1a940a02a5441b2aa76c730a3`,
  RD
  `bff0636270185e637c735c1abc58d3d27eb9447a63d89ae98c6733ebd9cb2862`,
  and RU
  `b4431b905224445f1e9b4172a144f59b4bbf2f8bdccaee6f8f7e75033c55ef47`.
  Sweep hashes are RN
  `2d29b7264db258b43df23c724abeb377ebe1e1bc1465c7322817d6413ce8da31`,
  RD
  `74ce9b9de5149b0d195db3f5065f1a70c825362f34171249b639c965c1c8c5c6`,
  and RU
  `ddf86888b8011a63b3f0a0f8707e197c2263679306d4084f5b0a1fbf8b1b4937`.
- h179 preserves the actual reduction quadrant and projects joint interval
  deltas back onto Tang state axes.  Current dense mode misses are 2,110
  sine and 1,517 cosine; outside states split 1,471 P-like / 1,603 Q-like.
- h180 confirms the path-aware Tang/P5 graph.  h181 rejects every individual
  wide-Q Horner coordinate.  h182 leaves only six equivalent wide
  `p*square` away/odd carriers; h183's fresh 43-input two-lane capture
  rejects all six.  No shared producer change is ported.

## Round 34: shared lookup/FIRC low-bit route

- h184 tests all 125 combinations formed by keeping the 67-bit lookup
  constant or routing it as RN/chop/away/odd 64 bits at the `cross*r`,
  `lead*q`, and `cross*p` consumers.  Complete joint-lane partition gates
  leave one changed survivor: `cross*p=RN64`.  It fixes two dense wide-table
  sine modes and regresses none.
- h185 freezes RN/chop/away/odd and selects 38 hardware-blind direct-wide
  separators (16 per mode).  Compiler-free Skylake results validate RN64:
  its targeted cosine score improves 7/7/10 -> 1/1/0 and its complete
  cosine score improves 13/12/11 -> 7/6/1.  Away and odd fail.  Chop also
  improves the fresh set but fails h184's complete old partitions.
- Round 34 ports the selected wide route as
  `--round34-table-lookup-firc`.  h186 proves exact C/Python parity for
  274,137 complete wide-table results, with two output changes and 595,977
  other results unchanged.  Dense sine table misses improve 1,334 -> 1,332;
  the structured full-sweep headline remains 330 mode / 280 input misses.

## Coordinated producer extension

- h187 freezes Round 34 and crosses a bounded beam containing one changed
  P-Horner coordinate and one changed Q-Horner coordinate.  Of 1,024
  schedules, 864 pass the deterministic sample and 736 pass all residuals
  plus independent controls.  Those 736 are only nine observational
  profiles; every representative fails a complete dense/sweep, train/held,
  sine/cosine partition.  Individually visible one-P/one-Q pairs are
  exhausted.  The next bounded family is a stage-local coefficient/product/
  sum combination whose individual pieces can be architecturally latent.

## Round 35: latent terminal-P materializations

- h188 changes exactly two of coefficient, product, and sum materialization
  at the terminal P or Q Horner stage.  It tests 7,920 schedules.  The 5,916
  sample survivors reduce to 4,426 all-residual survivors in 16 exact
  profiles; three profiles pass complete joint-lane validation.  Every one
  uses terminal P coefficient away64, paired with sum chop65, product
  away64, or sum RN65.
- h189 scans direct and constructed-reduction states without hardware data.
  The resulting 37 inputs contain 16 separators for every pair among Round
  34 and the three survivors.  Fresh Skylake output selects
  `coefficient=away64, sum=chop65`: sine improves 21/12/13 -> 12/7/7 and
  the h188 shared-state cosine score 10/8/6 -> 6/5/3.  The other profiles
  regress.
- Round 35 ports the selected P route as
  `--round35-table-p-terminal`.  It does not promote the older terminal-Q
  rule into paired FSINCOS.  h190 models that instruction-path distinction
  and proves exact C/Python parity for 548,274 complete wide-table
  lane/mode results; 1,191,954 non-wide results remain unchanged.
- Complete mode/input/C1 metrics improve
  `1515/1309/828 -> 1513/1308/827` for standalone sine and
  `1515/1304/807 -> 1514/1303/805` for paired cosine.  The structured sweep
  remains 330 mode / 280 input misses.
- The fresh Debian build at
  `/home/coduoserver/fsincos-round35-20260721021856` passes selftest.  Its
  RN/RD/RU full-sweep hashes remain
  `8a520893d63c2d0448fc19685a35c94c61481e500ac2d8852c210ee5c9537ba7`,
  `37d5284fbe940d4e9dbeeb23db5affb25ed542d7bcfbe9a4750fe1806d920eb5`,
  and `5386489050c6a71d35500332fb49545bcdd26c9e9e71f824d1b61e68c6918c01`,
  byte-identical to macOS.

## Penultimate-stage latent-pair exclusion

- h191 freezes Round 35 and applies h188's full two-operation grid to the
  penultimate wide-P stage.  All 3,960 schedules fail the componentwise
  sample gate; there are no residual or complete-corpus survivors.
- h192 repeats the 3,960-schedule grid at the penultimate wide-Q stage.  It
  retains away64 terminal Q for standalone FSIN and native RN67 terminal Q
  for paired FSINCOS.  Again, no schedule passes the sample gate.
- The recovered terminal-P pairing does not repeat at the adjacent P or Q
  stage.  No fresh capture or C change is justified; stage 3 remains the
  next bounded latent-pair target.

## Global Round-35 residual coherence

- h193 jointly inverts standalone-FSIN sine and paired-FSINCOS cosine for
  all 11,379 wide-table sweep points.  Of 323 joint outside states, the
  projected correction has 28 signatures even at the coarse 2^-67 scale;
  the four most common cover only 95 states.  At 2^-70 there are 232
  signatures and the four most common cover 18.  Global correction-axis
  concentration is 0.5534; source/cell strata reach at most 0.6730.
- Physical trace predicates do not expose a compact failure class on
  deterministic train/held halves.  The strongest single predicate,
  terminal-P sum LSB=1, has only 1.14/1.10 residual lift while selecting
  5,547 correct controls.  The strongest broad conjunction has 1.36/1.36
  lift but crosses independent P and Q states and selects 2,812 controls.
- h194 therefore scores the operation rather than its unsigned correction.
  It propagates 1,378 single-site 64..72-bit/exact counterfactuals through
  the Round-35 shared square, every P/Q Horner coordinate, the P-to-S
  carriers, and Q tail.  Sixty-seven candidates pass a sample containing
  every failure plus 1,200 correct controls.  Complete sweep validation
  leaves three: shared terminal-Q coefficient chop65/odd65 and common
  terminal-Q sum RN65.  They remove four/three paired-cosine mode misses.
- h195 tests those profiles and both same-stage combinations on 91,497
  complete dense/sweep and independent h183/h185/h189 points.  No profile
  survives.  The coefficient profile improves sweep and fresh h185/h189
  but worsens dense-train cosine 620/539/359 -> 624/543/365.  The RN65 sum
  profile improves fresh h185/h189 more strongly but worsens both dense
  halves.  Combining them also regresses sweep cosine.
- The high-payoff single-operation hypothesis is falsified on current data.
  No C change or new hardware capture is justified.  Remaining table work
  returns to coordinated multi-stage schedules rather than a missing global
  polynomial term or one shared materialization.

## Complete nonterminal stage-local exclusion

- h191-h192 originally test the stage-4 P/Q coefficient/product/sum pairs.
  h196-h197 generalize their producer replay through intervening current
  stages and apply the same grid at stage 3.  Assertions prove each current
  producer is exactly the Round-35 producer before candidate enumeration.
- h198 completes stages 2 and 1 independently for both chains.  Stage 0 has
  only the initial coefficient materialization and therefore no local
  coefficient/product/sum triple.
- All eight nonterminal grids test 3,960 schedules and have zero survivors
  at the first componentwise joint-lane sample gate: 31,680 schedules in
  total.  Including h188's 7,920 terminal schedules, the full same-stage
  family contains 39,600 schedules; only the already-ported terminal-P
  away64-coefficient/chop65-sum profile survives.
- The remaining bounded schedule hypothesis is cross-stage but physically
  adjacent: an upstream Horner sum carrier paired with the next product
  consumer.  Arbitrary nonadjacent multi-edge enumeration is not justified.

## Adjacent Horner carrier exclusion

- h199 pairs the materialized sum at stage k with the product at stage k+1
  that directly consumes it.  Each P/Q boundary tests 36 sum modes by 37
  product modes, including an exact product, under the exact Round-35 model.
- All four boundaries in both P and Q reject all 1,332 schedules at the
  componentwise sample gate: 10,656 additional schedules with zero
  survivors.  No all-residual or complete-corpus evaluation is warranted.
- Together, h188/h191-h199 cover 50,256 physically local two-edge schedules:
  39,600 same-stage and 10,656 adjacent producer/consumer pairs.  Only the
  already-ported terminal-P away64-coefficient/chop65-sum route survives.
- The remaining enumerations are qualitatively weaker: a triple that needs
  all three same-stage operations simultaneously, or arbitrary nonadjacent
  edges.  h194 already rejects adding a third terminal-P operation to Round
  35.  Do not launch the much larger nonterminal grids without a new state
  signature, hardware separator, or microarchitectural reason.

## Literal P5 FADD carrier

- US 5,257,215 FIG. 2 exposes the shifted mantissa and sticky as separate
  inputs to the X2 FADD path and returns a 68-bit FAMUBUS carrier.  h200
  implements the exercised unlike-sign far-subtraction path as bit vectors:
  alignment, discarded-tail detection, integer subtraction/borrow, one-bit
  normalization, and sticky compression.  Every measured Horner subtraction
  has an exponent difference of 11--41.
- h200 tests all 2,176 non-current P/Q retain-mask schedules under jammed-
  before-subtract and marked-after-subtract interpretations.  Its best
  complete profile improves aggregate mode/C1/input counts
  `366/188/326 -> 363/187/324`, but regresses train-cosine C1 `46 -> 48`.
  h201 adds direct/reduced gates; both exact complete profiles are the same
  rejected near-miss.  Neither pass reaches dense/fresh validation.
- h202 tests 384 internal-cosine schedules over Round-31--33 foundations.
  The leading raw profile improves aggregate focused metrics
  `2049/890/1425 -> 2045/888/1423`, but worsens h148 and h163; no profile is
  componentwise non-regressing.  h203 tests 540 coherent physical routes
  over square, ROM67/RN64 coefficient, FMUL writeback, FADD retention, and
  tail controls.  None passes the sample gate.
- h204 models the separate sticky wire as two's-complement borrow-in, with
  and without the complemented residual sticky.  Its 138 table schedules
  leave no complete survivor; all 192 polynomial-proxy and 540 coherent
  physical schedules fail the sample gate.
- h205 then tests the patent's independent FRND normalization control.  At
  retained cancellation stages, normalization-off preserves a compressed
  FAMUBUS carrier with J=0 before the next FMUL.  All 336 path-gated table
  candidates leave no complete survivor; all 372 polynomial and 864 coherent
  physical candidates fail the sample gate.  The four bounded sticky/borrow
  readings under both normalization states are falsified inside the
  polynomial producers.  This does not yet cover the final Tang additions or
  preserve the carrier representation explicitly through FMUL.

## Complete literal FADD/FIRC reconstruction

- h206 completes the FAMUBUS primitive with like-sign addition, X1-style near
  subtraction, overflow/right normalization, arbitrary cancellation/left
  normalization, and independent FRND normalization.  A retained J=0 or J=1
  carrier, including G/R/S, can be passed directly to FMUL X67 while an RN64
  operand occupies Y64.
- h207 replaces all three scalar additions in every one of h173's seven Tang
  reconstruction trees.  Its 16,128 schedules cross four sticky/borrow
  readings, retained-normalized, retained-raw, and four 64-bit FRND controls
  at both intermediates, both final normalization states, and eight linear/Q/P
  FMUL carrier routes.  Zero schedules pass the 1,423-point componentwise
  sample containing sweep failures/controls, h171/h175 final-addition data,
  and h183/h185/h189 producer data.
- h208 explicitly replays P/Q Horner as FADD carrier -> FMUL X67, with the
  square on Y64 and odd67/RN/chop/away/odd64 FMUL results.  All 32 retain masks
  are collapsed only after exact producer comparison.  Of 2,511 global and
  direct/reduced schedules, 409 sample survivors collapse to 40 profiles;
  every profile fails the complete 11,379-input wide sweep.
- h209 tests the remaining compensation hypothesis instead of requiring each
  half to work independently.  One representative of every h208 sample
  profile is crossed with 504 coherent literal Tang schedules, for 20,160
  end-to-end FIRC candidates.  None passes the componentwise sample gate.
- h210 reference-checks borrow-sticky FADD on 50,000 exact GRS-zero operand
  pairs.  All 25,004 like-sign additions, 23,765 far subtractions, and 1,231
  near subtractions equal exact arithmetic followed by a sticky 67-bit
  carrier.  A census over all seven measured Tang trees observes addition and
  far subtraction at exponent distances 4--39; no measured operation uses the
  near path.
- The broad literal FADD/FIRC hypothesis is now adequately searched within
  the documented datapath.  No candidate reaches a complete gate, so there is
  no C change and no hardware discriminator to capture.  Further work needs
  specific FIRC microcontrol evidence or undocumented/non-equivalent FMUL
  behavior, not another generic carrier grid.

## Round 36: conditional FIRC microcontrol

- h211 completes all fifteen commutative four-term addition trees.  Together
  with h207 it excludes all 34,560 unconditional tree/control/product
  programs.  h212 then permits a lane-local program choice: fixed `jam-sub`
  semantics can exactly reach all 166 failing sine lanes and all 160 failing
  cosine lanes in the structured sweep.  The arithmetic grammar is
  sufficient; a data-dependent selector is missing.
- h213-h215 restrict the selector to causal term and first-FADD state.  Of 25
  three-atom complete-corpus survivors, h216 chooses one on 31 hardware-blind
  Skylake inputs: first `linear+p` exponent distance 14, normalized raw
  exponent phase 0 modulo 4, and FAMUBUS bit 3 set.  The chosen program uses
  odd67 products, odd64 for `linear+p`, then odd67 for the Q and lead adds.
  It improves all-h216 standalone sine mode/input/C1 misses
  `8/5/3 -> 4/3/1`; every competing operation/GRS/sign/bit representative
  fails.
- Round 36 ports that leaf as `--round36-table-fadd-microcontrol`.  h217
  emits all 588 complete sweep/dense base-condition inputs, including both
  bit-3 values.  The Debian C model matches Python in 7,056 RN/RD/RU
  standalone-sine/paired-cosine checks.  The complete paired-cosine metric
  improves `1514/1303/805 -> 1512/1302/804`; standalone sine and the
  structured 330-mode/280-input headline are unchanged.
  Full Debian baseline/Round-36 replay confirms zero changed standalone-FSIN
  lines in dense or sweep, zero changed paired lines in the sweep, and exactly
  one paired dense line in each of RD and RU.
- h218 inventories 2,928 residual lane instances across complete and focused
  data.  h212's eleven representatives exactly reach 2,902; h219 tests the
  other 23 unique states against all 8,640 `jam-sub` programs and reaches all
  of them with four more schedules.  No additional arithmetic primitive or
  sticky mode is required by any measured residual.
- h220 synthesizes a second causal branch over 183,381 lanes.  Seven rules
  survive all old partitions.  h221's 49 fresh pairwise separators reject all
  seven.  h222 adds one counterexample atom; 31 refined rules survive, and
  h223's 43 fresh inputs leave four.  A 98-input h224 head-to-head then rejects
  both final carrier predicates.  No second microcontrol leaf is ported.
- h225 evaluates 604 base-condition lanes against aligned operand bits,
  discarded tails, jammed low bits, subtraction borrow-ins, raw X2 bits, and
  normalized FAMUBUS bits.  Only `normalized X2 bit 4`, raw X2 bit 4 in the
  exercised normalization state, and `FAMUBUS bit 3` equal the selected
  predicate; these are the same representation wire.  No independent
  carry/borrow/sticky alias remains to discriminate.
- Fresh Debian build `/tmp/fsincos-round36-final.k737DN` passes selftest.
  Its source SHA-256 is
  `722cbbac1dd1f440c5adf87c25b4b39f68f5b037b0b1b31dd41c814024bd96cc`.
  RN/RD/RU standalone full-sweep hashes remain respectively
  `8a520893d63c2d0448fc19685a35c94c61481e500ac2d8852c210ee5c9537ba7`,
  `37d5284fbe940d4e9dbeeb23db5affb25ed542d7bcfbe9a4750fe1806d920eb5`,
  and `5386489050c6a71d35500332fb49545bcdd26c9e9e71f824d1b61e68c6918c01`.

## Round 37: four-term graph

- The FSINCOS numerical graph uses four-term sine/cosine kernels for
  all table cells.  Its highest-degree sine coefficient differs from the P5
  value at payload bit 60; retaining the P5 value makes this graph fail badly.
- h226-h228 select the complete-state graph
  `odd67(lead*cos_tail) +/- chop67(cross*sin_state)`, followed by an away67
  correction and architectural lead addition.  h228 obtains zero C/Python
  differences in 1,090,830 all-cell dense/sweep lane-mode checks.
- h230 restricts the remaining search to the fixed operation boundaries.  A
  chopped 67-bit `a*a` carrier is componentwise non-regressing over 92,030
  points and the untouched h221/h223/h224 captures.  Two smaller sine-side
  carrier refinements (`away67(P*a*a)`, then `chop65(...*a)`) improve focused
  directed-mode observations and are neutral on the RN master.  Further
  Horner-product changes are complete-corpus neutral and are not ported.
- `--round37-p6-four-term` improves the structured standalone-FSIN sweep from
  330/150,114 mode misses on 280/50,038 inputs to 126 mode misses on 106
  inputs, all one ulp.  Standalone-FCOS dense misses improve from
  3,678/720,000 to 2,540/720,000; direct polynomial misses are unchanged.
  The paired FSINCOS RN master improves from 49,868/50,038 to
  49,991/50,038 exact inputs.  Dense paired FSINCOS exact-input counts are
  239,739/240,000 RN, 239,733 RD, and 239,761 RU, versus 238,817, 238,770,
  and 238,790 before Round 37.
- Fresh Debian build
  `/home/coduoserver/fsincos-round37-20260721194335` passes selftest and
  reproduces the 126/106 standalone-FSIN score.

## Standalone FCOS coefficient-bias exclusion

- The numerical path retains the decoded P5 six-term cosine coefficient
  values.  h233 searches a fixed effective-significand bias in each
  coefficient, scaling each range by its polynomial power and exhaustively
  checking sub-step deltas for the sensitive `x^2` and `x^4` terms.  No bias
  improves mode, affected-input, and C1 counts together.  The smallest `x^2`
  delta raises mode misses from 2,161 to at least 2,233.  An `x^4` delta of
  `-8` trades two fewer mode misses for three more affected inputs and seven
  more C1 misses; all other full-corpus candidates are worse.
- h234 maps all 2,540 FCOS dense misses.  Of these, 2,161 are in the direct
  polynomial path, which reads no trigonometric lookup entry.  The other 379
  span every active cell (`18`, `22`, `26`, `30`, `36`, `44`, and `52`) and
  include both error directions.  The two published-P5 lookup errors at
  `cos(18/64)` and `cos(44/64)` already use the independently validated
  corrections.
- A simple uniform-width replay of the fixed two-chain cosine graph scores
  2,179 mode misses, slightly worse than h119's 2,161.  h235's per-boundary
  search below shows that this was a materialization problem, not evidence
  against that topology.

## Round 38: standalone-cosine split graph

- h235 evaluates the reconstructed dependency graph as two interleaved chains:
  `((C10*x^4+C6)*x^4+C2)*x^2` and
  `((C12*x^4+C8)*x^4+C4)*x^4`.  Independent train/held-out halves both select
  `chop67(x^2)`, `RN64(x^4)`, RN68 on the terminal negative-chain multiply,
  RN64 on the `+C2` sum, odd66 on the `+C4` sum, and chop66 on the branch
  combine.  All other branch products/sums use chop67.  The full direct score
  falls from 2,161/1,545/850 to 390/390/264 mode/input/C1 misses.
- `--round38-p6-cosine-split` ports that schedule.  h236 proves zero C/Python
  differences over 240,000 direct checks.  Complete dense FCOS improves from
  2,540/720,000 mode misses on 1,919/240,000 inputs to 769 modes on 764
  inputs.  The 379 table-path mode misses are unchanged.
- On the independent 50,038-input FCOS sweep, h237 improves 1,490 to 1,378
  mode misses and 1,450 to 1,373 affected inputs.  It fixes 123 results and
  regresses 11; the changed paths are direct and M66-reduced cosine
  polynomials.  Of the 1,378 residual modes, 1,289 are the pre-existing tiny
  directed-rounding path and are unrelated to the split polynomial.
- Fresh Debian build
  `/home/coduoserver/fsincos-round38-20260721222300` passes selftest.  Source
  SHA-256 is `b8f6cc2a0d851d504f18c2ee34796f5ca80aa0a6f67c2bafa64a50eb5da10c5e`;
  executable SHA-256 is
  `5fdb7d4f89ff55f500f3c7a1888e903598c6093bcc5bf3b90a78a7f5e8370bc1`.
  Returned dense and sweep replays reproduce h236/h237 exactly.

## Round 39: standalone-FCOS tiny boundary

- The master sweep contains 8,406 direct-tiny lane/mode observations.  For
  nonzero inputs with exponent `-68..-33`, FCOS returns the representable
  value immediately below 1 under RD and returns 1 under RN/RU.  At exponent
  `<= -69`, all three captured modes return 1.  The transition is independent
  of input sign and significand.  RZ is inferred to follow RD because the
  exact result is positive and below 1.
- `--round39-fcos-tiny` ports this rule.  h238 validates every captured tiny
  observation and improves the Round-38 FCOS sweep from 1,378 mode misses on
  1,373 inputs to 89 modes on 84 inputs: 1,289 fixes, zero regressions.  Dense
  FCOS is unchanged because that corpus contains no tiny inputs.
- Fresh Debian build
  `/home/coduoserver/fsincos-round39-20260721223925` passes selftest.  Source
  SHA-256 is `42cb09dcee2e028d7e5baf626b67e7f52bec9da658c88921cfb1009b6f94f91d`;
  executable SHA-256 is
  `df033c45f73d9a97df9832b9e67f6754f27a96eedcd3b9f767528bff342ef085`.
  The returned RN/RD/RU sweep outputs reproduce h238's 89/84 score, 1,289
  fixes, and zero regressions exactly.

## Round 40: paired-FSINCOS tiny boundaries

- h239 freezes the first complete post-Round-39 residual census.  Standalone
  FSIN is 126 modes/106 inputs and standalone FCOS is 89/84.  Paired FSINCOS
  initially has 2,688 lane/mode misses on 1,399 sweep inputs; 2,578 are the
  direct-tiny sine/cosine directed-rounding cases already established for the
  standalone instructions.
- `--round40-fsincos-tiny` applies those captured lane rules to paired
  FSINCOS.  h240 validates all 16,812 tiny lane/mode observations and improves
  the paired sweep from 2,688 to 110 lane/mode misses and from 1,399 to 110
  affected inputs: 2,578 fixes and zero regressions.  RN remains at 47 misses;
  every remaining paired sweep miss is in a table path.
- Fresh Debian build
  `/home/coduoserver/fsincos-round40-20260721230849` passes selftest.  C-source
  SHA-256 is `84651c40bc2a3c303c0b7ffa305fe00cc4621570be1ed0aa6ae4bf837a72b7f0`;
  executable SHA-256 is
  `caecea802b6b9d11027d751242233b7026459f6a7830c6aa27f5aee6f2add9bf`.
  Returned RN/RD/RU sweep outputs reproduce h240's 110/110 score, 2,578 fixes,
  and zero regressions exactly.

## Round 41: standalone-FSIN internal-cosine split graph

- h241 replays the Round-38 two-chain cosine dependency graph on standalone
  FSIN's odd-quadrant internal-cosine producer.  The unchanged FCOS schedule
  already reduces the structured internal-cosine score from 62 to 17 mode
  misses.  Independent boundary fitting selects RN67 instead of RN68 on the
  terminal negative-chain multiply and away65 instead of odd66 on the last
  positive-chain sum, leaving 10 mode misses on 10 inputs and 10 C1 misses.
- Both structured halves improve.  Seven earlier focused discriminator
  captures are aggregate no-worse gates; five improve and two tie.  Relative
  to Round 33, the selected graph fixes 58 mode results, regresses six, and
  shares four misses, for a net improvement of 52.
- `--round41-fsin-cosine-split` ports the schedule.  Exact C/Python parity
  covers 36,747 structured and 7,179 focused lane/mode checks.  The complete
  standalone-FSIN sweep improves from 126 mode misses on 106 inputs to 74 on
  72.  Standalone FCOS remains at 89/84 and paired FSINCOS at 110/110.
- Fresh Debian build
  `/home/coduoserver/fsincos-round41-20260721235438-d` passes selftest.
  C-source SHA-256 is
  `60ce4237ec69d740374fe4d160648b3081b06ec8b405b8cbf6273ef5eadf0417`;
  executable SHA-256 is
  `e55b6a48066370b5b90938f0204d286d876e28e3fe551a64c752d9b3e0cddd2e`.

## Round 42: standalone sine-producing split graph

- h242 evaluates the six-term sine correction as two interleaved chains:
  `((S5*x^4+S3)*x^4+S1)*x^2` and
  `((S6*x^4+S4)*x^4+S2)*x^4`, followed by the chain combine, multiply by `x`,
  and final add to `x`.  One shared boundary search independently reaches
  zero misses on both direct and both reduced standalone-FSIN halves.
- The selected schedule uses chop67 on the square, RN65 on the fourth power,
  chop67 on ordinary branch operations, RN64 on `+S1`, odd66 on `+S2`,
  chop64 on the terminal even-chain product, RN64 on the chain combine, and
  chop67 on the correction multiply.  It is exact on 257,052 standalone-FSIN
  and 21,894 standalone-FCOS sine-state mode observations.
- The same carrier schedule would introduce 43 paired-FSINCOS polynomial
  misses, so Round 42 changes only standalone FSIN/FCOS.  Exact C/Python
  parity covers all 278,946 promoted checks.  The complete sweep improves
  standalone FSIN from 74/72 to 62/62 mode/input misses and FCOS from 89/84
  to 74/74; paired FSINCOS remains 110/110.
- Fresh Debian build `/home/coduoserver/fsincos-round42-20260722001600`
  passes selftest.  C-source SHA-256 is
  `ea490009c5187dc15d1f8b492136000647b5d94ffd23e6f7d4e7c8212f033e88`;
  executable SHA-256 is
  `b430718b9f85a5768240f0b87308d4914ac9efbc604e16f26dd70fbe366fd465`.

## Round 43: shared-sine retained carrier

- h277 rejects treating the final scalar `odd67`/`away67` representatives as
  literal shared FMUL/FADD modes.  h278-h279 then show that an unconditional
  literal P5-style final FADD reaches only 521 of 730 frozen residual lanes.
- h280 propagates small retained-unit changes through the corrected graph.
  The final correction reaches 729/730 residual lanes and the complete
  shared-sine state reaches 719.  The dominant remaining error is therefore
  in the `a + P*a^3` carrier, not another polynomial term or table value.
- Refitting the old sub-ulp state proxy after h275 exposes one separable case.
  When the local residual has top exponent -5 and the sine-FADD operands have
  exponent difference 13, using 3/32 rather than 5/32 of a local ulp improves
  every frozen aggregate partition.  The old joint table objective changes
  738/500/730 -> 615/405/610.
- h285 independently generates 192 hardware-blind reduced-entry separators
  spanning all three wide cells, four quadrants, and both signs.  On the fresh Skylake
  capture, paired table mode/C1/input metrics improve 180/119/175 ->
  22/16/22.  Standalone and paired results agree on all 1,152 comparable
  lane/mode observations.  Input SHA-256 is
  `1115284a5e916e37b3cb93c498ac7d8ce4f7e80783590d6556faa437c060b879`.
- `--round43-p6-sine-bias` ports the conditional carrier representative.
  h289 proves exact C/Python parity on 1,091,982 lane/mode checks.  The
  structured master census improves FSIN 62 -> 53, FCOS 74 -> 63, and paired
  FSINCOS 110 -> 90 mode/input misses.
- Fresh Debian build
  `/home/coduoserver/fsincos-round43-20260722080000` passes selftest.
  C-source SHA-256 is
  `b5088d50dc5bae56bc4d163ed77269c47b4a2ff2b569a11546c9813422d8a753`;
  Executable SHA-256 is
  `1bfc1b714fa618355e1c462476d697333816dec569edb4fbe4f1600927e20fb2`.
  Round 43 remains a processor-output-equivalent carrier rule, not a claim
  that 3/32 and 5/32 are literal microcode rounding fields.

## Rounds 44--48: coordinate and fractional carrier refinement

- h292 adds 128 direct Round-43 separators and 128 entries at the next wide
  coordinate `(-6,15)`, where each coordinate is `(local top exponent,
  sine-FADD exponent difference)`.  Bias 3/32 reduces fresh result/C1 misses
  from 240/153 to 20/18 on the direct class and from 236/90 to 24/10 on the
  next class.
- h297 finds no route, quadrant, cell, retained-bit, guard/round/sticky, or
  literal-FADD-bus predicate that improves both h292 halves.  h298-h300 then
  scan the carrier itself.  The hardware-blind h301 boundary capture selects
  21/256 ulp as the highest non-regressing wide representative at `(-6,15)`.
- h306 and h312 repeat the coordinate scan on the complete narrow dense/sweep
  train/held corpus.  Three independently generated captures select 29/256 at
  `(-6,15)`, 30/256 at `(-8,19)`, and 34/256 at `(-7,17)`.  Their targeted
  candidate/baseline totals are 32/142 (h307), 4/64 (h314), and 24/40 (h320).
  Standalone and paired results agree on every comparable capture result.
- `--round44-p6-sine-bias` through
  `--round48-p6-narrow-sine-fraction` port the five physical leaves.  h323
  proves exact C/Python parity on 1,094,382 lane/mode checks.  The structured
  master census is FSIN 49, FCOS 57, and FSINCOS 80 mode/input misses, versus
  62/74/110 before the carrier pass.
- Fresh Debian build
  `/home/coduoserver/fsincos-round48-20260722094500` passes selftest.
  C-source SHA-256 is
  `9d13127282127db002e51be2754e38c6cbbcfcfc7745c2bcb27c93ab389d33ae`;
  executable SHA-256 is
  `e8411773dfbad341d0eb27796e98cc03c601e61500515e930a7851920fb44300`.
  These values are processor-output-equivalent carrier representatives, not
  decoded literal rounding controls.

## Round 49: carrier-interval multiply

- h326-h327 collapse all six Round-48 fractional proxies to one legal 67-bit
  numeric carrier, `RN64<<3 - 1`; there are zero exceptions in the 21,805
  structured points or the dense/fresh partitions.  The low carrier suffix is
  therefore interpreted at the immediately dependent multiply rather than as
  several stored sine values.
- h333 models the suffix as a half-open interval with RN64 as its common upper
  endpoint.  Selecting the retained product unit immediately below the upper
  chop67 result improves the structured paired objective from `80/40/80` to
  `13/10/13` and the dense objective from `632/377/627` to `101/63/96`, with
  zero component regression on either deterministic half.
- h334 is a disjoint gate.  On h307, h314, and h320 the candidate changes
  result/C1 misses `24/8 -> 0/0`, `2/2 -> 0/0`, and `18/6 -> 0/0`.
  h335 proves exact C/Python parity on 1,094,382 lane/mode checks.
- h336's complete structured hardware census is FSIN 15, FCOS 24, and
  FSINCOS 13 lane/mode misses, down from 49/57/80.  The remaining paired table
  set is 5 sine and 8 cosine lanes.  Standalone FSIN's 15 includes 10 reduced
  polynomial misses; standalone FCOS's 24 includes 16 direct/reduced
  polynomial misses, so those are separate from the table carrier result.
- h337-h345 test the next broad explanations.  A second RN64-to-FMUL interval,
  all uniform Q-Horner/terminal boundaries, direct 64--72-bit materialization
  of the exact sine FADD, and the complete P5-style FADD grammar at both final
  additions do not improve Round 49.  The decomposed-product pass h342
  reproduces Round 49 as a chopped upper product minus one odd-retained
  sub-ulp contribution.  Twelve of the final 13 lanes are reachable by an
  adjacent retained-unit choice; one reduced wide cell-52 cosine lane is not.
  The unresolved table behavior is now a rare carry/borrow detail in the model
  on the sine-producer bypass, not a missing polynomial, lookup word, or broad
  operation class.
- Fresh Debian build
  `/home/coduoserver/fsincos-round49-20260722113000` passes selftest.  C-source
  SHA-256 is
  `22f349e0e79eeb01899ccf6e3cebb027c31792753d56cbffd64255c82a6d9500`;
  executable SHA-256 is
  `7c77b81236a4407edc2b7bf55bae7ff23e3ceb337b068a0dc9796feeab8c5d4f`.

## Rounds 50--51: standalone FSIN operation replay

- The h347 adversarial capture contains 197,044 residual-neighborhood inputs.
  Round 49 has 798 paired mismatches in 1,182,264 lane/mode observations:
  474 sine and 324 cosine. Sign-normalized positive/negative neighborhoods
  are exact mirrors, and the failures remain sparse within each window.
- The independent h349 scan balances one million direct/reduced narrow/wide
  table inputs. Round 49 has 515 paired mismatches in 6,000,000 observations:
  205 sine and 310 cosine, affecting 506 inputs. A fixed +/-1 correction-unit
  change is not viable because the unchanged exact population dominates.
- A finite standalone-FSIN operation replay reduces the h347 residual subset
  from 474 output misses to four. The same ordinary arithmetic classes are
  exact on the existing 48,747-input structured interpreter corpus and the
  240,000-input dense corpus. The four new observations are one input
  magnitude and its sign mirror under RD/RU, localized to the FADD completing
  the table sine state.
- Round 50 ports the operation graph and shared class policy to C. Round 51
  selects the non-incrementing result at the exceptional retained-bit
  signature. Together they have zero standalone-FSIN result misses in
  1,461,246 structured, dense, and h347 RN/RD/RU observations. The
  structured census becomes FSIN/FCOS/FSINCOS `0/24/13`.
- Routing the same Round-51 sine state into paired FSINCOS changes h347 from
  798 to 794 mismatches, with no regression, and leaves h349 unchanged at
  515/6,000,000. The remaining paired residue is therefore not another
  standalone sine polynomial or broad arithmetic-class error. It must be
  sought in paired state reuse and the later cross-product/subtract/final-add
  sequence. P6 output parity remains unmeasured until P6 hardware is
  available again.
- A fresh Debian x86-64 build passes selftest. Source SHA-256 is
  `c8aa7491d3df09b75696fdd44b17474320c4e0af15df665da561632cde94407a`;
  executable SHA-256 is
  `af5f4950ea78f5f5d485ddd10e8e8ddf971614efd73a273a8079a62b921529c2`.

## Round 52: standalone FCOS terminal retained product

- Complete operation replay localizes the former 12 dense output and 18 C1
  differences to the terminal table product and its chopped add.  The first
  multiplier operand's low three bits supply a retained payload, activated by
  the discarded product prefix and shifted with exponent alignment.
- Two collision rules are required.  At distance ten with payload six, the
  other product's top discarded bit selects an aligned lane two units lower.
  At distance eight with payload seven and an equal aligned lane, a numerical
  upper-three-bit discarded prefix of at least three decrements the payload.
  The hardware-blind h388 discriminator independently selects the latter rule
  and is exact on 49,548 RN/RD/RU observations.
- The C model improves to 73 output differences in 150,114
  structured observations and 379 in 720,000 dense observations; the
  remaining gap includes older hand-model producers.
- Focused retained-state captures remain nonzero: h363 `2/2`, h372 `8/8`,
  h380 `22/28`, and h384 `72/100` output/C1 differences.  h389 and h391--h397
  separately reject right-tail, literal carry-save, preceding-square-tail,
  and distance-seven lane extensions.  Each failed rule collides on visible
  state while hardware chooses both outcomes.  h396 is excluded because its
  generator did not constrain inputs to the direct small path.
- `run_fcos_terminal_carrier_prebuilt.sh` packages every valid discriminator
  for compiler-free x86 capture.  P6 parity remains unmeasured; the rules above
  are established against the remote Skylake processor only.
- Fresh Debian x86-64 build
  `/home/coduoserver/fsincos-fcos-final-20260723033016` passes selftest.
  C-source SHA-256 is
  `9b540b4bbf03f217267c90a0b04978c8bfc4d8d07ad089c5bad4eed636dda3d5`;
  executable SHA-256 is
  `6ede31c1f480e9e6f0000944bf6c84f309bf858d356f917f60f60d2519c13ddf`.

## Round 53: complete standalone-FCOS operation-class C path

- Round 53 replaces the remaining standalone-FCOS hand-model producers with
  the complete polynomial/table operation schedule.  The cosine phase increment selects the correct sine/cosine
  branch, and Round 52 supplies the terminal direct-cosine carrier.
- One structured RN difference remains after the first port.  Its large
  negative input is the previously identified reciprocal-seed disagreement.
  Literal exact division by the 66-bit reduction constant selects the centered
  quotient and removes it.
- The C model now has zero output and zero derived-C1 differences, with no
  interval ambiguity, on 150,114 structured, 720,000 dense, 591,132 h347, and
  49,548 h388 FCOS observations.  It is also exact on h285, h292, h301, h307,
  h314, and h320.  These checks cover direct, table, reduced, all three rounding
  modes, and the former table/shared-sine residual neighborhoods.
- The hostile terminal-adder sets remain unchanged at h363 `2/2`, h372 `8/8`,
  h380 `22/28`, and h384 `72/100` output/C1 differences.  The operation-class
  port therefore closes the old C-model approximation gap without disguising
  the remaining physical retained-state problem.
- The exact quotient is shared with the standalone-FSIN operation-class path.
  Its h377 frozen binary64 fixture improves from 12 result/15 C1 differences
  to 3/4, while the structured and dense FSIN corpora remain exact.  All former
  exponent-58--62 h377 result cases are eliminated.
- Fresh Debian x86-64 build
  `/home/coduoserver/fsincos-fcos-round53-20260723040020` passes selftest.
  C-source SHA-256 is
  `00ca2b1cffb051eaa69c81dc30696b3afb9dd485957354e11eec5a25550844a3`;
  executable SHA-256 is
  `38af894a3460e3340749a1aeaa1f2b95adf4edc606e51778a49a019f1f399864`.

## Round 54: paired FSINCOS table lanes are the standalone instructions

- A direct hardware-vs-hardware comparison of the saved h347 per-instruction
  streams shows paired FSINCOS equal to standalone FSIN/FCOS on all
  1,182,264 lane/mode results, with the paired non-TOP status word equal to
  standalone FCOS's status on every input and mode (C1 tracks the cosine
  lane there).
- Fresh per-instruction Skylake captures of the canonical structured sweep
  and dense corpora under RN/RD/RU localize every paired-vs-standalone
  hardware difference to polynomial-path inputs, direct and reduced.
  Exact-rational reduction classifies all 266 structured differing
  lane/mode results as polynomial; every dense difference is in the e=-3
  binade with zero differences in the e=-2/-1 table binades.  Table-path
  and tiny results are identical everywhere.  The AMD Zen 3 dense capture
  shows paired equal to standalone on both lanes throughout, including the
  polynomial binade.
- Conclusion: Skylake paired FSINCOS shares the table datapath bit-exactly
  with the standalone instructions; only its polynomial datapath is
  paired-specific.  The paired model's remaining table residue
  (13 structured, 515 h349, 794 h347 lane/mode misses) was a model routing
  gap, not unknown silicon behavior.
- `--round54-fsincos-table-lanes` routes each paired lane's table-path
  input through the standalone operation-class core (sine lane as
  standalone FSIN, cosine lane as standalone FCOS); polynomial, tiny, and
  exact-zero-residual inputs keep the legacy paired model.  It requires
  Rounds 50 and 53 and is inert for the standalone entry points.
- Validation: zero result and C2-line differences on all four paired
  Skylake corpora — h347 (1,182,264), h349 (6,000,000), fresh structured
  sweep (300,228), and fresh dense (1,440,000) lane/mode observations;
  8,922,492 in total.  The pre-Round-54 baselines on the same corpora are
  794, 515, 13, and 101 misses.  With the flag off, batch output is
  byte-identical to the Round-53 model on h347, and the structured-sweep
  output is byte-identical before and after the comment-tag cleanup
  rebuild.  Selftest passes.
- Paired C1 is not yet modeled: on table paths the paired status word
  matches standalone FCOS exactly, but the fresh polynomial-path
  differences include status-only differences, so a paired C1 derivation
  remains open work.
- A separate order-dependence check re-captured the h363/h372/h380/h384
  standalone-FCOS terminal-adder sets in reversed and two seeded shuffled
  orders: zero per-input differences over 281,028 inputs by three modes by
  three alternate orderings.  FCOS outputs are strictly input-determined;
  microcode history effects are ruled out for the collision sets.
- Working tree `/home/coduoserver/fsincos-residual-20260807-1` holds the
  fresh per-instruction captures (`fresh/`), the shuffle captures
  (`shuffle/`), and the validation outputs (`out54/`).  C-source SHA-256 is
  `fccf6c2c2dd41fea6dbabb390588eb461c8cb40cbbd8cef143561873be35976b`;
  executable SHA-256 is
  `a6c0ddb38a985f5f15a6deae879f405cb462691d5587944ac8c9620be5f1e978`.

## Round 54 addendum: paired C1 derivation

- With Round-54 lane results as the value oracle, paired C1 equals the
  cosine-lane rounding-increment flag: C1 = 1 exactly when the delivered
  cosine differs from its toward-zero directed bound (RD bound for
  positive results, RU for negative), i.e. the standalone C1 convention
  applied to the last-pushed lane.
- The rule has zero differences on all 4,461,240 comparable paired
  RN/RD/RU observations: h347 (591,132), h349 (3,000,000), fresh
  structured sweep (150,108), fresh dense (720,000).  Sine-lane,
  OR/AND/XOR composites are each rejected by six- to seven-figure miss
  counts.
- The earlier paired-vs-standalone status differences on polynomial paths
  are fully explained: the paired cosine result itself differs there, so
  its increment flag differs from standalone FCOS's; the C1 rule is the
  same.
- Analysis script preserved as `experiments/h402_paired_c1_rule.py`.

## Round 55: retire the Round-51 sine-state signature (h405-h407)

- h404's triangulation left three standalone-FSIN residuals.  The
  exponent-7 seed (`c006:8a7da33ed97f1000`, reduced entry, even quadrant,
  narrow table path) sits at sine-FADD coordinate (-6,14).  A
  `--debug-sine-state` trace shows its operation-class sine-state FADD
  carries *exactly* the Round-51 carrier signature — exponent difference
  14, above-half remainder, retained low byte `0x8c`, remainder prefix
  `0xc1` — so the Round-51 leaf selects the non-incrementing sum there,
  while hardware keeps the ordinary RN64 result in all three modes.
- h406 re-scans h347, the structured sweep, and the dense corpus with and
  without the leaf under the current flag stack: zero inputs depend on it.
  Round 51's four original observations were large-argument cases whose
  reduced residuals changed under Round 53's exact-division quotient; the
  leaf has been dead on every promoted corpus since, and the only known
  input it now fires on is the h377 seed it breaks.
- Round 55 therefore retires the leaf: the operation-class sine-state FADD
  is RN64 everywhere on current evidence.  `--round51-fsin-fadd-signature`
  is still accepted but inert in the operation-class path; the legacy
  pre-Round-50 kernel keeps its historical materialization branch.
- h407 revalidates the retired-leaf source with the standard shipping
  flag sets on every hardware corpus: standalone FSIN and FCOS and paired
  FSINCOS are all exact — 0 misses on h347, h349 (paired), the fresh
  structured sweep, and the fresh dense corpus, all modes and lanes.
  Selftest passes.
- The h377 fixture improves from 3 result/4 C1 to 2 result/3 C1
  differences; the gate baseline is updated.  The two remaining seeds
  (exponents 27 and 29) are reduced odd-quadrant internal-cosine
  polynomial cases whose model state is a sub-ulp high; the h405 +-3000
  windows add one more standalone family member each (offsets -848, -689)
  and expose one pre-existing paired-polynomial cosine residual
  (`c01c` window offset +716, RD), which the retirement does not affect.
- Scripts: `experiments/h405_windows.sh` (window captures/census),
  `experiments/h406_round51_census.sh` (dependence census),
  `experiments/h407_final_validation.sh` (full revalidation).
- Post-documentation build: gate `--expect-baseline` passes at 2/3.
  C-source SHA-256 is
  `c4e5a09f8f5c1eb6c5b273f2789a9b2351d6e2c7edfefd456b0b0126ad01f78f`;
  executable SHA-256 is
  `b0ef5975710b01fcfcb51040c5d3c9efd71fad69d7293401705687538435ea00`.
  The `2^32` sibling extensions were still running at write time; their
  summaries land in `fsincos-residual-20260807-1/h403/sibling_*_32.log`.

## Round 56: shared terminal carrier for FSIN's internal cosine (h408-h410)

- Hypothesis h408: FSIN's odd-quadrant internal cosine runs on the same
  physical cosine kernel as standalone FCOS, so the Round-52 terminal
  low-three-bit carrier must apply there too.  The operation-class model
  previously enabled that carrier only for the FCOS phase.
- Applying the carrier to the internal-cosine branch fixes three of the
  four known internal-cosine residual observations — the h377 exponent-27
  seed (RD) and both h405 window members (offsets -848 RN and -689 RD) —
  with zero regression on the h347/structured/dense FSIN corpora.
- h409 hardware-blind separator validation: of 400,000 deterministic
  candidates across exponents 2..62, exactly two inputs separate the
  with/without-carrier models.  Fresh Skylake capture scores
  baseline 2 / carrier 0 result misses on their six mode observations.
- The rule is ported as `--round56-fsin-cosine-carrier` (implies the
  Round-52 carrier machinery).  The h377 fixture improves from
  2 result/3 C1 to 1 result/2 C1; the gate baseline is updated.
- The sole surviving h377 input is the exponent-29 seed
  (`c01c:ccb8a935dddf4000`, RD result plus RN/RU C1).  Its terminal state
  sits in the same rare retained-carry collision family as the
  unresolved FCOS h363/h372/h380/h384 sets; with the Round-56 transfer
  established, that family is now a single shared open problem rather
  than two separate ones.
- Scripts: `experiments/h409_blind_separators.sh`,
  `experiments/h410_round56_validation.sh`.
- h410 final revalidation: standalone FSIN (with Round 56), standalone
  FCOS, and paired FSINCOS all score zero result misses on h347, h349
  (paired), the fresh structured sweep, and the fresh dense corpus; the
  h405 windows retain only the exponent-29 observation and the h409
  separators are exact.  Gate `--expect-baseline` passes at 1/2.
  C-source SHA-256 is
  `cb68d8537e3c2a462f3331999504d66c7fc71876a5bac198f58dae45432a36b2`;
  executable SHA-256 is
  `6652be7f2ddcb69f8f633668acff4f4cc0b89ee5bff61f66edfae64f42a5f91a`.

## h411-h421: retained-carry family characterization (no port)

A systematic pass over the four hostile FCOS terminal-adder sets with the
Round-56 model (numbers unchanged: 2/8/22/72 result misses on 281,028
inputs) establishes:

- A `--debug-cosine-carrier` full-state trace at the Round-52 terminal
  correction has **zero collision groups**: no two inputs with identical
  traced state have different hardware outcomes (140,514 distinct states).
  The earlier "hardware chooses both outcomes" reports were artifacts of
  narrower candidate features; a deterministic rule over (or upstream of)
  this state exists.
- Offline exact reconstruction of the correction and final add is
  bit-faithful to the C model on all 671,574 active observations.
- Every one of the 104 misses is explained by a small payload
  perturbation that reproduces hardware in **all three modes
  simultaneously**; no miss needs a non-payload mechanism.  Miss support
  is exactly the near-collision zone |aligned-lane-byte - payload| <= 2,
  with mixed directions (both increments and decrements).  The two ported
  Round-52 collision sub-rules are two cells of this family.
- Negative results, each scored against all active rows: a carry-dropped
  8-bit payload lane at the sum byte (fixes 18, breaks 644); OR-merge
  into the right product's aligned byte, and OR/XOR-merge into the
  accumulator byte (each fixes 76 of 104, breaks ~770).  The
  carry-suppressed merge direction is clearly implicated but must be
  gated by an enabling condition invisible in the terminal state.
- Feasibility search over allowed-delta sets: no consistent rule exists
  over 17 fine features (distance, low3, lane diff, discarded prefixes,
  operand low bits, signs, parities) up to depth-6 partitions; three
  cells remain contradictory.  The enabling condition therefore lives
  upstream of the terminal correction (product materialization or a
  physical selector), confirming and sharpening the h211-h225
  conclusion.
- Decisive next experiments: a constructed truth-table capture that
  sweeps only upstream discarded bits at one near-collision cell, and a
  retired-uop/timing side-channel comparison of miss-versus-matched
  inputs (residual-ideas idea 2).
- Datasets and scripts: `experiments/h411_hostile_rescore.sh` (note the
  miss files carry the input as two tokens),
  `h412_trace_collect.sh`, and `h413`-`h421` analysis scripts; traces in
  the remote workdir `fsincos-residual-20260807-1/h41[12]/`.

## h422-h424: informative-corpus pass on the retained-carry family

- h422 constructs a fresh hardware-blind corpus: 4,000,000 random direct
  e=-3 FCOS inputs traced through the model, filtered (model-only) to the
  541 boundary-sensitive near-collision rows, then captured under
  RN/RD/RU.  This multiplies the family's informative data by ~3.4x over
  the hostile sets.
- h423/h424 classify each row against candidate micro-behaviors, scoring
  all three modes jointly: 287 rows are consistent with both the
  arithmetic payload add and the carry-suppressed merge; 181 are
  add-only; 46 are merge-only; 27 match neither.  Every neither-row is
  consistent with the payload rising to at least the aligned lane byte
  (deltas >= diff at diff=+1/+2) — the same "payload <- lane" capture
  pattern as the first ported Round-52 collision rule.  A direct
  payload-vs-lane substitution test finds 33 lane-only and 189
  payload-only rows, interleaved within single (diff, distance, low3)
  cells.
- Conclusion: at the near-collision states the silicon exhibits at least
  three reachable micro-behaviors — arithmetic add, carry-suppressed
  merge, and lane capture — whose selection is not predicted by any
  output-derived feature tried (terminal state, discarded prefixes,
  operand low bits, square/fourth discarded fields).  This reproduces
  and sharpens the h211-h225 reachability-without-identifiability
  result on independent fresh data.  The gate is physical state that
  output bits do not expose; the recommended next probe is the
  residual-ideas idea-2 side channel (retired-uop or latency
  distributions on behavior-classified input pairs), which observes the
  executed path rather than its numeric shadow.
- Corpus: `h422/selected_inputs.txt` + traces + RN/RD/RU captures in the
  remote workdir and mirrored to
  `capture-kit-captures/skylake-fcos-h422/`.  Scripts h422-h424.

## h425: side-channel probe of the collision-family gate (negative on VM)

- Behavior-classified h422 rows (181 add / 46 merge / 27 lane / 100
  control) were timed with the capture kit's min-of-N serialized rdtsc
  probe (999 samples/input, taskset-pinned, game servers left running).
  Per-input minima are highly repeatable (median inter-run delta 0
  cycles; all inputs ~278 cycles).
- Separate per-class runs suggested merge/lane rows avoid a ~160-200
  cycle "fast band", but a fully interleaved shuffled rerun shows the
  fast dips are time-clustered measurement artifacts distributed
  uniformly across classes (12%/9%/11%/11%): the apparent separation was
  a run-order confound.  Methodology note: class-vs-class timing on this
  host is only valid input-interleaved.
- The KVM guest exposes no PMU (`perf stat` reports instructions/cycles
  unsupported), so the retired-uop variant is impossible here.  Both
  side channels are closed on this VM; the experiment requires bare
  metal, which the capture kit's static runners already support.  The
  gate for the three interleaved micro-behaviors (h422-h424) remains
  unobserved; bare-metal timing/PMU capture on a physical Skylake (or
  the Pentium II witness) is the next decisive step.
- Scripts: `experiments/h425_timing_probe.sh`; class files and timing
  runs in the remote workdir `fsincos-residual-20260807-1/h425/`.

## h426: bare-metal PMU probe (i7-6700, Skylake client)

- A rented bare-metal i7-6700 (no hypervisor, full PMU incl. idq.ms_uops)
  reproduces the Xeon corpus **byte-identically**: all 541 classified
  h422 inputs match under RN/RD/RU.  The collision-family behavior is
  therefore stable across Skylake server/client steppings, and the
  machine is a valid oracle.  Runner: /root/x87_capture_x86_64,
  workdir /root/h426 (class files, captures, h426_res.pkl).
- First per-input idq.ms_uops pass (perf around the batch runner,
  20k reps/input): class medians are indistinguishable (~316.5 +-5),
  but harness I/O dominates (~250 of ~316 uops), leaving sensitivity
  far above a plausible 1-2 uop path difference.  Inconclusive, not
  negative.
- Next step (ready to run): a minimal C loop executing only FCOS on a
  preloaded register value, perf-counting idq.ms_uops and cycles per
  input with zero I/O in the measured window — expected noise well
  below one uop.  If the gate is a microcode branch it will be directly
  visible there; if counts stay identical, the gate is sub-uop
  (within-FADD physical state) and the die-photo/patent route for the
  adder structure becomes the remaining path.

## h427: pure-FCOS PMU measurement — the gate is sub-uop

- A minimal bare-metal harness (fldt/fcos/fstpl loop, no I/O in the
  window; 200k reps/input; /root/h427.c on the i7-6700) measures
  idq.ms_uops and cycles per FCOS to ~0.05-uop / ~1-cycle resolution.
- Every one of the 354 classified inputs executes an identical
  ~159.58 ms_uops in a median ~118.8 cycles, with add/merge/lane/control
  class distributions overlapping completely (total spread 0.15 uop).
- Conclusion: the micro-behavior selection involves NO microcode branch
  and NO latency difference — the gate is combinational, sub-uop state
  inside the arithmetic datapath itself (the terminal FADD/FMUL carry
  structure).  Every software-observable channel is now exhausted:
  results, C1, uop counts, latency.  The remaining routes are physical
  structure (die-photo/patent recovery of the P6/Skylake FADD carry-save
  and block-carry organization) or gate-level parameterized SAT over the
  h422 corpus constraints.  Results: /root/h426/h427_res.pkl.

## h428: parametric adder search on the bare-metal i7 (in progress)

- The i7-6700 is the new search host (/root/search) with the complete
  labeled corpus: 224,399 active rows (hostile sets + h422), baseline
  177 violations for the current model.
- Family 1, stale-block-carry / block-wrapped payload injection
  (W in 4..64, all phases, two scopes): wide blocks tie the baseline at
  177 exactly (boundary above the payload — degenerate to plain add);
  every narrow-block variant scores worse.  Family eliminated.
- Family 2, borrow-in-gated lane capture: the borrow into the payload
  byte from the low bits of the subtract does not separate lane-capture
  from payload rows (both populations at every (diff, borrow) cell).
  Eliminated as a standalone gate.
- Framework ready for the next families: gates over subtract-internal
  carry-run structure, the 9-bit lane window, recomputed
  product-generation state, and full boolean-synthesis (CEGIS) over
  ~30 binary datapath signals constrained by the 765 informative rows.

## h429-h431: boolean-gate synthesis stages A/B (local, no gate yet)

- Stage A database: 224,399 rows, each with a mechanism-consistency
  bitmask over {add, payload+-1..6, lane-capture, OR/XOR-merge} and
  physical signals.  Every row has at least one consistent mechanism
  (the vocabulary is complete), 177 informative rows, and ALL
  informative rows lie inside |lane-payload| <= 3; zero non-add rows
  outside the zone.  The phenomenon is provably confined.
- Stage B v1 (25 signals, depth 8): no consistent gate.
- Stage B v2 (enriched: full top-16 discarded-field windows of both
  terminal products recomputed exactly from traced operands, lane
  overflow bits, operand low bytes; zone-restricted, depth 10,
  beam 4): no consistent gate.  The hardest conflict cell shrinks
  2825 -> 711 -> 229 -> 75 rows with depth but never resolves —
  conflicts subdivide indefinitely, the signature of missing gate
  inputs rather than a wrong mechanism vocabulary.
- Not yet exhausted (next stages): (1) complete discarded fields and
  deeper windows; (2) arithmetic-comparison predicates (multi-bit
  magnitude compares, wrap conditions) that bit-threshold trees cannot
  express compactly; (3) exact upstream Horner-chain internal state
  recomputed from ROM constants; (4) complete SAT-based synthesis in
  place of greedy trees; (5) the aliasing hypothesis — that the
  apparent payload adjustment is really an upstream product-carrier
  difference, testable by inverting at the product level instead.
- Scripts: h429_stageA.py, h430_stageB.py, h431_enriched.py
  (experiments/); database regenerable locally in seconds.

## h432-h435: ALIASING REFRAME — the gate is at product generation

- h432 comparator-predicate synthesis (42 features incl. magnitude
  compares and wrap conditions): no terminal gate through depth 9+
  (depth-11 run pending at write time), conflict mass shrinking but
  never resolving — consistent with the gate not being terminal at all.
- h433 product-level inversion: ALL 177 informative rows are explained
  by a +-1 retained-unit perturbation of a SINGLE terminal product,
  in two families: ~131 right-product-up rows (R+1 / R_rn / R_aw / R_od
  all consistent) and ~46 left-product-up rows.  h434 rejects every
  uniform rounding combination (L,R in {chop,rn,aw,od}^2; best is the
  chop/chop baseline at 177) — the increment is conditional.
- h435 learns per-product increment gates over PRODUCT-LOCAL features
  only (discarded-field width/half/sticky/top8, retained low3, operand
  low3s): **G_R is fully separable — zero conflicting feature vectors**
  between 86 must-fire and 220 must-not rows; G_L has a single
  conflicting vector (3 rows), expected to dissolve when G_R-explained
  rows are removed from its must-fire set.  The twelve-year mystery
  reduces to extracting two compact boolean gates over a product's own
  generation state — exactly the shape of every previously ported
  carrier rule.
- Next: extract compact G_R/G_L predicates, exclude-overlap relabel,
  hardware-blind Stage-C validation on the i7 oracle with fresh
  constructed inputs, then port as Round 57.  Scripts
  h432_comparators.py, h433_aliasing.py, h434_uniform.py,
  h435_product_gates.py (experiments/).

## h439-h440: corpus-2 and the basis verdict

- h440 built corpus-2 on the bare-metal i7: 8,000,000 traced e=-3
  candidates filtered (model-only) to 57,863 product-boundary-sensitive
  rows, captured under RN/RD/RU on its verified-exact silicon.  Fire
  rows roughly double (G_R 56->111 vectors, G_L 41->103); negatives for
  G_L grow to 59,439 vectors.  Labels remain PERFECTLY separable —
  zero fire/nofire conflicts — so the conditional product increment is
  deterministic over product-generation state.
- Espresso-style minimization over the merged corpus is the formal
  basis verdict: G_R's irredundant cover GROWS with data (24 -> 51
  cubes) and G_L degenerates to one prime cube per fire vector
  (102 cubes of 10-15 literals).  Memorization scaling proves the
  current literal basis (discarded top-16, retained low byte, operand
  low-3s, half/sticky aggregates) is NOT the basis the hardware gate
  reads.  One robust G_R core persists: kept_bit3 conjunctions
  (2-literal cube clean against all 287 negatives).
- Next basis, in order of physical plausibility for a multiplier-output
  artifact: (1) Booth-recoding digits of both 67-bit operands at each
  radix-4/radix-8 position (the P5 patents' multiplier structure);
  (2) the complete discarded field (all ~67 bits, not top-16);
  (3) carry-save partial-product column sums near the chop boundary.
  The labeling machinery, 58k-row corpus, and second-corpus pipeline
  make each new basis a one-script, minutes-scale test.
- Scripts: h436-h440 + corpus2_filter.py (experiments/); corpus-2
  mirrored on the i7 at /root/corpus2/.

## h441-h453: THE SINGLE-BORROW-BIT REFRAME — observable structure solved,
## computational hypothesis space exhausted

This campaign (2026-08-09, local analysis over /tmp/stageA) replaced the
"conditional product-increment gate" framing with an exact
characterization of what the hardware data can even express, then
eliminated every arithmetic-pipeline hypothesis family reachable from
the traced state.

Structure results (positive):

- h441: the truncated-Booth-array family (radix 2/4/8, either operand
  recoded, truncation column 40..69, correction bits dropped/lumped/
  kept, constant compensation 0..6 half-units) is ELIMINATED: no config
  beats never-fire; low truncation columns are invisible at the
  retained-unit scale and aggressive ones fire on the wrong rows.
- h442/h443: every fire row lives in the payload-active regime
  (lsign=1, rsign=0, active=1, dist 7-10) and every fire is equally
  explained by a small payload adjustment: fire_R rows by payload-1 at
  aligned-lane difference ~0, fire_L rows by payload+1 at difference
  ~+1/+2.  The two ported Round-52 collision patches are two cells of
  this single family (their pre-images unify after rewinding the
  patches).  Operand-level increments (rf+1 for ALL fire_R; mul+1 ==
  ls+1 for ALL fire_L) are aliases of the same observable.
- h444/h445: rewinding to pre-patch payload and probing offsets in
  [-3,3] shows every informative row's allowed-offset set is a
  HALF-LINE split at the row's chop-boundary crossing.  h446 probes
  [-8,8] and finds ZERO non-half-line rows across all 282,262 active
  observations.  Therefore each informative row constrains exactly ONE
  BIT: on which side of a retention-boundary crossing the hardware's
  effective payload lies (equivalently, the borrow/carry outcome at the
  terminal subtract's low unit).  The historical add/carry-suppressed-
  merge/lane-capture trichotomy (h422-h424) collapses into this bit —
  the three "micro-behaviors" were value-level over-parameterizations
  of one under-determined observable.
- Corpus totals in this framing: 4,180 constrained rows, 310 fires
  (model on the wrong side), boundary offsets theta confined to
  [-2,+2]; equivalently the hardware payload deviation delta lies in
  (-3,+3) and P(delta>=0) falls monotonically with prepay=low3+8-dist
  (h448).  At theta=0 (exact ties: accumulator discarded field exactly
  zero) hardware resolves DOWN on 182 of 514 rows — a strict
  1-lowest-unit deficit relative to exact arithmetic; at theta=+1
  (discarded all-ones) it resolves UP on 82 of 452.  The phenomenon is
  a +-1..2 lowest-unit error in the terminal subtract, visible only
  when the discarded field is within 2 units of all-zeros/all-ones.

Eliminations (each scored against all 282,262 rows, all three modes):

- h447: guard bits on the terminal products into the accumulator:
  g=1 already breaks 17,474 rows (baseline 310).  The accumulator
  consumes EXACTLY chop-67 products.
- h449: the payload is NOT a discarded-bits correction: replacing it by
  the exact (or floor/round/ceil) product-chop corrections, or removing
  it with full-width products, breaks ~33,000 rows.  low3+8-dist is the
  right magnitude; the deviation is genuinely small.
- h450: m (the reduced operand) is UNIQUELY recoverable from the traced
  square via integer sqrt (0 failures on 282k rows) — new primitive.
  The square's own discarded fraction does not threshold-separate
  sign(delta) (8/23 cells clean, rest mixed).
- h451/h452: fourth-power-path variants (true m^4, square guard bits
  k=1..12/full into the squaring, chop/RN combinations): all worse than
  baseline (best 370 vs 310).
- h453: full-pipeline Python replica from recovered m (constants
  P5C6_1..6, chain products chop67, chain adds RN64) validates
  bit-exactly against every traced field on 271,753 rows (the ~10.5k
  remainder are a second input family, likely the 4-term P5C4 path;
  they hold only 4 of the 310 fires).  Chain-construction variants
  (fused adds consuming the unchopped product, product widths 68-71,
  sticky-augmented RN64) are IDENTICAL to baseline on every validated
  row — the chains never sit at a double-rounding-sensitive state in
  these corpora — and add-width changes break tens of thousands.  The
  chain hypothesis class is eliminated.

Verdict: every computational hypothesis expressible over the traced
state and its exact upstream reconstruction now reproduces either the
baseline (with its 310 fires) or worse.  Combined with h427 (identical
uop counts and latency), the deciding state for the borrow bit is
physical carry-structure inside the terminal subtract, not an
alternative rounding/width/recoding rule.  The productive residual
formulation for the next pass: predict one bit per constrained row
(310 flips / 3,870 non-flips) from adder-physical signals — the exact
bit-vectors entering the subtract at each alignment, block-boundary
positions, and carry-run lengths, including intermediates of the SAME
instruction's earlier steps (stale-carry candidates from the replica's
chain adds and product normalizations, now all computable per row via
h453's validated replica).
- Scripts: h441-h453 (experiments/), datasets h446_zone.pkl,
  h448_constraints.pkl (regenerable in minutes from /tmp/stageA).

## h454: same-instruction stale-carry candidates — negative

- Using the h453 replica, every guard/sticky/round-up bit of the four
  chain adds and four product chops, plus operand nibbles and carry-run
  lengths at the terminal subtract, was scanned against the fire bit
  (2,447 zone rows, 303 fires with validated replica states): every
  single feature and every (theta x feature) pair sits at baseline
  inseparability (theta x B_low4 at 266/303 is the only mild signal,
  i.e. the already-known lane structure).  The borrow flip is not
  latched rounding state from the same instruction's earlier steps.
- With h441-h453 this closes every numeric-basis family: the deciding
  state is either a wide arithmetic comparison no scanned basis can
  express compactly, or physical carry structure below the numeric
  abstraction.  Decisive next probes: (1) exact SAT/CEGIS over raw
  aligned operand bit-vectors near the boundary (2,447-row constraint
  set, now small enough for exact synthesis); (2) the constructed
  truth-table hardware capture from the h422 plan — sweep one upstream
  bit at a time around fixed near-collision terminal states on the
  bare-metal i7, observing which input bits flip the borrow.
- Script: h454_stale_carry.py; dataset h454_rows.pkl.

## h458: direction-1 exact synthesis with held-out validation — formal
## memorization proof

- The zone constraint set (2,526 rows, 310 fires) was split in half by
  a deterministic input hash; an espresso prime-cube cover synthesized
  on the train half over 37 raw literals (ls low byte, rs low 16 bits,
  payload nibble, theta, dist, low3, b_model) needs 71 cubes and
  transfers at CHANCE level to the test half (77/156 fires caught,
  209/1107 false fires).  A parametric wide-compare sweep
  [(rs>>u) mod 2^k >= (ls>>v) mod 2^k + c], optionally theta-gated,
  never beats the never-fire baseline.
- This upgrades every prior "cover grows with data" verdict to a formal
  one: the borrow bit is NOT a function of the terminal subtract's
  numeric operand bits.  The deciding inputs are physically upstream of
  the terminal operands while remaining deterministic per input —
  observable only by the constructed truth-table capture (h455/h456).
- Script: h458_exact_synthesis.py.

## h456-h463: the constructed truth-table capture and the
## context-independence proof suite

The truth-table campaign ran on the bare-metal i7 (microcode 0xf0 after
the 2026-08-08 reboot; corpus2 re-validated byte-identically under it).
Package: all 3,455 constrained unique inputs (reconstructed from traces
via isqrt m-recovery + chain-validated exponents; reconstruction checked
0-mismatch against corpus2's original input file) plus all 63
significand single-bit-flip neighbors each — 221,120 inputs, RN/RD/RU.

Primary results:

- Replication: every genuine corpus fire re-fired; the full corpus2
  stream replays BYTE-FOR-BYTE across separate runner invocations
  (h461: 0 differing lines in 57,863 x 3 modes).
- Truth table: NO single-bit flip preserves fire-ness — 0 fires among
  all 15,687 neighbors of fire inputs.  Expected from the boundary
  confinement (any input perturbation moves the terminal accumulator
  thousands of payload units); per-input-bit truth tables cannot see
  the gate.  Six FRESH fires appeared among control neighbors
  (h456_package/fresh_fires.tsv) — new family members found
  hardware-blind; they enlarge the fire corpus to 249 distinct inputs
  (243 base + 6).
- A transient "cross-run drift" hypothesis (15 fires lost / 9 gained
  vs the corpus labels) dissolved on inspection: the flipped rows are
  exactly the PATCH-ACTIVE rows — h455 labels fires in pre-patch
  payload coordinates (deliberately rewinding the two ported Round-52
  patches), while the fire statistic compares hardware against the
  post-patch model.  All 8 corpus2-sourced flipped rows carry the
  dist8/low3=7 or dist10/low3=6 patch signature; hardware is exact on
  them under the patched model.  The 9 reverse flips are the patch
  misfire rows already inside the model's residual.  Hardware never
  changed.
- Context-independence proof suite (all direct, controlled, on-silicon
  experiments — each negative and decisive):
    h459  32-way predecessor panel [N,N,P,X]: outcome identical under
          every predecessor, including exact corpus predecessors —
          fires and non-fires alike (0/48 probes vary);
    h460  core sweep (all 4 physical cores) and frequency pinning
          (800 MHz and 4.0 GHz): fire sets IDENTICAL (243) in all 7
          conditions — timing-marginality rejected with a 5x clock
          margin;
    h462  current-sign forcing, predecessor-sign forcing, 8- and
          32-deep exact signed context replays: no effect;
    h463  corpus-prefix bisection (fresh invocation per prefix length
          K in {0..14,500}): outcome flat in K.
  Together: the collision-family behavior is fully deterministic,
  per-input, combinational, and independent of execution context, sign
  context, core, frequency, and run — closing the "physical
  state that output bits do not expose" escape hatch (h422-h427) with
  affirmative evidence.  h413's determinism conclusion stands in the
  strongest possible form.

Consequence for the search: the gate IS a per-input combinational
function after all; no basis tried expresses it compactly (h458's
held-out-transfer methodology is the standard going forward), and
input-bit perturbation cannot isolate its support.  The remaining
identification routes are (a) model-filtered constructed input FAMILIES
that hold the terminal state's visible cell fixed while sweeping one
upstream quantity (in-zone by construction, unlike raw bit flips), fed
by the now-249-strong fire corpus, and (b) the structural route
(die-photo/patent adder recovery, exact SAT over adder bit-vectors).
- Scripts: h455-h463 (experiments/); packages under /tmp/stageA/
  h456_package, h459_package, h460_package, h462_package; remote runs
  under /root/h456..h463 on the i7.

## h464-h468: cell-matched families — the corpus breaks open

- h464 pipeline (i7): 96M random positive e=-3 candidates in 8 parallel
  shards streamed through the model tracer into a validated arithmetic
  zone filter (theta computed in closed form, 1557/1557 agreement with
  the probe on corpus2; candidate/trace pairing self-checked per kept
  row via chop67(m^2)==mul).  Yield: 29,865 near-boundary rows, all
  captured RN/RD/RU.  Total labeled corpus now 19,962 constrained
  unique inputs (|theta|<=3), 2,186 fires — 8x the second-pass corpus.
  Both fire codings agree in-zone except on patch rows, as designed.
- h465 contrast ladder (nested exact matching): at L2 — rows matched on
  (dist, low3, theta, payload, ud, rud, lane byte, u5d) — 872 groups
  contain BOTH fire and no-fire rows (2,995 contrast pairs) with ample
  collision mass: matched-pair PROOF that lane-level terminal state
  does not determine the borrow bit.  One golden pair survives matching
  through rs_low16+ls_low8 (L3).  Beyond L3 exact matching is
  statistically unreachable (terminal state injective in m).
- h466 paired-difference mining over the L2 pairs (cell confounds
  cancel within pairs; scores reported per held-out half): FIRST
  REPLICATED GATE-INPUT SIGNAL of the campaign — the right product's
  discarded-field top byte rdisc_hi8 (z=+4.4/+5.1 pooled), plus a
  secondary in p4_g.  h467 direction split: z=+20.9 on down-fires,
  z=-15.6 on up-fires — large right-product discarded pushes hardware
  to the LOW side, exactly the rs+1 alias direction; the mirror
  appears as an ldisc~0 band boosting up-fires 0.08->0.22.  Response is
  SOFT (no clean threshold): these summaries correlate with the gate's
  true inputs.
- h468 greedy held-out lookup: (theta, rs low nibble, payload, rud)
  drives held-out logloss 0.351 -> 0.203 with excellent calibration
  and near-deterministic tails (band <0.1: rate 0.006; band >0.9: rate
  0.971 on held-out data).  rs bit 3 sits inside rs_nib0 — h439's
  surviving kept_bit3 core, now explained as part of a real structure.
  Middle bands remain mixed: more state still missing, but for the
  first time the fires are substantially predictable under the
  mandatory held-out discipline.
- Scripts: h464_zone_filter.py, h464_run.sh, h465_label_contrast.py,
  h466_paired_mining.py, h467_rdisc_rule.py, h468_greedy_lookup.py;
  datasets h464_package/{selected.tsv,labels.tsv} (TSV, no pickle).

## h469: hardware-blind validation of the h468 structure — PASSED

- A second fresh 96M-candidate batch (new seeds) yielded 29,782 zone
  rows; predictions from the (theta, rs low nibble, payload, rud)
  lookup (trained on the h464 corpus only) were computed and locked to
  disk from model-side state BEFORE any fresh hardware file was read.
- Scored on 28,166 classifiable fresh rows (1,964 fires): FIRE calls
  92.4 percent precise (146/158, 13x lift over the 7 percent base),
  CLEAN calls 0.08 percent leakage (8/10,584), and the locked
  probability bands reproduce monotonically (0.007 / 0.016 / 0.27 /
  0.38 / 0.61 / 0.62 / 0.69 / 0.79 / 0.92).
- Status: the discovered inputs are genuine and predictive under the
  full blind discipline, but the rule is NOT yet deterministic (middle
  bands remain mixed) — so no Round-57 port yet; a port requires an
  exact rule.  The labeled corpus now stands at ~48k constrained rows
  / ~4.2k fires across both batches.
- Next: close the middle bands — greedy/espresso over finer literals
  (rs full low byte, rdisc/ldisc top bits, u5d, lane bits, p4_g)
  WITHIN the established (theta, rs_nib0, payload, rud) frame, using
  both batches with held-out transfer; targeted generation into
  mid-band keys if data-starved; then re-run the blind protocol, and
  only on a deterministic rule proceed to Round 57 (h410 regression +
  h377 gate).
- Scripts: h469_blind_predict.py / h469_blind_score.py; packages
  h469_package/{selected.tsv,predictions.tsv,hw_*.txt}.

## h470-h475: frame refinement, mid-cell mining, and the increment-
## placement test

- h470 merged both family batches: 37,951 constrained unique rows,
  4,150 fires (pre coding).
- h471/h472: the subtractor-local difference (rs - payload) is
  theta-redundant in-zone (A = ls<<8 forces diff = theta mod 2^k for
  dist<=8) — the effective validated frame is (theta, rud, dist, low3)
  plus rdisc's top three bits, which the greedy selects first every
  time (held-out logloss 0.185 -> 0.144).  Determinism profile: 69
  percent of held-out rows in a <0.02 band (rate 0.001), 2 percent
  >0.9 (rate 0.94), and a persistent ~29 percent mid band at rate 0.31
  concentrated at dist=8, theta in {0,1}.
- h473 paired mining INSIDE the mid cells (32,957 pairs matched on
  theta/rud/low3/rdisc-top-3): four replicated signals — rs bits 4..11
  (z +6.8/+4.8), the even chain's first product guard p3_g
  (+4.6/+5.2), lf low byte (-6.2/-3.8), p2_g (-3.9/-3.4).  Upstream
  chain rounding states demonstrably reach the terminal borrow.
- h475 (user lead: two's-complement increment placement).  Parametric
  grid over where the subtract's +1 enters: single-subtract form with
  the ~B increment merged into the payload CSA row (slots 0-10,
  OR/XOR/ADD semantics) and nested form (B-P inner, A-T outer, per-
  stage slots), scored pre-patch on 341,909 rows.  NO exact variant.
  Best: F1/or/slot0 (increment lost when payload odd) fixes 561 fires
  but breaks 922 clean rows.  The nested-outer family degenerates at
  ties: T = B-P = 0 mod 256 there, every low slot is occupied, so it
  predicts a deficit on EVERY tie row while hardware fires on ~35
  percent — and at a tie any deficit in (0, 2^shift) yields the same
  retained value, making all its slots/semantics exactly equivalent
  (verified, not a bug).  VERDICT: pure increment-slot collision is
  rejected as the mechanism; its surviving insight is that the
  tie-deficit signature is increment-loss-like, with the loss
  CONDITION being the actual gate, reading the h473 state (rdisc top
  bits, rs mid bits, chain guards).
- Status: best validated predictor remains the h468/h472 lookup
  (blind-validated 92 percent FIRE precision); the rule is not yet
  deterministic, so nothing is ported.
- Scripts: h470_merge_labels.py .. h475_increment_slot.py; datasets
  h464_package/{combined_labels.tsv,augmented_labels.tsv}.

## Round 57: the standalone-FCOS terminal borrow rule (h476-h612)

The h476-h608 experiments
characterized the last standalone-FCOS residual — the +-1 near-boundary
deviations of the terminal subtract — to a hardware-blind-validated
predictive rule, and then PROVED its constants underivable from every
enumerable architectural mechanism class (value forms h607; word/bit
grouping-tree states h608; the schedule-dependence results h488/h594).
The 2026-08-10 "do not port" decision was explicitly REVERSED by the
user on 2026-08-12 in light of those closure results: the rule is
ported as the honest empirical characterization — a fitted surface,
not a derived circuit — and documented as such.

THE RULE (EU frame, h536/h598/h606): result = EU + req2 where EU is
the unchopped-exact terminal value (right product at full width),
req2(j) = floor((4*Vlow - j*rfv)/2^(kf+2)), and the selector
j = round(q*tau + a*mf + b + c(zone, state)) uses per-(stratum-side,
XD12[, mf16]) zone constants (1,434 zones; h604_model_v3 overridden
by h606_v5 on its ten pocket stratum-sides), per-(zone, state)
integer offsets (3,664 nonzero), and a six-bit resolved-sum read of
the right product's Booth/4:2-tree carry-save words (h587b winner
tree).  Cumulative pre-port blind record: 0.9975 over 217,843 fresh
hardware rows, three windows, both wrap sides.

PORT: `--round57-fcos-borrow-rule` (implies round52) in
fsincos_skylake.c; tables generated into src/fsincos_r57_tables.h by
experiments/h611_gen_tables.py from the two model JSONs (in
experiments/).  The rule engages only on the standalone-FCOS cosine
terminal (both routes: the round52 direct path and the round53
operation-classes path via phase_increment), only on active
lsign=1/rsign=0 rows inside the near-boundary zone (|theta| <= 2 in
the pre-Round-52-patch frame), and only where a fitted zone exists;
everything else falls through to the existing Round-52 behavior.
FSIN's internal cosine and the paired-FSINCOS lanes are structurally
unreachable (eligibility flag; paired path is table_only) — verified
bitwise flag-invariant.

D1 NUMBERS (original 282,262-row corpus, pre-patch coordinates, EU
labels, blind filter): 276,460 rows out of zone (untouched); in-zone:
1,644 scored observable, 3,888 blind (architecturally
indistinguishable), 248 replica-recovery failures, 10 uncovered, 12
OTHER.  Baseline mismatches on scored rows 292 -> 6 under the rule
(291 fixed, 5 broken).  Out-of-zone mismatches: 4 are the Round-52
dist-10 lane-merge patch rows (still fixed by the patch fall-through)
and 16 are pre-existing far-out residuals beyond the rule's scope.

VALIDATION (2026-08-12):
- Bit-exactness: C port vs Python reference predictor exact on
  1,119/1,119 covered sample rows x3 modes, via BOTH routing paths
  (h612_c_crosscheck.py).
- Flag-off: binary-identical outputs to the pre-port model (12k
  boundary inputs x3 modes); FSIN and paired outputs bit-identical
  with the flag on.
- corpus2 (i7 oracle, 57,863 boundary-sensitive inputs vs recorded
  hardware, full shipped flag set): mismatches rn/rd/ru
  39/34/60 -> 5/3/6 (123 fixed, 4 broken — the rule's known ~0.3
  percent residual).
- Fresh-hardware h410-equivalent on the i7 (sweep 50,038 + dense
  240,000 inputs, sin/cos/sincos x rn/rd/ru captured fresh):
  ZERO mismatches everywhere, flag off AND on.
- h377 FSIN binary64 residual gate: PASS at baseline with the flag
  available (FSIN path untouched).
- Skylake-VM h410 suite (run later the same day, VM back up):
  flag OFF reproduces the Round-56 record exactly — every corpus
  at 0 mismatches except the standing single-input FSIN residual
  (fsin_h405win = 1, the h377 input), h377 gate PASS at baseline.
  Flag ON: identical everywhere, including fcos_h347 = 0.  The
  full original validation suite passes with the port, both flag
  states.

CAVEATS: the rule is empirical; its ~0.3 percent residual (mixed
zones, band rows) is accepted and documented, not explained.  The
paired-FSINCOS near-boundary gate remains fully hidden (h594) and is
NOT modeled.  The 248 replica-mismatch corpus rows (the h519 64-row
residual family and relatives) remain open.
