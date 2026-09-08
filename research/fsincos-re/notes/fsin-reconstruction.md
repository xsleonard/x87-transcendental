# Standalone FSIN reconstruction

## Supported structure

Standalone Intel FSIN uses the same architectural special cases, M66
range reduction, P5 ROM constants, table cells, and final RC-controlled
rounding as the reconstructed FSINCOS path.  Its polynomial entry points are
not all bit-identical to FSINCOS:

1. direct sine polynomial for `|x| < 1/4`;
2. reduced-entry sine polynomial when the quadrant is even;
3. reduced-entry cosine polynomial when the quadrant is odd and
   `sin(x) = +/-cos(r)`.

The exact-integer C implementation is selected with
`--fsin-standalone` in `src/fsincos_skylake.c`.  The usual table refinements
remain explicit:

```text
--round18-poly --round21-table-bias
--round23-narrow-coefficient --round24-table-delta-rn67
--round28-tang-narrow
```

## Hardware evidence

- Pentium II and Skylake standalone FSIN RN outputs are identical on all
  240,000 dense operands.
- Skylake RN/RD/RU plus per-instruction status constrain the final hidden
  value.  C1 agrees with the directed increment direction in all
  478,278 dense FSIN cases where RD and RU differ.
- The 50,038-input structured sweep has standalone FSIN/FSINCOS differences
  on 26 RN, 44 RD, and 37 RU results.  All 26 RN cases are polynomial:
  one direct and 25 reduced; 23 reduced cases use the internal cosine
  producer.
- All 26 instruction differences are one ulp.  No table-cell difference is
  observed under RN.
- Directed results and C1 nevertheless distinguish the standalone FSIN table
  carrier.  h135 selects 80 fresh direct/reduced separators without reading
  hardware.  They validate a path-aware terminal-coefficient rule and reject
  transferring the direct P materialization through M66 reduction.

The local KVM timing capture is not usable as path evidence.  A repeated
FCOS paired-table run retained only 81 common fast classifications, so the
minimum serialized RDTSC result is dominated by virtualization noise.
Timing remains in the kit for bare-metal systems.

## Equivalent operation graphs

These schedules are the minimum current representatives of the observed
bits.  `RN`, `chop`, `away`, and `odd` describe exact-integer
materializations.  The nonstandard modes may represent alignment, carry,
partial-product, or sticky-bit behavior rather than literal micro-ops.

h200-h210 test that possibility directly.  The complete patent-shaped FADD
model covers like-sign addition, far and near subtraction, independent FRND
normalization, raw J/GRS retention into FMUL X67, every P/Q Horner mask, all
seven final Tang addition trees, and coordinated producer/reconstruction
schedules.  No literal profile passes the complete componentwise gates, so
the schedules below remain the best validated equivalents rather than being
replaced by a speculative physical route.

Direct sine, h110:

```text
a2 = chop67(a*a)
coefficients = RN67, except S2 = away64
Horner products = RN69, RN69, RN69, RN69, away64
Horner sums     = RN69, RN69, RN69, RN64, RN67
m = RN64(p*a2)
correction = chop67(m*a)
result = architectural_round(a + correction)
```

Reduced-entry sine, h122:

```text
a2 = away66(a*a)
coefficients = RN67
Horner products = RN69 at all five edges
Horner sums = RN69 at the first four edges, RN65 at the fifth
m = chop65(p*a2)
result = architectural_round(a + m*a)  # exact final product/add carrier
```

Standalone FCOS direct cosine, h119:

```text
a2 = odd68(a*a)
coefficients = chop66, except C2 = chop65
Horner products = chop66 at the first four edges, RN65 at the fifth
Horner sums = chop66 except the fourth = chop64
tail = away72(q*a2)
result = architectural_round(1 + tail)
```

FSIN's odd-quadrant internal cosine uses the same h119 representative except
its square follows the product-normalization split and its tail has a
freshly validated low-bit selector:

```text
a2 = away68(a*a) if the exact 64x64 product has 127 bits
a2 = away67(a*a) if the exact product has the high normalization bit
sum5 = chop65(product5 + C1) if product5 is low-normalized and sticky
sum5 = chop66(product5 + C1) otherwise
product5 = odd67(q4*a2) if its retained 65-bit LSB is zero,
           a2.low3 is three, and the sum5 selector is inactive
product5 = RN65(q4*a2) otherwise
tail = chop71(q*a2) if the exact product's retained 72-bit LSB is one
tail = away72(q*a2) otherwise
```

h121 first selects uniform away67 on both independent halves of 12,249
reduced residuals.  h146-h148 then isolate and freshly validate the
normalization split; h149 proves its C port.  h150-h152 isolate the tail
selector and validate it on the hardware-blind 538-input h151 capture; h156
proves its C port.  h153/h154 reject standard X67/Y64 writeback, fixed-grid,
and fused-tail explanations, so both unusual rules remain equivalent
representatives rather than literal microinstruction claims.

h157 then searches two-predicate selectors for the mixed-direction old
residuals.  The hardware-blind 634-input h158 capture rejects every chop64
sum and validates three chop65 selectors.  h159's complete gates select the
normalization+sticky rule as the only single mechanism that both survives
alone and improves both old halves.  h160 proves the dynamic Round 31/32 C
graph, including cases where the altered sum flips the downstream tail-bit
selector.

