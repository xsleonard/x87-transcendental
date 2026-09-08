# H1563 Pentium Pro rail-specific affine NOP-crib audit

Date: 2026-09-04

Status: exact conditional falsification of a bounded physical-mapping family;
no decoder, selector, or emulator change.

## Question

H1562 rejected a single invertible affine permutation of the 216 connected
Pentium Pro patch bits, but explicitly left rail-specific wiring open.  Does
the H1561 NOP-tail crib admit a mapper made from three independently permuted
72-bit uop rails?

The crib boundary is unchanged.  Public Pentium Pro source proves that
`MOVE.DSZ32(CONST, CONST_0)` is used as padding, and the documented Pentium Pro
72-bit word encoding makes that exact logical word
`060000000000800000`, with one-bits at positions 23, 65, and 66.  The
historical Intel 0x619 update is not the generated custom source build, so
identifying its repeated suffix as that NOP remains a strong structural
inference rather than a source-proven logical/physical pair.

## Exact family

H1563 tests both exact physical representations already fixed by H1555/H1556:

- the corrected seven-dword update group; and
- the source-exact CPUID-0x619 CRBUS group.

For each representation it enumerates forward and reversed dword traversal,
crossed with identity, 32-bit reversal, byte swap, and reversal within each
byte.  Each 216-bit connected stream is split in both natural ways:

- three round-robin rails selected by stream index modulo three; and
- three contiguous 72-bit rails.

Each source rail may be assigned to any logical lane and receives an
independent invertible affine map

```text
logical_bit = a * source_bit + b (mod 72), gcd(a,72)=1.
```

There are 24 unit multipliers and 72 offsets, hence 1,728 maps per rail and
six lane assignments.  Because all three target lanes contain the identical
NOP word, the three rail constraints are independent.  Exhaustive solution
counts for each rail therefore give the exact Cartesian-product survivor count
without materializing every combined mapping.

## Result

The implementation performs 165,888 primitive affine checks.  Those checks
exactly represent 990,677,827,584 combined three-rail mappings across the two
physical representations, two partitions, eight traversals, and six lane
assignments.

There are zero survivors.  More strongly, no tested case admits even one
affine solution on any individual rail.  Therefore no combined rail mapping
can satisfy the crib.

This closes the natural independent-rail affine extension of H1562 if the NOP
crib is correct.  It does not exclude an arbitrary rail permutation,
cross-rail mixing, or a non-affine old `p6scrambler` wiring.  It also does not
turn the H1557 statistical near-decoder into an exact decoder and provides no
Skylake R59 selector.

## Artifacts and boundary

- script: `experiments/h1563_ppro_rail_affine_nop_crib.py`
- script SHA-256:
  `a84f30b4dc66a7c5f9c650499fc355c3715bab647a1a0e7afb6e65f9c88c6709`
- report: `tmp/ledger33/current/h1563_ppro_rail_affine_nop_crib.json`
- report SHA-256:
  `db226c0c2195b5fb0b689a5df48ec19c8bc82e1c3c504372d23781565bee68de`

No x87 instruction or hardware capture ran, no microcode was loaded, and no
private ledger or unopened label was accessed.  No manifest, emulator
behavior/default, or academic paper/PDF changed.  H1488 remains
`FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the authoritative
frontier remains eleven mode rows over ten operands.
