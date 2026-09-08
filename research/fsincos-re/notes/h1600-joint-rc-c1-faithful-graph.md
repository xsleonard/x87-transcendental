# H1600 — one faithful graph path satisfies each operand's actual RC/C1 labels

**No new family exclusion beyond H1595/H1599.** Every one of the 36 audited
operands has at least one RC-independent H1595 graph path and common prevalue
satisfying all its authenticated recorded modes and C1 bits, under both
payload treatments. After actual C1 is imposed, the additional recorded RC
modes remove **no remaining graph path**, not merely no minimum witness.

This is joint per-operand feasibility, not a cross-input selector, a proof of
silicon equivalence, or a closed-form FSIN/FCOS solution. No hardware or C
model was executed; no labels or status bits were inferred. No emulator
source/default, paper/PDF, or failure-frontier count changed.

## Actual constraints, with provenance

H1595's 37 observed rows contain 36 distinct external FCOS operands; d0d0
has both RD and RZ. H1596 authenticates 27 additional already-recorded mode
observations for nine of the historical operands. The joint bank therefore
contains **64 observed RC constraints**:

| Recorded mode coverage | Operands | Actual RC rows |
| --- | ---: | ---: |
| RN/RD/RU/RZ | 9 | 36 |
| RD/RZ, d0d0 | 1 | 2 |
| One recorded mode, H1580/H1587 | 26 | 26 |
| Total | 36 | 64 |

The nine four-mode operands are b000, ba10, cca0, d920, f410, fa50 and the
three far-corner inputs. The equality-campaign inputs still have one actual
RC observation each. H1599 contributes **27 actual C1 constraints**: all 26
H1580/H1587 tuples and the separately authenticated f410/RU status. It does
not supply C1 for f410's other modes, or any other unobserved lane.

Before filtering, H1600 hash-checks H1595, H1596 and H1599 reports and their
implementations, all their recorded evidence, and the preserved de04 source
snapshot. It reruns H1596's read-only authenticated importer, reconstructs
the complete 150,005-row deduplicated direct/external union, and checks its
canonical observed-row hash. Filtering that full union by exact instruction
and external operand produces the 64 rows above. Thus coverage is not merely
assumed from the named subset. No alias-to-residual transfer or model output
is used to fill a missing mode.

## Joint test

An H1595 departure mask chooses a single internal graph path for one exact
external operand. Its square/fourth states remain shared across both arms.
The entire graph before final rounding is independent of architectural RC.
Payload is either absent or the original consumed numeric payload is frozen
at its original scale, as in H1595; it is not recomputed for changed states
or separately selected by rounding mode.

For every mask satisfying the original sparse labels, H1600 reconstructs
the signed correction `C` once and obtains the common prevalue `z=1+C`.
Each actually observed mode must then round that **same** z to its recorded
output. Forward integer rounding is checked against membership of H1596's
exact joint inverse intersection. Different internal masks may share one
prevalue, but different prevalues cannot be chosen separately for the modes.

Where C1 is actually recorded, H1599's conditional final-rounding contract
also applies: for these positive outputs, C1=1 iff the stored value is above
z. Its exact interval refinement is checked against H1599's independently
recorded correction inverse after reflection about one. PE is not used as
a test of final-prevalue exactness; earlier inexact operations can set it.

The complete output-matching sparse candidate set is sufficient: adding
mode/status constraints can only remove paths, never resurrect a path that
fails a required original observation. All per-mask signed corrections and
joint RC/C1 verdicts are retained in the compressed raw result stream.

## Results and redundancy

These are graph-path counts over **36 deduplicated operands**, not hardware
observation counts or general-input accuracy estimates:

| Constraints applied | Omitted payload paths | Frozen numeric payload paths |
| --- | ---: | ---: |
| Original sparse RC labels | 148,544 | 147,200 |
| All authenticated RC labels | 142,400 | 141,056 |
| Sparse RC plus actual C1 | 135,616 | 133,376 |
| All authenticated RC plus actual C1 | 135,616 | 133,376 |

The added RC modes alone remove exactly 6,144 paths per payload variant,
all at f410. Its four outputs force the exact prevalue

```text
z = 2240658402733039415 / 2305843009213693952.
```

H1599's f410/RU C1=0 independently imposes that same point. Accordingly,
every path removed by the additional RC modes had already been removed by
the authenticated C1 constraint. The other eight four-mode historical
operands lose no path on adding their recorded modes. This redundancy is
demonstrated at the full path-set level, not inferred just from matching
counts or a common best witness.

All 36 operands remain reachable with at most one local departure. Omitted
payload has seventeen zero-departure and nineteen one-departure operands;
frozen payload has nineteen zero-departure and seventeen one-departure
operands. These differ from H1595's 37-row counts because d0d0 is counted
once here, not because a hardware label was changed or a miss repaired.

