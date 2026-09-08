# H1460 exact Pentium Pro 0x612 patch recovery

> **H1555 correction (2026-09-04):** the public Pentium Pro format is 21
> seven-dword groups plus one spare dword and 16 controls, not this note's
> 19-eight-dword/15-control partition. This recovery is superseded as a
> physical-format result; retain it only as an internally exact analysis of the
> old mispartition. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: the old update's physical plaintext and controls are recovered as an
exact four-member IV equivalence class; the FSINCOS result is negative; no
selector or emulator change.

## Result

H1460 recovers the functional body of a checksum-valid 2 KiB Intel update for
processor signature `0x612`, revision `0xC6`, dated `0x12101996`.  The input
SHA-256 is
`b411ab12fca67bef7103ea75c07adc8dbb53b4a966bb619ca32012b26eac7db1`.
It reproduces byte-for-byte from the 512 hexadecimal dwords in the public
[Coreboot archive at commit 796af17](https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/microcode-99-B_c6_612.h)
when packed little-endian.
This old Pentium Pro layout is not the later public 21-group/16-control P6
layout:

- header words 0--11 and seed fields 12--13;
- one continuous encrypted stream at physical words 14--227;
- 19 MSRAM groups at words 14--165;
- an additional word at 166 and the MSRAM integrity word at 167; and
- 15 four-dword control records at words 168--227.

The shared irrelevant suffix begins at file byte 912, immediately after the
216-dword functional body.  Word 183 is part of the encrypted stream; it is
not a gap.

## Exact key and IV recovery

For a zero plaintext control mask, the public 37-clock patch cipher obeys

```text
BF(cipher_before_address XOR address)
    = cipher_address XOR cipher_mask.
```

H1460 enumerates all 512 architectural control addresses for every one of the
208 distinct values in the public 256-entry FPROM.  `D8000000` is the unique
winner: it yields one 9-bit address in 12 of 15 records.  Every other FPROM
value scores zero.  The key appears at FPROM indices CA and CC.  Once
decrypted, the other three records have nonzero masks, exactly explaining
their exclusion from the zero-mask score.

Each of the twelve zero-mask controls independently gives the same exact
GF(2) IV preimage:

```text
particular: 18126A68
nullspace:  25555555, 4AAAAAAA
IVs:        18126A68, 3D473F3D, 52B8C0C2, 77ED9597
```

All four IVs pass every later check.  They produce only two possible values
for the first plaintext dword, `501DA73D` and `3FE258C2`; physical words
15--227 are identical.  This is an exact equivalence class, not a claim that
one IV representative has been uniquely identified.

## Integrity and controls

The plaintext at physical word 166 is `FFFF441E`.  The state before the MSRAM
integrity word selects FPROM index E2, and the decrypted word is exactly
FPROM[E2] `D3728CBD`.  All fifteen control integrity words likewise equal
their independently selected FPROM values: 16/16 encrypted integrity checks
pass for every IV representative.

The decoded controls are:

| Register | Mask | Value | ICV |
|---:|---:|---:|---:|
| `1B1` | `00000000` | `00000004` | `0C863F24` |
| `1B8` | `00000000` | `30543FD9` | `30000000` |
| `1B9` | `00000000` | `367C3FEE` | `E0E9123E` |
| `1BA` | `00000000` | `33EC3FB0` | `00000000` |
| `1BB` | `00000000` | `1FA03FE5` | `72401864` |
| `112` | `00000000` | `3668366C` | `00000000` |
| `113` | `00000000` | `0BAD0BAD` | `00000000` |
| `116` | `00000001` | `00000112` | `0000000A` |
| `117` | `000000C6` | `00000000` | `00577251` |
| `156` | `7FFFFFFF` | `80000000` | `F5349300` |
| `1FF` | `00000000` | `0761A957` | `4E62105D` |
| `1FF` | `00000000` | `9D5DCBB3` | `00000000` |
| `1FF` | `00000000` | `0E75B369` | `E0BF85DE` |
| `1FF` | `00000000` | `ADF75FB9` | `44443E35` |
| `1FF` | `00000000` | `6BF36359` | `B994E239` |

Registers 1B8--1BB encode four match hooks:

```text
3054 -> 3FD9
367C -> 3FEE
33EC -> 3FB0
1FA0 -> 3FE5
```

Destination `3FB0` also confirms the 19-group patch window
is based at `3FAC`, with four-address group spacing through `3FF6`; it is not
a 19-group window top-aligned at `3FB4`.

## Remaining decode boundary

The report preserves all 19 physical MSRAM groups.  They are not converted to
logical 72-bit Pentium Pro uops.  The public Pentium-II permutation produces
noncredible output on this payload and is not evidence for the older format;
no public Pentium Pro physical permutation was available.  Consequently this
experiment establishes exact physical plaintext and exact controls, but does
not claim a logical MSRAM instruction listing.

The public update analysis adds no R59 selector and does not close the
eleven-row frontier.  The useful remaining ROM direction is recovery of the
Pentium Pro physical permutation or absolute base-ROM/control state, not
another fitted endpoint feature.

## Artifacts and discipline

Authoritative artifacts:

- `experiments/h1460_unknown_p6_padding_key.py`, SHA-256
  `67444ef02572100508f3525c26920a151cd991cf2a65dc10ea89ab6226b656d2`;
- `tmp/ledger33/current/h1460_exact_ppro_patch_recovery.json`, SHA-256
  `b3f3ce8b5c9aad9c30118c8bb8e2d7cc84ba4544765585a2341e4772f38d85ad`;
- public FPROM source SHA-256
  `758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5`.

No update was loaded, no hardware or x87 instruction was executed, no capture
label was opened, and no private capture ledger was accessed.  No selector or
emulator default changed.  The academic paper/PDF remains frozen.
