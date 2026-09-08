# H1540 remaining algebraic binate classes

Status: **exact negative circuit-class result; no selector and no
promotion**.

## Scope

H1539 leaves five untested NPN classes after the structurally motivated
three-input audits. H1540 exhausts the two classes with direct algebraic
reductions:

```text
class 0x06: gated_xor(a,b,c) = a AND (b XOR c)
class 0x1e: xor_or(a,b,c)    = a XOR (b OR c)
```

The literal universe already contains both input polarities. H1540 searches
both the target and its complement for physical carry and incumbent flip, so
input permutation/complementation and output complementation cover each
complete NPN orbit.

This is a circuit-complexity exclusion, not evidence that either arbitrary
binate function exists in the Skylake datapath.

## Exact reductions

For gated XOR, `a` must contain every target one. Once `a` is fixed, the
projection of `c` under `a` is exactly `(b XOR target) AND a`. H1540 builds
the complete projection map for every possible distinguished `a` and looks
up every `b`; the relation is necessary and sufficient.

For XOR-of-OR, fixing symmetric inputs `(b,c)` uniquely determines
`a = target XOR (b OR c)`. A 128-row signature is only a necessary lookup
filter. Every signature candidate is compared to the complete 34,473-bit
required vector. The direct and inverted flip searches each performed
1,446,458,929 full candidate comparisons; the carry polarities each performed
4,682,351.

The built-in exhaustive selftest passes. An independent randomized direct
cubic comparison reproduced unordered and ordered-role counts for both
functions: 20/20 pass.

## Result

Every count is zero:

| target | polarity | gated XOR | XOR-of-OR |
|---|---|---:|---:|
| physical carry | direct | 0 | 0 |
| physical carry | output inverted | 0 | 0 |
| incumbent flip | direct | 0 | 0 |
| incumbent flip | output inverted | 0 | 0 |

This closes NPN classes `0x06` and `0x1e` over the expanded 11,240-pattern
universe. Combined with H1535--H1539, 11 of 14 NPN classes and 184 of 256
three-input truth tables are now excluded. Three classes remain: exactly-one
(`0x16`), all-equal/opposite-minterms (`0x18`), and XOR/OR-mux (`0x19`),
containing 72 truth tables in total.

## Boundary

No physical provenance is inferred from the truth-function classification.
No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1540_remaining_binate_algebraic.py`, SHA-256
  `37f92e4f0e08ae3daf0e4e9c974d2c6842ffcbe6531cf18949815eaea555a43b`;
- `tmp/ledger33/current/h1540_remaining_binate_algebraic.json`, SHA-256
  `ef267d8c4cb914df5a28f2c915338806ee1ccb3837da74a6247e29703171ff57`.

The report pins the H1539 coverage audit, immutable wall inputs, and direct
helper-code hashes.