h161 independently rejects extending the chop65 sum selector with the
second h158 predicate.  h162 searches the complete existing materialization
grid and localizes its surviving signal to product 5; no sum-plus-companion
variant survives.  The hardware-blind 33-input h163 capture supplies 16
separators for each of 39 product/coefficient grids.  Product carriers
improve 27 -> 14 mode misses while coefficient changes reach only 22.
The 67-bit round-to-odd representative matches the documented normalized
P5 multiplier carrier and preserves sticky information.  h164 proves its
Round-33 C port over the old sweep and all six focused captures.
h165 then scans 30,000,000 constructed inputs for differences inside the
best width class.  Its sole separator rejects 72-bit RN (one mode/input
miss); odd67 and exact both match all three modes and C1.  Architectural
evidence therefore supports the 67-bit representative and cannot further
separate it from exact state.

h166 recomputes tomography with Rounds 30--33 frozen: 12,205 inputs are
inside the hardware interval, 31 need the hidden cosine up, and 13 need it
down.  h167 tests 146 adjacent product/sum/tail/final operations selected by
one or two physical bits across nine complete gates.  Its leading old-data
rule would improve internal-cosine mode misses 62 -> 58.  The hardware-blind
363-input h168 capture rejects it because affected inputs regress 33 -> 34,
and rejects all five other predeclared mechanisms componentwise.  No
post-Round-33 adjacent rule is ported.

Standalone FSIN's table producer retains the shared FSINCOS square, Horner
edges, state biases, and RN67 delta combine, with three terminal coefficient
materializations:

```text
direct narrow P terminal coefficient = chop64
direct wide P terminal coefficient   = away64
wide Q terminal coefficient          = away64  # direct and reduced
reduced narrow P and reduced wide P   = shared RN67 behavior
```

h131-h134 reject every uniform 64..72-bit producer/tail replacement, all
545 final-combine variants through 80 bits, fine `S`/`U` state biases, and
all other per-coefficient/per-edge changes.  h135 then validates the
path split on independent Skylake inputs.  The C model enables it by default
for `--fsin-standalone`; `--fsin-table-shared` reproduces the old shared
table carrier for A/B validation.

h136 then tests Tang's literal reconstruction
`Sj + r*Cj + (Sj*q+Cj*p)`.  No uniform 64/67/69-bit materialization
transfers.  h137 independently searches `C*r`, `Sj*q`, `Cj*p`, and both
sums.  Narrow `Cj*p=away64` is no worse on every complete train/held/fresh
partition, removes one dense mode/input miss, improves the independent
Pentium-II dense FSINCOS capture by one, and leaves the master unchanged.
Wide `Sj*q=odd67` improves dense data but regresses the master and is
rejected.  The C port is `--round28-tang-narrow`.

h139-h143 replace that away64 proxy with explicit P5 multiplier buses.
The cross-validated representative is:

```text
direct:  p -> X67 RN, Cj -> Y64 RN, product -> RU64
reduced: Cj -> X67 RN, p -> Y64 RN, product -> RD64
```

h169 then freezes this Tang/P5 graph and inverts the remaining table sweep.
Of 21,805 table-active inputs, 21,579 hidden values are inside the hardware
interval; the 226 residual inputs split into 129 needing greater magnitude
and 97 needing smaller magnitude.  Their midpoint offsets cluster within a
few `2^-67` units.  h170 therefore searches conditional 64..72-bit/exact
materialization of the final correction accumulator.  h171 freezes six
distinct survivors and constructs 283 fresh direct/reduced separators.
Skylake rejects all six componentwise.  One candidate improves mode/input
misses on its targeted set from 37/37 to 35/31 but worsens C1 from 22 to
24; it is not ported.  Simple final-correction quantization is exhausted,
leaving operation order, FADD carrier formation, or a path/promotion gate.
h172 also tests the architectural precision-control field directly.  PC24,
PC53, and PC64 produce byte-identical results and status words on the full
50,038-input sweep and all 283 h171 separators (150,963 lines total).  FSIN
therefore selects its internal precision in microcode and exposes no
PC-dependent carrier discriminator.

h173 next tests 1,183 global addition trees with independent exact or
64/67/69-bit RN/chop/away/odd carriers; none survives sweep train/heldout
plus h171.  h174 applies the same schedules only under direct/reduced,
narrow/wide, and sine/cosine-lane gates, leaving ten old-data survivors.
h175 freezes six representatives and constructs 243 fresh table-interval
inputs with 64 separators per rule.  Narrow-cosine RN64, narrow-cosine
odd67, and cosine-lane chop69 each pass their own targeted subset.  h176
then checks the complete capture and all six targeted subsets: every apparent
pass regresses a different independent subset.  No rule is ported.  Both a
global alternate FADD tree and the structural path-gated versions are
therefore exhausted.

h177/h178 then compare the same table inputs across all three x87
instructions.  Standalone FSIN and the paired FSINCOS sine lane are
identical on all 160,000 dense table inputs and 21,805 table-active sweep
inputs under RN/RD/RU.  Standalone FCOS and paired cosine are likewise
identical; dense C1 agrees in all 480,000 cases.  The residual is therefore
inside one shared table kernel, not an FSIN-specific final projection.

h179 rotates both lanes through the actual reduction quadrant before
inverting their intervals.  The current dense scores are 2,110 sine and
1,517 cosine mode misses; the 3,074 joint outside states split into 1,471
P-dominant and 1,603 Q-dominant projections.  h180 confirms the path-aware
Tang/P5 graph remains the best known shared graph.  h181 rejects every
individual wide-Q coefficient, product, and sum coordinate.  h182 finds
only a weak six-way equivalent wide `p*square` away/odd carrier.  The fresh
43-input h183 capture observes both lanes and rejects all six
representatives, usually with regressions in sine and cosine.  No joint
producer rule is ported.

