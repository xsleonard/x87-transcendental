# H1568: reconcile the expanded observed R59 frontier

This is an existing-capture replay, not a hardware campaign. No observation
was repeated, no selector was promoted, and no emulator or paper changed.

The old **11 mode rows / 10 operands** is the historical H1378 corpus count,
not the current combined known-failure count. With the four opened direct-FCOS
lattice campaigns included, the current ledger-off model has **33 captured
failing mode rows over 32 operands**. This is a lower bound from the five
explicit sources below, not a complete repository-wide census. Unobserved
rounding modes are not filled in or inferred.

| Source | Captured rows used | Baseline exact | Baseline misses |
| --- | ---: | ---: | ---: |
| H1378 historical misses | 11 | 0 | 11 |
| H1472 | 16 | 8 | 8 |
| H1477 | 10 | 5 | 5 |
| H1488 | 6 | 3 | 3 |
| H1566 | 8 | 2 | 6 |
| Total | 51 | 18 | 33 |

The 51 rows cover 50 distinct operands. Every one of them equals exactly one
of the model's two forced final-R59-carry endpoints. All 22 new misses require
carry 1; the 18 fresh exact controls require carry 0. Of the historical eleven
miss rows, eight require carry 1 and the three far-corner rows require carry 0.
This strengthens the terminal-carry localization; it does not determine the
missing selector or establish that the physical circuit uses this abstraction.

The replay checks each opened-once sidecar, immutable freeze, positional input
manifest, and raw-output hash. For all 40 new observations the current baseline
and no-merge endpoint reproduce the respective frozen predictions exactly.
Thirty signed unit perturbations across fifteen earlier arithmetic stages
produce no universal repair. For example, square +1 repairs 32/33 misses but
breaks all 18 controls; fourth -1 repairs 30/33 and breaks all 18. These
intervention figures apply only to this 51-row bank, not the larger earlier
control wall.

Reproduction uses current `src/fsincos_skylake.c` SHA-256
`8fe40b8c852918f9cbe57a91b678861aa5e847f6c07106db1a18175a22314f39`.
Build four software models with `cc -O2 -std=c11`, `-DG_ROUND84=0`, and `-lm`:
`baseline` has no extra define, `carry0` adds `-DG_R99CARRY=0`, `carry1` adds
`-DG_R99CARRY=1`, and `nomerge` adds `-DG_R1382MERGES4=1`. Then run
`experiments/h1568_expanded_causal_frontier.py --root fsincos-re --models DIR
--output NEW_REPORT.json` from the repository root. The report records binary
and input-evidence hashes; it refuses to overwrite an existing artifact.

Artifacts:

- `experiments/h1568_expanded_causal_frontier.py`, SHA-256
  `5d32b628c2bd510d65fd915907bb525932b621b348752da411e26dbc3acc006c`.
- `tmp/ledger33/current/h1568_expanded_causal_frontier.json`, SHA-256
  `891c20d6fb3e54dd6ed2ddcfabe9ee695b5785a1b232773be266b49843b000cc`.

Earlier handoff entries saying the authoritative frontier "remains eleven"
are superseded by this explicit reconciliation. R96 remains empirical and
incomplete; R1382, QX, Q, and the falsified pair/tree candidates remain off.
