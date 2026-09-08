# H1532--H1534: prime-CNF and factored-polarity Pentium Pro mapper audit

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their bounded results apply only to that
> mispartitioned dataset and do not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **two exact structural reductions completed; these CaDiCaL and
official Kissat runs return UNKNOWN; the bounded query is subsequently UNSAT
in H1543/H1544; no mapper, selector, emulator, or paper/PDF change.**

## H1532: exact prime implicates of the public opcode language

H1505 encoded recognition by excluding all 3,637 unrecognized complete
twelve-bit words independently on each of 38 recovered rows. That encoding is
exact but weak: every recognition clause has width twelve.

H1532 exhaustively derives every minimal forbidden partial assignment of the
same 459-value public P6 recognized-opcode language. There are exactly 533
prime implicates:

| Width | Count |
|---:|---:|
| 2 | 1 |
| 3 | 8 |
| 4 | 103 |
| 5 | 178 |
| 6 | 188 |
| 7 | 50 |
| 8 | 3 |
| 9 | 2 |

Evaluating both descriptions on all 4,096 twelve-bit words proves exact truth-
table equivalence. Substituting the prime clauses into H1505 leaves its
one-hot signed-channel choices, cross-bit channel distinctness, and decoded-bit
links unchanged. The result has the same 12,348 variables but 329,722 clauses,
117,952 fewer than H1505. Bitwuzla 0.9.1 with its compiled CaDiCaL backend
returns `UNKNOWN` at 300.058 seconds.

## H1533: independent official Kissat backend

The installed Bitwuzla advertises four SAT backends but was compiled only with
CaDiCaL. H1533 therefore builds the official MIT-licensed Kissat 4.0.4 source
release from <https://github.com/arminbiere/kissat> in an isolated temporary
directory and runs the resulting solver directly on H1532's immutable DIMACS
file.

The source archive SHA-256 is
`bfe93eaa6323b48011e4b1fcf74b3f2e20f9de544767e728009e5b2018296193`;
the local binary SHA-256 is
`b7ea81d672fc3e4581dcb4de12344f9cd3730d9ef2fcffe91120f2598e2694d9`.
Kissat also returns `UNKNOWN` at 300.016 seconds. No model is emitted.

## H1534: exact channel/polarity factorization

H1505/H1532 represent each logical opcode bit by one of 496 signed choices,
`2*c+p`, where `c` is one of 248 physical channels and `p` is its fixed
polarity. H1534 applies the exact inverse factorization: one 248-way channel
choice plus one polarity bit per logical opcode position. The mapping is a
bijection, not a relaxation.

The factorization exposes polarity as one shared bit across all 38 rows and
reduces channel distinctness from four binary clauses per logical-bit pair and
channel to one. Together with H1532's prime recognition clauses, the exact CNF
falls to 6,408 variables and 271,690 clauses. Official Kissat 4.0.4 returns
`UNKNOWN` at 300.010 seconds. Again, no model or UNSAT theorem is produced.

## Boundary

These are meaningful exact reductions, but they do not decide the bounded
mapper question. `UNKNOWN` is not evidence that the mapper exists or is
impossible. Even a future SAT/UNSAT result would apply only to an injective
twelve-channel, fixed-polarity decoder under the current 459-value public P6
recognized-opcode condition; that catalogue may be incomplete for Pentium Pro.

This stops further cosmetic mapper encodings and solver-seed changes. The
remaining high-value routes are a genuinely paired old-format mapping source,
a new raw control-state observable, or the separately authorized H1488 direct
orientation vote. H1488 remains `FROZEN_UNOPENED`.

## Subsequent exact resolution

H1543 later applies the same exact row-language CSP with an ambiguity-based
MRV tie break and bipartite all-different propagation. It exhausts the tree
and returns UNSAT. H1544 validates the matching predicate against exhaustive
enumeration on 10,000 random small graphs, then disables that pruning entirely
and independently replays the complete search to the same UNSAT result.

Thus the solver outcomes recorded above remain correctly `UNKNOWN`, but the
bounded H1504/H1505 query itself is now decided: no injective fixed-polarity
twelve-channel mapping satisfies the current 459-opcode public-P6 language on
all 38 recovered Pentium Pro rows. See
`notes/h1543-h1544-ppro-mapper-unsat.md`. This does not exclude a different
Pentium Pro opcode catalogue or a non-selection physical transform.

## Artifacts

- `experiments/h1532_ppro_prime_implicate_cnf.py`, SHA-256
  `3b545b71a72793f3d57f0c1bab01e38e666b9c150db84285949d11334211323f`;
- H1532 report, SHA-256
  `5bce70ca584d45ce6b09c36f657ffe21e468fd4a41ae0772fea753b69a007e71`;
- H1532 DIMACS CNF, SHA-256
  `5cfd3b8f5b10a9358d80e9faf47f0371ae6275a90c1a22f097148e33ad020af8`;
- H1532 SMT-LIB mirror, SHA-256
  `3b9bf75919377570db64ff796ffe336b68dbf20ef23388ad353bb46f0baf8595`;
- `experiments/h1533_kissat_dimacs_crosscheck.py`, SHA-256
  `c9efffa8065706d5db78d7b4faca5e2ec73002102e53125979d10abdbfe2bb34`;
- H1533 report, SHA-256
  `8551afbc68bd8f106b75edf1bd44431ea627d4f3bae6b197097273f04cce1afb`;
- `experiments/h1534_ppro_factored_polarity_cnf.py`, SHA-256
  `2bf79a00a84220adee9c349f97eefa0d9dd8f5491c3046784acdb64d666a24c2`;
- H1534 CNF, SHA-256
  `4326a7d4d10806834c7e6c5c6af477e18fd6363c41c018e351e00f6063ff20d3`;
- H1534 report, SHA-256
  `aa1f066228c4d5b4e6b77c3e4221e1d788ae1374e5481e153255e5faf31abdd2`.

No x87 instruction or hardware capture ran, no hardware label or private
capture ledger was opened, and no manifest, emulator behavior/default, or
academic paper/PDF changed. R96 remains empirical/incomplete and the
authoritative frontier remains eleven mode rows over ten operands.
