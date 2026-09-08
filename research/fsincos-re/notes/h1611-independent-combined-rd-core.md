# H1611: independent arithmetic certificate for the combined-family RD core

Date: 2026-09-04. Confirms H1609's specified finite-family rejection without
its decision-diagram compiler or live-state suffix optimization. No model,
capture, status label, private-ledger or paper/PDF change.

## Two actual outputs, one architectural mode

The observations are FCOS/RD, both from H1587:

| Case | Operand | Actual output |
| --- | --- | --- |
| Q008 | `3ffc:e73ffffd2c52df71` | `3ffe:f97ff2968a37b8b1` |
| Q015 | `3ffc:fcbfffffcee1bd36` | `3ffe:f83dc8dae4171d48` |

Output bits suffice. C1 is not needed, no missing status is invented, and the
proof does not combine different modes. Therefore an arbitrary RC-only choice
of the specified operation semantics cannot avoid this contradiction.

## Separate arithmetic proof

The checker uses H1604's separately implemented five-policy integer quantizer
and explicit operation schedule, plus exact numerical forwarding as the sixth
choice. It enumerates every numerical branch without memoizing live suffixes.
At each operation, disjoint groups partition all six policy labels according
to their exact output values. Every full policy vector follows exactly one
branch, so leaf boxes disjointly cover all `6^13 = 13,060,694,016` vectors per
operand/payload case.

Positive final RD is computed directly with the separate quantizer's CHOP64,
not via H1608's inverse intervals or acceptance diagrams. H1592 exact dyadic
primitives, constants and external encoding remain shared and are identified
as such. No H1608/H1609 solver code or diagram is read or imported.

For each accepting leaf box, existentially project its policy choices onto
four operations: square, negative factor, left product and correction add.
The other nine operation choices remain freely quantified, not fixed to
ordinary arithmetic. A common full vector necessarily projects to a common
four-choice vector. The projections are:

| Payload | e73 accepted projected vectors | fcb accepted projected vectors | Intersection |
| --- | ---: | ---: | ---: |
| omitted | 721 | 507 | 0 |
| frozen original numeric | 721 | 507 | 0 |

There are 1,296 possible four-choice vectors. The complete projection bitsets
are identical across payload treatments, not only equal in size. Their empty
intersection proves no shared full vector exists. These are constraints on
operation choices for two recorded observations, **not** features to classify
arbitrary input operands or a physical gate equation.

Both singletons have explicit full-policy witnesses, re-executed by a separate
straight-line path, proving minimum core size two. The checker covers 1,594,323
numeric leaf boxes for each e73 case and omitted fcb; frozen fcb has 1,515,591.
The total is 6,298,560 boxes, covering the full named-vector space four times.

Accepted full-vector volumes are 7,266,018,816 for e73 under either payload,
5,010,294,528 for omitted fcb, and 4,887,029,376 for frozen fcb. Only after the
independent construction are these compared to H1609's saved integer counts;
they agree exactly. They are not used to generate acceptance or projections.

## Verification and artifact scope

H1604's 30,660 internal-rounding and 2,000 Boolean-range checks pass. A further
5,184 explicit projection-membership checks verify the four-variable bitset
encoding, including full, singleton and mixed policy masks.

The raw compressed artifact aggregates exact numerical-leaf counts and
full-vector volumes by projected policy masks and verdict. It is **not** a
stored copy of every arithmetic leaf. The exhaustive generator, input hashes,
aggregate volumes, full projection bitsets and singleton stage witnesses are
preserved so the finite certificate can be reproduced.

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1611_independent_combined_rd_core.py` | `863df059a33f90cc9416cd851ec4ebdfbffbac500883452962c5222bce94febc` |
| `tmp/ledger33/current/h1611_independent_combined_rd_core/report.json` | `36fa91686b55fd4ff4ba488700eb73d40e5d6d3b718b22cd85c7260d05dedfd0` |
| `projected_policy_box_aggregates.jsonl.gz` in that directory | `3e7a375f6f5d740c763a6a7d5cf95e7dc062ac2cf854658aee3c4c3475cfcec1` |

```sh
python3 fsincos-re/experiments/h1611_independent_combined_rd_core.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
```

Existing directories are refused. Separate full replay reproduces the report
and aggregate stream byte-for-byte. The result strengthens the original-width
conventional-or-exact rejection; it does not test H1610's different finite
widths or prove general closed-form impossibility. The goal remains open.
