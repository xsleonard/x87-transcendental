# H1596: actual cached RC labels admit a common pre-rounded value

No authenticated group in this audit forces rounding-mode-dependent internal
arithmetic. Exact final-rounding inverse intersections are nonempty for all
**37,594 instruction/operand groups**, comprising **150,005 deduplicated
observed mode rows**. This is feasibility, not proof that the hardware is
RC-independent, that the current arithmetic is correct, or that a general
selector has been recovered.

No hardware or C model was executed, no previously unopened labels or private
ledger were consulted, no modes were inferred, and no emulator, paper/PDF, or
failure-frontier count was changed. The analysis uses hardware columns, never forced-carry or
literal-ledger model outputs, as labels.

## Provenance and actual mode coverage

The previously named 82-row direct bank contains the 77 reconciled direct
observations plus five defining controls. It has 81 operands; **within that
82-row subset alone**, d0d0 is the only multi-mode operand, with RD and RZ.
Those are identical constraints on a positive result. However, that subset
does not exhaust pre-existing cached hardware observations.

H1091 contains 116 actual observations for 29 operands, four modes apiece.
Its importer checks each operand against the corpus input index and reads
the corresponding four hardware status streams. H1291 pins that table's
SHA-256. H1596 verifies the raw table's
hash and exact agreement of its hardware columns with H1092, without using
any H1092 model predictions.

Nine of the ten current historical residual operands occur in H1091. Adding
their missing observed modes enriches the named direct bank to 109 rows over
the same 81 operands:

| Actual coverage | Operands |
| --- | ---: |
| RN/RD/RU/RZ independently recorded | 9 |
| RD/RZ only: `d0d000000cc0b3f8` | 1 |
| One recorded mode | 71 |

The nine four-mode operands are b000, ba10, cca0, d920, f410, fa50, and the
three far-corner operands. The full report provides exact operands, outputs,
and source identities. In particular, the new equality-campaign inputs and
H1589 opposing-profile pairs have no new cross-mode labels in this bank.

H1210's 44-row residual table was also inspected. Its generator explicitly
substitutes baseline outputs for missing hardware legs and sets RZ equal to
RD. It contains no d0d0 row. Those entries were **not** admitted as additional
observations. This does not deny the older suite-comparison argument; it
keeps this audit's raw-observation and inferred-truth categories separate.

H1107 independently joins four previously captured status streams for
37,441 control operands. Its 149,764-row hardware table is hash-locked by
H1590 and H1291. All of it is audited, separately from the named frontier.
H1590's complete input-evidence hashes and the newer campaigns' opened/raw
sidecars are checked before analysis.

## Exact test, independent of the proposed micro-operation sequence

For a recorded binary80 value `y`, let `prev(y)` and `next(y)` be its adjacent
representables. These include the asymmetric neighbor spacing at binade
boundaries. The pre-rounded value `z` must lie in:

| RC | Exact inverse interval |
| --- | --- |
| RN | Between `(prev(y)+y)/2` and `(y+next(y))/2`; endpoints included iff the normalized significand is even |
| RD | `[y,next(y))` |
| RU | `(prev(y),y]` |
| RZ, positive output | `[y,next(y))` |
| RZ, negative output | `(prev(y),y]` |

For the same instruction and external operand, intersect the intervals from
**only the modes actually observed**. An empty intersection would exclude
the model “one RC-independent prevalue followed by ordinary final RC
rounding.” It would not uniquely prove which internal operation consumes RC:
a nonstandard final mapping or another unmodeled state could also invalidate
that model. No such empty intersection was found here.

This formulation does not require a polynomial, a terminal carry, a 67-bit
correction, or an assumed `1-c` reconstruction. All current outputs admitted
here are finite normal binary80 values; the implementation explicitly rejects
unsupported output classes rather than silently extending the conclusion.

## A useful singleton constraint

For `3ffc:f4100000059862dd`, actual RN/RD/RU/RZ observations all equal
`3ffe:f8c35790ef2cf9b8`. Consequently the hypothetical common prevalue is
forced to the **single exact number**

```text
z = 2240658402733039415 / 2305843009213693952.
```

It cannot merely lie somewhere in the same rounding bin: RD and RU agreeing
make their intersection a point. If a separately justified graph ends in
`1-c`, that graph must produce

```text
c = 65184606480654537 / 2305843009213693952
  = 133498074072380491776 * 2^-72.
```

The `1-c` statement is conditional; the singleton `z` follows directly from
the observed outputs and ordinary final-rounding hypothesis. It supplies an
exact all-mode constraint for the independent whole-graph investigation.

The other eight four-mode historical residual operands admit open or
half-open half-ulp intervals. Five have a 65-bit dyadic witness and three
need 66 bits if searching normalized witnesses of precision at least 64.
These are **minimum precision of an existential witness**, not measurements
of the physical accumulator width.

## Aliases do not add missing canonical RC coverage

The 52 already-observed H1570/H1573 reduction aliases are audited as their
own external instruction/operand groups. Their output inverses are valid
without any transfer assumption. Combining them with the named direct bank
gives 134 rows over 133 instruction/operand groups, again all feasible.

For a separate, explicitly conditional residual projection, a negative
output's interval is reflected about zero. This exchanges RD and RU; RN is
unchanged, while RZ follows the sign-aware definition above. Every reflected
alias interval equals its already-observed anchor interval at `anchor_mode`.
Therefore the 52 aliases add **zero new effective RC lanes** and do not shrink
any enriched direct intersection.

Treating those intervals as constraints on a common residual producer assumes
transfer across the signed reduction and instruction paths. The report keeps
that assumed projection separate from direct-only necessary facts. It does
not turn an unobserved direct mode into a hardware observation or establish
universal transfer from 52 successes.

## Complete audited counts

| Bank | Unique observed rows | Instruction/operand groups | Empty intersections |
| --- | ---: | ---: | ---: |
| Named direct subset | 82 | 81 | 0 |
| Named direct plus actual H1091 modes for those operands | 109 | 81 | 0 |
| Complete H1091 historical bank | 116 | 29 | 0 |
| Complete H1107 control bank | 149,764 | 37,441 | 0 |
| Union: named, H1091, controls, external aliases | 150,005 | 37,594 | 0 |

The union has 37,470 four-mode groups, one RD/RZ-only group, and 123
single-mode groups. No label is counted twice. A separately chosen rational
witness is checked against every observed interval in every feasible group;
those witnesses are feasibility certificates, not an emulator or a lookup
table offered as a solution.

The historical four-mode importer/forced-response work already exploited
multiple RC labels to constrain specific model endpoints. H1596's distinct
result is an exact, model-free inverse-intersection reconciliation of actual
labels, including the newer sparse one-mode campaigns, their signed aliases,
and the independently cached all-mode wall. Current coverage does not select
an RC-dependent mechanism over an RC-independent one.

## Reproduction

```sh
python3 fsincos-re/experiments/h1596_rounding_mode_feasibility.py --selftest
python3 fsincos-re/experiments/h1596_rounding_mode_feasibility.py \
  --root fsincos-re --output NEW_REPORT_PATH
```

The selftest checks 4,464 signed exact-neighbor rounding cases, including
binade boundaries and tie parity, plus open/closed intersection endpoints.
The report preserves source hashes, all named/historical intersections,
alias projections, complete-wall counts, every conflict if any, and canonical
observed-row hashes. Its authoritative path is
`tmp/ledger33/current/h1596_rounding_mode_feasibility.json`.
