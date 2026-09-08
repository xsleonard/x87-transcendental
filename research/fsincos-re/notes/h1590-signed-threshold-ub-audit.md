# H1590: defined signed-threshold scaling; no selector change

Date: 2026-09-04. Status: implementation repair verified on cached evidence;
not a silicon-law repair or a claim of closure. No hardware was executed.

## Finding and exact repair

UBSan identifies negative signed left shifts at three threshold-scaling sites
in the R59 code: the `u0` comparison and the two `uu` comparisons. The saved
source reports these at lines 3881, 3961 and 3964. The original equality
controls f9e/RN and fcc/RN exercise the first site; the broader cached bank
exercises all three. Matching cached hardware despite a diagnostic does not
make the C operation defined.

Replace `((__int128)u << 66)` with
`(__int128)u * ((__int128)1 << 66)` at exactly those sites. An added comment
explains why. No existing comment, branch, threshold, selector, or default
was removed or changed. H1590's script asserts that the entire new source is
exactly these substitutions plus the comment relative to the saved source.

On this compiler `int` is 32 bits and `__int128` is 128 bits. For every signed
32-bit `u`, the mathematical product lies in

    -2^97 <= u * 2^66 <= 2^97 - 2^66.

That interval is strictly within signed 128-bit range. The positive shift
`(__int128)1 << 66` is defined, and the multiplication therefore expresses the
intended signed scaling without overflow or a negative left shift. This is
a range argument for every such threshold, not an inference from sampled
thresholds. Twelve extreme/interior values additionally check the equivalent
128-bit bit-vector interpretation. It is not a proof that the entire emulator
is free of undefined behavior.

## Cached compiler parity

`experiments/h1590_signed_threshold_ub_audit.py` checks the hash-locked H1589
evidence, all 134 named direct/defining/alias observations, and 149,764 cached
FCOS controls from H1107. The union contains 149,898 distinct observed legs.
R84 is disabled in every comparison.

The old and repaired source were each built at O0, O2, O3 and O2+UBSan using
Apple clang 17.0.0 (clang-1700.6.4.2), arm64. All eight programs produce the
same outputs on all 149,898 rows: **149,823 exact, 75 misses**. Every one of
the 134 previously reconciled baseline endpoints is reproduced. There are
zero before/after or optimization-level output differences. The old UBSan
build records twelve diagnostic lines across the four FCOS mode processes,
covering the three sites; the repaired UBSan build records none on this bank.
The number of diagnostic lines is not a count of affected inputs.

Common ordered-output SHA-256:
`57180956c6ac71755ac5fa32b3a996b0397b4d681aa73aa4132f429f9f8385f9`.

The canonical normal build and `--selftest` pass. The normal build emits 93
warnings (principally existing missing `rh` initializers and unused analysis
functions); it is not warning-free. Python syntax and `git diff --check` pass.

## Artifacts and source-history bridge

- Full old source: `tmp/ledger33/current/h1590_source_before.c`, SHA-256
  `8fe40b8c852918f9cbe57a91b678861aa5e847f6c07106db1a18175a22314f39`.
- Repaired canonical `src/fsincos_skylake.c`, SHA-256
  `de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.
- Audit script SHA-256:
  `0393b89d0522288c89066f715647387b1eb935d95a094817d01717f4d0984a14`.
- Report: `tmp/ledger33/current/h1590_signed_threshold_ub_audit/report.json`,
  SHA-256 `311a0771ac79b14e8de2bdbb8dacbec07edc536298fd233385d6ccd1badfeeb3`.
- The report directory also preserves raw stdout/stderr for each program,
  instruction and mode, and compiler identification. Their hashes and all
  input-evidence hashes are recorded in the report.

Do not rewrite historical source hashes or artifacts to the new source hash.
Use the saved old source for exact historical replays; H1590 supplies a
separate, finite semantic-parity bridge to the repaired source. Replay requires
new output/build directories and refuses to overwrite existing evidence:

```sh
python3 fsincos-re/experiments/h1590_signed_threshold_ub_audit.py \
  --root fsincos-re --build-dir NEW_BUILD_DIRECTORY \
  --output-dir NEW_EVIDENCE_DIRECTORY
```

The frontier remains 45 failing direct mode/residual rows over 44 residual
operands, or 75 failing rows over 74 external operands including known exact
reduction aliases. R96 remains empirical/incomplete and speculative selectors
remain off. No manuscript/PDF was changed. Successful forced-carry intervention
continues to be an endpoint fact, not proof that missing physical state lives
in the final carry selector. Conditional upstream operation semantics remain
open despite failures of particular fixed perturbations.
