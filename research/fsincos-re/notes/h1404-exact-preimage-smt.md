# H1404 exact preimage synthesis

`experiments/h1404_exact_preimage_smt.py` is an analysis-only QF_BV system.
It does not run x87 hardware and it does not change the default emulator.  Its
fixed-path graph encodes the exact 64x64 square, square-of-square, both Horner
chains, terminal products, R1270/R1272 merge, R59 comparator, and endpoint
projection.  Every reported SAT assignment is replayed by an independent
integer Python implementation and, when supplied, the C model.

## R1382 endpoint separator

The known operand `3ffc d0d000000cc0b3f8` is SAT and changes the candidate's
RD/RZ endpoint.  Its Python, compact-C, incumbent-C, and candidate-C replays
are exact in `tmp/ledger33/current/h1405_r1382_exact_separator_w136.json`.

After blocking d0d0, Z3 4.15.3 reached its 300,000 ms bound.  An independent
CVC5 1.3.1 run on the preserved QF_BV query also reached its 300,000 ms bound.
The result is therefore **UNKNOWN**, not unreachable.  The query fixes the
complete d0d0 materialization path and relaxes only the R1272 tree gate to its
enabling value.  Thus an eventual UNSAT result would prove the physical
subset, while any SAT assignment still requires exact-tree and C/Python
replay.  No fresh endpoint-visible operand was produced, so no capture
manifest was frozen and no hardware label was opened.

The independent-solver report is
`tmp/ledger33/current/h1409_r1382_second_witness_cvc5.json`.  Its exact input
is `tmp/ledger33/current/h1409_r1382_second_witness_exact.smt2` (13,642 bytes,
SHA-256 `b358fd7e65a7ed83fccd7fe3ff2f2b24d7528406ac5d7f7f79f7a9951d03efba`).
The two Z3 checkpoints remain preserved as
`h1404_r1382_exact_separator.json` and
`h1405_r1382_exact_separator_w136.json`.

## Exact observed-feature collision

The solver found this exact reduction-preimage pair:

| Instruction | Operand | Reduction quotient | M66-add carry into column 64 |
|---|---|---:|---:|
| FCOS | `3ffc d920000000749eaa` | 0 | 0 |
| FSIN | `3fff e433daa22177560a` | 1 | 1 |

At scale 2^-66 the synthesized external integer is exactly
`2*M66 + 0xd920000000749eaa`.  The C replay is byte-identical from `DI_RED`
through `DI_POLY`, `DI_TC`, `DI_R59`, and `DI_BR`, including all raw exposed
fields, while the proposed reduction-history carry differs.  The incumbent
architectural outputs differ by one low bit in RN and coincide in RD/RU/RZ.
This is a SAT collision on every currently exposed post-reduction feature,
not a sampled collision or operand scan.  The authoritative replay artifact
is `tmp/ledger33/current/h1408_exact_reduction_history_collision.json`.

The later H1412 causal audit established that the incumbent RN output split
is introduced after this common arithmetic path by the default-on R84
literal operand ledger.  With `G_ROUND84=0`, both operands agree in all four
modes.  The inverse-equation carry is therefore a correlated silicon
hypothesis, not a state consumed by the current C model.  The correction and
reproducible on/off matrix are preserved in
`notes/h1412-reduction-collision-causal-audit.json`; H1408 remains unchanged.

## External-preimage classification

For a positive finite normal x87 operand below 2^63, the exact constraint is

```text
sig << (se - 0x3ffc) = 2*q*M66 +/- residual,  q > 0
```

Three of the ten unresolved reduced anchors have exact external preimages:

| Reduced anchor | Exact external operand | q | side |
|---|---|---:|---:|
| `3ffc cca0000009242f0c` | `403b 9b96fed99478343c` | 892177135061317282 | -1 |
| `3ffc d920000000749eaa` | `3fff e433daa22177560a` | 1 | +1 |
| `3ffc d0d000000cc0b3f8` | `4001 c2895aa22102bc95` | 4 | -1 |

The other seven anchors are globally UNSAT in this external domain.  Their
preserved cores contain
`preimage.exact_M66_equation` and
`preimage.external_positive_finite_normal_below_2^63`; the report also keeps
the two nearest representatives at each frozen transfer quotient.  In
particular, the earlier statement that cca0 was bracket-only was too narrow:
its small q=5 positive construction brackets, but the global exact solver
finds the large-q negative-side preimage above.

The complete SAT witnesses, UNSAT cores, brackets, and C reduction replays
are in `tmp/ledger33/current/h1404_exact_external_preimages.json`.

## Reproducibility and capture discipline

The solver writes new artifacts exclusively and refuses to overwrite an
existing report.  Its `freeze` command refuses to operate without private
ledger paths, checks repository-visible and private tuples without printing
private paths or contents, rejects duplicates, and only emits a
`FROZEN_UNOPENED` manifest.  No freeze or capture operation was needed for
the results above.
