# H1515--H1517: exact quartet-state isomorphism and support bounds

Date: 2026-09-03

Status: **exact abstract defect representation; unique minimum ordered-quartet
set in the tested representation family; physical Skylake orientation remains
unresolved; no selector promotion.**

## Question

H1498 expresses the pair-A/pair-B disagreement as a local swap defect in a
nine-column compressor cone.  H1515 and H1516 ask which first-level quartet
state must survive in order to compute that defect exactly.  The goal is an
isomorphic internal-state representation, not another decision tree over
known error operands.

For each of the six first-level quartets, write its two nine-bit redundant
outputs as `(S_g,C_g)`.  Define

```text
T_g = (S_g + C_g) mod 2^9
P_g = S_g XOR C_g
U_g = S_g.
```

`T_g` is the ordinary arithmetic residue.  `P_g` retains the unordered
carry-save decomposition.  `U_g`, together with `T_g`, retains its order.

## H1515: arithmetic and unordered state are insufficient

H1515 works on the complete normalized 67-by-64-bit radix-8 Booth domain at
absolute output columns 45 and 46.  It asks whether the swap defect factors
through progressively richer states for all six quartets:

| Retained state per quartet | Column 45 | Column 46 |
|---|---:|---:|
| `T_g` | SAT counterexample | SAT counterexample |
| `T_g` plus top propagate | SAT counterexample | SAT counterexample |
| `T_g,P_g` | SAT counterexample | SAT counterexample |
| `T_g,U_g` | UNKNOWN (timeout) | UNSAT |

Thus neither each quartet's arithmetic residue nor its complete unordered
propagate word determines the defect.  Exact normalized Booth witnesses have
identical retained state and opposite defects at both columns.  The ordered
state is sufficient at column 46.  H1515's column-45 query timed out, but
H1516's stronger arbitrary-pair theorem below independently proves the same
sufficiency there; no inference is taken from the timeout itself.

## H1516: the exact minimal ordered-state form

H1516 removes the Booth reachability restriction and proves the representation
on the stronger domain of six arbitrary nine-bit redundant pairs.  It retains
`T_g` for every quartet and enumerates all 64 choices in which each companion
is either ordered `U_g` or unordered `P_g`.

Exactly four choices are exact: the supersets of `{0,1,2,3}`.  The unique
minimum ordered-quartet set is therefore

```text
ordered:    g = 0,1,2,3   retain (T_g,U_g)
unordered:  g = 4,5       retain (T_g,P_g).
```

The other 60 choices have explicit same-state/opposite-defect SAT witnesses.
For the minimum form, omitting any one of the six arithmetic words or any one
of the six companion words also has a SAT witness.  Hence all twelve retained
words are individually essential within this representation family.

The decoder is closed form.  For an ordered quartet,

```text
(S_g,C_g) = (U_g, T_g-U_g).
```

For an unordered quartet, let `G_g=(T_g-P_g)>>1` and choose the canonical
representative

```text
(S_g,C_g) = (P_g OR G_g, G_g).
```

An independent QF_BV query proves that decoding all six quartets this way and
applying the common H1498 downstream template reproduces the exact pair-A XOR
pair-B defect for arbitrary input pairs.  No table of operands, fitted
boundary, or hardware label appears in this formula.

## H1517: exact coordinate support and reachability gap

H1517 audits all 108 bits in H1516's twelve-word state.  A shared one-hot
miter enumerates every coordinate whose isolated flip can change the defect;
the final blocked miter is independently UNSAT in CVC5 1.3.1.

On the unconstrained canonical extension, exactly 87 coordinates are
semantically present:

| Field | Exact sensitive bits |
|---|---|
| `g0.T` | 0--7 |
| `g0.U` | 0--4 |
| `g1.T` | 0--7 |
| `g1.U` | 0--3 |
| `g2.T` | 0--7 |
| `g2.U` | 0--4 |
| `g3.T` | 0--7 |
| `g3.U` | 0--4 |
| `g4.T`, `g4.P`, `g5.T`, `g5.P` | 0--8 in each word |

