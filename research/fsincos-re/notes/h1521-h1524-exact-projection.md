# H1521--H1524: exact 63-coordinate projection and decoder-extraction wall

Date: 2026-09-03

Status: **exact 63-coordinate minimum inside the H1516 raw-coordinate
projection family; H1523/H1524 did not extract a decoder, but H1528--H1530
subsequently supplied and proved one constructively; physical Skylake
orientation unresolved; no selector promotion.**

## H1521: exact width reduction

H1518's unresolved candidate used two copies of twelve nine-bit words plus 63
bit equalities.  H1521 reconstructs the same obligation with one shared
Boolean variable for every retained coordinate, independent left/right
variables for the omitted extension-sensitive coordinates, and zeroes only
the 21 coordinates H1517 proved absent on the unconstrained extension.

Two controls validate the reduction:

- the 62-coordinate lower case is SAT and preserves a counterexample;
- the complete 87-coordinate upper case is UNSAT and preserves H1517's exact
  sufficient projection.

The middle case retains H1517's 62 individually necessary coordinates plus
`g5.P[5]`.  It remained UNKNOWN after Z3 and CVC5 bit-vector bounds.  H1521
therefore made no sufficiency claim.

## H1522: the candidate is exactly sufficient and minimal

H1522 applies Z3's exact
`simplify -> propagate-values -> solve-eqs -> bit-blast -> tseitin-cnf`
pipeline to H1521's middle case.  The immutable result has 746 Boolean
variables, 3,388 clauses, and 65,665 bytes.

The solver outcomes are:

| Backend | Result | Bound/runtime |
|---|---|---:|
| Z3 propositional SAT | UNKNOWN | 300,009 ms |
| CVC5 QF_SAT CaDiCaL | **UNSAT** | 4,061 ms |
| CVC5 QF_SAT MiniSat | UNKNOWN | 300,014 ms |

An independent CaDiCaL replay of the preserved CNF also returned UNSAT in
4,140 ms.  Combined with H1518's exact one-coordinate lower bound, this proves
that the minimum projection in the named H1516 raw-coordinate family has
exactly 63 coordinates.  Its unique one-coordinate extension of the H1517
mandatory set is `g5.P[5]`.

The retained coordinates have the compact window form

```text
g0: T[0..7], U[0..4]       g1: T[0..7], U[0..3]
g2: T[0..7], U[0..4]       g3: T[0..7], U[0..4]
g4: T[3..7], P[2..3]       g5: T[5..7], P[4..5]
```

This is a universal quotient theorem for every valid H1516 redundant state,
not a fit to the known x87 misses.  It is not a global lower bound over every
possible derived encoding and does not choose pair A versus pair B.

## H1523--H1524: formula extraction remains unresolved

H1523 asks CVC5 for a Craig interpolant between a valid defect-one completion
and the proposition that every valid right completion has defect one.  A
successful interpolant would use only the 63 shared coordinates and would be
an explicit Boolean decoder.  Both the default shared-interpolant run and the
recommended `full-sygus-verify` run returned a null interpolant after roughly
300 seconds.  CVC5 warned that its SyGuS engine failed to verify a candidate;
that is recorded as UNKNOWN, not as a rejected decoder or impossibility
result.

H1524 instead defines the projected decoder as

```text
F(k) = exists private completion: valid(k,private) AND defect(k,private)=1
```

and tries three exact Boolean quantifier-elimination pipelines.  `qe2` and the
`qe-light`/`qe2` route timed out at 120 seconds.  Plain `qe` returned an
incomplete expression: it had 63 free shared variables and a 1,172-node DAG,
but still contained a quantifier.  No decoder artifact was accepted.

These extraction failures do not weaken H1522.  They show only that the local
solver portfolio did not turn the exact quotient into a practical explicit
formula.  Per the directional pivot, no further primary effort is spent on
representation compression.

## Subsequent constructive resolution: H1528--H1530

