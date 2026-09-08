# H1556--H1558 Pentium Pro public representation and near-decoder

Date: 2026-09-04

Status: **exact CPUID-0x619 update/CRBUS representation map and strong
structural near-decoder; no authoritative logical decoder or R59 selector.**

## Exact public representation

The public `ruikruik/utools` source at commit
`ab6aa24ed91de1c048313c10cb7546ea3397b827` contains a CPUID-`0x619`
transform from the CRBUS MSROM readout to the Pentium Pro update
representation. H1556 reconstructs its inverse independently and proves it is
a bijection over exactly 216 bits, the three 72-bit uops in one patch group.

Connected bits per CRBUS dword are `31,31,30,31,31,31,31,0`; connected bits
per update dword are `31,31,31,30,31,31,31,0`. The public converter compiled
from the pinned source agrees exactly with the independent replay on all 21
`0x619` groups. Every disconnected update bit is zero.

Applying the public later-P6 lower-72-bit decoder literally still fails its
calibrated thresholds. Exhausting 322,560 dword/orientation transforms finds
no threshold-exact candidate, whether applied to corrected update groups or
to the exact `0x619` CRBUS representation. This is a bounded negative, not a
proof that the old logical format is unavailable.

## H1557 near-decoder

One configuration is a conspicuous structural outlier:

```text
candidate_position_to_original_dword = [0,4,7,1,6,2,3,5]
logical_orientation                  = published_core
within_dword_transform               = reverse_each_byte
```

On the full `0x619` body it yields 52/63 opcodes recognized by the current
later-P6 catalogue, 63/63 zero flow fields, 63/63 zero U1 bits, and 54/63 zero
U2 fields. It is the only candidate with the joint vector `(52,63,63,54)`.
The eleven catalogue misses are `000` (three), `009` (two), `020`, `040`
(two), `443`, `640`, and `831`. A catalogue miss is not a proof of a bad old-
format decode; direct unknown opcodes are explicitly supported by the public
assembler documentation.

H1558 applies that exact configuration to the other corrected bodies, while
marking the CPUID-`0x619` CRBUS transform as a hypothesis outside `0x619`.
The identical `0x612`/`0x616`/`0x617` body yields 29/63 recognized opcodes,
60/63 zero flow, 63/63 zero U1, and 31/63 zero U2. `0x611` yields 28/63,
56/63, 63/63, and 31/63. This transfer is visibly structured but is not an
authoritative old-format decoder.

## Boundary

H1557/H1558 do not provide a paired known Pentium Pro logical/physical
fixture. Therefore they cannot prove that every recovered bit has the correct
logical meaning, distinguish legitimate old opcodes from residual
misalignment, or identify an absolute ROM state used by FSINCOS. No emulator
behavior is changed.

Primary sources:

- [ruikruik/utools at the pinned commit](https://github.com/ruikruik/utools/tree/ab6aa24ed91de1c048313c10cb7546ea3397b827).

Artifacts:

- `experiments/h1556_ppro_correct_layout_mapping_audit.py` SHA-256
  `96d171c1389fcd95887b7b77b18c1007a07928f754c4f4241bd0e18c193dce6c`;
- `tmp/ledger33/current/h1556_ppro_correct_layout_mapping_audit.json`
  SHA-256
  `65fbbf326f7a11f4b748b97b05b137091ab64a12beb2fe5514b2cdb35d912cdc`;
- `experiments/h1557_ppro_near_decoder.py` SHA-256
  `5e8f05f3eff2ecd34425cc4aa34e9f5f3e4832570ae4ba2493dfdfe49ce99ed0`;
- `tmp/ledger33/current/h1557_ppro_near_decoder.json` SHA-256
  `5c1242f83e98f841d7544bf1a76bd31ceb7c91efbfba535ff6b4bf24b7b23f8a`;
- `experiments/h1558_ppro_near_decoder_transfer.py` SHA-256
  `a442539c4ac534f23b0b29b872df7ecf68775bafaf740ff3cc63a058b6b72ebe`;
- `tmp/ledger33/current/h1558_ppro_near_decoder_transfer.json` SHA-256
  `f1a9549d35ab6c80bbca24df8f92c206cf9caf924d38120572d41b5dc9876458`.

No update was loaded, no hardware or x87 instruction ran, no private ledger or
capture label was opened, and no academic paper/PDF changed. H1488 remains
`FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the authoritative
frontier remains 11 rows over ten operands.
