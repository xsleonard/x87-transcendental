# H1538 complete three-input unate audit

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Question and complete class boundary

There are 20 monotone Boolean functions of three variables.  Constants,
projections, and two-input AND/OR are reducible.  The irreducible functions
are represented, up to input permutation, by:

```text
AND3(a,b,c)
OR3(a,b,c)
majority(a,b,c)
AO21(a,b,c) = a AND (b OR c)
OA21(a,b,c) = a OR (b AND c)
```

H1536 already excludes majority over the complete expanded literal universe.
H1538 exhausts the other four shapes, including repeated input histories.
Repeated inputs also cover the reducible projections and two-input AND/OR
cases.  Because both polarities of every named history are literals, the
monotone basis under arbitrary input polarity is exactly the class of all
three-input unate Boolean functions.

This boundary is broader than a list of hand-picked AOI/OAI standard cells,
but narrower than all 256 three-input Boolean functions.  In particular,
binate functions require separate treatment; H1535 and H1537 independently
exclude the canonical parity and mux shapes.

## Exact reductions

For `AND3=T`, every input must contain all one-bits of `T`; the zeros supplied
by the three candidates must cover every zero-bit of `T`.  `OR3` is the dual
three-set-cover problem.  H1538 uses at most 128 sampled universe rows only
to reject impossible third sets.  Any full solution necessarily covers the
sample, and every survivor is checked against the complete 34,473-bit truth
vector.  The production searches happened to have zero sample survivors, so
the exact exclusions complete at that necessary condition.

For `AO21`, fixing the distinguished `a` requires `a` to contain `T`; both
symmetric inputs must be zero on `a AND NOT T`, and their union must supply
`T`.  For `OA21`, `a` must be a subset of `T`; both symmetric inputs must
supply `T AND NOT a`, and their intersection must remain inside `T`.  The
script enumerates every surviving symmetric pair and verifies the complete
formula directly.

The built-in exhaustive selftest passes.  An independent randomized harness
also compared all four shapes, unordered counts, and ordered-role counts
against direct cubic evaluation: 20/20 pass.

## Wall and results

The immutable wall is the same as H1535--H1537: 34,473 constrained rows
(nine positives and 34,464 controls) and 2,977 neutral rows, with H1401
reproduced at 6,864 named features / 7,924 literal histories and the expanded
current universe at 10,456 / 11,240.

Every exact count is zero:

| target | AND3 | OR3 | AO21 | OA21 |
|---|---:|---:|---:|---:|
| required physical carry | 0 | 0 | 0 | 0 |
| incumbent-carry flip | 0 | 0 | 0 | 0 |

Important exhaustive bounds include:

- flip `AND3`: 630 candidate patterns and 41,873,160 unordered candidate
  multisets;
- carry `AND3`: 23 candidates and 2,300 multisets;
- flip `OA21`: six distinguished inputs and 1,684,644 exact symmetric-pair
  checks;
- flip `AO21`: 630 distinguished inputs and 59,828 pair checks;
- all other AO21/OA21 and OR3 searches are smaller and fully enumerated.

Together with H1536, this proves that no three-input unate function over the
current terminal, P5 tree, P5 CPA, borrow, or incumbent-carry histories is the
missing selector on the cached wall.

## Boundary

The result does not exclude binate Boolean functions other than the separately
tested parity and mux classes, hidden/raw control bits, or an observable absent
from the feature bank.  It is therefore not a selector and does not justify
an emulator change.

No x87 instruction or hardware capture ran.  No H1488 label or private ledger
was opened.  No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1538_complete_three_input_unate.py`, SHA-256
  `2ca844d2556afaf05a5b6cb6c6556e6a8858f72e831537c0a1683ec7441287f9`;
- `tmp/ledger33/current/h1538_complete_three_input_unate.json`, SHA-256
  `54b5353b4d23a52fc3a80b41bbc9d1b3234cd171757244f85f1e8eb3cced2066`.

The JSON pins the immutable inputs and all direct helper-code hashes.