h184 then tests the FIRC-side routing that earlier passes had covered only
for narrow `Cj*p`: preserve each 67-bit lookup constant or materialize it at
RN/chop/away/odd 64 bits independently for `cross*r`, `lead*q`, and
`cross*p`.  Only native routing and `cross*p=RN64` survive every complete
dense/sweep, train/held, narrow/wide, sine/cosine partition.  The latter
fixes two old dense sine modes.  h185 freezes all four 64-bit modes and
selects 38 hardware-blind two-lane separators.  Fresh Skylake results
validate RN64 and reject away/odd; chop passes the fresh set but remains
rejected by h184's old complete gates.  Round 34 ports the wide-family
RN64 route.  h186 proves C/Python parity on 274,137 complete wide-table mode
results, two changed outputs, and 595,977 unchanged other results.  The
structured sweep remains 330/280 because its table subset contains no
architectural separator for this route.
A fresh staged-tree Debian build passes selftest and produces the same
RN/RD/RU full-sweep hashes as the native macOS build:
`8a520893d63c2d0448fc19685a35c94c61481e500ac2d8852c210ee5c9537ba7`,
`37d5284fbe940d4e9dbeeb23db5affb25ed542d7bcfbe9a4750fe1806d920eb5`,
and `5386489050c6a71d35500332fb49545bcdd26c9e9e71f824d1b61e68c6918c01`.

h187 starts the follow-on coordinated search by allowing one P-Horner edge
and one Q-Horner edge to change together while freezing Round 34.  Its
bounded beam crosses 1,024 schedules.  Although 736 survive samples plus
all currently wrong inputs, they reduce to nine distinct output/C1 profiles;
all nine regress a complete dense/sweep joint-lane partition.  This rejects
cross-chain pairs built from individually visible coordinate changes.  It
does not reject a stage-local coefficient/product/sum schedule whose
individual components are architecturally latent.

h188 searches that latent family at the terminal P and Q stages.  It tests
3,960 two-operation schedules per chain; 4,426 schedules survive the
all-residual gate but reduce to 16 exact profiles.  Three profiles survive
complete joint-lane validation and all share terminal P coefficient away64.
h189 then scans 3,332,105 fresh model states and selects 37 direct/reduced
inputs with 16 pairwise separators for every survivor and Round 34.  Fresh
Skylake data selects coefficient away64 plus terminal-sum chop65; the other
two profiles regress.

Round 35 ports only this terminal P producer as
`--round35-table-p-terminal`, retaining the chopped 65th bit through the
following RN64 product.  h190 keeps standalone FSIN's existing Q-away path
separate from paired FSINCOS's shared Q path.  It proves exact C/Python
parity on 548,274 wide-table lane/mode results and 1,191,954 unchanged other
results.  Complete mode/input/C1 metrics improve from 1,515/1,309/828 to
1,513/1,308/827 for standalone sine and from 1,515/1,304/807 to
1,514/1,303/805 for paired cosine.  The structured 330/280 sweep is
unchanged.  The next target is the same pair search at earlier Horner stages.

h191-h192 test the immediately preceding Horner stage before widening that
search.  Each chain contributes 3,960 two-operation schedules across the
complete 64..72-bit RN/chop/away/odd grid, with exact included for products.
Neither P nor Q produces a single componentwise non-regressing sample
survivor under the C-exact Round-35 instruction split.  The penultimate stage
is exhausted without a hardware capture; stage 3 is the next saved frontier.

Reduced RD64 remains tied with round-to-odd; RD64 is retained because it is
a documented FMUL mode.  The independent five-input h140 capture improves
from 5 to 2 mode misses.  h143 proves exact C/Python parity on all 271,278
complete narrow results and 598,836 unchanged other results.  The C port is
`--round29-p5-fmul-route`.

## Tiny inputs

The structured h117 probe establishes a separate hardware boundary:

- exponent -68 through -33: RN and directed rounding away from zero return
  the operand; directed rounding toward zero decrements its magnitude by one
  x87 ulp;
- exponent -69 and below: every rounding mode returns the operand, although
  the instruction still reports inexact.

The C rule is exact on all 1,080 RN/RD/RU h117 results and on all 12,000
quick-small results in the full sweep.

## Scores

Direct 80,000-input polynomial constraints:

| producer | mode misses | input misses | C1 misses |
|---|---:|---:|---:|
| FSIN h110 | 420 / 240,000 | 303 / 80,000 | 157 / 240,000 |
| FCOS h119 | 2,161 / 240,000 | 1,545 / 80,000 | 850 / 240,000 |

Reduced standalone-FSIN subpaths:

| producer | mode misses | input misses | C1 misses |
|---|---:|---:|---:|
| internal cosine h121 + Rounds 30/31 | 64 / 36,747 | 46 / 12,249 | 22 / 36,747 |
| plus Round 32 Horner selector | **62 / 36,747** | **44 / 12,249** | **22 / 36,747** |
| plus Round 33 product selector | **62 / 36,747** | **44 / 12,249** | **22 / 36,747** |
| reduced sine h122 | 6 / 17,052 | 6 / 5,684 | 4 / 17,052 |

Direct 160,000-input table constraints:

| table carrier | mode misses | input misses | C1 misses |
|---|---:|---:|---:|
| shared FSINCOS terminal coefficients | 2,119 / 480,000 | 1,806 / 160,000 | 1,125 / 480,000 |
| h135 path-aware FSIN terminals | **2,112 / 480,000** | **1,801 / 160,000** | **1,125 / 480,000** |
| plus h137 narrow Tang product | **2,111 / 480,000** | **1,800 / 160,000** | **1,123 / 480,000** |
| plus h142 P5 FMUL route | **2,110 / 480,000** | **1,799 / 160,000** | **1,121 / 480,000** |

