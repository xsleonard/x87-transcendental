# H1594: internal-operation semantics and provenance audit

Date: 2026-09-04

Status: **no new source-backed FSIN/FCOS arithmetic contract, control bit, or
executable silicon hypothesis.** Internal operation variants remain a valid
research direction, but the audited source does not supply the missing rule.
No selector is promoted.

## Primary-source evidence matrix

Source: John O'Leary, Xudong Zhao, Rob Gerth and Carl-Johan H. Seger,
*Formally Verifying IEEE Compliance of Floating-Point Hardware*,
[Intel Technology Journal Q1 1999](https://www.intel.com/content/dam/www/public/us/en/documents/research/1999-vol03-iss-1-intel-technology-journal.pdf).
Article pages 1-8 are physical PDF pages 48-55, inspected completely as rendered
pages. Figure 3 was also inspected at higher resolution. The footer's
"Formerly" is a source typo, not the article title. PDF SHA-256:
`65a461af7650a0945acfa72e362f39de8a93f34d9f480d850f14b3629d3a9f02`.

| Location | Actually specified | Not supplied |
|---|---|---|
| p. 1, abstract/introduction | Pentium Pro FEU verification; earlier verification missed an erratum. | Skylake equivalence; FSIN/FCOS proof. |
| p. 3, Figure 1 | Parameterized mantissa/rounding relations, including binade-edge asymmetry. | Concrete intermediate register width or opcode mapping. |
| pp. 4-5, Figure 2 | Truncated multiplication, loss-of-significance sticky, then destination rounding. | Variant-specific precision, bypass or wiring. |
| p. 5, Figure 3 | Internal FPSHR reference pseudocode: exponent-distance-capped significand shift, zero handling. | Numeric cap, field widths, flags, opcode encoding. |
| pp. 5-6, FADD/FSUB section | Five-stage *reference* algorithm; gate model checked as a black box. | Five physical stages, internal signal/control implementation. |
| p. 5, footnote 1 | Some internal operations lack meaningful IEEE-level specifications. | Their complete semantics or transcendental-site bindings. |
| p. 7, aims 3-5 | Flags/faults, microcode-only variants, precisions and rounding modes covered. | Names or a semantics table for those variants. |
| p. 7, scope paragraph | Executing microcode correctness and interference/stall behavior excluded. | Composition proof for transcendental routines. |
| p. 8, first paragraph | FMUL structural properties required changes across generations. | Transferable later-generation netlist. |

The source's only explicit internal-operation reference program is FPSHR, not
an FADD/FMUL variant. Its parameterized dataflow is
`k = min(abs(e1-e2), max)`, `m' = shr(m2,k)`,
`e' = (0 if m' == 0 else e2)`, `s' = s2`. The `shr` helper, widths and
numeric `max` are not defined. No separate normalization, rounding increment
or sticky accumulation appears. This is not permission to substitute a
particular low-bit interpretation at another operation.

## Reconciliation with existing work

The wording in H1431-H1433 that the source publishes no reference implementation
should be read specifically as **no relevant FADD/FSUB implementation**: the
small FPSHR example is public. That clarification does not add an R59 selector
coordinate or establish an executed FPSHR at the unresolved cosine tail.

The current audit checked these prior boundaries before assigning novelty:

- H1425-H1427 already covered the named historical multiplier sticky,
  normalization, bus-layout and FADD-rounder signals. Their exclusions apply
  to those exact reconstructed signal vocabularies, not every possible
  conditional intermediate-precision rule.
- H1450, H1453 and H1454 separate validated carrier metadata, visible flags, the unknown
  final-add low-bit contract, and public Goldmont raw controls. Intel 1999
  does not establish the missing guard/sticky equation.
- H1457-H1459 exhaust the named current public legacy-P6 update corpus, not
  base ROM. The expanded census still has no candidate tail forms. No new
  patch corpus or ROM was obtained here.
- H1460/H1467's old body partition is superseded by H1555. H1556's exact
  physical representation is distinct from H1557's nonvalidated near-decoder;
  H1559-H1563's history, adversarial and conditional NOP-crib results do not
  turn that near-decoder into control semantics. None yields a final-add
  variant.
- H1499 already restricts historical tree topology by generation. H1589 now
  also prevents using R1263 as a recovered physical-gate anchor.

## Consequence for the next arithmetic model

Zero new executable silicon hypotheses are justified by this documentary
audit. Inventing a precision selector or assigning an unknown opcode a desired
rounding equation would add an assumption, not consume newly recovered
evidence. The source does support the *methodological* separation between
operation correctness and correctness of their composition.

Accordingly, an independent arithmetic specification should label each
stage's width, normalization, sticky treatment, rounding and forwarding as
either an observed constraint, an independently documented contract, or an
untested assumption. Backward intervals from observed outputs can test shared
operation semantics without assuming that the final forced-carry intervention
is the physical cause. A mechanism-discriminating capture needs concrete
competing predictions first; this note supplies neither a new tuple nor a
reason to repeat an observation.

## Artifacts and checks

`experiments/h1594_internal_operation_provenance.py` hash-checks the original
PDF, checks the expected text-page anchors, and records identities of prior
artifacts in `tmp/ledger33/current/h1594_internal_operation_provenance.json`.
It is a documentary consistency check, not proof of the visual interpretation
or silicon behavior. Rendered source pages remain under the same H1594 prefix.

The audit passes eight page checks; a second output reproduces the JSON
byte-for-byte. Python compilation and scoped diff checks pass. Script SHA-256:
`3dc7799210e138167e5427a3e6f65bfacd29db13af53684fdeb7c0799bdfefdf`.
Report SHA-256:
`dbf427723d53a4ecee0e2374acecbac07892b1708e78d160b5c9123c625382b6`.

No x87 instruction, remote execution, ROM loading, hardware capture, label
opening, emulator/default change, paper/PDF edit, or commit occurred. The
source PDF is untouched. R96 remains empirical/incomplete; the current
45-row/44-residual-operand frontier and the full emulation goal are not closed.
