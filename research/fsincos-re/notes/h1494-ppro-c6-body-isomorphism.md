# H1494: Pentium Pro C6 body-isomorphism audit

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: exact rejection of the shared-body permutation crib; no logical
Pentium Pro decode, selector, hardware run, emulator change, or paper/PDF
change.

## Question

The `0x612` and `0x617` public updates both carry revision `0xC6`.  Their first
ten decrypted architectural controls have identical address, mask, and value
triplets, including the same four match hooks, and their nineteen recovered
MSRAM groups cover the same candidate addresses from `0x3FAC` through
`0x3FF6`.  Because H1467 proves both physical plaintexts with 16/16 integrity
checks, this looks like a possible crib for the missing Pentium Pro mapping:
perhaps the two bodies are the same address-aligned bit matrix under a
stepping-specific physical-channel permutation.

H1494 tests that exact proposition without decoding an opcode or fitting a
field boundary.

## Exact invariant

For each physical channel `(dword, bit)`, H1494 forms its 19-bit column
signature across the address-aligned groups.  Any fixed bijection of physical
channels preserves the multiset of those signatures.  If each target channel
may additionally have an independent fixed XOR polarity, the bijection must
instead preserve the multiset obtained by canonicalizing every signature with
its 19-bit complement.

Counter intersection gives the exact maximum number of channels that can be
paired under either relation.  This covers arbitrary channel permutations;
it is not restricted to dword order, endian transformations, or lane order.

## Result

| Physical view | Plain permutation matches | Permutation + fixed per-channel XOR |
|---|---:|---:|
| All 256 channels | 0 / 256 | 1 / 256 |
| Low 31 bits of each dword | 0 / 248 | 1 / 248 |

The sole complement-canonical match pairs `0x612` channel `(dword 2, bit 20)`
with `0x617` channel `(dword 3, bit 20)`: signatures `0x706E1` and `0x0F91E`
are exact 19-bit complements.  No raw signature occurs in both bodies.

This is far short of either a 216-bit Pentium Pro uop payload or a 231-bit
physical line.  Therefore the two address-aligned bodies cannot be one
identical bit matrix under a fixed physical-channel permutation, even when
every channel may be independently inverted.

The conclusion is narrower than logical-program inequality.  The two updates
may implement related fixes using different stepping-specific programs, and a
format could change shared-field encoding or use a transformation more general
than a bitwise affine relabeling.  H1494 does not decode either body.  It proves
that shared revision and control hooks cannot be used as an identical-body crib
for recovering the old physical-to-logical permutation.

## Artifacts

- `experiments/h1494_ppro_c6_body_isomorphism.py`, SHA-256
  `6b1b65c9db7de1d7cef94b6a121b2877204c0a3fdc46935a26709c9d719117d7`;
- `tmp/ledger33/current/h1494_ppro_c6_body_isomorphism.json`, SHA-256
  `b10bc70806e13011cf200d7a5d2f7bf948ae6b9196a1fa2fe5c945c4bf7d2263`;
- H1467 report dependency, SHA-256
  `63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74`.

An independent rerun is byte-identical.  No microcode update was loaded, no
x87 instruction or capture ran, no hardware label or private ledger was
opened, and H1488 remains `FROZEN_UNOPENED`.  The academic paper/PDF and
emulator defaults are unchanged.  R96 remains empirical/incomplete; the
ledger-free frontier remains eleven mode rows over ten operands.