Complete 50,038-input RN/RD/RU sweep:

| C path | mode misses | inputs with any miss | maximum |
|---|---:|---:|---:|
| shared FSINCOS producer | 1,652 / 150,114 | 1,593 / 50,038 | dominated by missing tiny directed rule |
| direct FSIN + tiny rule | 355 / 150,114 | 300 / 50,038 | 1 ulp |
| plus FCOS transfer | 348 / 150,114 | 289 / 50,038 | 1 ulp |
| plus h121 internal cosine | 342 / 150,114 | 287 / 50,038 | 1 ulp |
| plus h122 reduced sine | 334 / 150,114 | 283 / 50,038 | 1 ulp |
| plus Round 30 cosine normalization | **332 / 150,114** | **282 / 50,038** | **1 ulp** |
| plus Round 31 cosine tail selector | **332 / 150,114** | **282 / 50,038** | **1 ulp** |
| plus Round 32 cosine Horner selector | **330 / 150,114** | **280 / 50,038** | **1 ulp** |
| plus Round 33 cosine product selector | **330 / 150,114** | **280 / 50,038** | **1 ulp** |

Round 31 changes no old-sweep architectural result, but improves fresh h147,
h148, and h151 mode misses from 90/310/489 to 85/304/471 and h151 C1 misses
from 254 to 227.  Round 32 improves h148/h151/h158 mode misses from
304/471/474 to 278/446/429.  The final 330 old mode misses partition into
74 polynomial and 256 table results; tiny inputs have zero.  Round 33 changes
no old result, but improves h161 mode/input/C1 misses 186/132/78 ->
184/131/77 and h163 27/20/9 -> 14/10/4.  h135 improves independent direct-table
coverage.  It changes six master-sweep boundary results—three fixes and three
regressions.  h137 and h142 each improve dense coverage without changing the
master, so the headline score is unchanged.

The final C source was compiled independently on Apple Silicon macOS and the
Debian Skylake x86-64 host.  Their complete sweep outputs are byte-identical:

```text
RN  8a520893d63c2d0448fc19685a35c94c61481e500ac2d8852c210ee5c9537ba7
RD  37d5284fbe940d4e9dbeeb23db5affb25ed542d7bcfbe9a4750fe1806d920eb5
RU  5386489050c6a71d35500332fb49545bcdd26c9e9e71f824d1b61e68c6918c01
```

Round 32 was rebuilt from a fresh source archive in
`/home/coduoserver/fsincos-round32-20260720-1`; selftest passed and all
three hashes above matched the native macOS build.  The C source SHA-256 was
`22a8507bd566ce57c28c657ce66f76e4cacd21d529a2ba9d745d987e1f90dff4`.

Round 33 was rebuilt from staged tree
`d48e18767e13bb21fdfa598c6792320ee2dfc9e7` in
`/home/coduoserver/fsincos-round33-20260720-2`.  The deterministic source
archive SHA-256 was
`7456a83e0450e57d17af9387eb1456ed61ca84f8a362d2069c61e2dd24dc566d`;
the C source SHA-256 was
`ede5eea491de3d9b65fc0f41ff73d29b4e75c2f6a62a308fc822cf833910a9e0`.
Selftest passed and all three sweep hashes above matched macOS.

## Falsified alternatives

- A constant hidden-value bias loses even at `2^-76` scale.
- Effective coefficient deltas through +/-512 units do not transfer across
  train and held-out halves.
- Wider raw-carrier, 64..80-bit intermediate, exact-Horner, and effective
  coefficient searches do not improve the direct polynomial path.  h129's
  apparent reduced-sine `-256` coefficient correction improves one old
  boundary but loses decisively on h130's 512 fresh separators
  (415 versus 341 mode misses), so it is rejected.
- Factored finals and several uniform per-edge width rules lose to the
  explicit schedules.
- Treating standalone FCOS as FSIN's exact odd-quadrant producer improves
  the shared baseline but loses to the FSIN-specific h121 square rule.
- Fitting separate reduced table biases improves the master sweep but fails
  the fresh h108 reduced-parameter discriminator; it remains rejected.

## Conditional FIRC microcontrol

h211-h225 replace the failed fixed literal-FADD search with a bounded
data-dependent microprogram.  The complete fixed `jam-sub` grammar can reach
every measured residual lane, while all 34,560 unconditional programs fail.
h216 freshly selects one first-node leaf:

```text
if exponent_difference(linear, p) == 14
   and exponent(raw(linear+p)) mod 4 == 0
   and FAMUBUS_bit3(raw(linear+p)) == 1:
    first  = odd64(linear + p)
    second = odd67(first + q_product)
    final  = odd67(second + lead)
else:
    use Round 35 lookup/FIRC route
```

Round 36 ports this as `--round36-table-fadd-microcontrol`.  h217 proves
7,056 exact C/Python RN/RD/RU checks over every 588 old base-condition input.
The complete paired-cosine metric improves from 1,514/1,303/805 to
1,512/1,302/804 mode/input/C1 misses; standalone sine and the structured
330/280 score are unchanged.  h221-h224 use 190 additional fresh inputs to
reject every bounded second-leaf survivor.  h225 confirms that the selected
bit is the physical representation identity `normalized X2 bit 4 = FAMUBUS
bit 3`, not a carry/borrow/sticky proxy.

## Round 37: four-term table kernel

