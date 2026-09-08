# H1510: existing targeted captures cannot choose pair A or pair B

Date: 2026-09-03

Status: **1,832,550 cached architectural rows audited; zero endpoint
separators; no orientation evidence and no hardware execution.**

## Question

H1509 found no incumbent/R1382 endpoint separator in the broad 240,000-
operand dense corpus.  H1510 asks the same question of nineteen older,
targeted adversarial suites.  These suites probe terminal neighbors, scaled
tails, payload bits, tail gates, carry-save gates and bits, square tails and
bits, D7 lanes, sine-coordinate neighborhoods, and round-49 residual
neighbors.

Every named input file remains exactly count-aligned with its cached Skylake
standalone-FCOS RN/RD/RU results.  Across 610,850 input positions and three
rounding modes, H1510 evaluates the current incumbent and the default-off
R1382 build.  Only an architectural row where those builds differ can label
the hidden merge choice and expose pair A versus pair B.

## Result

| Suite group | Input positions | Modes | Architectural rows | Endpoint separators |
|---|---:|---:|---:|---:|
| H363 | 229,404 | 3 | 688,212 | 0 |
| H372--H397 | 183,810 | 3 | 551,430 | 0 |
| H285--H320 | 592 | 3 | 1,776 | 0 |
| H347 | 197,044 | 3 | 591,132 | 0 |
| **Total** | **610,850** | **3** | **1,832,550** | **0** |

The two builds are byte-identical on every audited row.  Consequently no
existing targeted row can score the exact H1487 pair functions, and the pair-
discriminator count is zero.  Combined with H1509, the audited pre-existing
corpora now cover 2,552,550 cached architectural rows without one endpoint-
visible vote.

This is not evidence that pair A and pair B are equivalent.  H1487/H1498
already prove an exact Boolean disagreement.  The result instead shows that
these historical corpora do not make that narrow internal disagreement
architecturally visible.  H1488 remains the frozen, unopened direct
orientation vote.

An independent execution reproduces the JSON byte for byte.

## Artifacts

- `experiments/h1510_existing_targeted_pair_audit.py`, SHA-256
  `401a51badf03f9bcc73cd56aa1e6fbd3b3289f986783bf7605c0284cfe708ec4`;
- `tmp/ledger33/current/h1510_existing_targeted_pair_audit.json`, SHA-256
  `c0841bcceae0a02c61871e35cd0de3fb76dae14055e33b109cf1d4c3c22fb143`.

The report records the SHA-256 of both analysis binaries and every input and
capture file.  No x87 instruction or fresh hardware capture ran, no H1488 or
private-ledger label was opened, and no emulator behavior/default, academic
paper, or PDF changed.  H1488 remains `FROZEN_UNOPENED`; R96 remains
empirical/incomplete; the authoritative frontier remains eleven mode rows
over ten operands.
