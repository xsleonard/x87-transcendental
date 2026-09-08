# H1575: current rule composition on the expanded direct bank

This is a software-only replay of 56 existing observations: H1568's 51
direct-FCOS rows plus the five H1531/H1564 defining controls for the equality
and hard-3x consumers. No external alias is counted again. The source is
unchanged and every build has R84 off.

| Fixed program | Exact | Misses | Repairs | Regressions |
| --- | ---: | ---: | ---: | ---: |
| Current baseline | 23 | 33 | 0 | 0 |
| Disable R1263 equality gate | 19 | 37 | 0 | 4 |
| Disable R1270 hard-3x merge | 28 | 28 | 24 | 19 |
| Remove R1272 qualification, always permit merge | 23 | 33 | 0 | 0 |
| Disable R1378 negative Horner history | 23 | 33 | 0 | 0 |
| Disable R1237 positive Horner history | 23 | 33 | 0 | 0 |
| Disable all five listed rules | 24 | 32 | 24 | 23 |

Removing the hard-3x merge repairs the 22 H1472/H1477/H1488/H1566 failures
and d0d0 RD/RZ, but breaks the eighteen fresh controls and d800/RU. All other
nine historical failing mode rows are invariant under these seven programs.
Turning R1272's qualification off changes nothing on this bank. This is a
bounded observation about these rows, not a claim that the qualification is
globally redundant.

The equality-gate ablation breaks precisely the four defining old equality
controls and changes no new row. Thus the new merge-attachment evidence does
not itself challenge the equality gate's enabled branch. Nor do these
ablations establish a universal failure mechanism for any component: an
upstream change can reach the same endpoint as a missing terminal carry.
No program here is an exact replacement or a promoted selector.

This identifies a useful next test: construct exact b1 comparator equalities
where both hard-3x merge conventions give the same comparison value, then
challenge the existing equality gate and its complement on fresh inputs.
That is a separate question from refitting the already-rejected attachment
selectors. H1576 derives the required interval directly from integer arithmetic.

Artifacts:

- `experiments/h1575_current_rule_ablation.py`, SHA-256
  `b2e69a5ca71300567111badac069428021b7ff775d174ea6316a559cd9573543`.
- `tmp/ledger33/current/h1575_current_rule_ablation.json`, SHA-256
  `92ab4d2bcf3d4183bf8c87e6ecffc4fd409a3292b58a2bc037cfa365f66eb75e`.

The report includes exact per-case outputs, all compiler defines, source and
model hashes, and evidence provenance. Seven compile-time programs are tested;
it is not an exhaustive search over all combinations or all inputs. No
hardware, emulator default, or academic paper/PDF was changed.
