# H1541 all-equal NPN class

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Scope

H1541 exhausts NPN class `0x18`, represented by the opposite-minterm or
all-equal function:

```text
all_equal(a,b,c) = (a AND b AND c)
                 OR (NOT a AND NOT b AND NOT c).
```

Both target and output-complement polarities are searched for the physical
carry and incumbent flip. The literal universe contains both input
polarities, and the function is symmetric, so this covers the complete NPN
orbit.

## Exact reduction

On every target-one row, all three histories must agree. Patterns are first
grouped by their complete projection onto those rows, so only valid first
pairs are considered. On a target-zero row:

- if the first two histories differ, the third history is unconstrained;
- if they agree, the third history must be their complement.

Together with equality to the first history on target-one rows, this gives
one exact partial assignment for the third input. A deterministic 128-row
index is only a necessary filter; every surviving candidate is checked
against the full 34,473-bit assignment and then the complete all-equal
formula.

The built-in selftest passes. An independent randomized cubic enumeration
reproduced unordered and ordered-role counts: 20/20 pass.

## Result

Every polarity is zero:

| target | polarity | first-pair checks | full third checks | exact programs |
|---|---|---:|---:|---:|
| physical carry | direct | 11,874 | 573 | 0 |
| physical carry | output inverted | 11,564 | 631 | 0 |
| incumbent flip | direct | 553,514 | 24,895,744 | 0 |
| incumbent flip | output inverted | 11,296 | 41,136 | 0 |

This closes NPN class `0x18`. H1535--H1541 now exclude 12 of 14 classes,
containing 192 of the 256 three-input truth tables. The only remaining
classes are exactly-one (`0x16`, orbit 16) and XOR/OR-mux (`0x19`, orbit 48).

## Boundary

This remains a circuit-complexity result, not physical provenance. No x87
instruction or hardware capture ran. No H1488 label or private ledger was
opened. No emulator behavior/default and no academic paper/PDF changed. R96
remains empirical/incomplete, and the authoritative frontier remains 11 rows
over ten operands.

## Artifacts

- `experiments/h1541_all_equal_npn.py`, SHA-256
  `c484dbbefc0705dbaeb0b526fbdc22bec572812c0abf9393fa3775cd9e287463`;
- `tmp/ledger33/current/h1541_all_equal_npn.json`, SHA-256
  `fd2f5c37caf693ed77077de9b3cf6ed36edca347006601419139f5887c4b31de`.
