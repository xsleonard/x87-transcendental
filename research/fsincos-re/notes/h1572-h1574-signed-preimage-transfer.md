# H1572–H1574: exact residual-side and signed-result transfer

**28/28 fresh transfers exact; 12 model misses; no residual-side pair split.**
This closes a coverage gap in the preceding transfer experiment, not the R59
selector. No emulator behavior/default or academic paper/PDF changed.

## Why this test was distinct

H1570 covered twelve of H1569's 26 anchors with representable exact external
preimages: positive residual, q mod 4 in {0,1}, positive cosine projection.
The fourteen omitted anchors have low-three-bit residual classes 4 or 6.
Their exact preimages require q mod 4 = 2, or q mod 4 in {1,3} depending on
residual side. They therefore exercise a negative cosine projection or the
opposite reduced-input sign. These classes were not covered by H1570.

H1572 reconstructs all 271 exact preimages of those fourteen anchors. Every
candidate matches its direct anchor's baseline result in all four modes under
the fixed sign relation

    output = (-1)^floor(q/2) * cosine(abs(residual));
    instruction = FSIN for odd q, otherwise FCOS.

All external inputs in this experiment are positive; this is not a test of
negative external encodings. For negative output projection, the anchor's RD
observation predicts an RU capture and vice versa; RN and RZ are unchanged.
Both forced final-carry endpoints also map exactly in the selected anchor mode.

The trace comparison checks, rather than simply discarding, the expected
sign changes in `DI_RC2.r/c`, `DI_RED.i0/rsn`, `DI_POLY.i0/rsn`, and
`DI_FIN.neg`. It then canonicalizes those seven sign fields to the direct
anchor. Every other diagnostic field and stage must be identical, excluding
only the external input identity and ASLR address already excluded by H1569.
All 271 candidates pass. In particular, no numerical word, branch choice,
normalization field, or rounding-history field is omitted to make them match.

This is exact equality of the exposed C arithmetic under a fixed sign
symmetry, not evidence that every physical silicon state has been observed.

## Frozen bank and hardware result

H1573 chose the minimum fresh quotient separately for residual side -1 and
+1 for each anchor. A conservative significand-level repository/private-ledger
gate removed one previously seen candidate. All 28 selected operands passed
the gate again immediately before execution. They comprise eighteen FCOS and
ten FSIN tuples, 23 negative output projections, and nineteen RD/RU swaps.
No direct anchor was recaptured and no tuple was repeated.

The immutable kit ran once under standing user authorization on
`45.32.204.118`, the Skylake Xeon oracle. The existing capture binary and
source hashes matched the previously validated harness. The runner checksum,
freeze, manifest, and all input hashes were verified remotely before the
first x87 instruction. The runner refuses any existing output directory,
including one left by a partial run. Raw files are preserved under
`transfer-tests/h1573/hardware-output/`, with an `OPENED_ONCE` sidecar.
**Never rerun H1573.**

| Instruction | Observations | Transfer exact | Baseline exact | Baseline misses |
| --- | ---: | ---: | ---: | ---: |
| FCOS | 18 | 18 | 12 | 6 |
| FSIN | 10 | 10 | 4 | 6 |
| Total | 28 | 28 | 16 | 12 |

All twelve misses require carry 1; all sixteen controls require carry 0.
There are no values outside those endpoints. After the predetermined sign
projection, both residual sides agree in every family and equal the existing
anchor hardware observation. The cca0 anchor now has fresh, exact FCOS
observations at q=2 on the negative residual side and q=350 on the positive
side; these are not the old q=5 brackets.

Together H1570 and H1573 provide 52/52 successful exact preimage transfers
covering all 26 representable anchors in H1568's finite bank. They do not
observe all 509 preimages, prove universal sign/quotient independence, or
identify the missing internal arithmetic wire. They constrain future
mechanisms: these errors persist through the tested reduction and final-sign
paths, including directed-rounding polarity changes. Another campaign of
equivalent preimages without a new distinguishing hypothesis is not indicated.

The explicitly reconciled raw union is now 103 observations over 102 external
operands, with 63 failing rows over 62 operands: 49 FCOS and fourteen FSIN
failures. **These added failures are aliases of known reduced states, not new
independent arithmetic failure families.** The distinct direct reduced-state
frontier remains H1568's 33 failing mode/residual rows over 32 residual
operands. Both counts matter; do not replace the latter with inflated counts
of exact external aliases. All 103 observations have one matching forced
final-carry endpoint.

## Other checks and corrections

The read-only i7 availability check at the user's address `142.132.217.24`
timed out before SSH connected. No x87 instruction or PMU measurement ran
there, and the obsolete `.243` address was not tried. This did not block the
Skylake campaign. Earlier H427 PMU data already supplied a bounded no-count-
difference result; it must not be restated as exhausting every possible
observable or proving that no hidden microcode branch can exist.

The transfer-coverage note still contained H1404's superseded assertion that
the d920 direct/preimage split proves a consumed reduction carry. It now
incorporates H1412's hash-verified correction: the current C model's apparent
RN split is R84's literal operand overwrite, not arithmetic consumption of
the carry. All comparisons here use R84-off models. No original solver or
capture artifact was altered.

H1572 reproduces byte-for-byte. H1574 verifies all positional inputs, raw
counts, and frozen/remote hashes, and its software-only replay reproduces the
score and report byte-for-byte. Python and shell syntax checks, normal C
build, software selftest, and diff checks pass.

Artifacts:

- `experiments/h1572_signed_preimage_projection.py`, SHA-256
  `f62cbf9a9659067e5301935cec2c3f0de43388c8e285d5e7d68aa53f7dfecd32`.
- `tmp/ledger33/current/h1572_signed_preimage_projection.json`, SHA-256
  `20a5a546be349e4f2738d163b135eee1f2c3d27fd148073157b5cc8e37406899`.
- `experiments/h1573_freeze_signed_preimage_transfer.py`, SHA-256
  `83981759a4858783eb08c35d78f92277f09a0119043b035f8932943d34e46dd1`.
- `experiments/h1574_score_signed_preimage_transfer.py`, SHA-256
  `66fbf2d5ce8ef7fcdaf755b4a0c679490fb0605045501ae393ae1d64c72ffb06`.
- `transfer-tests/h1573/FREEZE.json`, SHA-256
  `f0fae66d3eae7f6e6e2081ad61dc80fee82909c6d47a4d94099057f3f8b2f6c7`.
- `transfer-tests/h1573/OPENED.json`, SHA-256
  `e532e72289384e1a1fd621ba7a14fe889474e7acfd3d8a70e0aa4a2b968d2f9c`.
- `tmp/ledger33/current/h1574_signed_preimage_transfer_score.tsv`, SHA-256
  `d5bdd3be2f5a0ec9567fc5e1dc54ec0376158706838b262d889d13ce106400b2`.
- `tmp/ledger33/current/h1574_signed_preimage_transfer_report.json`, SHA-256
  `b279fcc6ce6426b97b237918c7498daf7f3e917341b46998ad5b29b80b878590`.

R96 remains empirical/incomplete. R1382/QX/Q/pair/tree candidates remain off.
The active goal remains unresolved; no general selector survived or emerged.
