# H1583–H1589: the equality predictor fails on both branches

**Seven fresh misses in fifteen one-shot observations. R1263 is not a general
equality law.** Its enabled b1 branch now has a fresh false positive, its
disabled b1 branch has four further false negatives, and its disabled b2
branch has two false negatives. No new selector was fitted or promoted.
The emulator source/defaults and academic paper/PDF are unchanged.

## Exact construction, with explicit scope

H1583 generalizes H1576's comparator window. Let `h = rsh`, `B = 2^(h-16)`,
and write the right-product discard as `R = v*B + u`, `0 <= u < B`.
The comparison integers divided by B are

```text
unmerged: 3v + floor(2u/B)
merged:   3v + floor(3u/B).
```

For b1 equality the target is 65536, so `v=21845`. The union of the two
equality windows is `ceil(B/3) <= u < B`; their intersection, used by H1576,
is only `B/2 <= u < ceil(2B/3)`. For b2 equality the target is 131072 and
`v=43690`: only merged arithmetic can equal the threshold, at
`ceil(2B/3) <= u < B`. The unmerged expression cannot supply the needed
remainder two. This is integer algebra, not a fitted threshold.

H1583 enumerates all RN64 positive-Horner proxy coefficient plateaus within a
specified number of plateaus on either side of four old R1263 controls:
de4/e740 for b1 and f9e/fcc for b2. A modular floor-sum construction finds
fourth-product values in the equality windows. Exact integer inversions
recover square and external operand preimages at s4=67. The known controls
are useful constructor checks, not fresh hardware candidates.

The constructor selftest compares modular counts/first hits with 400 bounded
brute-force cases, checks both exact-window endpoints, and recovers all four
old external controls. Every emitted row is also checked independently with
Python integer arithmetic. The construction is exhaustive over its specified
proxy plateaus and modular windows, not over the global input domain, all
rounding schedules, or all equality failures.

H1584's radius-1024 run visits 8,196 plateaus and emits 13,314 exact proxy
preimages. Only the four old controls separate strict/inclusive endpoints.
At radius 8,192, it visits 65,540 plateaus and emits 106,095 preimages, adding
one new b2 off-branch separator. Independent constant-tap binaries check every
row in RN/RD/RU. No candidate is rejected in these two smaller runs.

H1585's streaming two-tap evaluator is checked against that entire 106,095-row
independent replay. H1586 then visits 524,292 plateaus at radius 65,536,
emitting 848,518 exact proxy preimages; the complete raw stream is preserved
in gzip. Thirty mode rows are endpoint-visible. Seven fail the actual current
model's equality check and are excluded, not silently accepted as proxy
matches. The remaining 23 operands have exact current equality, matching
positive-factor values, independently reconstructed P5 gate bits, and exact
baseline/strict/inclusive endpoint replay. They include four known controls
and nineteen repository-fresh candidates before the private audit.

Actual candidates: twelve b1/gate0, four b1/gate1 (two old), five b2/gate0,
and two b2/gate1 (both old). Thus this search supplies fresh b1 enabled-branch
coverage but no fresh b2 enabled-branch coverage. The absent case is not
declared impossible or unreachable.

## Locked capture and results

H1587 rejects the four old significands, checks all candidates against the
local private 26-file supplemental ledger, and selects up to eight fresh
operands per `(tap,gate)` cell in operand order. One separating mode per
operand is selected in RN/RD/RU priority order. This freezes fifteen tuples:
eight b1/gate0, two b1/gate1, five b2/gate0. Four unselected b1/gate0
candidates remain software-only and were not captured or frozen.

Freshness was rechecked immediately before execution. The exact kit ran once
on the user-authorized Skylake Xeon `45.32.204.118`, after a no-prior-path
check and capture source/binary, manifest, runner, input and checksum-file
hash verification. No private data was copied. H1587 is OPENED_ONCE with
zero repeats. Its raw values, status words and host metadata are preserved.
Never rerun H1587, including any selected mode on another campaign.

H1588's positional/hash-verified score is:

| Captured cell | Rows | Baseline exact | Baseline misses |
| --- | ---: | ---: | ---: |
| b1 / gate 0 | 8 | 4 | 4 |
| b1 / gate 1 | 2 | 1 | 1 |
| b2 / gate 0 | 5 | 3 | 2 |
| Total | 15 | 8 | 7 |

Every output equals one of the predeclared strict/inclusive endpoints.
The enabled-branch false positive is RN `3ffc:de3ffffc7a17c3dd`: baseline
and strict predict `3ffe:f9fe744bc50c3827`, but hardware gives inclusive
`3ffe:f9fe744bc50c3828`. The other fresh gate1 input,
RD `3ffc:e7400001dd7c7276`, does require strict. Therefore neither retaining
nor universally disabling that branch is exact. The six other new misses
require strict when the current gate requests inclusive.

## Exact collision result, not another fitted function

H1589 independently replays the arithmetic and reconstructs the gate bits.
It finds two opposite-label collision groups on the full listed profile

