# H1576–H1582: exact equality adversaries expose five new misses

**The current model is falsified on five new direct residual operands. No
replacement selector was found or promoted.** Eleven fresh FCOS/PC64 tuples
ran once on the authorized Skylake Xeon, with six current-model successes and
five strict-comparison endpoints. No other output occurred. No hardware tuple
was repeated; no emulator behavior/default or paper/PDF was changed.

## Construction before labels

H1575's fixed-rule ablation showed that the earlier hard-3x challenge did not
exercise the equality gate's enabled branch. H1576 constructs a different
surface from integer arithmetic, without fitting hardware labels. Put
`h = rsh`, `B = 2^(h-16)`, `v = 21845`, and `R = v*B + u`. For
`h in {63,64}` and `B/2 <= u < ceil(2*B/3)`, both comparison expressions obey

```text
3R - (2R mod B) - (R mod B) = 3R - (3R mod B) = 2^h.
```

Thus the b1 equality exists under both hard-3x merge conventions. A Euclidean
floor-sum routine finds modular-product hits inside sampled positive-Horner
RN64-proxy plateaus. Exact integer inversions recover fourth-to-square and
square-to-external-input preimages. Both `s4=66` and `s4=67` are sampled.
This is not an exhaustive input-domain search; the proxy must also agree with
current-source arithmetic before a candidate is eligible for capture.

H1576's selftest covers 400 modular count/first-hit comparisons with brute
enumeration, including deliberately nonempty windows; the equality algebra;
and 200 square-inversion probes. H1577 generated 50,000 rows and compared
separately compiled current-source strict/inclusive tap endpoints. One operand
was endpoint-visible and passed the exact current-source equality check.

H1578 provides a bounded-memory streaming endpoint filter. Its output was
checked against the independent constant-tap builds on all 50,000 H1577 rows,
not just a visible spot check. H1579 generated 500,000 further rows, preserving
all raw inputs in gzip and independently checking every proxy equation in
Python integer arithmetic. Ten endpoint-visible operands survived all current
trace and independent P5-tree checks; none was rejected. Every emitted endpoint
was checked again with the separately compiled constant-tap binaries.

The combined eleven candidates all have `held_carry & final_kill = 0` and
`final_kill = 0`: ten at s4=66, one at s4=67. Therefore the frozen challenge is
explicitly an **off-branch false-negative test**, not validation of the enabled
R1263 branch. The known de4 enabled-branch control is inside the same algebraic
window. Failure to find a fresh enabled-branch separator in these sampled runs
is not evidence of unreachability or UNSAT.

## One-shot capture and result

H1580 froze all eleven candidates, choosing one separating mode per operand
in RN/RD/RU order. Baseline was inclusive for every selected tuple. A
conservative significand-level repository audit and the local 26-file private
ledger audit found zero collisions at freeze and immediately before copying.
Private data was not copied or published.

The new `/root/h1580` directory was reserved after verifying no prior path.
Capture binary and source hashes matched the established oracle; all frozen
files and the CHECKSUMS file itself matched remotely before execution. The
runner refuses any existing hardware-output directory, including a partial
one. It completed eleven tuples with zero repeats on `45.32.204.118`, the
user-designated Skylake Xeon. Raw outputs, status words, host metadata and
hashes are preserved in `transfer-tests/h1580/hardware-output`.
`OPENED.json` records OPENED_ONCE; the original FREEZE.json is unchanged.
Never rerun H1580.

H1581 verifies raw hashes, positional input order, row counts and endpoints:

| New failing input | Mode | Baseline significand | Hardware significand |
| --- | --- | --- | --- |
| 3ffc:c6db323ae10c933c | RD | fb302283ae33f706 | fb302283ae33f705 |
| 3ffc:c891b50fb448de18 | RN | fb1ae3a271670cbd | fb1ae3a271670cbc |
| 3ffc:cd4893119fccd843 | RD | fadf7d10c9428cdc | fadf7d10c9428cdb |
| 3ffc:cf62ea1253ad3be5 | RU | fac48d8e3089061b | fac48d8e3089061a |
| 3ffc:d61e3ebad895931b | RD | fa6c81c5c2eb7176 | fa6c81c5c2eb7175 |

All outputs above have exponent/sign word 3ffe. These five match the strict
endpoint; six controls match inclusive. Always changing equality to strict
would therefore break six controls in this bank. This falsifies completeness
of the composed current predictor on its off branch. It does not identify the
physical cause or prove that silicon has the abstract gate used by the model.

## Causal replay and reconciled frontier

