# H1536 complete three-wire majority audit

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Question

H1535 excludes the sum/parity output of every possible three-wire
carry-save compressor over the current named R59 histories.  H1536 tests the
other canonical 3:2-compressor output,

```text
carry = majority(a,b,c)
      = (a AND b) OR (a AND c) OR (b AND c).
```

Both polarities of every source pattern are present, so this also covers the
corresponding input-polarity variants over the named histories.  This is not
an arbitrary three-input Boolean census.

## Exact reduction

For a fixed pair `(a,b)`, majority has a complete per-row characterization:

- where `a == b`, the output is already `a`, independently of `c`;
- where `a != b`, the output is exactly `c`.

Therefore a pair is impossible if it disagrees with the target on any
agreement row.  For every surviving pair, the audit checks every later
literal history for equality to the target on all disagreement rows.  This
is an exact elimination identity, not a probabilistic filter or learned
classifier.  A 64-word prefix only rejects pairs that already violate the
same identity; every prefix survivor is checked over all 34,473 rows.

The implementation selftest passes, and an independent harness exhaustively
compared it with the direct cubic definition on 20 randomized small
universes: 20/20 exact count and witness-list matches.

## Wall and result

The immutable inputs and expanded feature universe are identical to H1535:

- 37,450 source rows;
- 34,473 carry-constraining rows, comprising nine positives and 34,464
  controls;
- 2,977 neutral rows omitted because either carry is correct;
- H1401 reproduced exactly at 6,864 named features / 7,924 literal patterns;
- expanded current universe at 10,456 named features / 11,240 literal
  patterns;
- 236,609,272,280 unordered distinct-pattern triples.

The complete results are:

| target | pair checks | prefix survivors | full-row pair survivors | third-pattern checks | exact triples | direct literals |
|---|---:|---:|---:|---:|---:|---:|
| required physical carry | 63,151,941 | 42,170 | 6,166 | 16,430,690 | 0 | 0 |
| incumbent-carry flip | 63,151,941 | 1,379,495 | 15,374 | 25,972,307 | 0 | 0 |

Repeated-history triples reduce to a direct literal under majority because
`majority(a,a,b)=a`.  Neither target equals a literal, so those cases are
excluded too.

## Boundary

No carry/majority output of any three current terminal, P5 tree, P5 CPA,
borrow, or incumbent-carry literals is the missing selector on the cached
wall.  Together H1535 and H1536 exclude both canonical outputs of an
arbitrary 3:2 compressor connected to those histories.  They do not exclude
arbitrary three-input Boolean functions, hidden/raw control bits, or an
observable absent from the feature bank.

No x87 instruction or hardware capture ran.  No H1488 label or private ledger
was opened.  No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1536_complete_three_wire_majority.py`, SHA-256
  `cf61c35606c0b2666faf49bb52a03b35434651fd25f7f3de9ce2eecc640c94c3`;
- `tmp/ledger33/current/h1536_complete_three_wire_majority.json`, SHA-256
  `27bbabd6512854cc418b406fd05489fed0b6d3f47fd01eb3d26a10cefec2b8ed`.

The JSON pins the immutable input hashes and every direct helper-code hash.
