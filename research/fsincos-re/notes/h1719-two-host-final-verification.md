# H1719 — policy-2 saved-label verification on both x86 hosts

2026-09-05. Requested: rerun the full verifier for the final solution on i7
and Skylake. No hardware observations were repeated. This is software replay
of previously opened outputs, not a new corpus-v1 Cartesian capture.

## Status

COMPLETE: zero output, applicable recorded C1, or C2 misses on either host.
The full shared retained suite and all available mapped native historical
banks pass. Totals (overlapping row appearances) are:

| Execution host | Instruction-row appearances | Output lanes | Applicable recorded C1 checks |
| --- | ---: | ---: | ---: |
| i7 | 299,028,167 | 356,459,555 | 193,825,064 |
| Skylake | 17,604,112 | 29,648,279 | 17,600,228 |

| Completed component | Instruction-row appearances | Output lanes | Applicable recorded C1 checks | Misses |
| --- | ---: | ---: | ---: | ---: |
| i7 h491: every mapped saved status bank, plus sc_recheck | 281,799,519 | 327,186,732 | 176,600,292 | 0 |
| i7 h633 wholesale, RN/RD/RU | 1,572,864 | 1,572,864 | 1,572,864 | 0 |
| Skylake historical h347/sweep/dense, all four RC | 1,948,328 | 1,948,320 | 1,948,320 | 0 |
| Shared complete retained suite, both x86 hosts and local ARM replay | 15,655,784 each | 27,699,959 each | 15,651,908 each | 0 |

The shared suite has 167 jobs: all 15 retained paired banks (three RC), all
72 retained standalone jobs, all 357,360 normalized H1712/H1714/H1715/review
observations, and the 81 frontier plus 53 legacy regression fixtures. The
fixture expectations are retained test evidence, not operand corrections in
the algorithm. Their synthetic SW fields encode only the recorded C1, not
newly observed full status words.

Counts overlap between banks, hosts, and repeated numerical projections of
PC-specific rows. They are not unique silicon observations. Both hosts run
the same complete retained suite plus their available historical banks; the
larger i7 h491 wall is not claimed to have been executed on Skylake or to
contain Skylake-origin observations.

## Exact build and verification integrity

Both hosts rebuilt the unchanged main source and current all-product-cut
header with GCC 12.2, `-O2 -std=c11 -ffp-contract=off`. The resulting main
binaries are byte-identical:

- main source: `490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32`;
- policy-2 header: `4eeb671562969e39b334923cbf41a40cb86f2a5ecb3dbad23de320be315b9a5d`;
- x86 main executable: `90ae468561ce4f9a5f572c1f9956fc1bb79dcd385b85da6fbb081eae67867559`;
- x86 embedded verifier: `8dcc965afa201f004beab5bb061aa6212dce31f43fb9e19de469cbe79957fac8`.

Execution contexts reported i7-6700 family 6/model 94/stepping 3 at
`142.132.217.243` and Xeon Skylake family 6/model 85/stepping 4 at
`45.32.204.118`. These are execution-host metadata, not retroactive upgrades
to the historical captures' CPU identity quality. Xeon virtualization and
historical FMS-only provenance remain limitations.

The old shell wall did not validate complete stream lengths or recorded C1.
The new verifier calls the unchanged promoted C entry points, strictly parses
input/output records, rejects short/extra/malformed streams, and compares C1
only when both applicable and recorded. Files are hashed before and after
the native wall. Missing mode files are retained in the inventory: 31 on i7,
zero in the selected Skylake historical wall. Every existing h491
`*status.txt` file was mapped, including h633; sc_recheck's non-status-suffixed
files were included separately. No absent mode is counted as a pass.

Both hosts passed the main self-test, six saved paired regressions (including
the policy-1 separator), and 1,704 actual-CLI versus embedded-driver cases.
Five negative controls reject truncated/extra/malformed labels, incorrect
C1, and the old policy-1 output. Local UBSan matches all 1,704 probes without
diagnostics. All eight corpus-toolkit synthetic tests pass. Python syntax
and changed-file whitespace checks pass.

The original-raw Skylake CLI replay also passes 357,360 tuples / 482,304
lanes / 353,520 applicable C1 checks, including the saved C2 operand
preservation and stack mappings. This is an independent reader of the same
opened observations, not additional unique coverage, and is not added to
the table totals.

## Artifacts and boundaries

- Code: `experiments/h1719_saved_verifier.c`, `h1719_run_saved_suite.py`,
  `h1719_retained_bundle.py`, `h1719_finalize_replay.py`.
- Canonical downloaded evidence:
  `tmp/ledger33/current/h1719_two_host_replay/{i7,skylake}-bulk/`.
- Reconciled counts, code hashes, per-component provenance and limitations:
  `tmp/ledger33/current/h1719_two_host_replay/report.json`, SHA256
  `a6eb46893e2f8a83f5478f6347d4c126f1e3163427b9ebd296b7f89c871f8d84`.
- Shared public bundle: `tmp/ledger33/current/h1719_local_checks/retained.zip`,
  220,327,102 bytes, SHA256
  `4351394266f9af1df1298d28eec2873dabbc1a5d1d7a1999287c0345c2e29ab1`.
- Remote isolated builds/reports: `/root/h1719-policy2-verifier` on each host.

The platform rejected uploading model sources to Skylake. Read-only checks
then located an already-present, exact policy-2 source/dependency copy at
`/root/fsincos-review-p2`. Those local files were copied into the isolated
verification directory and rebuilt without uploading the model sources.
Only the new public test drivers and public saved-test bundle were uploaded
after that discovery. No private supplemental data or implementation was
accessed/exported. Original remote builds and capture files were preserved.
Only per-job generated scratch copies are automatically removed; all reports
and the recoverable public bundle remain.
All verifier processes finished. Final disk headroom: approximately 1.2 GiB
on i7 and 486 MiB on Skylake; do not expand a new full capture there without
checking storage first. No original data was deleted to make room.

The algorithm, corpus v1, paper TeX and PDF are unchanged. TeX SHA256 remains
`9d11c734967fcb1c830d571fc99387a0de0bd1765519dc771daf4b7dfa4829ff`;
PDF remains
`e08a56571c3a40c011fddf3487ceeb44a1483e194d1495dee43ea3b9bdf636e0`.
The unmaterialized seed-based native exhaustive loop was not rerun, and
unrecorded/undefined C1 and unimplemented architectural state are not claimed
as verified. Zero saved-label misses is not universal silicon or
cross-generation proof.