H1528 later bypassed interpolation and quantifier elimination by constructing
one valid canonical completion for every 63-bit projected key. Independent
UNSAT obligations prove that the completion is total and projection-preserving
and that its defect equals every valid original completion. H1529 reproduces
both immutable-CNF proofs. H1530 unrolls the completion's carry recurrence into
a direct Boolean formula and proves exact equivalence.

Thus H1523/H1524 remain correct method-specific UNKNOWN results, but their
explicit-decoder stopping point is no longer the current boundary. See
`notes/h1528-h1530-constructive-projection-decoder.md`. The physical pair-A
versus pair-B orientation remains unresolved, so no emulator selector follows.

## Physical boundary and next decision

The 63-coordinate result refines the abstract pair-A/pair-B defect
representation.  It does not establish which orientation, if either, is wired
in Skylake.  The frozen H1488 six-tuple campaign remains the direct physical
vote: two pair discriminators plus four unanimous controls, one observation
maximum per tuple.  Its repository-side hashes and scorer selftest were
rechecked after H1524 and remain intact, with no hardware-output directory.

No H1488 copy or execution occurred.  The mandatory immediate private-ledger
collision check and one-shot hardware run still require the exact named H1488
authorization.  If H1488 selects one pair across all six rows, that justifies
integrating the structural circuit as the leading physical model, but remains
fresh finite validation rather than global x87 closure.  If both pairs fail,
the pair model must be abandoned and the strongest remaining directions are
absolute ROM/control-state recovery or a genuinely new observable.

## Artifacts

- `experiments/h1521_width_reduced_valid_projection.py`, SHA-256
  `ca9f83ae9f4b98b7d3f367d627622cf8dbaeed12e9cd1ceb173484299487ad4c`;
- H1521 report, SHA-256
  `884dcbcd883ab9a65b62c4b0a347be378da1f2590987d7ec1aeca5dabedce7da`;
- H1521 lower/candidate/upper SMT2 queries, SHA-256
  `a7f2bd9c8580fce7b4a0a461282dc5d0be77da39b6d3b80eab6d1c1c98e720e4`,
  `3f445e15896ab459bf414c8cb1752dc01a236c8159723a3629fd57cea9ddc750`,
  and `c004ce72a624085212ef175b2d9a79a3596310b4fe6fb6d774f4c1fe240cd078`;
- `experiments/h1522_exact_cnf_projection.py`, SHA-256
  `66b366030cc58694716a39908f8aa9aea352535f8d47774dee9f6a22e3f5aa35`;
- H1522 report, SHA-256
  `f4e09346f6185324245d2363a922f26d8bc0e41962982157077d165e9bebf4b8`;
- H1522 CNF, SHA-256
  `b9b9c47653a88ad9b0e5af653de3da2afddc1e6907b636a0886e97add6c0dee6`;
- `experiments/h1523_exact_projection_interpolant.py`, SHA-256
  `390026657e399da50713af1404c69c3d8fa6f7636c98bdddbfe3ba46ed40aa4e`;
- H1523 default/full-verification reports, SHA-256
  `172ce16f5f3ec2ea4c8d03158da2963576af441cdee3628f02e32f0a1d2c23b9`
  and `5e5cbc466d63c7b468d18bc0fa381c93d3e5ef814030064e73b887d19373939f`;
- shared H1523 query content, SHA-256
  `016296c0594f790a68b6ee78baa07c448ce1a649bdf2a386a9f9e1721f55a4ee`;
- `experiments/h1524_exact_projection_qe.py`, SHA-256
  `bc27e7e6cf6fc7ba8f6a334ba7a843f4e74088144242045bafc96c0337b101f6`;
- H1524 report, SHA-256
  `29da8dbdd5f56bb20943d61711dc968b084b4b760bf1188bf5e9c1bb2d38f2f9`.

No x87 instruction ran, no hardware or private-ledger label was opened, no
capture manifest changed, and no emulator behavior or default changed.  The
academic paper and PDF were not modified.  H1488 remains `FROZEN_UNOPENED`,
R96 remains empirical/incomplete, and the authoritative frontier remains
eleven mode rows over ten operands.