The remaining 21 coordinates are absent from the closed-form decoder for all
possible values of the twelve words.  Retaining the 87 listed coordinates is
therefore an exact coordinate-minimal projection of that unconstrained
extension and, by restriction, an exact upper bound for all original
redundant pairs.

The valid redundant-pair image is not a Cartesian product in `(T,P)` for
quartets 4 and 5.  A second exact one-hot audit uses the validity equations

```text
Delta = (T-P) mod 2^9
Delta[0] = 0
P AND (Delta >> 1) = 0.
```

It finds 62 coordinates with reachable one-bit sensitivity witnesses: the 51
listed bits of groups 0--3, plus `g4.T[3..7]`, `g4.P[2..3]`,
`g5.T[5..7]`, and `g5.P[4]`.  Its terminal complement is also independently
UNSAT in CVC5.  The other 25 extension-sensitive coordinates have no isolated
one-bit edge inside the valid image.

That gap is reported as a bound, not misrepresented as a 62-bit quotient.
Disconnected valid-state fibers can require several coordinates to change
together, so H1517 proves an exact 62-bit lower bound and exact 87-bit upper
bound inside the named encoding.  A separate multi-coordinate quotient proof
would be required to narrow that interval.

## Interpretation and boundary

The exact result identifies where ordering information matters in the abstract
tree.  Quartets 0--3 cannot be quotiented by exchange of their two redundant
outputs; quartets 4--5 can.  This is an isomorphism of the local defect
calculation and is strictly stronger than agreement on the known misses or on
reachable Booth products.

It does **not** identify which of pair A or pair B is physically wired in
Skylake, prove that this twelve-word encoding is globally bit-minimal among all
possible derived encodings, or supply the missing silicon selector.  The
H1488 six-tuple direct orientation vote remains `FROZEN_UNOPENED`.  The
authoritative frontier remains eleven mode rows over ten operands, and R96
remains empirical/incomplete.

## Artifacts

- `experiments/h1515_quartet_state_quotient.py`, SHA-256
  `6f5c3c050636c0066a349ac22a975e46ce4a15f782cabf313479f56d942e92cf`;
- `tmp/ledger33/current/h1515_quartet_state_quotient.json`, SHA-256
  `25ca77cdf8f1b506be911598a76c54e07d5d927d04f100b567a1f48ef4d697e5`;
- `experiments/h1516_minimal_ordered_quartet_state.py`, SHA-256
  `4513cb796610051297e75f0a064c2e946e34ee4b82ccad9bd6bd46733e9a69fa`;
- `tmp/ledger33/current/h1516_minimal_ordered_quartet_state.json`, SHA-256
  `215d4e6626a35f96492d410b5cd34f45bce864f1b4795ec67419fd62a34f5955`;
- `experiments/h1517_quartet_state_bit_support.py`, SHA-256
  `ee6048cbb237fffd16e420fe142cb8e10d4bcb5d5a19813f73b29a84c9919b55`;
- canonical H1517 report
  `tmp/ledger33/current/h1517_quartet_state_bit_support_canonical.json`,
  SHA-256
  `3846ebdb9d818861b9ef645daf3d5b7f637fb206dcca8a3b676c4f576d58caeb`;
- canonical extension terminal query, SHA-256
  `da362e68c457e984a113f2cc0793f42634c20920513e0e7fcd9ed4f15f0b16f9`;
- canonical reachable-state terminal query, SHA-256
  `cd3b0e5f03f29ca8773f4ef4cbbba107f304f3a3daf084d64db09d5a6fe49b45`.

The H1516 report and the canonical H1517 report plus both terminal SMT2
queries independently reproduce byte for byte.  H1517's earlier witness-rich
report is preserved separately; its support sets and verdicts reproduce, but
arbitrary SAT model assignments were deliberately removed from the canonical
serialization.  Z3 4.15.3 resolves all SAT enumerations, while CVC5 1.3.1
independently proves both terminal complements UNSAT.  No x87 instruction ran,
no hardware or private-ledger label was opened, no manifest was created or
changed, and no emulator behavior or default changed.  The academic paper and
PDF were not modified.
