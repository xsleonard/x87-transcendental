# H1528--H1530: exact constructive closed-form projection decoder

Date: 2026-09-04

Status: **exact table-free closed-form decoder for the H1516 pair-A/pair-B
defect quotient; physical Skylake orientation unresolved; no selector,
emulator, or paper/PDF change.**

## Result

H1522 proves that 63 raw coordinates are exactly sufficient and minimal inside
the H1516 projection family, but H1523/H1524 did not extract an explicit
formula. H1528 resolves that extraction boundary constructively: it maps every
63-bit projected key to one valid canonical twelve-word state, then evaluates
H1516's exact common defect circuit on that state. No table, decision tree, or
learned boundary is involved.

For ordered groups 0--3, omitted `T` and `U` coordinates are zero-filled. Every
`(T,U)` word pair is a valid ordered redundant state, so this needs no
constraint solving.

For unordered groups 4 and 5, let `k=3` and `k=5`, respectively. The retained
windows are `T[k..7]` and `P[k-1..k]`. Define

```text
c_k       = T_k XOR P_k
G'_(k-2)  = c_k AND P_(k-1)
G'_(k-1)  = c_k AND NOT P_(k-1)
c_i       = c_k AND (AND over j=k..i-1 of NOT T_j),  i >= k
P'_i      = T_i XOR c_i,                              k <= i <= 7
T'        = P' + 2*G' mod 2^9
```

All unspecified `P'` and `G'` bits are zero, apart from
`P'_(k-1)=P_(k-1)`. The canonical redundant pair is then
`(S',C')=(P' OR G',G')`. Because `P' AND G'=0`, it has
`S' XOR C'=P'` and `S'+C'=T'` exactly.

The carry expression above is the closed-form unrolling of H1528's original
one-step recurrence. It contains no lookup table, decision tree, or state
machine.

## Proof obligations

H1528 proves two universal counterexample queries UNSAT after exact bit
blasting:

| Obligation | Variables | Clauses | Z3 | CVC5 CaDiCaL |
|---|---:|---:|---:|---:|
| completion valid and projection-preserving for every key | 50 | 193 | UNSAT, 1 ms | UNSAT, 1 ms |
| every valid original state has the same defect as its completion | 620 | 3,276 | UNKNOWN, 60 s | UNSAT, 34.629 s |

The second result proves equivalence over every valid arbitrary first-level
redundant state, not merely states reached by known operands. H1529 reparses
the two immutable CNFs in an independent driver and reproduces both CaDiCaL
UNSAT results; the equivalence replay takes 34.599 seconds.

H1530 replaces the recurrence with the unrolled formula above. Its 39-variable,
143-clause disagreement miter is UNSAT in both Z3 and CaDiCaL in 1 ms. By
composition with H1528/H1529, the unrolled expression is a total explicit
decoder for all `2^63` projected keys and agrees with the full defect on every
valid state.

## Interpretation boundary

This is the representation sought after H1516: a genuine algebraic circuit
isomorphic to the complete pair-A/pair-B swap defect, rather than a table or a
fit to the known x87 error rows. It supersedes only H1523/H1524's formula-
extraction stopping point; their solver outcomes remain correctly recorded as
UNKNOWN for those extraction methods.

The result still does not choose whether pair A, pair B, or neither is the
physical Skylake orientation. H1488 remains the frozen direct orientation
vote. Therefore H1528--H1530 are not promoted into emulator behavior and do
not close the eleven-row x87 frontier.

## Artifacts

- `experiments/h1528_constructive_projection_decoder.py`, SHA-256
  `a5d2eb5f1786998e795eb4f566b78302c9533f22e8670d6a81b26d87dbe46ab2`;
- H1528 report, SHA-256
  `ea79668f6e3b27e26ec185bec16ff1e44f5b8d9c66f40be256b2fa6d1a60bb73`;
- H1528 totality CNF, SHA-256
  `d2c2b18432663b0f6fbc5934c420e7e802b04c4ac0e4fa439ccd74a0a1d57e45`;
- H1528 equivalence CNF, SHA-256
  `34db421d4fadc71b4b74bace1b7c56b052b7c8b9f2f76dfe6ffb4a4e0c3f8f38`;
- `experiments/h1529_replay_constructive_decoder_cnf.py`, SHA-256
  `10cc5b590e942e419d2dd437392f45ae36de4e9ce37c1e008f8595a0e800731c`;
- H1529 report, SHA-256
  `f9ec0610978752712204f2d5fb5ddb5fca1c301f375fb0db6199d31d5931d478`;
- `experiments/h1530_closed_form_projection_decoder.py`, SHA-256
  `a0159f02995429d306b235e1e1ba9306e35d53dcfc4534a8185d9306fc81bf11`;
- H1530 report, SHA-256
  `019ca231e4b054b4e94387387a0bb5f8598c2a93c63f06c8e05a1012c29b1196`;
- H1530 recurrence-equivalence CNF, SHA-256
  `06a2f152aa01b4d03a823decfa1d77c50564302efa54f7eed78df8360c4e5bfc`.

No x87 instruction or hardware capture ran, no label or private capture ledger
was opened, and no manifest, emulator behavior/default, or academic paper/PDF
changed. H1488 remains `FROZEN_UNOPENED`; R96 remains empirical/incomplete;
the authoritative frontier remains eleven mode rows over ten operands.
