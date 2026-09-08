# H1554 K=3 mapping transfer to sibling Pentium Pro bodies

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its held-out failure applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **exact held-out transfer failure for both H1553 feasibility mappings;
no general physical decoder or R59 selector.**

## Question

H1552/H1553 establish that three is the exact minimum number of `0x611`/
`0x612` rows that must fall outside the current 459-value public-P6 opcode
language under the bounded injective fixed-polarity direct-selection model.
That theorem does not make either SAT mapping a physical decoder. H1554 tests
the most direct generality condition: apply both mappings unchanged to the two
other H1467 bodies with exact continuous physical recovery, `0x617` and
`0x619`.

The held-out bodies were not used to select the K=3 mappings. H1554 first
replays `0x611`/`0x612` byte-for-byte against H1553, then decodes the same 12
signed channels on all 19 groups of each held-out body.

## Exact result

| mapping exception triple on training bodies | training recognized | `0x617` | `0x619` | held-out recognized |
|---|---:|---:|---:|---:|
| `611:g11, 612:g00, 612:g08` | 35 / 38 | 1 / 19 | 3 / 19 | 4 / 38 |
| `611:g11, 612:g00, 612:g15` | 35 / 38 | 3 / 19 | 2 / 19 | 5 / 38 |

The public recognized language contains 459 of 4,096 twelve-bit values. A
uniform reference would therefore yield 4.26 recognized values among 38
rows. The observed held-out counts of four and five are on that descriptive
scale; no independence or random-payload assumption is needed for the exact
transfer conclusion.

Neither mapping preserves its 35/38 training behavior on the sibling bodies.
The first has 34 held-out unrecognized rows and the second has 33. Thus neither
H1553 feasibility witness can be treated as a validated general Pentium Pro
physical decoder under the current public opcode-language test.

## Boundary

The failure does not prove whether the selected physical wiring is wrong, the
current later-P6 opcode catalogue is incomplete for Pentium Pro, the old
serialization is non-selective, or several of those are true. The precise
conclusion is unchanged-mapping non-transfer under one explicit language.
The exact minimum-three theorem remains valid for its 38-row training model,
but it is not evidence of a structural decoder.

No absolute ROM/control-state observable or R59 selector follows. No x87
instruction or hardware capture ran, no H1488 label or private ledger was
opened, and no manifest, emulator behavior/default, or academic paper/PDF
changed. H1488 remains `FROZEN_UNOPENED`, R96 remains empirical/incomplete,
and the authoritative frontier remains 11 rows over ten operands.

## Artifacts

- `experiments/h1554_transfer_k3_mappings_to_sibling_bodies.py`, SHA-256
  `b8262481ac00731ed122105c095d0a2c84dd2b5e832ea3c646873e18f4f9c7a8`;
- `tmp/ledger33/current/h1554_transfer_k3_mappings_to_sibling_bodies.json`,
  SHA-256
  `33888062d7116decf0867e3340c8717e91be6028a35d15a22223233385659a02`.
