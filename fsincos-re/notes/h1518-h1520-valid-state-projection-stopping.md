# H1518--H1520: minimum valid-state projection stops at UNKNOWN

Date: 2026-09-03

Status: **exact 63-coordinate lower bound and 87-coordinate upper bound inside
the H1516 encoding; one-coordinate candidate unresolved; no selector or
solution promotion.**

## H1518 CEGIS result

H1517 leaves 25 coordinates between its 62 individually necessary valid-state
coordinates and its exact 87-coordinate canonical-extension projection.  H1518
uses exact counterexample-guided synthesis to ask which of those 25 must be
retained jointly.

Each two-copy SAT counterexample has equal values on the currently retained
coordinates and opposite pair-A/pair-B defects.  Its set of differing optional
coordinates becomes a hyperedge that every exact projection must hit.  A
cardinality-minimum, deterministically canonicalized hitting set proposes the
next candidate.  If a proposed candidate were UNSAT, the accumulated edges
would prove that its cardinality is globally minimum among raw-coordinate
projections of the H1516 state.

The first four candidates are SAT.  Their counterexample edges contain 12, 8,
8, and 5 optional coordinates.  In particular, retaining none of the optional
coordinates is falsified, so the H1517 lower bound rises exactly from 62 to 63
coordinates.  The four edges have the one-coordinate minimum hitting set

```text
g5.P[5].
```

The query retaining H1517's 62 mandatory coordinates plus `g5.P[5]` is
UNKNOWN after independent bounded Z3 and CVC5 runs.  H1518 therefore preserves
the exact SMT2 query and stops.  It does not claim that 63 coordinates are
sufficient, that the candidate fails, or that 63 is the final minimum.

The confirmed interval after H1518 is

```text
63 <= minimum raw-coordinate projection size <= 87.
```

## H1519--H1520 backend wall

H1519 runs the frozen H1518 terminal query under four requested CVC5 backend
configurations.  Eager CaDiCaL remains UNKNOWN after 300 seconds.  The local
CVC5 build advertises Kissat and CryptoMiniSat modes but was not compiled with
either backend, so those three configurations return explicit availability
errors rather than solver verdicts.

H1520 exhausts the remaining compiled variants, each for 180 seconds:

| Configuration | Result |
|---|---|
| eager bit-blast + MiniSat | UNKNOWN |
| lazy bit-blast + MiniSat | UNKNOWN |
| lazy CaDiCaL + `bv-to-bool` | UNKNOWN |
| lazy CaDiCaL + BV Gaussian elimination | UNKNOWN |

No backend returns SAT or UNSAT.  Runtime is not evidence about truth, and all
UNKNOWN results remain UNKNOWN.

## Claim boundary

The exact contribution is the improved lower bound and the preserved
one-coordinate stopping query.  `g5.P[5]` is a solver candidate, not an
emulator rule, silicon selector, or confirmed solution.  H1488 remains
`FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the authoritative x87
frontier remains eleven mode rows over ten operands.

## Artifacts

- `experiments/h1518_minimum_valid_state_projection.py`, SHA-256
  `315d95fd655947f7646553e498e4e97663979a0d71afbab9aff13e7c6351fd8f`;
- `tmp/ledger33/current/h1518_minimum_valid_state_projection.json`, SHA-256
  `9ac382b27fbc980214dad9ed9244238b51e16669ec061807fc092dd6b63901d5`;
- `tmp/ledger33/current/h1518_minimum_valid_state_projection_terminal.smt2`,
  SHA-256
  `78b125032269a8ea9585cfa8e023aa480665ab58a72bc46edc046e1499bac1d5`;
- `experiments/h1519_terminal_bv_backend_crosscheck.py`, SHA-256
  `08bc98c544c986d2a0a96de59d4b86052acdaa66eb05472fb1c33b91205f857f`;
- `tmp/ledger33/current/h1519_terminal_bv_backend_crosscheck.json`, SHA-256
  `b5c0686ab40b82be8b1e02e283da72bc075e81ad2fc03cae5bef8078501aceca`;
- `experiments/h1520_terminal_minisat_crosscheck.py`, SHA-256
  `6d347df5abd7bac9963f2914de1c26157fc86b1336c448d1479a4063709fc974`;
- `tmp/ledger33/current/h1520_terminal_minisat_crosscheck.json`, SHA-256
  `26b79913f38e4b2fa1b9737f4302293113c5c5149519bae5a96b408c50980269`.

No x87 instruction ran, no hardware or private-ledger label was opened, no
manifest was created or changed, and no emulator behavior or default changed.
The academic paper and PDF were not modified.
