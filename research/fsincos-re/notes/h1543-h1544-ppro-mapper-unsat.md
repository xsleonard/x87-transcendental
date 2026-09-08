# H1543--H1544 Pentium Pro direct mapper UNSAT

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their exact UNSAT results apply only to that
> mispartitioned dataset and do not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **exact bounded mapper impossibility, independently replayed without
the new pruning; no physical mapper, selector, or promotion.**

## Question

H1504--H1534 ask whether each of the twelve logical public-P6 opcode bits can
select one distinct bit from the 248 non-bit-31 channels in a recovered
Pentium Pro physical line, with one fixed optional inversion per logical bit,
such that all nineteen groups from each of the exact `0x611` and `0x612`
bodies decode to one of the 459 recognized public-P6 opcode values.

The prior QF_BV, Boolean CNF, table-CSP, CaDiCaL, MiniSat, CVC5, and Kissat
runs all remained `UNKNOWN` at their time bounds. H1543 changes search order
and propagation without changing the question.

## H1543 exact search

For each of the 38 recovered rows, the solver keeps the exact bitset of legal
opcodes compatible with the partial mapping. For every unassigned logical bit,
rows whose opcode domains force zero or one define the complete current domain
of signed physical channels. Empty domains reject a state. H1543 adds an exact
bipartite perfect-matching check over the remaining logical-bit/channel
domains, enforcing the injective-channel condition globally.

H1506 broke equal-size MRV domains by logical bit number. At the root all
twelve domains contain 496 signed choices, so that rule selected bit zero.
H1543 instead breaks MRV ties by the exact current ambiguity of each logical
bit across the row opcode domains. This is only a variable-order heuristic;
it cannot remove a solution. Candidate values remain ordered by their exact
remaining opcode mass.

The complete search terminates in 192.227 seconds:

| outcome | nodes | maximum depth | empty-domain failures | Hall failures |
|---|---:|---:|---:|---:|
| UNSAT | 645,503 | 8 | 500,463 | 3,520 |

Therefore no mapping in the stated family exists.

## H1544 independent pruning checks

H1544 first compares the Hall predicate against an independent exhaustive
injection enumeration on 10,000 deterministic randomized bipartite graphs
with one through nine channels and zero through eight variables. All 10,000
results agree.

It then replaces the Hall predicate by constant true and replays the entire
mapper search. The result remains UNSAT after 649,124 nodes in 191.973 seconds,
with zero Hall failures and the same maximum depth eight. Thus H1543's UNSAT
does not depend on the new Hall pruning. The remaining row-domain recursion is
the same exact search principle used by H1506; only its completeness-preserving
variable tie break changes.

## Interpretation and boundary

This resolves H1504/H1505/H1532--H1534's previously UNKNOWN bounded query.
The recovered early Pentium Pro bodies cannot be decoded by directly selecting
twelve distinct physical channels with fixed per-bit polarity while requiring
every row to use the current public later-P6 459-opcode language.

It does **not** prove that no Pentium Pro decoder exists. The old format may
use a different opcode catalogue, a non-selection transform, shared fields, or
other serialization logic. It recovers no absolute ROM address or raw
Skylake control state and supplies no R59 selector. The result therefore closes
the direct later-P6-language shortcut rather than the emulator frontier.

## Subsequent row localization

H1545 replays the exact CSP on row subsets. Each complete patch body alone is
SAT, as is the shared aligned prefix through group 11. The aligned prefix
through group 17 is UNSAT, and that remains true when either body's final
group 18 is restored alone. Thus the contradiction is cross-body, is introduced
somewhere among groups 12--17, and does not depend on either final group. See
`notes/h1545-ppro-mapper-prefix-localization.md`.

No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1543_ppro_hall_csp.py`, SHA-256
  `a5121734bc22796bc470122c3e24a158a55846184df49832982ace29eac40f14`;
- `tmp/ledger33/current/h1543_ppro_hall_csp.json`, SHA-256
  `532c3f05f47c5f4d872450a5231a1363ccbc9af7736f498049d04e571c9e5900`;
- `experiments/h1544_ppro_no_hall_replay.py`, SHA-256
  `e05db278bca92c16943e9301a85243a3017f844c3f1bf699b2d0662a1b3593c1`;
- `tmp/ledger33/current/h1544_ppro_no_hall_replay.json`, SHA-256
  `73364d48cc394ed6be9da14cc1a758107865f49f8c6b3cbf45f08d3d45a9f378`.
