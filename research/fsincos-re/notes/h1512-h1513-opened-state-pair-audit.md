# H1512--H1513: opened transfer/history labels cannot orient pair A/B

Date: 2026-09-03

Status: **537 already-opened state observations reconciled; 48 endpoint-visible
rows all have exact candidate pattern `0000`; zero pair discriminators and no
hardware execution.**

## Motivation

H1486 reduced the surviving selector spellings with 28 direct FCOS hardware
labels.  The later-reconciled H1400 exact-preimage transfer bank and the
H1414-corrected history/prelude campaigns were not part of that 28-label
reduction.  H1512 and H1513 therefore test whether an already-opened
nonstandard observation had silently resolved the remaining pair-A/pair-B
orientation.

## H1512: H1400 transfer bank

H1512 verifies the 124-row frozen identity manifest against the immutable raw
FXSAVE output, then scores the 100 core transfer rows under their exact
instruction, target lane, and rounding mode.  The current and default-off
R1382 builds differ on exactly two rows:

| Case | Instruction | Mode | Operand | Hardware endpoint | Pair pattern |
|---|---|---|---|---|---|
| T0039 | FCOS | RD | `4001:c2895aa22102bc95` | R1382 | `0000` |
| T0041 | FCOS | RZ | `4001:c2895aa22102bc95` | R1382 | `0000` |

This is the q=4 exact external preimage of the d0d0 reduced state.  Silicon
selects the R1382/no-merge endpoint in both modes, but all four exact H1486
spellings also select that endpoint.  The transfer bank thus validates a
common branch and supplies zero pair-A/pair-B discriminators.

The other 98 core rows are not current/R1382 endpoint separators.  No paired-
lane diagnostic is ambiguous.

## H1513: corrected history/prelude campaigns

H1513 consumes the authoritative H1414 score for 437 immutable observations:
33 H1406, 24 H1408, 133 H1410, and 247 H1412 rows.  It first verifies that all
437 observed values equal H1414's corrected hardware endpoint.

There are 46 current/R1382 endpoint-visible observations: the 23 producer or
prelude variants of direct d0d0 under RD and the same 23 under RZ.  Every row
selects the R1382 endpoint, and every exact candidate pattern is `0000`.
The remaining 391 observations are not endpoint separators.  Therefore these
campaigns also contain zero pair discriminators.

Together the two audits score 537 already-opened state observations with 48
endpoint-visible rows, all belonging to the same d0d0 common-pattern class.
They do not choose the physical pair orientation and do not replace H1488.

Both JSON reports independently reproduce byte for byte.

## Artifacts

- `experiments/h1512_opened_transfer_pair_audit.py`, SHA-256
  `0701e8d78fee8fced153a12ba27b5575d2929cf41c42e7d9c779afeedc186707`;
- `tmp/ledger33/current/h1512_opened_transfer_pair_audit.json`, SHA-256
  `4227a80f4c5d89af832bea514aaadf69c2acd5d38dfebffb04bc5ff1e002a5bc`;
- `experiments/h1513_opened_history_pair_audit.py`, SHA-256
  `d5a7fd2951a05d0e36513abed9ddca8ed5548c9b301dfae8f574753e483227b9`;
- `tmp/ledger33/current/h1513_opened_history_pair_audit.json`, SHA-256
  `67f72cd5d86e7352890c06ac95ca35cbe281258689102701affe09293edce86e`.

No x87 instruction or fresh hardware capture ran, no H1488 or private-ledger
label was opened, and no emulator behavior/default, academic paper, or PDF
changed.  H1488 remains `FROZEN_UNOPENED`; R96 remains empirical/incomplete;
the authoritative frontier remains eleven mode rows over ten operands.
