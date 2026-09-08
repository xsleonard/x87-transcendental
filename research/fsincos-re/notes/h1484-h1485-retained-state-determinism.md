# H1484-H1485: retained-state determinism and support instability

Date: 2026-09-03

Status: the local four-bit X2-to-WF group state cannot determine the observed
split, and the first full-vector six-signal table is falsified by a fresh
software wall.  A different six-signal table still fits the enlarged finite
wall, so no full-vector impossibility or closed-form selector is claimed.
R1475 was subsequently falsified 7/10 by the opened-once H1477 challenge and
remains default-off.

## Complete four-bit group reconstruction

H1484 extends H1483 from individual signals to joint retained state.  For all
seventy arithmetic-exact P5 tree layouts, it reconstructs all 32 four-bit
groups covering product columns 2 through 129, their group generate and
propagate bits, conditional carries and sums, prefix states, and the separately
handled top column.  It tests both the eighteen known labels and the combined
forty-row R1475 function wall.

The nine four-bit groups local to the retained cut provide eighteen G/P bits.
Their complete vector has opposite-value collisions on the forty-row wall in
all seventy layouts.  Without conditioning on rounding mode, 62/70 layouts
already collide on the eighteen known labels alone.  In the
patent-transcribed layout, seven labeled rows occupy three mixed signatures,
including these direct hardware-label pairs:

- L001/RU versus L002/RN;
- L016/RD versus L006/RN; and
- L005/RU versus L014/RD.

Those three pairs alone would permit a rounding-mode gate.  H1484 therefore
repeats every collision test with RC included in the signature.  Forty-four
of seventy layouts still have known-label collisions.  The patent layout has
the decisive same-mode pair: L016 and the established d0d0 anchor are both
direct FCOS, PC64, and RD, have identical complete local G/P vectors, and
require opposite selector values.  Thus no deterministic downstream function
of that local vector plus rounding mode can explain the known split in the
patent layout.  This is a vector collision result, not a failure to guess the
right Boolean gate.

## Why the full vector is not a closed form

The complete 64-bit vector of all 32 group G/P pairs separates the finite
forty rows in every tested layout.  That only shows that distant product state
can identify these samples.  Exhaustive opposite-class set cover on the
patent layout proves that no subset of one through five signals determines
R1475 on the forty rows.  The minimum is six:

```text
group21.g, !group25.g, group22.g, group28.g, group20.g, group19.g
```

Its arbitrary 64-entry truth table has only 33 assigned states and 31 don't
cares.  The inputs are widely separated high-product groups rather than a
localized carry boundary.  This is a finite classifier, not an algebraic or
causal identification.

## Fresh challenge

H1485 uses a new deterministic lattice seed, `0x13198a2e03707344`, for
10,000,000 sampled plateaus.  It yields twenty exact external pre-candidates
and six endpoint-visible software rows, with zero operands shared with H1471,
H1476, d0d0, or d800.  No hardware label is involved.

Only one fresh row reaches a state assigned by the original table, and it is
correct.  Five reach previously unassigned states.  Two of those rows share
the identical six-bit code 24 but have opposite R1475 values, which proves
that the selected six signals cannot determine R1475 under any completion of
the table.

An exact support solve on all 46 rows still finds a different six-signal
classifier:

```text
group23.g, group19.g, group21.g, group17.g, !group26.g, group24.g
```

Only group19 and group21 survive from the first support.  The replacement
table assigns 35 of 64 states and leaves 29 unspecified.  Therefore H1485
falsifies the selected representation but not every possible six-signal fit.
The rotation under six fresh rows is negative evidence against treating any
such high-dimensional table as a structural isomorphism.

## Artifacts

- `experiments/h1484_x2_wf_state_determinism.py`, SHA-256
  `2204e7b48f9d62aed36eebe298ba1fc1a6cc0eba95a5b3517be8a3da26bc5a5c`;
- `tmp/ledger33/current/h1484_x2_wf_state_determinism.json`, SHA-256
  `9fd35bde8f6c646f6ff6680e653576ca9cf7edc736e029b12b10ced83bdc9b7a`;
- `experiments/h1485_score_retained_state_support.py`, SHA-256
  `6279cfe51a6d3b26e1ac39901198423b31574155611a77c4a3dcd7a60e90b500`;
- `tmp/ledger33/current/h1485_fresh_lattice_bank.json`, SHA-256
  `fcf199a64fbdaf3c4f964f53d22e403728f39c85ea7426369208d061cd3fe9b7`;
- `tmp/ledger33/current/h1485_retained_state_support_score.json`, SHA-256
  `9c9c390c312f45737abee9066c3ecbed82ca0f7621e405be6de82b521afca1d8`.

Both reports reproduce byte-for-byte.  No x87 instruction ran, no H1477 label
or private ledger was opened, and no emulator default or academic paper/PDF
changed.

Postscript: the statement above describes the H1484--H1485 execution itself.
H1477 was later opened under separate explicit authorization; see
`notes/h1474-h1478-r1382-split.md` and
`transfer-tests/h1477/OPENED.json`.  Its labels do not alter the local-vector
collision or support-instability results.
