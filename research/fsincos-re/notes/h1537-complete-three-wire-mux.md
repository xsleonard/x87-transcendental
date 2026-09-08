# H1537 complete three-wire mux audit

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Question

The unresolved bit is a selector, so after H1535/H1536 exclude both outputs
of every 3:2 compressor over the current named histories, H1537 tests the
other canonical three-wire datapath primitive: a 2:1 mux,

```text
mux(s,d0,d1) = (NOT s AND d0) OR (s AND d1).
```

Selector, data-0, and data-1 are independently chosen from every distinct
literal history.  Both polarities of every named source are present.

## Exact reduction

For a fixed selector `s`, an exact mux has two necessary and sufficient
conditions:

- `d0` equals the target on every row where `s=0`;
- `d1` equals the target on every row where `s=1`.

H1537 checks both masked equalities for every selector/data history.  A
64-word prefix uses the identical equality on only a subset of rows, so it
can reject only invalid candidates.  Every survivor is rechecked over all
34,473 constrained rows.  Counts include all ordered role assignments and
separately classify repeated roles.

The built-in exhaustive selftest passes.  An independent harness also
compared category counts and totals against direct cubic evaluation on 20
randomized small universes: 20/20 pass.

## Wall and result

The immutable wall and universe are identical to H1535/H1536:

- 37,450 source rows;
- 34,473 carry-constraining rows: nine positives and 34,464 controls;
- 2,977 neutral rows omitted because either carry is valid;
- exact H1401 reproduction: 6,864 named features / 7,924 literal patterns;
- expanded universe: 10,456 named features / 11,240 literal patterns.

The complete ordered search contains

```text
11240^3 = 1,420,034,624,000
```

pattern-role programs.  Each target performs 252,675,200 masked membership
checks.  The physical-carry target has 175,702 full data-0 memberships and
175,702 full data-1 memberships across all selectors; the flip target has
270,590 of each.  No selector has a compatible pair of data histories:

| target | all-distinct | `s=d0` | `s=d1` | `d0=d1` | all equal | total |
|---|---:|---:|---:|---:|---:|---:|
| required physical carry | 0 | 0 | 0 | 0 | 0 | 0 |
| incumbent-carry flip | 0 | 0 | 0 | 0 | 0 | 0 |

Repeated-role cases are included rather than assumed away.  They cover the
ordinary reductions to direct literals and two-wire AND/OR gates.

## Boundary

No 2:1 mux over any current terminal, P5 tree, P5 CPA, borrow, or
incumbent-carry literal is the missing selector on the cached wall.  This is
a complete exclusion of that circuit class, not a claim about arbitrary
three-input Boolean functions, hidden/raw control bits, or an observable
absent from the feature bank.

No x87 instruction or hardware capture ran.  No H1488 label or private ledger
was opened.  No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1537_complete_three_wire_mux.py`, SHA-256
  `203c094474393c571a8d619abc8851b53d3940079a42c3f46e882628ae6608d6`;
- `tmp/ledger33/current/h1537_complete_three_wire_mux.json`, SHA-256
  `c096272fa20ea1282463564f5c91f7410b8d0ccb7647909afbce491682ebb59d`.

The JSON pins the immutable inputs and all direct helper-code hashes.
