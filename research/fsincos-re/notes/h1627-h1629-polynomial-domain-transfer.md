# H1627–H1629: wider cosine transfer and a reachable-width theorem

2026-09-04. Analysis-only continuation of the fixed arithmetic candidate.
No new hardware, private-history access, canonical/default change, or paper/PDF
edit. The full FSIN/FCOS solution goal is still unachieved.

## What changed in our knowledge

The same arithmetic that passed H1624's fresh binade -3 campaign now passes
the retained lower-binade boundary walls and broader reduced/signed cosine
observations. No new selector or binade-dependent arithmetic was fitted.

The initial apparent ambiguity between the simplified formula and its
all-X67/Y64-port formulation also disappears over the current model's entire
reachable cosine-polynomial domain. A source-backed integer-grid argument
proves that reduced polynomial inputs have at most63 significant bits; direct
inputs have at most64. The H1617 width-induction argument therefore applies
throughout this domain, not just binade -3.

That is a theorem about the specified reduction/dispatch/numerical program,
not proof of physical port widths, hidden silicon state, or universal hardware
correctness. The runtime scope guard in the original H1618 artifact is not
edited or promoted by these experiments.

## H1627: two fixed wider hypotheses, exact hit/fallback accounting

Two analysis builds remove H1618's residual-binade/precision guard while
leaving the original dispatcher intact:

- `simplified`: the unchanged whole H1618 graph, including
  `F=T67(S*T64(S))` and ordinary terminal `T67(L+R)`.
- `all_ports`: the original natural formulation with X=CHOP67 and Y=CHOP64
  applied uniformly at multiplication inputs. No input classifier is added.

Both still run only for the cosine-polynomial branch chosen by the existing
operation-class dispatcher. Table, tiny, exact-residual, special-input and
sine-polynomial paths retain the incumbent; their agreement receives no new
arithmetic or C1 credit. R84 is OFF in every software comparison.

The retained H110 sweep and dense inputs feed both standalone instructions
in actual RN/RD/RU captures. The historical runner documents their shared
positional input streams. FCOS files/inputs are checked against H1620's pinned
hashes; all FSIN/FCOS streams also match the retained per-instruction copies
byte-for-byte. Those duplicate files are provenance checks, not additional
observations. Source hashes are locked before scoring and checked afterward.

| Bank | Actual row appearances | Candidate hits | Outside old guard | Fallback |
| --- | ---: | ---: | ---: | ---: |
| Sweep, FCOS | 150,114 | 26,484 | 14,295 | 123,630 |
| Sweep, FSIN | 150,114 | 21,894 | 15,090 | 128,220 |
| Dense, FCOS | 720,000 | 240,000 | 0 | 480,000 |
| Dense, FSIN | 720,000 | 0 | 0 | 720,000 |
| Total | 1,740,228 | 288,378 | 29,385 | 1,451,850 |

For EACH fixed formulation, every candidate-hit output and recorded C1 bit
passes. All fallback outputs remain unchanged/exact; fallback C1 is unscored,
not established by zero-valued placeholder counters. The only incumbent miss
in this audit is H1621's already-known sweep FCOS/RU `9f4c...` row. It is fixed
again, not a new frontier operand. The variants are numerically identical on
every observed hit; none has input precision above64.

The hits include 38,946 reduced-input appearances, 249,432 direct-input
appearances, and 19,479 negative-result appearances. Residual top exponents
span -32 through -3. The 29,385 extended hits lie below binade -3. These are
finite retained-bank appearances, partly overlapping prior audits, not a fresh
or deduplicated all-corpus count. No RZ observation is imputed.

H1627 first independently checks 2,696 selected full-graph/terminal rows,
including all changes/misses and a representative per observed scope/precision/
sign/mode cell. H1629 below upgrades this to full independent arithmetic and
reduction replay for every candidate-hit row.

Preserve the initial H1627 parser failure. It lowercased the status marker
while matching uppercase `SW`, and its global `c2` replacement could corrupt
hexadecimal payloads. The run stopped on the first raw row before any score
was counted. Its source, binaries, prepared record, partial streams and
`run-status.json` remain intact. The v2 reader uses case-insensitive token
matching without payload mutation and adds normal, uppercase-hex and C2 parser
checks. It uses a separate source/output directory. Neither arithmetic
hypothesis was changed, and no failed artifact was rewritten.

## H1628: the difficult lower-binade walls

The broad sweep is not a substitute for the old R1158 boundary challenges.
H1628 therefore imports all 51,229 H1135 and 2,151 H1160 actual mode/input rows.
Their original raw streams and per-mode input files must agree positionally
with the frozen manifests and with independently pinned historical scores.

Both wider builds pass **53,380/53,380 actual outputs**, over 38,804 distinct
operands. The full tuple union also has 53,380 members. All these inputs are
positive direct FCOS in binade -4 and enter the widened hook, not fallback.
The current R1158-enabled incumbent also passes all rows. Thus this is
evidence that the same simpler arithmetic accounts for the tested lower-binade
behavior; it is not a proof of global identity to every R1158 recurrence cell.

Every row receives an independent Fraction-graph check in H1628 and a separate
integer-graph check in H1629. Raw captures have no status: known hardware C1
count is ZERO. Predicted C1 is internally checked but never labeled observed.
The full per-variant replay is retained, including exact inputs, raw ordinals,
outputs, reduction metadata and independent predictions. There are zero new
incumbent misses, and the current frontier remains direct50/48, external81/79.

