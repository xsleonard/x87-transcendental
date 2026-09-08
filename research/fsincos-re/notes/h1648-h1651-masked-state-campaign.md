# H1648–H1651: fresh masked-state challenge

2026-09-04 local date (capture records use UTC). The unchanged fixed numerical
candidate and H1645's predeclared known-state predictions pass all 16,128 fresh
standalone FSIN/FCOS tuples. A separate parser, rational/integer numerical
implementation and status algebra reproduce the result. This is finite
prospective evidence, not full-state or all-input silicon closure. No production
source/default, arithmetic candidate, H1645 model, paper or PDF was changed.

H1649 is **OPENED_ONCE** locally and on the Xeon. Never execute its hardware
tuples again. The immutable proposal and freeze retain their historical
SOFTWARE_ONLY_NOT_FROZEN / FROZEN_UNOPENED states; `OPENED.json` is the current
campaign state. Do not rewrite those earlier artifacts to update their status.

## What was frozen and executed

H1648 creates 672 unique external operands from 96 distinct significands,
covering both signs of 14 kinds: true denormal, pseudo-denormal, its exactly
equal normal encoding, quiet/signaling NaN, unnormal, pseudo-NaN, tiny bypass,
tiny non-bypass, polynomial, table, reduced, out-of-range and empty-stack.
Each kind has 48 operands. Zero and infinity are NOT in this campaign.

There are 24 prestate profiles: all 16 combinations of C0/C1/C2/C3 with clear
exception flags, plus eight all-condition-bits-set profiles with prior flags
01/02/04/08/10/20/41/7f. Stack depths 1 through 8 are covered. Each operand
receives only one prestate and both instructions, four RC modes and PC24/53/64:
672 × 2 × 4 × 3 = 16,128 tuples. Even the narrower instruction/RC/PC/operand
keys are unique; new state metadata was NOT used to permit old tuple recaptures.

Before freezing, H1649 replays all predictions, pins the compiled capture and
its disassembly, and searches compressed public and private history. It finds
zero public and zero private prior-visible significand collisions. The local
private audit examines 26 files; no private identities, contents or hashes
are published or copied remotely. Only the declared H1648 software proposal
directory and the new campaign directory are excluded from public history.
The conservative prior-visible-significand policy is unchanged.

The H1646 harness was compiled with GCC 12.2.0, O2, C11, Wall/Wextra/Werror on
the authorized Skylake Xeon `45.32.204.118`, GenuineIntel family 6/model 85/
stepping 4. Its restore/snapshot/prestate-check path and mutually exclusive
FSIN/FCOS execution branches were inspected in the target disassembly.
It verifies full requested CW/SW/tag/raw ST0 before the tested instruction.
An atomic `hardware-output` directory guard consumes even a partial run.
All 16,128 rows completed once, with no warmup, timing pass or hardware rerun.
The isolated remote directory is `/root/fsincos-h1649-masked-state`.
The i7 remains `142.132.217.24`; no i7 capture was made in this campaign.
No unrelated remote service was touched.

## Prospective result and independent check

The frozen H1650 scorer passes every predicted output, known status bit,
unchanged control word, TOP/tag transition and deeper-register relation.
Every recorded prestate also equals the requested prestate. Deeper R1–R7
raw bytes are preserved, including empty-tag slots. The 1,152 empty-stack
cases return masked indefinite, set IE/SF and occupy the original ST0 slot.
These are actual observations, not merely a software empty-stack simulation.

All 1,152 pseudo-denormal/normal equal-value pairs have identical output;
both sides' predicted C1 checks pass. Their new flag masks differ by DE=02,
and the observed final flags differ by 02 unless DE was already sticky.
This tests an encoding distinction with identical numerical value, not an
error-boundary selector. All 5,376 PC groups agree in output, full recorded SW
and abridged tag; this does not prove universal PC independence.

H1651 does not import the H1650 parser or H1645 status implementation. It
independently parses all 33 fields per row, reconstructs the before state,
checks sentinels/deeper slots and recomputes exact numerical results and
class-based exception flags. Four pinned C builds agree on 64,512 software
row evaluations. Of these, 59,904 are nonempty hardware-output comparisons;
empty-stack handling belongs to the state model, not the numerical point API.
All 16,128 independent raw/output/known-state checks pass.

## Newly observed condition-bit rule — retrospective only

Previously unknown bits were frozen as explicit clear/set/preserve/invert
discriminators, not as successful predictions. Each kind/instruction group
contains 576 trials and both possible initial bit values. The unique survivors
among those four alternatives are:

| Bit and tested domain | Surviving behavior |
| --- | --- |
| C0 and C3, every tested kind and both instructions | Preserve |
| C2, empty-stack/unnormal/pseudo-NaN/quiet-NaN/signaling-NaN | Clear |
| C1, range rejection | Clear |

The compact retrospective full-status candidate is:

```text
SW_after = H1645.status_bits | (SW_before & 0x4100)
```

Here the previously unknown exceptional C2 and range C1 are filled with zero;
ordinary C1 and range C2 still come from the existing outcome logic. This is a
condition-bit write-mask rule, with no operand lookup or fitted arithmetic
boundary. It matches all 16,128 full observed status words in H1651. It has
NOT been installed into H1645 or the production emulator, and this post-hoc
agreement is NOT a fresh validation of the rule. A separate fresh holdout must
freeze the full-status rule before observing hardware. Zero/infinity and
arbitrary untested state combinations are not silently included in its evidence.

## Verification and continuation

H1648's bank, H1650's raw score and H1651's independent report/recomputation
reproduce byte-for-byte in software-only replay. No freezer or hardware runner
is rerun. Syntax, runner syntax, build, both emulator selftests, diff/whitespace
and frozen artifact checks pass. The completed OPENED_ONCE sidecar is copied
to the isolated remote directory after verifying that it was absent.

The documented incumbent frontier remains direct 50 rows/48 residuals and
external 81 rows/79 operands. This campaign is not a new complete incumbent
census. No new fixed-candidate miss is found. R96 remains empirical/incomplete;
speculative gates remain off and R84 remains off in numerical comparisons.
The canonical source hash remains 0339a7d6…26f2b.

Next: freeze a fresh full-condition-bit holdout that challenges the newly
observed write mask, and develop the distinct unmasked/pending-state observable.
Reconcile exact retained provenance for remaining center/zero/infinity cases
without repeating tuples or weakening freshness. Unmasked exceptions, pending/
busy state, reserved controls and all-input silicon equivalence remain open.
The full goal is active/unachieved. Research stays in handoff/experiment notes;
the paper is not an ongoing research log.

## Verification anchors

Paths below are relative to `fsincos-re`; all digests are SHA256.

| Artifact | Digest |
| --- | --- |
| `tmp/ledger33/current/h1648_masked_state_proposals/bank.json` | `370808966ce27c4c4f94fda177cddbc7c9c6a888c50d50d3e63b44a552240755` |
| `transfer-tests/h1649/FREEZE.json` | `cd257a2353b8dd90a7ba06026ed715554454dbeac7462d42b46aa46f8383ec33` |
| `transfer-tests/h1649/manifest.json` | `00ba74c08d8f4154cfdc74e0fdd0bd876dca2b69282e6656c23d5a3f9b1c19ee` |
| `transfer-tests/h1649/hardware-output/state-output.txt` | `49ae75da9a8589672b5547fa82c795e10310f946199e1299317a7ab73fb89820` |
| `tmp/ledger33/current/h1649_capture_build/x87_masked_transition_capture` | `bd00b7ca1cf30a767ccdf7984929872188b251c3a7ab6823c3f5933f4642dbb6` |
| `tmp/ledger33/current/h1649_capture_build/capture.disassembly.txt` | `b1bdd90f33b847f4596909e7584d17dc0480bd0867134ae8a6e4a1240c964641` |
| `tmp/ledger33/current/h1650_score_masked_state/report.json` | `6373f96f8e62d7d2ef32a784800f754109081ac60aabe111661ca0babb202a28` |
| `tmp/ledger33/current/h1651_independent_masked_state/report.json` | `d042ca52458071f4b91291227cb8945b14df0254f6e2ba5726e9a53422ef8c9c` |
| `experiments/h1648_masked_state_proposals.py` | `11db0d315529ded56f2ed7aa714316c49ad7634ccd5422f97c764c38edb13724` |
| `experiments/h1649_freeze_masked_state.py` | `496002b3db56886ccd5391916c5231a4d092c7de3c94022d6715a99a494e7f35` |
| `experiments/h1649_run_capture.sh` | `a7938662f36740ccffe3d3f0264b211b7459f2c647e453c84a98e946e795e2db` |
| `experiments/h1650_score_masked_state.py` | `a675dadd1759373a125467453298fa5cfdd21831c0b277df310b6b22220357c7` |
| `experiments/h1651_independent_masked_state.py` | `2a6a657df1a18f50ded98fc5f097b994f060774ed500090ec1dcf83c8b14f596` |
