# H1610: shared multiplier and adder precision does not rescue this graph

Date: 2026-09-04. All 17,822 tested precision/payload cases fail. This is a
bounded structural arithmetic hypothesis audit, not a recovered chip contract
or a general impossibility result. No source/default, capture or PDF change.

## Hypothesis and provenance boundary

H1606 changed only one materialization width. H1608/H1609 allowed conventional
rounding or exact forwarding at every node, but kept the original finite
widths. Neither test excluded simultaneous changes to several finite widths.

H1610 assigns one precision M to all eight multiply operations (including
square, fourth and terminal products), and one precision A to all four Horner
adds. The correction add uses either A or the original 67-bit precision.
This is a shared operation-class structure, not a width selected by operand.

M and A each range over `{24, 53, 64, 65, ..., 128}`. Widths are **significand
bits**, not total storage-format widths. The upper limit is a finite audit
bound, not a physical-width assertion; untested widths are not excluded.
Duplicated correction choices when A=67 are removed, leaving 8,911 distinct
width vectors per payload, 17,822 cases in total.

For each width vector, all thirteen operation policies remain independently
free among CHOP, nearest-even, nearest-away, AWAY and JAM. A policy at a given
node must be common across inputs and RC. Thus each case quantifies all
`5^13` named policy vectors; it does not leave surrounding arithmetic ordinary.
The graph, coefficients, final RC64 and absent/frozen original numeric payload
are held fixed. There is no optional exact bypass in this new width family.

H1594 supplies no concrete missing FADD/FMUL variant widths. It was reviewed
before this test: the class-sharing above is an explicitly unvalidated
numerical hypothesis, not something established by that source. A survivor
would still require control-bank and fresh-hardware scrutiny.

## Results

All cases are rejected by actual **output bits alone**. The number of required
operands in the fixed rejection prefix is:

| Prefix length | Rejected width/payload cases |
| --- | ---: |
| 1 | 792 |
| 2 | 16,754 |
| 4 | 22 |
| 6 | 254 |

The prefix starts with the two H1609 RD observations, `e73ffffd2c52df71` and
`fcbfffffcee1bd36`, then `b0000000044ca2bf`, `b72fd2547f8c2fef`,
`ba100000056e0a67`, and `cdcc0585c940196f`; all have exponent `3ffc`.
Every actually recorded mode of an added operand is constrained.

The 254 six-operand cases all use M=64. They survive the old RD pair and the
first five operands under some shared assignments, but fail when cdcc joins.
They are not candidates or near-solutions. No case reaches the full 36-operand
bank or H1603 controls. Later untested operands are not counted as successes,
and these sufficient rejection prefixes are not claimed minimum cores.

The first one/two-operand rejections use only RD, but the 276 longer-prefix
cases add other modes. Consequently this audit does **not** exclude arbitrary
RC-dependent policy choices for every new width vector. H1609's RC-only proof
applies to its original-width six-choice family, not automatically to this one.

## Verification

The exact dynamic program keeps live numerical values and constructs complete
five-choice diagrams for every hypothesis. Saved artifacts retain widths,
checked operands, complete allocated nodes, both output/output+C1 roots and
false final roots. The traversal represents 195,938,544 numerical paths via
6,001,084 distinct live states across the checked hypotheses.

- All 72 original-width operand/payload functions are canonically identical
  to H1602's full saved functions, not merely equal in accepted counts.
- 32 arbitrary multi-width cases agree in complete function and numerical
  path count with H1606's separate non-memoized traversal.
- 171,182 straight-line full-policy replays agree on both actual-output and
  output+C1 acceptance.
- 5,360 rational quantizer cases span every tested precision; 128 random-width
  rational graphs check 1,664 intermediate stages. H1602's 2,430 diagram and
  6,132 nearest-away reference cases also pass.

The compiler and quantizer reuse named prior components. These checks do not
constitute a newly recovered physical unit implementation. No real x87 input
was executed or observed for this audit.

## Artifacts and remaining scope

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1610_shared_operator_precision.py` | `a9a3dbe97512db6e49d664ef089d1d00edf33fa57056faf0f55af6373a30bd7d` |
| `tmp/ledger33/current/h1610_shared_operator_precision/report.json` | `5b19899c92d5ba3b471ccfeea98eb4d8388ebeb266ccd0bdca449371cfdc5013` |
| `precision_diagrams.jsonl.gz` in that directory | `f24d0779926ece6896d2776f7cf5b6c88a8d6b7cadc423f7cfc37940ec34a0d2` |

```sh
python3 fsincos-re/experiments/h1610_shared_operator_precision.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing directories are refused. Separate full replay reproduces the report
and complete diagram stream byte-for-byte. Syntax, whitespace and normal
build/selftest checks pass.

Outside this family remain arbitrary per-cut finite widths, the untested
precisions, changed-width-plus-bypass combinations, different graphs/routing,
RC/input-dependent choices, nonstandard/history semantics and changed payload
generation. In particular, a next mode-only refinement could test the 276
width/payload cases not already rejected by the RD pair. This is not authority
to infer operand-specific precision predicates. R96 remains empirical and
incomplete; the 45/44 direct and 75/74 external failure frontiers are unchanged.
