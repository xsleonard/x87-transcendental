# H1490: later-P6 core permutation does not transfer to Pentium Pro

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: exact later-P6 calibration, negative old-format transfer; no logical
Pentium Pro decode, selector, emulator change, or paper/PDF change.

## Question

H1467 recovered four complete Pentium Pro update bodies as exact physical
eight-dword groups, but left their 72-bit logical micro-operations undecoded.
The public later-P6 descrambler maps each eight-dword line to three 80-bit
micro-operations.  Seventy-one positions per operation come from its main
left/right permutation, logical bit 70 uses three additional physical taps,
and logical bits 72--79 are later-generation additions.  H1490 asks whether
the 72-bit portion can be transferred to the older bodies without assuming
the eight added bits.

## Exact calibration

H1490 independently transcribes the physical extraction and logical mapping,
without importing or executing the public NumPy script.  A paired CPUID 0x652
later-P6 fixture contains 21 physical groups and the corresponding 63 logical
micro-operations.  The transcription reproduces all 63 lower-72-bit words
exactly, with zero mismatches.  Under the public opcode map, 61/63 operations
(96.8%) are recognized, all 63 have `unknown1=0`, and 54/63 have
`unknown2=0`.

This calibration also catches an important scope detail: logical bit 70 is not
part of the 213-bit main permutation.  Three physical taps outside that set
complete the 216 logical core bits.  The audit includes those taps while
excluding every logical bit from 72 through 79.

## Pentium Pro result

Applying the exact calibrated mapping to each 19-group recovered body gives:

| Signature | Recognized of 57 | Fraction | `unknown2=0` |
|---:|---:|---:|---:|
| `0x611` | 12 | 21.1% | 2 |
| `0x612` | 3 | 5.3% | 0 |
| `0x617` | 4 | 7.0% | 0 |
| `0x619` | 9 | 15.8% | 0 |

A deterministic 100,000-word random 72-bit baseline recognizes 11.3%.
Removing the final 72-bit reversal does no better: recognition ranges from
10.5% to 21.1%, and `unknown2` is nonzero on every one of the 228 candidate
operations.  By contrast, the paired later-P6 calibration has the strong
opcode and reserved-field structure above.

All fifteen available match-hook destinations inside the old three-uop patch
slots decode as unknown opcodes under the published mapping.  The remaining
`0x619` sentinel destination is outside the patch window.  Slot reordering
cannot repair the aggregate opcode or reserved-field statistics.

The exact later-P6 72-bit mapping is therefore not a credible Pentium Pro
logical permutation.  This rejects the proposed transfer; it does not prove
that the old format is undecodable under a different mapping.  In particular,
opcode recognition is bounded by the public later-P6 map and cannot establish
an impossibility result for stepping-specific old opcodes.

## Artifacts

- `experiments/h1490_ppro_core_permutation_transfer.py`, SHA-256
  `5047be2a453b3776c3ce8782c1e571b672b3288426f9fcd977fdc9f4153e5af7`;
- `tmp/ledger33/current/h1490_ppro_core_permutation_transfer.json`, SHA-256
  `df1dbfbe4e20081903f73da1abc09f19d9860ac9a0e779fb2b81184a5141e1b5`;
- later-P6 physical calibration fixture, SHA-256
  `ead0687a628371015b79505ba0d38a37df937e444db0f2ee5dbf676a065dc603`;
- paired later-P6 logical fixture, SHA-256
  `869b93c7091a8dcdb39b570d2680b0620892d575dc12615afff06f8d64bcc9d5`.

An independent rerun reproduced the JSON byte-for-byte.  No update was loaded,
no hardware or x87 capture ran, no private ledger or hardware label was
opened, and no emulator default or academic paper/PDF changed.  The
ledger-free frontier remains eleven mode rows over ten operands.
