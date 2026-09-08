# H1509: existing dense capture cannot choose pair A or pair B

Date: 2026-09-03

Status: **720,000 cached architectural rows audited; zero endpoint separators;
no orientation evidence and no hardware execution.**

## Question

H1508 confirms that none of H1488's exact six tuples has been opened.  That
does not by itself exclude a different already-captured operand from deciding
the same H1487 pair orientation.  H1509 therefore audits the complete existing
standalone-FCOS dense corpus before requesting a fresh observation.

The corpus contains 240,000 unique operands and cached Skylake results in RN,
RD, and RU, for 720,000 architectural rows.  For each mode H1509 evaluates the
current incumbent and the default-off R1382 build.  Only rows where those two
outputs differ can label the hidden merge/no-merge choice; the exact H1487
pair functions would then be evaluated on the dumped multiplier operands.

## Result

The two builds are byte-identical on every row:

| Mode | Cached rows | Incumbent/R1382 endpoint separators |
|---|---:|---:|
| RN | 240,000 | 0 |
| RD | 240,000 | 0 |
| RU | 240,000 | 0 |
| **Total** | **720,000** | **0** |

Consequently there is no endpoint-visible row on which pair A and pair B can
be scored, and the number of existing dense pair discriminators is zero.  This
is not evidence that the functions are equivalent: H1487/H1498 already prove
their exact disagreement.  It shows that this broad historical corpus never
enters an architecturally visible instance of the narrow R1382 state.

An independent execution reproduces the JSON byte for byte.

## Artifacts

- `experiments/h1509_existing_dense_pair_audit.py`, SHA-256
  `46776df092333dae06241b565aca549f549261bef818d460330185ba213437a7`;
- `tmp/ledger33/current/h1509_existing_dense_pair_audit.json`, SHA-256
  `0bfe819369fe908f03f0e6a3936679885f8c01e543de57c2bcc5ff5bcab0e3cb`;
- dense input SHA-256
  `37bbec24b4e286495268223befb7f29a6e37448c2ccbffae466255c666e934d1`;
  and
- cached RN/RD/RU capture SHA-256 values
  `d4a3dd53208ff6eaebf8fef3a79c918b4734a2b46c7e8485076ae676edc736ab`,
  `68e1abaf20fffa62041ddb09c957141fe782ee7856808371ef94850a09294410`,
  and `807177cd8d0b9b49cbf9a653d67577b9def9e2a2a2e562cc646fac07784b6cc7`.

Both analysis builds pass `--selftest`.  No x87 instruction or fresh hardware
capture ran, no H1488 or private-ledger label was opened, and no emulator
behavior/default, academic paper, or PDF changed.  H1488 remains
`FROZEN_UNOPENED`; R96 remains empirical/incomplete; the authoritative
frontier remains eleven mode rows over ten operands.