## H1629: the whole-domain numerical equivalence

The canonical reducer uses the integer
`M = 0x3243f6a8885a308d3` at scale2^-65. For the reduction-input exponent range
`e=-1..62`, an external operand is exactly the integer
`A = significand * 2^(e+2)` at the same scale. Its centered quotient gives
`D=A-N*M`. Since M is odd, `2*remainder=M` is impossible: this particular
exact-division quotient has no half ties. This does not address historical
reciprocal-seed rounding or claim new hardware evidence about either.

The centered residual satisfies `|D| <= floor(M/2) < 2^65`. The polynomial
dispatcher requires `2^-32 <= |D|*2^-65 < 2^-2`, hence:

```text
2^33 <= |D| <= 2^63-1
```

Consequently a reduced polynomial input has at most63 significant bits. More
precisely, residual binade `t=-32..-3` permits integer magnitudes from
`2^(t+65)` through `2^(t+66)-1`, with at most`t+66` bits. Direct unreduced
external inputs have at most64 significant bits by their representation.
The reducer's optional 65th-bit `c` component belongs at magnitude>=1/2,
outside the polynomial domain. Padding a 63-bit value into a 64-bit container
does not make it a wider numerical input.

Now apply H1617's inductive width argument: each multiply result fits67,
each Horner-add result fits64, native cosine C5 fits59 and C6 fits64. All X67
cuts and every Y64 cut except square feeding fourth are identities. Removing
them preserves every later exact operation/materialization. This proves the
natural all-port and simplified programs equivalent over the entire reachable
cosine-polynomial domain of this specified model. There is no reachable
>64-bit numerical polynomial input requiring a new selector between them.

The certificate is a source-backed mathematical argument plus finite C-trace
verification, not a formal proof of every C execution or silicon behavior.
Do not infer that undocumented physical state or a different reduction graph
is impossible. Do not force the six-coefficient graph through the table/tiny
dispatcher to manufacture a broader domain claim.

## Full independent verification and reproduction

H1629 imports no producer arithmetic, freezer, scorer or parser modules. Its
unbounded integer dyadics spell out the entire fixed graph and final RC rule.
It independently recomputes the M66 quotient/residual and quadrant sign for
every candidate-hit external input, authenticates the stored magnitude, and
checks all per-row width/binade metadata. Every one of the 288,378 hit outputs
and recorded C1 bits passes for each variant. All 53,380 targeted lower outputs
pass for each variant too, with absent status kept unknown. There are 134,927
distinct normalized magnitudes in its arithmetic cache, not a new hardware
tuple count.

A second software run reproduces the COMPLETE H1628 output directory and
the H1629 report byte-for-byte in
`/private/tmp/h1629-root-replay.yPS9q4`. H1627's complete data is independently
re-read/recomputed by H1629; no second C rebuild/report reproduction is claimed
for H1627. No hardware instruction is run during any verification.
Python syntax, canonical build/selftests and whitespace/diff checks pass.
Source/defaults remain unchanged at SHA
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.

## Artifact anchors

All paths relative to `fsincos-re`. Reports pin their raw sources and streams.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1627_wider_cosine_observer.h` | `7ed2154d488b779539c89e3e008d9e339b665062c29a47c6b9bf99e7d701c46f` |
| `experiments/h1627_wider_cosine_transfer_v2.py` | `5e8350946774fca72520464c186c319371e26cd8b5f67cb48bb67eeab3d321e5` |
| `tmp/ledger33/current/h1627_wider_cosine_transfer/run-status.json` | `eec7f40a20b29cee68f3e790a23cd442e4805cba9b5b0d3e4264d9d9cad5849f` |
| `tmp/ledger33/current/h1627_wider_cosine_transfer_v2/report.json` | `4481d624bc46037674ef0c60313c5f2f171ba5f87d65eaa368a42292655db962` |
| `experiments/h1628_targeted_lower_transfer.py` | `feb57ba316aa55374d816e3b8cd2d11b370b208759fcbd4f10e838fbce5c4042` |
| `tmp/ledger33/current/h1628_targeted_lower_transfer/report.json` | `7a66c76cfc3b403173593a602ddcd89707aae5f4d1362082f9c2e61ea4428f3a` |
| `experiments/h1629_polynomial_domain_certificate.py` | `72291e774bd4301dfcdea4095d9d01641797701cf6c90b7bb567f150ba5dca1f` |
| `tmp/ledger33/current/h1629_polynomial_domain_certificate/report.json` | `8bdae726f3f01af3b1e30955af28b08f20d1e5b88aba2f3f7185b17112c22aee` |

## Next work

Keep the fixed arithmetic and audit the sine-polynomial schedule using the
same explicit operators and native sine constants. Its current R86 square-
port truncation is already unconditional; do not invent an activation gate.
The cosine and sine polynomial paths have different terminal schedules,
so sharing multiply/add operators does not authorize silently sharing a
terminal rounding rule. Use separate hit/fallback and known-status accounting.
Then pursue the table, tiny/special and full architectural status obligations.
Numerical program equivalence and finite hardware passes remain distinct from
the required general silicon model. No canonical promotion or paper update.
