# H1463--H1465: exact modular-square reduction of the R1382 search

Status: **four exact local reductions proved; second-witness query remains
UNKNOWN; no selector promotion.**  This is analysis-only evidence.  It does
not establish R1382 as a silicon law or as a generally reachable endpoint
correction.

## Question

H1410/H1461 left the exact fixed-path second-witness query at UNKNOWN after
blocking the known d0d0 operand.  H1463 asks whether the expensive endpoint
part of that query can be replaced by exact modular conditions before the
remaining polynomial graph is sent to a bit-vector solver.

The primary variable is the 67-bit chopped first square.  This is a sound
superset of externally representable `3ffc` significands.  Every SAT square
would still be checked by exact integer square-root bounds for a unique
64-bit external preimage and then replayed through the independent H1404
integer graph.  Consequently:

- UNSAT would prove absence in the external subset;
- SAT is not reported as an external witness without the preimage and replay;
- UNKNOWN proves neither existence nor absence.

## Exact reductions

Four independent QF_BV counterexample queries are UNSAT:

1. The current/plain hard-3x comparator split holds exactly when the 64
   discarded right-product bits lie in the closed interval
   `[0xaaaaaaaaaaaaaaab, 0xaaaaffffffffffff]`.
2. On the proved retained-value binade, four-mode endpoint visibility is
   exactly the six residues modulo 512
   `{0x000, 0x100, 0x001, 0x101, 0x081, 0x180}`.
3. The signed 72-bit `Mreg` range `0 <= Mreg < 2^66` is exactly the test that
   bits 71:66 are zero.
4. On this fixed terminal path,
   `umag = (left_sig << 8) + 3 - right_sig`.  Zero terminal discard is exactly
   `right_sig mod 256 = 3`; the retained residue is the low nine bits of
   `left_sig - (right_sig >> 8)`.  Fusing this with item 1 constrains the low
   72 bits of the right product to
   `[0x03aaaaaaaaaaaaaaab, 0x03aaaaffffffffffff]`.

These are algebraic circuit equivalences, not fitted boundaries.  Each is
proved by asking for a counterexample to the original/reduced equivalence and
obtaining UNSAT.

## Solver results

The known operand `3ffc d0d000000cc0b3f8`, chopped square
`0x552954800a66eecbb`, remains SAT and matches the independent Python replay.
After excluding that square:

- the combined Z3 4.15.3 query reaches 60,000 ms as UNKNOWN;
- splitting on each of the six exact endpoint residues also gives six
  UNKNOWN results at 60,000 ms;
- CVC5 1.3.1 independently returns `UNKNOWN (TIMEOUT)` for the combined query
  and all six residue branches with explicit `QF_BV` logic.
- Bitwuzla 0.9.1 independently returns UNKNOWN for the combined query and all
  six branches using its default bit-blast/abstraction/CaDiCaL configuration.

No SAT square, rejected non-preimage square, or external witness was produced.
The result therefore sharpens the exact query but does not close it.  R1382
remains an upstream boundary alias and remains default-off.

## Artifacts

- `experiments/h1463_r1382_modular_square.py`, SHA-256
  `e5b3d41309e535825e84746b7b91a2f38bab7452191835efd21b4b544f85a5bc`;
- `experiments/h1464_r1382_cvc5_crosscheck.py`, SHA-256
  `41c5608cc31dcc699274b7f45cb46cb171f2a179e8f6feb7960c518f1c324d94`;
- `experiments/h1465_r1382_bitwuzla_crosscheck.py`, SHA-256
  `44cb653e10bfdd8c6166b4221703f09e01cba4cc3d463dc4881cc2dfd89e41e7`;
- `tmp/ledger33/current/h1463_r1382_modular_square.json`, SHA-256
  `a2f660a2eeebaccd1ffc28e2ad03641dcfb5b46e080554a8161ebbbfa1f15d14`;
- `tmp/ledger33/current/h1463_r1382_modular_square.smt2`, 14,166 bytes,
  SHA-256
  `1910d0718257437a86b9a57e5ddf2f201916f444a8833524f13ebb01333dffe1`;
- the six residue-specific H1463 JSON/SMT-LIB pairs alongside the combined
  artifact;
- `tmp/ledger33/current/h1464_r1382_cvc5_crosscheck.json`, SHA-256
  `cf3b35a701fb4d5725fa60568241f0754cd4cb29e07b4259dccc4ae59a627a4b`;
- `tmp/ledger33/current/h1465_r1382_bitwuzla_crosscheck.json`, SHA-256
  `355d4fad1957968c2c663836d10113da44df6deed812b932f3e1357ced3491ff`.

No x87 hardware was run, no capture label or private ledger was opened, no
manifest was frozen, and no emulator default changed.  The academic paper and
PDF were not modified by this investigation.
