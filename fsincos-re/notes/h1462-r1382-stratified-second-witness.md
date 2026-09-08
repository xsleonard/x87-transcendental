# H1462 fresh stratified R1382 second-witness search

Date: 2026-09-03

Status: deterministic negative software search; no selector promotion and no
hardware or paper change.

## Search surface

The earlier R1382 adversarial work evaluated 17,094,967,359 external
significands: one 4,294,967,295-input slice centered on d0d0 plus 64
200,000,001-input strata across the normalized `3ffc` binade.  H1462 uses
the midpoints of a separate 128-stratum partition, with radius 50,000,000.
The script proves that none of its 128 closed intervals intersects either
the earlier 64 strata or the earlier d0d0 slice.

The new surface contains exactly 12,800,000,128 inputs.  The existing exact
integer scanner found 50,902 theta-zero, low3-three, s4=66/67 structural
events.  Every event was replayed in RN, RD, and RU through the ledger-free
incumbent and the default-off R1382 candidate.  The candidate changed zero
architectural outputs: there are zero software separator operands and zero
separator mode legs.

As a guard against silently using the wrong executables, the script first
replays the known d0d0 anchor.  The candidate changes RD from
`3ffe:fab221ca33fb39e4` to `3ffe:fab221ca33fb39e3` while RN and RU remain
unchanged, exactly as required.  Positive FCOS RZ duplicates RD and is not a
separate software-search mode.

Together, the two disjoint surfaces cover 29,894,967,487 deterministic
software inputs without a second R1382 endpoint separator.  This is stronger
sparsity evidence, not an exhaustive-domain result.  It does not resolve the
H1410/H1461 exact query, does not validate R1382, and does not justify a
boundary selector.

## Reproduction and discipline

The guarded run reproduces byte-for-byte.  Artifacts are:

- `experiments/h1462_r1382_stratified_second_witness.py`, SHA-256
  `d91f2f5d77e4ee66d7856f56cfa4ebb46f5b61961415d1155e333912e44ffdd3`;
- `tmp/ledger33/current/h1462_r1382_stratified_second_witness.json`, SHA-256
  `aebfac95d5299524514a1c030f7e4a97ae46efc4cbb727378ce0a6b9c03b3f42`.

No x87 hardware ran, no private ledger or hardware label was read, and no
capture manifest was frozen.  R1382 remains default-off.  The emulator,
academic paper, and PDF remain unchanged; the ledger-free frontier remains
eleven mode rows over ten operands.