H1582 rechecks opened evidence and replays the unchanged ledger-off model.
Every new observation equals exactly one forced final-R59-carry endpoint:
carry 1 for all five failures, carry 0 for all six controls. No new output is
outside these endpoints. All five failures are invariant under H1575's seven
fixed programs, including disabling all five listed rules. Neither disabling
the equality gate nor removing hard-3x merge changes any new row.

Thirty earlier signed unit interventions were tested on the new bank. Every
intervention repairing all five misses breaks all six controls. This is a
bounded numerical localization result, not exhaustion of all possible earlier
circuits or proof of a physical terminal carry mechanism.

The explicit direct bank is now 62 observations over 61 operands, containing
**38 failing mode/residual rows over 37 distinct residual operands**. The
five new misses are fresh residual states, not reduction aliases. Including
the 52 already captured H1570/H1573 exact preimages gives 114 observations over
113 external operands, with 68 failing mode rows over 67 external operands
(54 FCOS, fourteen FSIN). All 114 have one exact forced carry endpoint. These
are lower bounds from named sources, not a complete repository census; modes
that were not observed are not filled in.

The H1575 bank plus these eleven rows has 67 observations. Baseline is 29/67;
disabling equality is 25/67; disabling hard-3x merge is 34/67; disabling all
five listed rules is 30/67. These are adversarial-bank results, not estimates
of general-input accuracy. No tested fixed program is exact.

## Reproduction and integrity

Source `src/fsincos_skylake.c` remains SHA-256
`8fe40b8c852918f9cbe57a91b678861aa5e847f6c07106db1a18175a22314f39`.
All analysis models have R84 disabled. The prior R84 causal correction and all
SAT/UNSAT/UNKNOWN artifacts remain unchanged. R96 remains empirical/incomplete;
R1382, QX, Q and rejected pair/tree candidates remain default-off.

- H1577 bank: `tmp/ledger33/current/h1577_equality_bank/bank.json`, SHA-256
  `f4d4767e5ab88015598868f1393a163e57c3f8b934b8cc8ab4d8b9cadb30cc40`.
- H1579 bank: `tmp/ledger33/current/h1579_equality_bank/bank.json`, SHA-256
  `db6e5a24a3fc653ee904982ca697211a2b2340eced01426d6280fb534b06c489`.
- H1580 freeze: `transfer-tests/h1580/FREEZE.json`, SHA-256
  `0f3f9fbf68df7d11640d3505ae9e89a2f04d65dbb534064efd4a352631d0d613`.
- H1580 opened sidecar: `transfer-tests/h1580/OPENED.json`, SHA-256
  `3c59e0d0407049acd996d6f2bc4b81315396f74383a8ad04738165015ebe6822`.
- H1581 score: `tmp/ledger33/current/h1581_equality_off_branch_score.tsv`, SHA-256
  `39191eb70a6b5f81783693673e747e8e12962154553ee9f586192897d1aa3c38`.
- H1581 report: `tmp/ledger33/current/h1581_equality_off_branch_report.json`, SHA-256
  `7a43d682d2ea9b20bc2e86f091a5eb891e92db8e1c2b909f8deb40d55d1d235a`.
- H1582 report: `tmp/ledger33/current/h1582_equality_frontier_reconciliation.json`, SHA-256
  `fdf3db3fc44584c46cf05f5be8561e43d80510c0219548f0e3707c8376bb0795`.

The source files are `experiments/h1576_equality_plateau_lattice.c`,
`h1577_equality_adversarial_bank.py`, `h1578_stream_equality_endpoints.c`,
`h1579_stream_equality_bank.py`, `h1580_freeze_equality_off_branch.py`,
`h1581_score_equality_off_branch.py`, and
`h1582_equality_frontier_reconciliation.py`. Their report/freeze records include
source, model, raw-data and dependency hashes. H1577/H1579 are historical
software-only bank records: their selected candidates were subsequently
opened by H1580, not fresh candidates for another campaign.

Replay H1581 without `--mark-opened`, writing a new output prefix. Replay
H1582 with the H1568 baseline/carry0/carry1/nomerge models and the seven H1575
ablation models; use a new output path. Both reports and the H1581 score
reproduce byte-for-byte. Python syntax, fresh C builds, generator selftest,
normal build and model selftest pass.

Next work must explain both this merge-independent equality surface and the
older hard-3x failures, with independent falsification. A new fitted decision
boundary would not establish a general law. Exact enabled-branch construction
or absolute control/datapath recovery remain separate open directions. No
experimental result here is promoted into the academic paper.
