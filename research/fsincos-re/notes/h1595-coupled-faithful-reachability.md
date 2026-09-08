# H1595 — coupled faithful-rounding reachability, not a selector

**All 37 observed endpoints are individually reachable, but no common
rounding rule is recovered.** The exhaustive fixed-width graph gives a
stronger conditional constraint for e73/RD: with ordinary terminal products
and correction, every successful path must change the initial square's
rounding. Arbitrary faithful choices at the fourth power and all eight
Horner operations cannot compensate while the square remains ordinary.
This does not establish a physical square fault: changing the terminal left
product or final correction can independently reach the same endpoint.

No hardware ran, no unobserved label was inferred, and no emulator source,
default, selector, or paper/PDF was changed by H1595.

## Exact finite family

H1595 uses H1592's independently implemented signed dyadic arithmetic and
the same explicitly hypothesized direct-cosine graph. At each of thirteen
materializations it permits either adjacent numerical floor or ceiling:

1. Square and fourth power, each at 67 significant bits.
2. Four operations in each Horner arm: multiply67, add64, multiply67, add64.
3. Terminal left product67, right product67, and correction67.

The architectural final addition uses the actually observed rounding mode
and is not a freely selected cut. Constants and exact external input are
fixed. Normalization follows every exact operation; its exponent is not
artificially frozen. A single square state and a single fourth-power state
feed both arms and their terminal products, preserving the coupled graph.
An exact operation has one faithful neighbor, not two duplicate branches.

The two payload variants are explicitly separate:

- **Omitted:** signed correction is `C = Q67(L+R)`.
- **Frozen numeric:** signed correction is `C = Q67(L+R+P_signed)`, where
  `P_signed = -payload_integer * 2^(original_left_e2-8)` for this negative
  left arm. This is the same as adding positive payload to the positive
  magnitude subtraction `|L|+P-|R|`.

Every selected row's pre-gate DI_TC payload is checked equal to its consumed
DI_R59 payload. The reconstructed signed sum is checked against DI_R59's
`umag` and `rscale`. The original payload number and original left exponent
remain frozen even when square, fourth, factors or products change. H1595
does not silently regenerate the empirical payload from a modified graph.

A departure means choosing the other faithful neighbor instead of the
ordinary local rule **on the altered path's own exact inputs**: CHOP for
67-bit multiplications/correction, RN-even for 64-bit Horner additions.
It is not a fixed signed perturbation to a baseline register. Successful
paths are encoded by a thirteen-bit departure mask, with fully reproducible
intermediate-value witnesses for all minimum-cardinality supports. These
are existential witnesses selected using each observed endpoint, not a
cross-input predictor or proposed hardware implementation.

## Evidence and completeness

The bank is the same 37 observed rows over 36 distinct operands used by
H1592: eleven historical H1378 misses, eleven H1580 observations and fifteen
H1587 observations. H1592 report, implementation, input-label artifacts,
OPENED sidecars, raw captures and source hashes are rechecked before use.
H1593's immutable v3 report is also hash-checked for the earlier excluded-cut
claim. No random input or unobserved mode is assigned hardware truth here.
This audit constrains stored result bits, not the x87 status word or C1;
those would be additional constraints on the existential paths.

Every finite path is evaluated: 298,752 with omitted payload and 295,680
with frozen numeric payload, **594,432 total paths**. At most `2^13=8192`
paths occur per row/variant; exact materializations collapse duplicates.
The complete mask-to-endpoint enumeration is preserved in a compressed TSV.
The selftest independently enumerates 49,152 numerical floor/ceil direction
assignments over six graph/payload cases and checks the complete mapping
against the ordinary-relative-mask traversal, including exact-cut duplicates.

Reachability is derived from that complete enumeration, restricting the set
of permitted departure cuts without running another fitted search:

| Permitted departures | Omitted payload | Frozen numeric payload |
| --- | ---: | ---: |
| All thirteen cuts | 37/37 | 37/37 |
| All ten upstream cuts; terminal operations ordinary | 37/37 | 37/37 |
| Eight Horner cuts only; square/fourth/terminal ordinary | 33/37 | 33/37 |
| Two final Horner adds only | 33/37 | 33/37 |
| Three terminal cuts only | 37/37 | 34/37 |
| Two final Horner adds plus three terminal cuts | 37/37 | 36/37 |

With the entire graph or just upstream cuts available, no row needs more
than one local departure. Omitted payload has seventeen zero-departure and
twenty one-departure rows; frozen payload has twenty zero-departure and
seventeen one-departure rows. These counts do not identify which operation
silicon actually changes, and do not provide a common rule selecting a
neighbor across inputs.

The four failures of the all-Horner-only family are:

- Omitted payload: RN `de3ffffd548db2bf`, RN `fa50000007503a2f`,
  RD `e73ffffd2c52df71`, RU `f9e0000229067583`.
- Frozen payload: RN `f9dffffdf814cc29`, RD `e73ffffd2c52df71`,
  RU `cdcc0585c940196f`, RU `ffffc00024077827`.

Every listed significand has external sign/exponent `3ffc`. The report
retains full identities, all successful masks, inclusion-minimal supports,
and the intersection of cuts that must depart under each restricted family.

## e73/RD: a stronger coupled-graph exclusion