```text
(rounding mode, tap, s4, rsh, theta, low3, arithmetic branch,
 held level-2 carry, final kill).
```

One pair is especially direct: RN `3ffc:f9dffffdf814cc29` and
RN `3ffc:f9dfffffa971b4a5` both have b2, s4=67, rsh=64, theta=0, low3=1,
the tie branch, and `(held,kill)=(0,0)`. The first requires inclusive, the
second strict. Both belong to the f9e coefficient neighborhood. The other
pair is RD `3ffc:de3ffffc73d9080b` versus RD `3ffc:e73ffffd2c52df71`, with
b1, s4=67, rsh=63, theta=-1, low3=5, the band branch, and `(0,0)`; these
also require inclusive versus strict.

Identical function inputs cannot map to opposite output bits. Consequently
no deterministic function of precisely these profile fields can select the
correct endpoint on this bank. This excludes any replacement Boolean gate
over the two R1263 bits, even conditioned on all the listed fields. It does
not exclude a full-input algorithm, another datapath observable, or a state
machine supplied with additional information. No timing or physical causation
claim follows from an endpoint intervention alone.

R1263 must no longer be used as an established physical-gate/orientation
anchor. H1531/H1564's measured failures of particular composed programs and
the abstract-tree automorphism proof remain valid; the additional inference
that the historical R1263 consumer itself is a recovered universal silicon
law is not supported. Pair A/B remain independently hardware-falsified. This
result does not resurrect those selectors or negate an abstract arithmetic
identity.

## Current frontier and checks

All fifteen new observations equal exactly one forced final-R59-carry
endpoint. The false positive requires carry 0, and the six false negatives
carry 1. The directly observed bank now has 77 rows over 76 operands,
including **45 failing mode/residual rows over 44 residual operands**.
Adding the existing 52 reduction aliases gives 129 observations over 128
external operands, including 75 failing rows over 74 operands (61 FCOS,
fourteen FSIN). All 129 have one exact forced carry. This is a lower bound
from named evidence, not a full repository census or a claim about unobserved
modes. New counts do not double-count aliases as independent residuals.

Including the five old defining controls gives an 82-row fixed-ablation bank:
baseline 37 exact/45 misses; no equality 33/49; no hard-3x merge 42/40;
all five H1575 rules disabled 38/44. No fixed program is exact. These are
adversarial-bank counts, not general-input accuracy estimates.

H1588's score/report and H1589's report replay byte-for-byte without hardware.
Python syntax, fresh C builds, generator selftest, normal build and model
selftest pass. Source SHA-256 remains
`8fe40b8c852918f9cbe57a91b678861aa5e847f6c07106db1a18175a22314f39`.
R84 is disabled for causal comparisons; R96 remains empirical/incomplete;
R1382/QX/Q and rejected pair/tree selectors remain default-off. All historical
SAT/UNSAT/UNKNOWN artifacts remain unchanged.

Artifacts (all paths relative to fsincos-re):

- `experiments/h1583_equality_control_plateaus.c` and
  `experiments/h1584_equality_control_bank.py`; the radius-1024 bank SHA-256 is
  `6d8641851a3aee84b1897efe684259e90fa2727fcf54a879443672f81f9e3204`,
  and radius-8192 bank is
  `02fd567a46cdd9a472adeea62ea5347ea85fd7f62cbc54524bf3201b6522ac69`.
- `experiments/h1585_stream_both_equality_taps.c` and
  `experiments/h1586_stream_control_plateaus.py`; bank at
  `tmp/ledger33/current/h1586_stream_control_plateaus/bank.json`, SHA-256
  `386db4b2d903aa0f13f70ea8cfefd8a1ddd0a601d9c215b3942600c60af5a75b`.
- `experiments/h1587_freeze_both_equality_taps.py`; freeze
  `transfer-tests/h1587/FREEZE.json`, SHA-256
  `519adea2c37b79a6ba4ebf562bfb4db3fb99ffc1c51609f662e6d35289a29a27`;
  OPENED sidecar SHA-256
  `effe9d43bc8042a726a8ed703fe3063caf7d3e9c85ff572588689d9b1edfcdbe`.
- `experiments/h1588_score_both_equality_taps.py`; score TSV SHA-256
  `2a8074be81794ceccd140c68176d680a3c10427dfab53f26d22430406d5e557e`;
  report JSON SHA-256
  `c336fa0310f710571b24fb2bcb1b054f6d68646bf0b256ee0c9bfb0be3389b6d`.
- `experiments/h1589_equality_gate_collision_audit.py`; report at
  `tmp/ledger33/current/h1589_equality_gate_collision_audit.json`, SHA-256
  `ab9b655b9a09f9d8bc434ccbc8c1e4ea85446bd0bae93aeee17af015eb4c273c`.

Each bank/report records source, model and raw-evidence hashes. Software bank
records remain immutable; selected tuples were subsequently opened by H1587.
Do not mistake their historical SOFTWARE_ONLY state for current freshness.
The strongest next work is recovering additional justified control/datapath
information. Any new construction must explain both opposite-label pairs;
recombining the same gate bits cannot do so.