The numerical graph uses four-term sine/cosine coefficients for every
table cell.  Its highest-degree sine coefficient differs from the naturally
corresponding decoded P5 value at payload bit 60.  That change is necessary:
the P5 value makes the four-term graph grossly incompatible with processor
output.

h226-h230 evaluate a fixed dependency graph. The validated all-cell
table schedule is:

```text
q_product = odd67(table_lead * cosine_tail)
p_product = chop67(table_cross * complete_sine_state)
correction = away67(q_product +/- p_product)
result = architectural_round(table_lead + correction)
```

The complete sine state is `sin(a)` including the retained bias, not only the
leading `a` term.  h230 then searches materializations at the fixed
operation boundaries.  The clean complete-corpus profile uses
`chop67(a*a)`, `away67(P*a*a)`, and `chop65(P*a*a*a)` before the RN64 sine
FADD.  The 67-bit square is the high-impact result; the two sine carriers
improve focused directed-mode observations but are neutral on the structured
RN sweep.  The next best Horner coordinate is neutral on the complete corpus
and is not ported.

`--round37-p6-four-term` ports this schedule and adjusted coefficient for both
narrow and wide cells.  h228 proves exact C/Python parity on 1,090,830
lane/mode checks over the dense and structured all-cell table corpora.  A
fresh x86-64 build on the Debian Skylake host passes selftest and scores
126/150,114 mode results and 106/50,038
inputs different on standalone FSIN, all by one ulp; the prior score was
330/150,114 and 280/50,038.  Standalone FCOS dense misses improve from
3,678/720,000 mode results to 2,540/720,000.  Direct-polynomial misses are
unchanged; the table/other category falls from 1,517 to 379.  The paired
FSINCOS RN master improves from 49,868 to 49,991 exact inputs.

## Rounds 38 through 42: standalone split graphs and tiny boundaries

h235 replaces standalone FCOS's serial six-term Horner proxy with two
interleaved chains.  Its independently split survivor uses chop67 for the
square and ordinary products/sums, RN64 for the fourth power and `+C2`, RN68
for the terminal negative-chain multiply, odd66 for `+C4`, and chop66 for the
chain combine.  Round 38 ports this graph.  The dense FCOS score improves from
2,540 to 769 mode misses; direct-polynomial misses fall from 2,161 to 390.

Round 39 applies the captured standalone-FCOS tiny directed-rounding boundary,
leaving 89 mode misses on 84 inputs in the structured sweep.  Round 40 applies
the corresponding tiny rules to both paired-FSINCOS lanes, leaving 110
lane/mode misses on 110 inputs, all on table paths.

h241 then replays the two-chain cosine graph inside standalone FSIN.  An
aggregate no-worse gate over each of seven earlier focused captures selects
RN67 for the terminal negative-chain multiply and away65 for the final
positive-chain sum.
The internal-cosine class improves from 62 to 10 mode misses; the complete
standalone-FSIN sweep improves from 126/106 to 74/72 mode/input misses.  Round
41 has zero C/Python differences over all 36,747 structured and 7,179 focused
lane/mode checks.

h242 replays the corresponding two-chain six-term sine graph.  One schedule
is exact on independent direct/reduced halves: chop67 square, RN65 fourth
power, RN64 on `+S1`, odd66 on `+S2`, chop64 on the terminal even-chain
product, RN64 on the chain combine, and chop67 on the other branch operations
and correction multiply.  Round 42 is exact on 257,052 standalone-FSIN and
21,894 standalone-FCOS sine-state mode observations.  It is not applied to
paired FSINCOS because that path's existing polynomial schedule is exact and
the standalone carrier schedule would introduce 43 misses.  The structured
sweep improves to 62/62 FSIN and 74/74 FCOS mode/input misses.

h243 closes the table index and breakpoint producer rather than fitting
another grid.  The four-bit address is formed from exponent parity and two
leading fraction bits, and its paired midpoint breakpoint reproduces all
181,805 independently prepared direct/reduced table arguments exactly.  The
four-fraction-bit alternative disagrees with 175,608 addresses and every
residual and would require a table four times larger.  Independently computed
high-precision series also reproduce all 16 lookup payloads as RN67
`sin(b)`/`cos(b)`.  Thus the remaining table misses are downstream retained-
carrier/microcontrol effects, not a cell, anchor, subtraction, or lookup-word
error.

h244 then groups the arithmetic sites across multiple revisions.  The full
55-operation sine/cosine arithmetic sequence and 47-operation exponential
sequence retain identical opcodes, operands, destinations, and modifier
fields; only completion metadata changes.  Ordinary FMUL, FADD, FSUB, and the
distinct multiply-class operation have no per-site modifiers.  Consequently,
the remaining few-bit effects cannot be justified as independent rounding
modes selected at each polynomial edge.  Future candidates must instead use
shared datapath behavior, operand/port formatting, distinct opcode classes, or
explicit hidden state, constrained by sibling instructions.

h245--h276 add the independent FPTAN constraint and close it on all current
captures.  The earlier away67 reconstruction-multiply leader was compensating for
an incorrectly retained operand: the complete sine state has a 69-bit
analysis carrier, but FPTAN reads it through RN64.  Keeping F2XM1's chop67
ordinary multiplier and chop67 subtraction after that read leaves only four
table mode misses on two inputs, with a zero-miss structured sweep.  The
six-term polynomial path transfers chop67 FMUL, RN64 FADD, RN64
multiply-class scaling, and chop67 FSUB exactly; a direct-tiny bypass through
exponent -69 completes all 108,231 polynomial inputs.  A one-million-input
cell-36 scan adds five signed residuals to the two old cases.  Causal replay
localizes all seven to the shared sine-state producer, whose empirical
RN64/away67/chop65 product rules predated the F2XM1 operation-class result.
Changing the P/Q Horner products, P times square, and the following P times
residual product to shared chop67 closes every dense/sweep result and C1,
every focused residual, and all one million RD scan results.  The C path has
zero result misses over the 870,114 existing comparisons and the large scan.

