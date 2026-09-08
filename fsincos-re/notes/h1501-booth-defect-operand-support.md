# H1501: exact operand support of the surviving swap defect

Date: 2026-09-03

Status: **exact normalized-Booth-domain representation; physical orientation
unresolved; no selector promotion.**

## Result

H1501 substitutes the exact radix-8 Booth recoding constraints into H1500's
local pair-A/pair-B swap-defect circuit.  On the complete normalized 67-by-64
multiplier-port domain, the result has the exact residue form

```text
D_45(m,q) = f_45(m mod 2^45, q mod 2^45)
D_46(m,q) = f_46(m mod 2^46, q mod 2^46).
```

Every displayed residue bit is essential:

| Column | Essential multiplicand bits | Essential multiplier bits | Total |
|---:|---|---|---:|
| 45 | 0..44 | 0..44 | 90 |
| 46 | 0..45 | 0..45 | 92 |

For each essential bit, Z3 supplies a normalized assignment where flipping
that bit alone flips `D_j`.  Every higher free input bit is either absent from
the exact Booth cone or has an UNSAT sensitivity query.  Thus these are
coordinate-minimal residue projections: no individual low residue bit can be
dropped while the others remain free.  This does not rule out a differently
encoded function with fewer derived state variables.

The two column functions are not identical.  A SAT witness is

```text
m = 400000db48bd29ff4
q = 800092858535752f
D_45 = 1
D_46 = 0
```

## Proof chain

The operand-level circuit is connected to the existing full construction in
three checked steps at both columns:

1. H1501 proves every local Booth partial-product/correction input bit equal
   to H1487's corresponding complete 136-bit physical input (UNSAT);
2. H1500 proves the Boolean CSA42 circuit equal to an independent bit-vector
   CSA42 circuit for pair A and pair B (four UNSAT queries);
3. H1498 proves the full final-propagate output depends only on the selected
   nine input columns for both pairs (the relevant four locality queries are
   UNSAT).

The composition proves H1501 is the same pair-disagreement function as H1487,
not a new fitted classifier.  An independent H1501 execution produces the
same JSON byte-for-byte.

## Interpretation and boundary

This is the cleaner isomorphic representation suggested by H1498/H1500: the
topology ambiguity is exactly a function of the two low operand residues at
the target boundary.  It is universal over the complete normalized Booth
domain, rather than a table or decision tree over observed x87 failures.

It still does not decide whether pair A, pair B, or neither representation is
the physical Skylake path.  That orientation bit is independent empirical
information.  H1488 remains the precommitted direct vote and remains
`FROZEN_UNOPENED`.  Even an H1488 survivor would be fresh finite validation,
not proof of global x87 closure.

H1502 subsequently proves that the ordered residue pair cannot be quotiented
to the ordinary product residue and that `D_j` is not symmetric under swapping
the multiplicand and multiplier residues.

## Artifacts

- `experiments/h1501_booth_defect_operand_support.py`, SHA-256
  `60cc05b75bc7abdc960834d83e2894689aeb85acc96f94e94b1829abab34adaf`;
- `tmp/ledger33/current/h1501_booth_defect_operand_support.json`, SHA-256
  `5ef2ddd6db82ce204b02b039102ddf5178ed69ab9d956f782845a333888fc610`;
- H1487 input report, SHA-256
  `c19fdf1587f8f87243e0ee46e57b42776fb17654fc6f51719a6c1d235c3a396f`;
- H1498 input report, SHA-256
  `96a20527c1ff576f1705eabf63cd84aac44b4e0d46fad44175a34b781ffcb721`;
- H1500 input report, SHA-256
  `f332ddabd40773eb61399ba073b7dcc47fd089ee726f951394dc5f33c8bfbe16`.

No x87 instruction ran, no hardware or private-ledger label was opened, no
manifest was created or changed, and no emulator behavior/default changed.
The academic paper and PDF were not modified.  R96 remains
empirical/incomplete and the authoritative frontier remains eleven mode rows
over ten operands.
