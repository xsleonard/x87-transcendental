# Sine and cosine reconstruction, with the complete x87 reference

**Reconstructing FSIN, FCOS and FSINCOS from Public Constants and Processor
Tests** is the current article: [PDF](../../output/pdf/x87-suite.pdf),
and [LaTeX source](x87-suite.tex).

The main contribution is the FSIN/FCOS/FSINCOS reconstruction: distinct
standalone and paired schedules, operand widths, table rounding destinations,
exact reduction, and the experiments that distinguish those rules. The
[findings map](TRIG-FINDINGS.md) connects those claims to the research records.
The article and its reference appendices now use three separate families:

1. **FSIN, FCOS and FSINCOS:** the main investigation, including its published
   foundations, reconstructed algorithms, constants, validation and limits.
2. **FPTAN and FPATAN:** tangent and arctangent, with their own algorithms,
   source evidence and validation.
3. **F2XM1, FYL2X and FYL2XP1:** the shorter exponential/logarithm material,
   placed last with its own constants and checks.

The article explains the final algorithms and how the sine/cosine arithmetic
was derived. Development history remains in the research records. The family
listings contain all executable statements; the complete commented sources
are included in the repository and package. A final support appendix holds
the shared arithmetic and dispatch code. All 239 literal entries remain, grouped by family.

From the repository root, with Python 3.10+ and Tectonic:

```sh
python3 fsincos-re/paper/build_suite.py
```

Add `--render` to generate page PNGs using Poppler. The first Tectonic build
may download its TeX packages and fonts. Counts and listings are generated
from canonical source and authenticated receipts; changed specification
hashes stop the build. The generated `generated-suite/suite-manifest.json`
records article and evidence hashes for that build. Source formatting is independent of any eventual venue.

The [programmer package](../../output/release/x87-suite-review-v6/README.md)
contains a clean build/check entry point and offline hardware witnesses.
Licensing is undecided at the author's request. This is a local technical
report and review artifact, not a claim of external peer review or an
assigned public repository/DOI.

The [evidence register](EVIDENCE.md) and [source register](SOURCES.md) explain
the claims and their supporting sources.

## Earlier paper: Thirty Years of the Pentium Kernel

The publication manuscript is `skylake-x87.tex`; the rendered paper is
`skylake-x87.pdf`. Build with `tectonic --keep-logs skylake-x87.tex` from
this directory, or with a standard LaTeX distribution.

## Programmer's pseudocode

Appendix A gives a code-first walkthrough of exact reduction, quadrant and
kernel dispatch, standalone and paired polynomial schedules, the shared table
kernel, tiny predecessors and final rounding/C1. Section 4 links to it.
The same code blocks appear in the
[trig pseudocode reference](../docs/TRIG-PSEUDOCODE.md), with links to
their C counterparts. Arithmetic is exact except at the explicitly named
rounding steps; the walkthrough does not use host floating point or extend
the paper's numerical claim to complete x87 state emulation.

## Current confirmed result — H1717, 2026-09-05

All three numerical instructions are promoted in the default main C:
standalone FSIN/FCOS retain H1708 and FSINCOS uses the independent all-product
paired Horner program. Every Horner product is CHOP67 before its RN64
coefficient add, with exact quadrant mapping and the external-cosine C1 rule.
No operand ledger, fitted selector or history correction is on either route.

H1717 rechecks 23,838,534 retained paired lane appearances, 3,379,017
standalone outputs and all 81 standalone frontier rows: zero misses. The
actual main executable also replays the frozen H1712 campaign's 13,800 tuples,
27,456 outputs and 13,728 C1 checks exactly. H1712 was prospective: all four
RC modes and PC24/53/64, once per fresh tuple; its predecessor fails 750 rows.
H1717 additionally passes the 45,517,233-row i7 paired review census and all
357,360 saved H1712/H1714/H1715/review tuples across the three instructions.
These counts overlap; they are not unique fresh captures.
The replays are not new observations. Four compiler variants and an independent
integer/rational program verify the promotion, with the original standalone
kernel arithmetic byte-identical. The paired interval certificate covers
every polynomial binade: 840 operation checks, at most 139 accumulator bits
and 132 alignment shifts, within the established entry/helper contracts.

The independent review falsified H1713's last-product-only program at paired
RN input `3ffc:e79000000c3e46e7`. The corrected paper includes that exact
separator and its midpoint arithmetic, not an input-specific patch. The
prior H1713 numerical closure claim is withdrawn; its artifacts remain
historical evidence. Policy 2 has no known miss in the completed checks,
not an exhaustive or uniquely identified physical-circuit proof.

