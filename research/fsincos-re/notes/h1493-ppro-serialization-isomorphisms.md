# H1493: Pentium Pro simple-serialization isomorphism audit

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-03

Status: exact exhaustion of a bounded mapping family with deterministic
multiple-search controls; no credible old-format mapping, selector, hardware
run, emulator change, or paper/PDF change.

## Question

H1490 proved that the public later-P6 lower-72-bit physical-to-logical mapping
does not decode the four integrity-checked Pentium Pro bodies recovered by
H1467.  H1493 tests the next narrow possibility: perhaps the old format uses
the same core bit wiring but differs only in dword serialization, a conventional
within-dword endian transform, or the final core reversal.

This is deliberately a bounded isomorphism audit.  It is not a search over
arbitrary cross-dword bit permutations and cannot establish that every possible
Pentium Pro mapping is impossible.

## Exact search

The audit reconstructs the H1490 lower-72-bit mapping by injecting every one
of the 256 physical basis bits and recording the source coordinate of each of
the 216 logical bits.  It then exhausts:

- all `8! = 40,320` global dword permutations;
- four conventional within-dword transforms: identity, bit reversal,
  byte swap, and bit reversal within each byte;
- both published-core and no-final-reversal orientations.

That is `322,560` candidates, scored over all 76 recovered groups and all 228
candidate micro-operations from patches `0x611`, `0x612`, `0x617`, and
`0x619`.  Lane permutations need not be enumerated because every reported
field statistic is invariant under lane order.

The literal H1490 mapping is replayed as a positive implementation check.  It
reproduces the exact earlier recognized-opcode counts: 12, 3, 4, and 9 for
`0x611`, `0x612`, `0x617`, and `0x619`, respectively.

## Results

The public later-P6 fixture, scaled from 63 to 228 operations, would imply
diagnostic thresholds of 221 recognized opcodes, 225 zero flow fields, 228
zero `unknown1` fields, and 196 zero `unknown2` fields.  No candidate reaches
even one of those four thresholds.

| Diagnostic | Recovered maximum | Later-P6-rate threshold |
|---|---:|---:|
| Recognized opcode | 45 / 228 | 221 / 228 |
| Flow field zero | 29 / 228 | 225 / 228 |
| `unknown1` zero | 146 / 228 | 228 / 228 |
| `unknown2` zero | 6 / 228 | 196 / 228 |

Four independent deterministic random controls replace every low 31-bit dword
payload while preserving the recovered bit-31 value at every physical
position.  Each control undergoes the identical 322,560-candidate search.  Its
post-search recognized-opcode maxima are 44, 47, 49, and 47; the recovered
maximum of 45 is therefore inside the control range rather than evidence for
a decoder.  The controls likewise equal or exceed the recovered maxima for
the other field diagnostics, apart from one control's lower `unknown1` maximum
and one control's lower `unknown2` maximum.

Training recognition on the early `0x611/0x612` bodies peaks at 26/114, with
only 11--15/114 held out recognitions on `0x617/0x619`.  Reversing the split
peaks at 27/114 on the late bodies and transfers only 14/114 to the early
bodies.  There is no cross-stepping structure resembling the later-P6
calibration.

## Interpretation

The exact later-P6 core wiring cannot be repaired on these four old bodies by
any global dword permutation, any of the four tested endian/bit orientations,
or the final core reversal.  The best apparent opcode fit is fully explained
by the multiple-hypothesis search on bit-31-matched random data.

This result does **not** prove that all Pentium Pro mappings are impossible,
that opcode recognition alone would prove a decoder, or that the recovered
bodies are invalid.  The remaining space requires a genuinely different
cross-dword bit permutation, shared triplet fields, a stepping-specific format,
or recovery of the unreleased old-format tooling.  H1493 yields no R59 selector
or absolute base-ROM/control state.

## Artifacts

- `experiments/h1493_ppro_serialization_isomorphisms.py`, SHA-256
  `2be00896dddae1d1cb0ab101c445e68f7626042a48b48b1d79f8eabddef32010`;
- `tmp/ledger33/current/h1493_ppro_serialization_isomorphisms.json`, SHA-256
  `aae819bd1dded1780c80ceb9cb33e30dc7765d58577798226f395dd8932eb889`;
- H1467 report dependency, SHA-256
  `63d32e546726b602e0c55b87a6e89792dab2d9ad3ce8938dec123b023cb4fa74`;
- H1490 report dependency, SHA-256
  `df1dbfbe4e20081903f73da1abc09f19d9860ac9a0e779fb2b81184a5141e1b5`.

An independent rerun is byte-identical.  No microcode update was loaded, no
x87 instruction or capture ran, no hardware label or private ledger was
opened, and H1488 remains `FROZEN_UNOPENED`.  The academic paper/PDF and
emulator defaults are unchanged.  R96 remains empirical/incomplete; the
ledger-free frontier remains eleven mode rows over ten operands.