h251--h259 close F2XM1 as an independent arithmetic witness.  The
complete path uses chop67 for every ordinary multiply, RN64 for every FADD,
RN64 for the distinct multiply-class operation, and switches from final
linear multiply to the long polynomial at exponent -68.  Its table begins at
`|x|=1/4`.  Existing and fresh captures produce no output or C1 misses, and
the C port is exact on all 915,162 result comparisons.  This does not license
copying scalar representatives blindly into the trig graph.  Instead, h260
uses the shared chop67 multiply while explicitly materializing FPTAN's sine
operand at RN64.  h275 then transfers that class to the remaining ordinary
P/Q state-producer multipliers and resolves the rare carrier cases above.

h277--h324 use the solved sibling classes to revisit the remaining trig table
residue.  Completing the scalar FMUL/FADD labels at the final graph regresses,
and a literal final P5-style FADD can reach only 521 of 730 residual lanes.
Propagated retained-unit changes reach 729 lanes at the final correction and
719 through the complete shared-sine state, localizing the dominant gap to
the `a + P*a^3` producer rather than another polynomial or lookup value.

After h275's multiply correction, changing the wide shared-sine proxy from
5/32 to 3/32 ulp removes most fitting residuals but is not globally valid.
h283--h284 separate a physical subcase: the local residual has top exponent
-5 and its sine-FADD operands have exponent difference 13.  h285 generates
192 hardware-blind reduced-entry separators across all wide cells, quadrants,
and signs.  On that fresh Skylake capture, Round 43 improves the paired table
metric from 180 mode and 119 C1 misses to 22 and 16.  The old frozen table
objective improves 738/500/730 to 615/405/610 with no aggregate component
regression.

h291--h305 extend the same physical coordinate model.  The direct h292
capture validates the Round-43 coordinate and a second wide coordinate
`(-6,15)`.  A hardware-blind fractional discriminator then selects 21/256
ulp as the highest cross-validated representative for that second coordinate.
h306--h324 apply the same method to the narrow table.  Three independent
captures select 29/256 at `(-6,15)`, 30/256 at `(-8,19)`, and 34/256 at
`(-7,17)`.  Each coordinate and numerator is representation-independent and
is scored on dense/sweep train and held partitions before promotion.

The Round-48 C port matches Python on 1,094,382 lane/mode checks.  A fresh
Debian GCC build passes selftest.  Structured master misses fall from
62/74/110 to 49/57/80 for FSIN/FCOS/FSINCOS.  These sub-ulp values remain
processor-output-equivalent carrier representatives; they are not claims
about literal microcode rounding fields.

h325--h345 replace those several representatives with one carrier-level
interpretation.  Every proxy becomes the same legal 67-bit word,
`RN64<<3 - 1`, so the distinguishing state cannot be a wider stored scalar.
Treating its low suffix as a half-open producer-to-FMUL interval and retaining
one product unit below the upper chop67 result reduces the dense paired
objective from 632/377/627 to 101/63/96 and the structured objective from
80/40/80 to 13/10/13 without component regression.  Three independent fresh
captures become exact for both results and C1.

Round 49 ports that arithmetic rule and matches Python on all 1,094,382
lane/mode checks.  The structured hardware census is now 15 FSIN, 24 FCOS,
and 13 FSINCOS misses; the paired table residue is only 5 sine and 8 cosine
lanes.  Follow-up passes reject a missing broad Q-polynomial boundary, a
literal numeric 64--72-bit sine-FADD result, a generic second-edge interval,
and P5-style literal FADD behavior at either final addition.  The remaining
table gap is a rare retained carry/borrow decision in the model.  The separate
standalone polynomial residue is 10 FSIN and 16 FCOS modes.

## Reproduction

