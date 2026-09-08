# H1410 width-reduced R1382 second-witness check

> **H1461 standalone-file correction.**  The in-process H1410 Z3 check did
> apply its two tracked constraints and its `UNKNOWN` result remains valid.
> However, the preserved H1410 `.smt2` file contains only implications from
> the two tracking literals and does not assert those literals.  It is
> underconstrained and is not a faithful standalone query.  Use
> `tmp/ledger33/current/h1461_h1410_query_fidelity.smt2` for standalone
> replay; the corrected query also returns `UNKNOWN` at 60,000 ms.  Full
> audit: `notes/h1461-h1410-query-fidelity.md`.

`experiments/h1410_width_reduced_r1382.py` is an analysis-only exact QF_BV
reformulation of the H1409 fixed-path query.  It replaces uniform 136-bit
carriers with operation-specific widths: each product keeps the sum of its
operand widths and every addition reserves its carry bit.  The known
`3ffc d0d000000cc0b3f8` witness replays exactly through the independent H1404
Python model.

Before the main search, a finite local QF_BV lemma proves UNSAT for the
negation of the endpoint reduction.  The lemma establishes exact equivalence,
on the fixed correction-exponent range, between the four duplicated output
rounders and the reduced comparator/Mreg/retained-residue predicate.  This is
a proof-preserving circuit reduction, not an operand scan.

After excluding d0d0, the width-minimal in-process external-input query reached its
60,000 ms bound.  Its result is **UNKNOWN**, not UNSAT and not evidence of
unreachability.  The original preserved report is
`tmp/ledger33/current/h1410_width_reduced_r1382.json`; the exact 10,632-byte
serialization is preserved for provenance in the repository worktree at
`tmp/ledger33/current/h1410_width_reduced_r1382.smt2`, SHA-256
`18a583a2b92e736e5afe89f07d26cd2e0a903b4722908f75abac8be95c713c46`;
because it omits the tracking-literal assertions, it must not be treated as
the exact standalone query.  H1461 preserves the faithful replacement and
the same bounded `UNKNOWN` outcome.

No SAT assignment was produced, so no C witness replay or capture manifest
was applicable.  No hardware was executed and no emulator default changed.
