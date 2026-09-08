# H1467 Pentium Pro sibling patch recovery

> **H1555 correction (2026-09-04):** the public Pentium Pro format is 21
> seven-dword groups plus one spare dword and 16 controls, not this note's
> 19-eight-dword/15-control partition. The `0x616` boundary disappears under
> the correct public keys/layout, and `0x612`/`0x616`/`0x617` have identical
> corrected bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: four exact physical recoveries and one exact control-only boundary;
no R59 selector or emulator change.

## Result

H1460 recovered the old Pentium Pro `0x612` update without assuming a CPU
base key.  H1467 applies the same local control equations and exact GF(2)
state recovery to all five public Pentium Pro updates in the historical
corpus:

| Signature | Revision | Control key | State result | Integrity |
|---:|---:|---:|---|---:|
| `0x611` | `0xB27` | `F5349300` | unique IV `D0A66904` | 16/16 |
| `0x612` | `0xC6` | `D8000000` | four equivalent IVs | 16/16 |
| `0x616` | `0xC6` | `55555555` | two exact control states; body continuity UNSAT | 15/15 controls |
| `0x617` | `0xC6` | `68000000` | unique IV `6F4795C6` | 16/16 |
| `0x619` | `0xD2` | `0037417F` | two equivalent IVs | 16/16 |

Thus `0x611`, `0x612`, `0x617`, and `0x619` now have exact physical
plaintext for the complete functional stream.  The `0x616` result is
deliberately narrower: its complete control block is exact, but its MSRAM
body is not recovered.

## Exact key and state method

For a zero plaintext control mask, the public 37-clock P6 transform obeys

```text
BF(cipher_before_address XOR address)
    = cipher_address XOR cipher_mask.
```

For every update H1467 evaluates this equation at all 512 architectural
control addresses for every distinct value in the public 256-entry FPROM.
The winning keys and their zero-mask scores are:

- `0x611`: `F5349300`, 14 records versus runner-up 0;
- `0x612`: `D8000000`, 12 versus 0;
- `0x616`: `55555555`, 12 versus 5;
- `0x617`: `68000000`, 12 versus 0; and
- `0x619`: `0037417F`, 12 versus 0.

For the four complete recoveries, all winning local equations yield one
consistent affine state class from physical word 14.  Every representative
survives the independent MSRAM integrity word and all fifteen control
integrity words.  The `0x612` four-member class is the H1460 result.  The two
`0x619` states, `20EA4CF1` and `DF3032A4`, decrypt identical physical
plaintext; they are cipher-state equivalents rather than alternate payloads.

## The exact `0x616` boundary

The `0x616` key is not a weak ranking accident.  Its twelve local zero-mask
equations identify the correct architectural addresses, and a control-block
solve gives exactly two states before physical word 168:

```text
55F9CE10
CC605789
```

Both states decrypt the same fifteen controls.  Every encrypted control
integrity word equals its independently selected FPROM value, so the control
result passes 15/15 checks.  The first ten controls are exactly the same as
the `0x612` and `0x617` C6 controls, including these four match hooks:

```text
3054 -> 3FD9
367C -> 3FEE
33EC -> 3FB0
1FA0 -> 3FE5
```

The public `0x55555555` block transform is highly rank-deficient.  H1467
therefore tests reachability directly rather than enumerating a huge IV
class.  For each of the two validated states before word 168, the exact GF(2)
preimage from a state before physical word 14 is UNSAT.  In other words, the
single continuous-stream model that exactly recovers the other four updates
cannot generate this control block from the `0x616` body.  A format boundary,
state reset, different body key, or unmodeled stepping-specific cipher rule
is required.  The available equations do not distinguish those mechanisms,
so the MSRAM body is left unrecovered.

This also prevents an invalid shortcut.  Although `0x612`, `0x616`, and
`0x617` have the same first ten C6 control triplets, the exact `0x612` and
`0x617` MSRAM bodies differ in 151 of 152 physical dwords.  Shared controls
do not imply a shared body and cannot be used as an `0x616` plaintext crib.

## Relevance to FSINCOS

The recovered MSRAM words remain in physical order.  Applying a
generation-specific logical permutation without validation would turn source
recovery into another representation fit, so H1467 makes no logical-uop or
hidden-control claim.  No recovered control selects the unresolved R59 carry,
and no patch contains the missing absolute base-ROM state.

## Sources and artifacts

The public packed-update SHA-256 values are:

- `0x611`: `3d963b50eef0867008a1c767c514214a21426922c0b02cad0f4848e81d7732df`;
- `0x612`: `b411ab12fca67bef7103ea75c07adc8dbb53b4a966bb619ca32012b26eac7db1`;
- `0x616`: `3b8ad8d55fc1f7fffb46efa77de1dbdc498d5f21d132bedbdeb285bfcb28faaf`;
- `0x617`: `8fa7bcc2d450c2ac810648201a14ce6bcc0883840eb46975fa04ed1dfeabd678`;
  and
- `0x619`: `a513f9c3b37b98550323f7afb257cc08469b1597a0318bb65339b9fedca5921d`.

The `0x612`, `0x616`, `0x617`, and `0x619` C headers are from the public
[Coreboot archive at commit 796af17](https://chromium.googlesource.com/chromiumos/third_party/coreboot/+/796af17f18554380a49d69d7768ac18ee039d711/src/cpu/intel/model_6xx/).
The `0x611` packed update is from the public
[CPUMicrocodes corpus](https://github.com/platomav/CPUMicrocodes/tree/master/Intel).
No third-party update is copied into this repository.

Authoritative local artifacts:

- `experiments/h1467_pentium_pro_sibling_patch_recovery.py`, SHA-256
  `438ab502b647dc930a098ffdaf5b71f980216ab570126eeb7f36f7e2c41bdedd`;
- `tmp/ledger33/current/h1467_pentium_pro_sibling_patch_recovery.json`,
  SHA-256
  `63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74`;
- public FPROM source SHA-256
  `758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5`;
  and
- H1460 dependency SHA-256
  `67444ef02572100508f3525c26920a151cd991cf2a65dc10ea89ab6226b656d2`.

An independent rerun reproduced the authoritative JSON byte-for-byte
(`cmp=0`).

No update was loaded, no hardware or x87 instruction ran, no capture label was
opened, and no private capture ledger was accessed.  No selector or emulator
default changed.  The academic paper/PDF remains frozen, the ledger-free
frontier remains eleven mode rows over ten operands, and the active goal
remains open.