```sh
make -C src fsincos_skylake
python3 experiments/h112_fsin_c_parity.py src/fsincos_skylake
python3 experiments/h116_fsin_full_sweep.py src/fsincos_skylake
python3 experiments/h117_fsin_tiny_boundary.py \
  --capture capture-kit-captures/skylake-fsin-h110 \
  --model src/fsincos_skylake
python3 experiments/h119_fcos_standalone.py
python3 experiments/h121_fsin_internal_cosine.py
python3 experiments/h122_fsin_reduced_sine.py
python3 experiments/h123_fsin_reduced_c_parity.py src/fsincos_skylake
python3 experiments/h124_fsin_cosine_c_parity.py src/fsincos_skylake
python3 experiments/h125_fsin_residual_map.py src/fsincos_skylake
python3 experiments/h135_fsin_table_terminal_discriminator.py \
  --model src/fsincos_skylake --parity
python3 experiments/h135_fsin_table_terminal_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h135 --score-existing
python3 experiments/h136_tang_reconstruction_search.py
python3 experiments/h137_tang_edge_schedule_search.py
python3 experiments/h138_tang_c_parity.py src/fsincos_skylake
python3 experiments/h139_p5_fmul_route_search.py
python3 experiments/h140_p5_fmul_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h140
python3 experiments/h141_p5_fmul_path_modes.py
python3 experiments/h142_p5_fmul_path_route.py
python3 experiments/h143_p5_fmul_c_parity.py src/fsincos_skylake
python3 experiments/h146_fsin_cosine_boolean_search.py
python3 experiments/h147_fsin_cosine_boolean_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h147
python3 experiments/h148_fsin_cosine_boolean_crossvalidate.py \
  --score capture-kit-captures/skylake-fsin-h148
python3 experiments/h149_fsin_cosine_square_c_parity.py \
  src/fsincos_skylake
python3 experiments/h151_fsin_cosine_tail_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h151
python3 experiments/h152_fsin_cosine_tail_grid.py
python3 experiments/h153_fsin_cosine_p5_tail_round30.py
python3 experiments/h154_fsin_cosine_fused_tail.py
python3 experiments/h155_fsin_cosine_state_tomography.py
python3 experiments/h156_fsin_cosine_tail_c_parity.py \
  src/fsincos_skylake
python3 experiments/h157_fsin_cosine_two_predicate.py
python3 experiments/h158_fsin_cosine_two_predicate_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h158
python3 experiments/h159_fsin_cosine_two_predicate_union.py
python3 experiments/h160_fsin_cosine_horner_c_parity.py \
  src/fsincos_skylake
python3 experiments/h161_fsin_cosine_round32_composition.py \
  --score capture-kit-captures/skylake-fsin-h161
python3 experiments/h162_fsin_cosine_round32_residual_search.py
python3 experiments/h163_fsin_cosine_product_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h163
python3 experiments/h164_fsin_cosine_product_c_parity.py \
  src/fsincos_skylake
python3 experiments/h165_fsin_cosine_product_width_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h165
python3 experiments/h166_fsin_cosine_round33_tomography.py
python3 experiments/h167_fsin_cosine_round33_operation_search.py
python3 experiments/h168_fsin_cosine_round33_operation_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h168
python3 experiments/h169_fsin_table_round33_tomography.py
python3 experiments/h170_fsin_table_correction_search.py
python3 experiments/h171_fsin_table_correction_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h171
python3 experiments/h172_fsin_precision_control.py
python3 experiments/h173_fsin_table_fadd_topology.py
python3 experiments/h174_fsin_table_path_gate.py
python3 experiments/h175_fsin_table_path_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h175
python3 experiments/h176_fsin_table_path_crossvalidate.py
python3 experiments/h177_table_sibling_triangulation.py
python3 experiments/h178_table_sibling_reduced.py
python3 experiments/h179_table_joint_state_projection.py
python3 experiments/h180_table_cosine_graph_compare.py
python3 experiments/h181_wide_table_q_coordinate.py
python3 experiments/h182_table_joint_terminal_edges.py
python3 experiments/h183_table_joint_product_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h183
python3 experiments/h216_fadd_microcontrol_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h216
python3 experiments/h217_table_fadd_microcontrol_c_parity.py \
  --score-complete
python3 experiments/h218_fadd_residual_programs.py
python3 experiments/h219_fadd_exception_oracle.py
python3 experiments/h220_fadd_causal_tree.py
python3 experiments/h221_fadd_tree_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h221
python3 experiments/h222_fadd_tree_cegis.py
python3 experiments/h223_fadd_tree_refined_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h223
python3 experiments/h224_fadd_tree_final_discriminator.py \
  --score capture-kit-captures/skylake-fsin-h224
python3 experiments/h225_fadd_bit3_physical_aliases.py
python3 experiments/h230_p6_microop_materialization_search.py \
  --width 8 --rounds 1 --full 8
python3 experiments/h228_p6_four_term_c_parity.py src/fsincos_skylake
python3 experiments/h116_fsin_full_sweep.py \
  --p6-four-term src/fsincos_skylake
python3 experiments/h120_fcos_c_parity.py \
  --p6-four-term src/fsincos_skylake
python3 experiments/h241_fsin_internal_cosine_split.py
python3 experiments/h241_fsin_internal_cosine_split_c_parity.py \
  src/fsincos_skylake
python3 experiments/h241_round41_residual_census.py \
  src/fsincos_skylake
python3 experiments/h242_fsin_sine_split_graph.py
python3 experiments/h242_sine_split_sibling_gate.py
python3 experiments/h242_sine_split_c_parity.py \
  src/fsincos_skylake
python3 experiments/h242_round42_residual_census.py \
  src/fsincos_skylake
python3 experiments/h243_p6_table_wire_constraints.py
python3 experiments/h245_ingest_sibling_capture.py \
  capture-kit-captures/skylake-sibling-h245
python3 experiments/h246_fptan_operation_search.py
python3 experiments/h247_fptan_literal_fadd.py
python3 experiments/h248_fptan_shared_state_search.py
python3 experiments/h249_fptan_final_divide_search.py
python3 experiments/h250_fptan_residual_overlap.py
python3 experiments/h251_f2xm1_exact_baseline.py
python3 experiments/h252_f2xm1_literal_graph.py
python3 experiments/h253_f2xm1_path_threshold.py
python3 experiments/h254_f2xm1_operation_search.py
python3 experiments/h255_f2xm1_table_word.py
python3 experiments/h256_f2xm1_long_transfer.py
python3 experiments/h258_f2xm1_validation.py
python3 experiments/h259_f2xm1_c_parity.py src/fsincos_skylake
python3 experiments/h260_fptan_multiplier_input_format.py
python3 experiments/h261_fptan_divide_input_format.py
python3 experiments/h262_fptan_literal_subtract.py
python3 experiments/h263_fptan_residual_node_search.py
python3 experiments/h264_fptan_polynomial_transfer.py
python3 experiments/h265_fptan_c_parity.py src/fsincos_skylake
python3 experiments/h280_trig_unit_causal_localization.py
python3 experiments/h282_trig_sine_writeback_refit.py
python3 experiments/h283_trig_sine_bias_selector.py
python3 experiments/h284_trig_sine_bias_alignment13.py
python3 experiments/h286_ingest_trig_sine_bias_capture.py
python3 experiments/h288_trig_sine_bias_rule.py
python3 experiments/h289_round43_c_parity.py \
  src/fsincos_skylake --dataset h285
python3 experiments/h290_round43_residual_census.py \
  src/fsincos_skylake
python3 experiments/h293_ingest_trig_coordinate_capture.py
python3 experiments/h302_ingest_trig_sine_fraction_capture.py
python3 experiments/h308_ingest_trig_narrow_sine_fraction_capture.py
python3 experiments/h315_ingest_trig_narrow_sine_fraction2_capture.py
python3 experiments/h321_ingest_trig_narrow_sine_fraction3_capture.py
python3 experiments/h323_round48_c_parity.py src/fsincos_skylake
python3 experiments/h324_round48_residual_census.py src/fsincos_skylake
python3 experiments/h335_round49_c_parity.py src/fsincos_skylake
python3 experiments/h336_round49_residual_census.py src/fsincos_skylake
python3 experiments/h337_round49_causal_localization.py
python3 experiments/h338_qtail_carrier_interval_transfer.py --scope sweep
python3 experiments/h341_exact_sine_fadd_carrier.py
python3 experiments/h342_decomposed_sine_product.py
python3 experiments/h343_round49_q_producer_boundaries.py
python3 experiments/h344_round49_literal_final_fadd.py
python3 experiments/h345_round49_literal_final_writeback.py
python3 experiments/h357_round51_residual_census.py src/fsincos_skylake
python3 experiments/h356_fsin_interpreter_c_gate.py \
  src/fsincos_skylake \
  capture-kit/inputs/constraint_round49_residual_neighbors_h347.txt \
  capture-kit-captures/skylake-trig-h347 \
  --extra-flag=--round50-fsin-operation-classes \
  --extra-flag=--round51-fsin-fadd-signature
```