The 15-page PDF, including the three-page pseudocode appendix, compiles
without TeX warnings and passes render/visual
review using the PDF skill. Only confirmed arithmetic and exact evidence
limits were added. No hidden physical-schedule uniqueness or cross-generation
claim is made.

## H1708 standalone milestone — preserved

The user authorized promoting the validated standalone FSIN/FCOS program into
the default C implementation and paper. The manuscript now specifies exact
M66 integer reduction, X67/Y64 multiplication, RN64 additions, distinct
sine/cosine terminals, the table multiply's direct RN64 destination, and the
tiny predecessor rule. No captured-operand ledger or fitted exception
selector is part of the promoted standalone route.

All 81 recorded incumbent-frontier outputs match. The promoted build passes
3,379,017 retained output appearances and 3,378,987 applicable C1 checks.
It also passes the 7,056 already-opened boundary/center outputs and 5,136
frozen C1 predictions. Four compiler variants agree with the archived
candidate; paired FSINCOS was unchanged in that earlier promotion.
These are retained appearances, not new observations or a new hardware run.

## Evidence map

- `../notes/h1717-policy2-promotion.md`: current corrected promotion,
  exact separator, regressions and source/report hashes.
- `../notes/h1718-corpus-v1-expansion.md`: finite adversarial corpus,
  practical run sizes, archived previous v1 and separate CPU observations.
- `../notes/h1713-paired-promotion-and-completion.md`: historical promotion,
  requirement-by-requirement completion evidence, commands and source hashes.
- `../notes/h1711-h1712-paired-fresh-validation.md`: immutable fresh campaign,
  exact preimages versus brackets, provenance and negative controls.
- `../experiments/h1717_promoted_regression.py`,
  `h1717_verify_promotion.py` and `h1717_paired_carrier_bounds.py`: current
  main-entry regressions, compiler/independent checks and interval bounds.
- `../notes/h1707-h1708-standalone-promotion.md`: current promotion, exact
  source/report anchors, validation scope and pre-promotion archive.
- `../experiments/h1708_verify_promotion.py` and
  `../tmp/ledger33/current/h1708_default_promotion/report.json`: default
  C regression, header identity, compiler and paired-isolation checks.
- `../experiments/h1708_opened_boundary_regression.py` and the same
  artifact directory's `opened_boundaries.json`: raw H1641/H1694 replay.
- `../notes/h1630-h1632-shared-polynomial.md`,
  `../notes/h1633-h1635-shared-table.md`,
  `../notes/h1638-h1643-tiny-and-remaining-scope.md`: fixed programs,
  independent verification, domain arguments and component validation.
- `../notes/h1622-h1626-fixed-candidate-fresh-challenge.md` and
  `../notes/h1690-h1695-exact-center-campaign.md`: frozen prospective
  challenges and the exact-center coverage union.
- `../notes/h1698-h1699-integer-helper-and-carrier-proof.md`,
  `../notes/h1700-exact-reduction-contract.md`,
  `../notes/h1701-conversion-and-bypass-grid.md` and
  `../notes/h1702-configured-route-and-history-audit.md`: supporting
  implementation certificates, with their stated trust boundaries.
- `../notes/rom-errata.md` and `../notes/amd-zen3-comparison.md`:
  retained ROM-lineage and cross-vendor findings.

The policy-1 header/binary, preceding paper and READMEs are preserved under
`../tmp/ledger33/current/h1717_pre_promotion/`. The H1708 source, PDF, README and build wrapper are preserved under
`../tmp/ledger33/current/h1713_pre_promotion/`. The preceding artifacts from
before the standalone promotion are preserved under
`../tmp/ledger33/current/h1708_pre_promotion/`. The obsolete R96-as-current
narrative is superseded, not retroactively declared correct. Detailed failed
fits and research chronology remain in the handoff and historical notes.
Those old notes' no-promotion statements describe their original epochs.

Only confirmed results belong in this paper. The numerical claim is
standalone FSIN/FCOS and paired FSINCOS on one Skylake Xeon reference, not a
recovered netlist, complete x87 state emulator or cross-generation guarantee.
Future investigations belong in the handoff, not in the paper as confirmed laws.

Author attribution is intentionally withheld. Do not infer a name or contact
address from Git metadata, account details, or local paths. Add attribution
only after an explicit instruction from the user.
