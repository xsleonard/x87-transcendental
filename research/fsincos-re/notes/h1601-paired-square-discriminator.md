# H1601: paired square transport is observable, but not at the mandatory cuts

Date: 2026-09-04. Software contrast and capture-readiness audit only. No new
hardware observation, paired label opening, tuple-ledger audit, frozen
manifest, emulator default change, or manuscript/PDF update.

## Question and explicit assumptions

H1595/H1599/H1600 leave upstream-square and terminal explanations alive.
Could paired FSINCOS expose a different consequence of the square change?
This requires two extra assumptions: the paired producer uses the specified
graph below, and the changed standalone square semantics transfer across
instruction schedules. Neither assumption is established by matching software
implementations. Transporting one successful per-input departure is not a
general square selector; fixed AWAY67 already fails the standalone bank.

The contrast deliberately keeps all paired operations except the initial
square unchanged. A standalone-only terminal change leaves this paired graph
unchanged. More general upstream or paired-terminal changes are outside this
two-program contrast and can defeat its interpretation.

## Independent paired graph

For positive direct operands in [1/8,1/4), define S as CHOP67(x*x), or AWAY67
for the square-transport comparison. The paired Round18 producer is distinct
from the standalone split even/odd graph:

- The sine factor starts at S6_6 and takes five fused RN64 multiply-adds
  with S and coefficients S6_5 through S6_1.
- The cosine factor starts at C6_6 and takes four fused RN64 multiply-adds
  through C6_2; the final multiply by S is CHOP67, followed by RN64 addition
  of C6_1.
- The sine correction is CHOP67(RN64(p*S)*x); sine is RC64(x+correction).
- The cosine correction is CHOP67(q*S); cosine is RC64(1+correction).

`h1601_paired_square_discriminator.py` implements this graph with H1592's
tested exact signed-dyadic arithmetic. It checks all literal sine coefficients
against the repository constants. Two isolated C snapshots differ only by
the analysis-only square substitution inside the paired polynomial branch.
Canonical source remains unchanged. R84 is off in both builds.

Both independent integer results match both C result lanes on all 8,336
software mode rows per build: 36 named operands plus 2,048 deterministic
random software operands, each in four modes. These are software checks,
not new hardware samples. Named-mode metadata identifies only the 37 actual
standalone observations inherited from H1595; the other predictions remain
unobserved. No paired hardware value is imported.

The altered square changes four named cosine outputs and one named sine
output, plus 21 cosine and ten sine outputs in the software-only random bank.
The complete named stage values and eight raw C output streams are preserved.
The main task independently reran the full script: report and raw stream
hashes reproduce exactly, including both C executable hashes.

## Joint necessity versus paired observability

`h1601_paired_square_projection.py` joins the hash-locked H1600 joint RC/C1
paths and the H1601 predictions. It recomputes every named paired stage and
compares the two outputs and both mathematical final-round-up indicators.
For a positive lane these indicators are `stored_value > exact_prevalue`.
They are **not assigned to physical FSINCOS C1**: which internal operation
supplies that status has not been established here.

Six operands require the square departure in at least one of H1600's two
payload variants when terminal arithmetic is ordinary:

```text
3ffc:de3ffffd548db2bf
3ffc:e73ffffd2c52df71
3ffc:f4100000059862dd
3ffc:f9e0000229067583
3ffc:fa50000007503a2f
3ffc:ffffc00024077827
```

At **all six**, changing only the paired square changes neither stored lane
nor either ordinary lane-round-up indicator in any of the four modes. This
does not mean their exact internal paired prevalues are equal. In particular,
e73/f410 cosine corrections change by one unit of 2^-72, yet the external
projections above remain identical. Thus those probes cannot distinguish
these two specified paired predictions.

Across all 144 named software mode rows, seven have a changed output or
ordinary lane-round-up indicator. None belongs to that mandatory-square set:

| Operand suffix | Mode | Output contrast | Additional indicator-only contrast |
| --- | --- | --- | --- |
| c891b50fb448de18 | RN | cosine | none |
| de3ffffc7a17c3dd | RN | sine | none |
| de400000a2e32d2a | RD, RZ | cosine | none |
| de400000a2e32d2a | RN, RU | none | cosine |
| fffff00047c167a3 | RU | cosine | none |

For example, c891/RN paired cosine is `3ffe:fb1ae3a271670cbd` under the
ordinary square versus `3ffe:fb1ae3a271670cbc` under AWAY67. But c891 admits
an unchanged square: omitted payload can instead change the negative factor,
and frozen numeric payload requires no departure at all. De400 similarly
admits a positive-factor alternative or no departure. The other contrast
operands also do not force a changed square. Selecting their AWAY67 witness
would therefore select one possible explanation, not a consequence of the
whole surviving upstream family.

This is a finite negative readiness result, not a theorem that paired
FSINCOS can never be useful, not a global square-cause exclusion, and not a
reason to stop pursuing a general solution. A new campaign needs a genuinely
specified mechanism with distinct necessary predictions, or a new justified
observable/producer relationship. Before any eventual capture, audit exact
tuples against public and private local history and freeze predictions.

## Artifacts

Paths are relative to `fsincos-re`:

- `experiments/h1601_paired_square_discriminator.py`, SHA-256
  `5d50301144f912e674333675b3b05ea5e920f12e1f05cfdec1a8a93eba093fa9`.
- `tmp/ledger33/current/h1601_paired_square_discriminator/report.json`, SHA
  `8dac3cb548ad3182817bd077f63cca5472cf3c244eb510e7a799aa4805cda53e`.
  Its directory contains both C models and eight output streams.
- `tmp/ledger33/current/h1601_source_before.c`, SHA
  `0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`,
  equals the unchanged canonical source.
- `tmp/ledger33/current/h1601_source_square_away.c`, SHA
  `0f55852da2a15205769db59126591178ce44834f98a4f3698f11d3e99d07011b`,
  is isolated analysis only, not a proposed default or general rule.
- `experiments/h1601_paired_square_projection.py`, SHA
  `2291996a466b17ca893545dec392908ca9ef8087b732048e23fd302dbf6358af`.
- `tmp/ledger33/current/h1601_paired_square_projection.json`, SHA
  `9fee759843dd40a454720bfaa6941cf80c26a77b2ef777fbea55fe3d7a3c7885`.

```sh
python3 fsincos-re/experiments/h1601_paired_square_discriminator.py \
  --root fsincos-re --output-dir NEW_OUTPUT_DIRECTORY
python3 fsincos-re/experiments/h1601_paired_square_projection.py \
  --root fsincos-re --output NEW_PROJECTION_FILE
```

Both refuse existing outputs. No H1601 hardware campaign has been frozen or
run. The separate projection replay reproduces its JSON byte-for-byte. Normal
build/selftest, Python syntax, and whitespace checks pass. R96 remains
empirical/incomplete, speculative selectors remain off, and the observed
direct 45/44 and external 75/74 failure frontiers are unchanged.
