# H1497: exact column-45 R1382 tie-cell invariant

Status: **the reachable target cell changes an internal comparator bit but
cannot change an architectural endpoint; no selector promotion.**  This is
analysis-only evidence.  It neither validates R1382 nor identifies which
H1487 redundant-pair representation is physical.

## Question

H1496's fresh endpoint-visible R1382 surface exercised only
`product_cut-18 = 46`, because its inherited lattice fixed the right-product
shift to 64.  H1497 asks whether the corresponding shift-63 path can expose
the absolute column-45 state and challenge the H1495 boundary-carry
representation independently.

The relevant fixed cell is

```
theta=0, s4=66, side=1, low3=3, distance=9, rsh=63, payload=2.
```

R1382 can affect this parent only when the existing R1272 attachment gate is
enabled: the current path retains the hard-3x low-block merge, while R1382
removes it because `s4=66`.  The source materializes that merge only in the
`theta==0` arm.  Threshold differences at nonzero theta are therefore
counterfactual, not R1382 effects.

## Exact reductions

Four counterexample queries are UNSAT under Z3 4.15.3:

1. The merged/plain comparator changes `b1` from one to zero exactly when the
   63 discarded right-product bits are in
   `[0x2aaaaaaaaaaaaaab, 0x2aaabfffffffffff]`; `b2` stays zero.
2. Fusing that comparator interval with the theta-zero terminal congruence
   gives the exact low-72-bit product interval
   `[0x022aaaaaaaaaaaaaab, 0x022aaabfffffffffff]`.
3. The fixed-cell tie law has
   `base0 = -4 + 2*b1 + b2`.  Its recovered operation is mathematical floor
   division by four, so all four `(b1,b2)` states give `u0=-1`.  The merge can
   change `rd3` and `b1`, but it cannot change the tie threshold, fire bit,
   retained correction, or endpoint.
4. The existing H1463 endpoint lemma was replayed: four-mode visibility of
   adjacent retained values is exactly the six residues modulo 512
   `{000,100,001,101,081,180}`.

These are fixed-width circuit equivalences, not fitted operand boundaries.

## Cached and adversarial replay

The cached H1386 population contains 234 unique rows in the fixed cell.
Incumbent-versus-R1382 replay gives 74 `rd3`-only changes, 160 rows with no
internal change, and zero endpoint changes.

A deterministic 30,000,000-plateau modular search with seed
`0xcbbb9d5dc1059ed8` found an exact external strongest adversary at iteration
7,002,878:

```
operand      3ffc:b5129d2af173677e
square       0x4009a9cc99fa6bf73
fourth       0x4013550eb7ff41a65
right low72  0x022aaab44b4dbdb588
```

It simultaneously reaches the comparator transition and an H1463
endpoint-visible residue.  Independent current-source replay nevertheless
shows the proved invariant exactly:

```
                 incumbent                 R1382
rd3              0x8000000000000000       0x7fff800000000000
b1,b2             1,0                       0,0
u0                -1                        -1
tie fire          0                         0
retained result   identical                 identical
all four modes    identical                 identical
```

Eleven earlier near rows also remain endpoint-identical.  The final report
reproduces byte-for-byte under an independent rerun.

## Corrected intermediate assumption

Before the report was accepted, independent current-source replay rejected a
provisional scanner classification.  That draft had used C truncation toward
zero for the negative quotient, incorrectly mapping `base0=-2` to `u0=0`.
The recovered R59 law uses `r59_floordiv`, which maps both `-2/4` and `-4/4`
to `-1`.  The invalid draft artifact was moved outside the repository and was
never entered in the handoff, paper, emulator, or hardware record.

## Claim boundary

The no-go is exact for the stated column-45 cell.  It explains why extending
the H1470/H1496 R1382 lattice from shift 64 to shift 63 cannot create another
endpoint discriminator there.  It is not a proof about unrelated column-45
cells or about the physical H1487 pair.  H1488 remains the only frozen direct
hardware discriminator between those two pair functions.

## Artifacts

- `experiments/h1497_r1382_column45_lattice.c`, SHA-256
  `2071d378a86e5e6fd98ce2e3b27add49f0d7684fdbf784002a1e22bb42c5cb16`;
- `experiments/h1497_r1382_column45_lattice.py`, SHA-256
  `34ae042c8f4439a83c62ca2e95ce5b2bb8d5d48638c1b0b101e1755526d77fd8`;
- `tmp/ledger33/current/h1497_r1382_column45_lattice.json`, SHA-256
  `066f4ed66cbe7151fd3901177a756d74d7f30aa44113cf07b82473db06c51ee1`.

No x87 hardware was run, no capture or private-ledger label was opened, no
manifest was frozen, and no emulator behavior/default changed.  The academic
paper and PDF were not modified.