For RD `3ffc:e73ffffd2c52df71`, observed hardware is
`3ffe:f97ff2968a37b8b1`. Ordinary reconstruction gives
`3ffe:f97ff2968a37b8b2` with either payload variant. H1593 excluded faithful
choices at both final Horner additions while holding surrounding operations
fixed. H1595 additionally permits all earlier Horner cuts and the shared
fourth-power cut to vary faithfully at their proposed precisions.

With all three terminal operations ordinary, **every** successful path has
the square departure. There is no path with ordinary square, even after
arbitrary faithful choices at every other upstream cut. A square-only
departure is sufficient. In the unrestricted graph the inclusion-minimal
successful supports are exactly `{square}`, `{left}`, and `{correction}`.
Thus an alternative physical account at either terminal cut remains viable
under this finite family; the result is not physical-cause localization.

The square alternative is an actual faithful rounding choice, not an
unconstrained `+1` register tweak:

```text
exact x*x = 0xd0e48ffae493b8b5a43b5afcbf6a0fe1 * 2^-132
CHOP67    = 0x687247fd7249dc5ad * 2^-71
ceil67    = 0x687247fd7249dc5ae * 2^-71
discard   = 0x043b5afcbf6a0fe1 / 2^61 retained units
```

The discard is **below one half**, and the lower retained significand is
**odd**. Consequently RN67 and JAM67 both choose the lower value, not the
required square alternative. AWAY67 chooses the upper value. With that
single changed square and all subsequent operations ordinary, both arms are
recomputed from their shared updated fourth power, the terminal correction
becomes `-0x6800d6975c8474e01 * 2^-72`, and the observed endpoint is reached.

The independent terminal alternatives are a numerical floor of the negative
left product (one greater magnitude unit), or a numerical floor of the
negative correction (one greater magnitude unit). The report includes exact
local inputs, ordinary outputs, chosen neighbors, and every descendant stage
for all three witnesses. No statement about the hidden hardware direction
is inferred from the existence of those witnesses.

## Fixed square-policy diagnostic

For context, H1595 also evaluates four named operation-wide square policies,
with every other operation ordinary. These are fixed semantic tests, not
operand predicates, and none is exact even on this small adversarial bank:

| Square policy | Exact, omitted payload | Exact, frozen payload |
| --- | ---: | ---: |
| CHOP67 | 17/37 | 20/37 |
| RN67 | 19/37 | 18/37 |
| JAM67 | 20/37 | 23/37 |
| AWAY67 | 22/37 | 21/37 |

The best finite count is not a candidate for promotion. No control-wall
survival or global accuracy is claimed. In particular, neither ordinary
nearest-even nor ordinary round-to-odd at the square can explain the e73
square-only witness.

## Relationship to earlier negative results

H1177 tested exact discarded-error coordinates for monotone separation of
existing gate labels. H1183 tested fixed signed displacements at one named
producer at a time. H1400 similarly tested signed unit interventions and
forced terminal carry endpoints with a large cached control wall. Those are
not the same experiment as H1595's exhaustive coupled faithful-rounding graph.
H1595 does not repeat their coordinate fitting or rebrand their perturbation
counts. Its new result is a complete finite per-input reachability set,
including the stronger e73 upstream cut constraint.
H1593's variable-precision terminal family is different from this fixed-67-bit
terminal family, so their individual-reachability counts need not coincide.

Widths, operation sequence, constants, ordinary final composition and the
chosen payload treatment remain assumptions. A wider register, exact
forwarding, a different operation sequence, non-faithful internal rounding,
a newly generated coupled payload, or additional control state lies outside
this family. Agreement of an endpoint with some faithful path is not proof
of silicon equivalence. No broad impossibility claim or frontier change
follows, and the full FSIN/FCOS goal remains unsolved.

## Artifacts and reproduction

```sh
python3 fsincos-re/experiments/h1595_coupled_faithful_reachability.py --selftest
python3 fsincos-re/experiments/h1595_coupled_faithful_reachability.py \
  --root fsincos-re --output-dir /private/tmp/NEW_h1595_output
```

The output directory must not exist. The comparator provenance is locked to
source SHA `de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.
No C compilation or execution is needed by H1595. If the canonical source
has advanced, pass `--source-snapshot` naming a preserved file with that
exact hash; the planned H1598 preservation path is
`fsincos-re/tmp/ledger33/current/h1598_source_before.c`. This does not permit
silently treating a changed source as the audited one.

Authoritative artifacts, relative to `fsincos-re`:

- `experiments/h1595_coupled_faithful_reachability.py`, SHA-256
  `ace7b0f79cbf50728f082800882df36bda5ffddd7327de9624214e4da7bac47a`.
- `tmp/ledger33/current/h1595_coupled_faithful_reachability_v2/report.json`,
  SHA-256 `d1c4a18f462a24b2282a2e15eb6e0ac374e34f124b0bf3cd0a24663d98669f2f`.
- `all_graph_outcomes.tsv.gz` in that same directory, SHA-256
  `3f0bf5109edbdaa345b631258d0984ffa2e2aedb9a916d24bb939add72e0083f`.

Version 1 is preserved as a superseded complete graph audit; v2 adds the
exact square remainder, fixed square-policy diagnostics and historical-source
override without changing the graph enumeration. Python syntax and whitespace
checks pass. The final report and compressed complete outcome stream replay
byte for byte in an independent temporary directory. Earlier SAT/UNSAT/UNKNOWN
artifacts and hardware observations are untouched.
