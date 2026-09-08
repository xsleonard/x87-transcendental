# H1561--H1562: Pentium Pro NOP-tail semantic crib

Status: exact exhaustion of two bounded physical-mapping families under an
explicit inferred NOP-padding crib; no authoritative Pentium Pro decoder, R59
selector, emulator change, hardware execution, or paper/PDF change.

## Stronger semantic check on H1557

The exact corrected CPUID-`0x619` update has six unique groups followed by
fifteen copies of one physical group. That repeated group contains exactly
nine one-bits. The pinned public `ruikruik/utools` Pentium Pro source fills the
unused end of `msromdumper.asm` with
`MOVE.DSZ32(CONST, CONST_0)` instructions, and its Makefile selects the
Pentium Pro assembler target for CPUID `0x612` and `0x619`.

Under the documented 72-bit Pentium Pro logical format, an omitted
destination is `SINK=1`, `MOVE.DSZ32` has opcode `0x600`, and the complete
logical word is:

```
060000000000800000
```

It contains three one-bits, so a triplet contains exactly nine. This exact
Hamming-weight match and the fifteen-group unreachable-looking suffix make a
NOP-padding identification physically strong. It is not a source-proven
logical/physical pair: the public tree does not contain the generated custom
`msromdumper-619.hex`, and the historical Intel `0x619` update is not that
custom build. All conclusions below are therefore conditional on the explicit
NOP-tail crib.

H1557's unique statistical configuration decodes the repeated group as:

| Lane | Raw 72-bit word | Opcode |
|---:|---:|---:|
| 0 | `002400011000000000` | `FXORS` (`0x024`) |
| 1 | `040000000000000000` | `MOVE` (`0x400`) |
| 2 | `040900020000000000` | `OR` (`0x409`) |

It therefore fails the exact NOP triplet. This does not erase H1560's
multiple-control result: H1557 remains a nonrandom structural alignment. It
does mean that alignment is not a credible physical decoder under the
strongest semantic crib now available.

## H1561: complete simple-family result

H1561 tests every H1556/H1557 simple isomorphism against the exact NOP word:

- two logical-core orientations;
- four conventional within-dword transforms;
- all `8!` dword permutations;
- both the corrected seven-dword update representation and the source-exact
  CPUID-`0x619` CRBUS representation.

That is 322,560 mappings per representation, 645,120 total. Neither
representation has a survivor.

## H1562: compact algebraic result

H1562 expands beyond dword permutations without learning an arbitrary 216-bit
table. For each exact representation it tests:

- all invertible stream laws
  `logical_index = a * source_index + b (mod 216)`, for every
  `gcd(a,216)=1` and every `b`, crossed with forward/reversed dword traversal
  and the four conventional bit orientations: 124,416 candidates; and
- every cyclic offset of an order-preserving compaction into the exact
  published later-P6 lower-72 physical-coordinate order, crossed with both
  core orientations and the same eight source traversals: 3,456 candidates.

Across both representations, all 255,744 candidates fail the NOP crib. The
combined H1561--H1562 wall is 900,864 exact candidate checks with zero
survivors.

## Interpretation and boundary

If the repeated suffix is the canonical NOP triplet, the Pentium Pro mapping
is neither a conventional dword isomorphism nor a compact affine/stream
compaction of the published later-P6 core. A rail-specific cross-dword wiring
or the unreleased old `p6scrambler` is required. If the suffix is not NOP
padding, these searches remain correct conditional falsifications but do not
constrain the true decoder.

This result supplies no absolute Skylake ROM/control-state observable and no
R59 carry selector. H1488 remains `FROZEN_UNOPENED`; R96 remains
empirical/incomplete; the authoritative frontier remains eleven mode rows over
ten operands.

## Artifacts

- `experiments/h1561_ppro_nop_tail_crib.py` SHA-256
  `2a0ca9fbaca20c70d49ef33f7352dc2970d3f3af51352d1ae48c1f065126e3a8`;
- `tmp/ledger33/current/h1561_ppro_nop_tail_crib.json` SHA-256
  `9a0fbf7fc0f60dda0a91d2f9df7a8384a31cb2c8106d7988dfa2938386f0fe8a`;
- `experiments/h1562_ppro_nop_algebraic_permutations.py` SHA-256
  `640a56c00e6d68b52db2db0be6c510918f7d10ea8429686614c3eed5b79ced97`;
- `tmp/ledger33/current/h1562_ppro_nop_algebraic_permutations.json` SHA-256
  `457ae8c3c2cddbbd4c53a9a6e009ebfef22f8ba8c81da14c4b2d2fa7dfa4b6c0`.

Public sources are pinned at `ruikruik/utools` commit
`ab6aa24ed91de1c048313c10cb7546ea3397b827`: `msromdumper.asm` SHA-256
`314563685370c287a5710405c40173e6a0fea9c84d1405116c1426ebc5df9823`,
Makefile SHA-256
`03a3a460127bbf4cf3c46dc3e26918bad3df72a5d6f63dcca36c24772883dc28`,
and `msrom2scramble.c` SHA-256
`7c41477039cb2a183f32aeb0b0263560c52fdee8bbad965d69a7a786ea195d00`.

No x87 instruction or hardware capture ran, no private ledger or H1488 label
was opened, no manifest was frozen, and no emulator default or academic paper
changed.