Final restricted-family reachability is:

| Permitted departure cuts | Omitted payload | Frozen numeric payload |
| --- | ---: | ---: |
| Entire graph | 36/36 | 36/36 |
| All upstream cuts, ordinary terminal arithmetic | 36/36 | 36/36 |
| All eight Horner cuts only | 31/36 | 31/36 |
| Last two Horner additions only | 31/36 | 31/36 |
| Terminal cuts only | 36/36 | 33/36 |
| Last two Horner additions plus terminal cuts | 36/36 | 35/36 |

Relative to the original sparse RC labels **plus actual C1**, no family
loses reachability, no minimum departure count increases, and no
inclusion-minimal support or mandatory-departure cut changes. The report's
new-family-exclusion and support-transition lists are correctly **empty**.

The existing e73 and f410 conclusions remain: under ordinary terminal
arithmetic, all successful upstream paths for each require the square
departure. Terminal-left and correction alternatives still exist; this
does not establish the square as the physical fault. The five Horner-only
exclusions per payload variant are the four already identified by H1595
plus f410 from H1599, not new exclusions invented by the joint join.

The common inverse becomes a singleton for f410 and for the three previously
known positive RU/C1=0 equality inputs cf62, de400000a2e32d2a and f9e0000229067583.
That follows under the ordinary final-round/C1 contract; it does not measure
silicon's intermediate register width or identify its producer operation.

For selecting a possible paired-instruction contrast, square *sufficiency*
must not be confused with square *necessity*. Under joint RC+C1 and ordinary
terminal arithmetic, c891 RN (`3ffc:c891b50fb448de18`) with omitted payload
has minimal supports `{square}` or `{negative_factor}`; de400 RU
(`3ffc:de400000a2e32d2a`) has `{square}` or `{positive_factor}`. With frozen
numeric payload both require no departure at all. Neither operand therefore
requires a square change in this graph. This differs from e73 and f410,
whose upstream-only successful paths require square under both payload
treatments. These facts alone neither authorize nor design a new capture.

## Scope and next inference

H1596 established model-free common-prevalue feasibility. H1595 enumerated
faithful fixed-width graph paths for sparse observations. H1599 added C1.
H1600 checks the stronger conjunction: a *single* path and prevalue per
operand must satisfy all of those actual constraints simultaneously.
The conjunction is feasible, with no further cut exclusion.

Thus these cached constraints do not require RC-dependent internal arithmetic
within the tested graph family. They also do not disprove RC-dependent
silicon behavior. A per-input existential choice is not an operation-wide
rule and supplies no legitimate selector for unseen inputs. Changing graph
widths, forwarding, operation sequence, payload generation or the final C1
interpretation is outside the present family. No further fitting of the
collided gate profile follows from this result.

## Reproduction and artifacts

```sh
python3 fsincos-re/experiments/h1600_joint_rc_c1_faithful_graph.py --selftest
python3 fsincos-re/experiments/h1600_joint_rc_c1_faithful_graph.py \
  --root fsincos-re --output-dir /private/tmp/NEW_h1600_output
```

The output directory must not exist. The current canonical C source is not
executed or substituted for the historical graph. Provenance uses
`tmp/ledger33/current/h1598_source_before.c`, SHA-256
`de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.

The selftest includes H1596's 4,464 signed-neighbor cases and two intersection
endpoint checks, plus 204 forward/inverse/C1 cases with exact integer final
rounding. Full replay checks every distinct generated prevalue against every
actual required output and the exact inverse, and verifies agreement with
H1599's previously filtered path sets. Minimum witnesses include the complete
graph stages, the common prevalue, and all observed-mode predictions.

Authoritative artifacts, relative to `fsincos-re`:

- `experiments/h1600_joint_rc_c1_faithful_graph.py`, SHA-256
  `6ce8f94f999a66746194ed06d35819df8cbae317d42ca3e116c7f8a770978198`.
- `tmp/ledger33/current/h1600_joint_rc_c1_faithful_graph_v2/report.json`, SHA-256
  `e5d9c15ac734d6bc21d609890c3a31d581c3defe913ae8318354ab0cee8e2da6`.
- `joint_rc_c1_paths.tsv.gz` in the same directory, SHA-256
  `84ee757aa61a73bdb3877bea00d2db8559d22fa1445785bd1d09b1c944455051`.

The raw stream contains 295,744 candidate paths. The final JSON and compressed
stream reproduce byte for byte in a separate temporary directory. Python
syntax and whitespace checks pass. Version 1 is retained as a superseded
report; v2 adds explicit path-set-redundancy fields without changing arithmetic
or accepted paths. No historical SAT/UNSAT/UNKNOWN artifact was altered.
