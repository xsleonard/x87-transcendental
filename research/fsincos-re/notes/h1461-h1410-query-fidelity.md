# H1461 H1410 standalone-query fidelity correction

H1410's in-process Z3 result and its exported SMT-LIB file did not describe
the same assertion set.  `Solver.assert_and_track` checks each tracked
constraint under a tracking literal, but Z3's `to_smt2()` output contains
only an implication from that literal.  The original 10,632-byte H1410 file
declares `h1410.exact_materialization_path` and
`h1410.endpoint_visible` but never asserts them.  It is therefore
underconstrained and is not a faithful standalone reproduction of the H1410
second-witness query.

This does **not** turn H1410's result into SAT or UNSAT.  The Python call to
`solver.check()` did apply the tracked constraints and correctly reported
**UNKNOWN** after its 60,000 ms bound.  H1409 is unaffected: its exporter
already inserted explicit assertions for both of its tracking literals, and
its exact Z3/CVC5 checkpoints remain authoritative.

`experiments/h1461_h1410_query_fidelity.py` rebuilds the same width-minimal
external-input graph, asserts both H1410 tracking literals explicitly, checks
the known d0d0 witness, excludes it, and emits a self-contained QF_BV file.
The known witness remains SAT and its independent Python replay is exact.
The corrected second-witness query remains **UNKNOWN** after 60,000 ms under
Z3 4.15.3.  Invoking the standalone Z3 4.15.3 binary on the corrected file
with `-T:60` independently returns `timeout`; this is still not evidence of
unreachability.

Artifacts:

- `experiments/h1461_h1410_query_fidelity.py`, SHA-256
  `5045895aa044af4aebf6d65877a2bf72ec0ddc6d76242a7996f60a359fb93432`;
- `tmp/ledger33/current/h1461_h1410_query_fidelity.json`, SHA-256
  `bd230672cae4590216ca4b0f4a8afdb8c360fcfd4e8b0e1e07429dfeacce0d3a`;
- `tmp/ledger33/current/h1461_h1410_query_fidelity.smt2`, 10,721 bytes,
  SHA-256
  `e245f87e736c4a3d03361b91deacadc24039a3650d37c73787ac515e7880e499`.

The original H1410 files are preserved unchanged for provenance, but its
SMT-LIB file must not be supplied to another solver as the intended query.
No hardware was executed, no selector was promoted, and no emulator default
or academic-paper artifact changed.
