# H1492: Pentium Pro separate-body-key audit

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: exact positive controls and exact later-stepping UNSAT wall within the
public FPROM-key cipher family; no logical decode, selector, hardware run,
emulator change, or paper/PDF change.

## Question

H1467's integrity-checked physical plaintext has a sharp split.  In the
`0x611` and `0x612` bodies, bit 31 is zero in every dword of the first eighteen
eight-dword MSRAM groups.  Their final groups contain only two and one set
bit-31 positions, respectively.  The recovered `0x617` and `0x619` bodies
instead have 73 and 64 set positions in those first 144 dwords.

That does not by itself make either recovery wrong: the public later-P6
descrambler does not consume dword bit 31, and old steppings can have different
physical metadata or formats.  H1492 tests the narrower alternative that the
later bodies use a separate ordinary patch-cipher key selected from the same
public FPROM.

## Exact solve

For each of the 208 distinct 32-bit values in the public 256-entry FPROM,
H1492 symbolically propagates all 32 IV basis vectors through physical words
14 through 167 under the public 37-clock block transform.  It first imposes
144 exact equations requiring bit 31 to be zero in words 14 through 157.

The MSRAM integrity check is included in the same solve rather than tested by
sampling a large affine IV space.  For each possible eight-bit FPROM index,
the solver conjoins:

```text
low8(state after physical word 166) = index
plaintext at physical word 167 = FPROM[index]
```

This adds eight state equations and 32 plaintext equations.  Gaussian
elimination therefore covers every one of the `208 * 2^32` key/IV pairs
implicitly.  Every final affine solution is replayed through the scalar
cipher as an independent implementation check.

## Results

| Signature | Prefix-SAT keys | Prefix ranks | Integrity spaces | Integrity IVs | Result |
|---:|---:|---|---:|---:|---|
| `0x611` | 89 | 1 | 28 | 35 | SAT |
| `0x612` | 89 | 1 | 20 | 35 | SAT |
| `0x616` | 1 | 31 | 0 | 0 | UNSAT |
| `0x617` | 1 | 32 | 0 | 0 | UNSAT |
| `0x619` | 1 | 31 | 0 | 0 | UNSAT |

The positive controls are exact at the independently recovered H1467 control
keys:

- `0x611`, key `F5349300`: H1492 recovers exactly IV `D0A66904`;
- `0x612`, key `D8000000`: H1492 recovers exactly the four H1467 IVs
  `18126A68`, `3D473F3D`, `52B8C0C2`, and `77ED9597`.

The structural and integrity constraints are not globally key-identifying on
those two patches; other FPROM key/IV spaces also satisfy them.  Their role is
to prove that the symbolic equations and integrity split reproduce the known
solutions, not to replace H1467's control-address key proof.

For each of `0x616`, `0x617`, and `0x619`, exactly one FPROM key admits the
144-bit prefix constraint.  In every case it is the H1467 control key:
`55555555`, `68000000`, and `0037417F`.  Once the encrypted MSRAM integrity
relation is conjoined, all three are UNSAT.  No other FPROM value even reaches
that final test.

## Interpretation

The proposed second key from the ordinary public FPROM family is therefore
not the explanation for the later bit-31 surface.  This also prevents a false
correction to H1467: its `0x617` and `0x619` bodies remain exact plaintext
under the stated continuous-stream cipher and all sixteen integrity checks.
H1492 supplies no evidence that they should be replaced by zero-bit-31 bodies.

The remaining explanations are narrower but unresolved: stepping-specific
physical metadata or body format, a key outside the public FPROM value family,
or another transform before the body stream.  Bit 31 is not promoted to a
universal Pentium Pro invariant.  The old physical-to-logical mapping and
absolute base-ROM/control state remain unknown, and no R59 selector follows
from this result.

## Artifacts

- `experiments/h1492_ppro_body_key_recovery.py`, SHA-256
  `6140ff4061277691b81364d71c6793394bb97d9456e0f815cf5db97b60b46a85`;
- `tmp/ledger33/current/h1492_ppro_body_key_recovery.json`, SHA-256
  `3955031b7b0d8b707139c12b483bd906aaf81f86ec96a3786925d8ba49eb6cfb`;
- public FPROM source, SHA-256
  `758ce01ac9a4cbd37c3d847186f1f287a50d1818eb7b213221cc464a43681bb5`;
- H1467 report dependency, SHA-256
  `63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74`.

The five packed public patch hashes are recorded in the JSON and match H1467.
No third-party update or FPROM source is copied into the repository.  No
update was loaded, no x87 instruction or capture ran, no hardware label or
private ledger was opened, and H1488 remains `FROZEN_UNOPENED`.  The academic
paper/PDF and emulator defaults are unchanged.  R96 remains empirical and
incomplete; the ledger-free frontier remains eleven mode rows over ten
operands.
