# H1542 final three-input NPN classes

Status: **exact bounded circuit-class theorem; no selector and no
promotion**.

## Scope

H1542 exhausts the last two NPN classes left by H1539--H1541:

```text
exactly_one(a,b,c) = (a AND NOT b AND NOT c)
                   OR (NOT a AND b AND NOT c)
                   OR (NOT a AND NOT b AND c)

xor_or_mux(a,b,c) = a ? (b OR c) : (b XOR c)
                  = (b XOR c) OR (a AND b AND c).
```

Both target and output-complement polarities are searched for the physical
carry and incumbent flip. The 11,240-pattern literal universe contains both
polarities of each named source. The functions' symmetric roles are
enumerated without loss, so the searches cover the complete `0x16` and
`0x19` NPN orbits.

## Exact reductions

For exactly-one, fix the symmetric pair `b,c`. A target-one row may not have
`b=c=1`. Everywhere else the distinguished input is uniquely fixed by

```text
a = target XOR (b XOR c).
```

Candidate pairs are therefore enumerated by exact disjointness on target-one
rows. The nine-one incumbent-flip target uses complete projection groups;
dense targets use a deterministic 128-row necessary filter followed by a
full-vector equality check. The resulting partial assignment for `a` is
queried with the same necessary-only index and verified over all 34,473
constrained rows and by direct formula evaluation.

For XOR/OR-mux, fix `b`. On target-zero rows `c=b`; on target-one rows with
`b=0`, `c=1`; and on target-one rows with `b=1`, `c` is unconstrained. Once a
valid symmetric pair is selected, `a=target` wherever `b=c=1`. These two
partial assignments are necessary and sufficient. Again, sampled bits only
reject candidates; every survivor receives the full-vector and direct-formula
checks.

The built-in exhaustive small-domain selftest passes. A separate randomized
cubic enumeration covering sparse and dense targets reproduced unordered and
ordered-role counts: 20/20 pass.

## Result

Every exact-program count is zero:

| target | polarity | exactly-one full `a` checks | XOR/OR-mux full `a` checks | exact programs |
|---|---|---:|---:|---:|
| physical carry | direct | 820 | 357 | 0 |
| physical carry | output inverted | 7,100 | 242 | 0 |
| incumbent flip | direct | 875,024 | 110,500 | 0 |
| incumbent flip | output inverted | 1,031,003 | 5,564,324 | 0 |

For exactly-one, the pair stage examined 481,958, 401,350, 12,716,123, and
301,333 valid symmetric pairs in those four cases. For XOR/OR-mux it found
144, 242, 638, and 32,272 valid symmetric pairs before the distinguished-input
test.

This closes NPN classes `0x16` and `0x19`. Combined with H1535--H1541 and
H1539's exhaustive 14-class partition, it proves that **none of the 256
three-input Boolean functions**, instantiated over any three current named
literal histories, exactly equals either the physical-carry selector or the
incumbent-flip target on the current wall. The wall has 37,450 source rows,
34,473 constrained rows, 2,977 neutral rows, 10,456 named features, and
11,240 distinct literal patterns.

## Boundary

This is a bounded circuit-complexity lower bound over the current named
observables. It is not a silicon selector, a proof that no hidden/raw control
bit exists, or a closed-form emulator solution. It does not justify arbitrary
four-input truth-table fitting.

No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1542_final_three_input_npn.py`, SHA-256
  `cc73ac1e349009a74e1a5cfdf3e31b9bf321d54999404f4349555f4efb279476`;
- `tmp/ledger33/current/h1542_final_three_input_npn.json`, SHA-256
  `ba9d850390bb7ec81da29ffb7ad0e77b26f4aca5c1783e2a83c284e60bce74e6`.