## Rounds 50--51: executable standalone-FSIN operation classes

- h347 expands every structured Round-49 paired residual into +/-4096 input
  neighbors and sign mirrors. Round 49 leaves 798 paired lane/mode misses in
  1,182,264 observations. The residuals are sparse across direct/reduced and
  narrow/wide cells rather than contiguous input intervals.
- h349 independently scans one million balanced direct/reduced narrow/wide
  table inputs. Round 49 leaves 515 misses in 6,000,000 paired lane/mode
  observations, or 99.991416667% parity. A uniform correction-unit change is
  rejected because it fixes rare rows while regressing many exact rows.
- Executing the finite standalone-FSIN operation sequence selects shared
  arithmetic classes: ordinary FMUL and the signed-input FSUB use chop67;
  ordinary FADD and the multiply-class operation use RN64; final additions use
  architectural RN/RD/RU. The polynomial is evaluated as two interleaved
  six-term chains, while the table path uses the four-term P/Q graph and
  explicitly materializes its anchor through chop67.
- On a 13,063-input h347 subset containing every paired residual plus regular
  controls, this replay reduces standalone-FSIN output misses from 474 to four
  in 39,189 observations. The four observations are RD/RU for one magnitude
  and its sign mirror; two also expose a C1 difference. h358 localizes them
  to the FADD completing `a + sine_tail`. A chop64 materialization fixes only
  that site, whereas applying chop64 globally creates 991 output and 815 C1
  misses on the same subset.
- h359 identifies the exceptional FADD by exponent difference 14, an exact
  above-half remainder, retained low byte `0x8c`, and normalized remainder
  prefix `0xc1`. Round 51 keeps RN64 everywhere else and selects the
  non-incrementing result only at that behavioral signature. This is an
  empirical retained-bit condition, not a complete physical-adder model.
- `--round50-fsin-operation-classes` and
  `--round51-fsin-fadd-signature` port the result to C. Standalone FSIN has
  zero result misses over 150,114 structured, 720,000 dense, and 591,132 h347
  RN/RD/RU observations: 0/1,461,246 in total. h357 confirms the structured
  residual census is now FSIN 0, FCOS 24, and paired FSINCOS 13.
- Reusing the Round-51 sine-state addition in paired FSINCOS fixes the same
  four h347 observations without regression: 798 -> 794 misses. The h349
  million scan remains 515/6,000,000, also with no regression. This proves
  that the recovered state is genuinely shared, but most paired residuals
  arise later or require another retained-state distinction.
- The final Debian x86-64 build and selftest pass in
  `/home/coduoserver/fsincos-round49-model-20260722090214`. C-source SHA-256
  is `c8aa7491d3df09b75696fdd44b17474320c4e0af15df665da561632cde94407a`;
  executable SHA-256 is
  `af5f4950ea78f5f5d485ddd10e8e8ddf971614efd73a273a8079a62b921529c2`.

The next paired pass should operate only on the 788 h347 and 506 h349
mismatching inputs. A compact C trace should emit exact operands, retained
bits, and guard/round/sticky information at the shared-sine FADD, both
cross-products, their signed subtract, and the final architectural addition.
Cluster the required adjacent output direction against those signatures, then
promote a rule only if it passes h347, h349, the structured/dense corpus, and
standalone FSIN/FCOS. This avoids the memory cost of replaying a million full
Python traces and directly tests the remaining shared-state sequencing.
