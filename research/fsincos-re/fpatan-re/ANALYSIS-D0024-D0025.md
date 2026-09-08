# D0024–D0025: reciprocal falsification and an exact index-alias identity

**V7 passes D0024's fresh 66,248 observations with zero output, C1,
exception or pre-load-flag differences.** All 260 three-PC groups agree.
Combined with D0023, the same unchanged candidate now passes **261,056
prospective observations**, after matching all 2,158,896 prior observations.
The corpus totals **2,419,952 observations across thirteen one-shot jobs**.
The main C/library remain V4 pending final acceptance/delivery work; no paper
or existing trigonometric-source changes have been made.

## D0024: denominator low bits distinguish the surviving reciprocal rule

The software-only scan in D0023's follow-up supplied mechanism separators;
the new campaign added their immediate neighbors and 8,192 independently
seeded near-midpoint proposals. Denominator low bits are not masked. The
local clearance selected 16,432 raw pairs, holding 24 possible private and two
possible public pairs. All predictions, including seven alternatives, were
frozen and pinned before dispatch. Sanitized Clang and GCC 15 independently
agree with every frozen Python prediction.

| Frozen index rule | Output misses | C1 misses | Any affected rows |
| --- | ---: | ---: | ---: |
| Nearest, ties lower (V7) | 0 | 0 | 0 |
| Nearest, ties upper | 635 | 495 | 1,007 |
| Nearest, ties even | 635 | 495 | 1,007 |
| Nearest, ties odd | 0 | 0 | 0 |
| CHOP67 reciprocal, CHOP67 multiply, ties upper | 725 | 461 | 935 |
| RN67 reciprocal, CHOP67 multiply, ties upper | 661 | 443 | 964 |
| RN64 reciprocal, CHOP67 multiply, ties upper | 2,391 | 1,781 | 3,324 |

Exception and pre-load flags match for all alternatives. These observations
falsify the previously indistinguishable CHOP67-reciprocal construction. The
lower/odd pair remains clean and endpoint-identical, now explained by D0025.
D0024 is terminal/OBSERVED, authenticated and scored; the remote ledger is
integrity `ok`, with no repeated hardware tuples.

## D0025: a closed arithmetic identity, not another selector fit

The only indices where lower-tie and odd-tie rounding can select different
table cells have even lower index `n = 2,4,...,30` and exact ratio
`r = (2*n+1)/64`. At odd lower indices the selected cell is already identical;
at 1/64 both possible indices dispatch to the same direct polynomial.
Off exact midpoints the index rules are identical.

For an exact midpoint, normalize the larger positive operand as
`x = S*2^e`, where `2^63 <= S < 2^64`. This includes raw80 subnormals after
exact normalization. With `m = 2*n+1`, either neighbor `j = n` or `n+1` has
an **exactly representable numerator** `y - (j/32)*x = +/-x/64`.
Its denominator before chopping is `x*(2048+j*m)/2048`. Set
`K = 2048+j*m`. Since `K*S < 2^76`, its CHOP67 denominator can discard at most
nine integer bits:

```text
denominator = (K*S - t) * 2^(e-11),    0 <= t <= 511
abs(z) = CHOP67(32*S / (K*S-t))
32/K <= 32*S/(K*S-t) <= 32*2^63 / (K*2^63-511)
```

The last bounds are conservative: they also contain unrepresentable external
pairs and unreachable residuals. There are only **106 representable 67-bit
states** in all thirty signed neighbor enclosures. Exhaustively evaluating
them proves that **each midpoint has one common output/C1 vector** across
both cells, all four quadrants, both signs and all four rounding modes.
The certificate contains **3,392 independent endpoint checks**. The angles
are normal/nonzero, so candidate PE/UE agree; DE depends only on the identical
original operand classes. Special-value handling is unchanged.

This is an all-input equivalence theorem **within the specified numerical
graph**, not a statement that the chip uses either physical index circuit,
and not a universal proof of V7 versus silicon. The two representations
cannot be distinguished through the modeled outputs/status under that graph.

`d0025_midpoint_alias_certificate.py` transports constants independently from
the C literals, uses an independent integer/rational quantizer and endpoint
encoder, and cross-checks the production Python kernel/rounder. Its exact
certificate is reproducible with `--verify`; no solver timeout, hardware
sample or statistical extrapolation is used in the equivalence result.

## Artifacts and checks

All artifacts are under `../tmp/fpatan-re/`:

- `d0024-index-residue-mining.json`: software-only search and selected witnesses.
- `d0024/{MANIFEST,INDEX-HYPOTHESES,STRUCTURAL-HYPOTHESIS}.json`: frozen pins.
- `d0024/{C-PREFLIGHT,GCC15-PREFLIGHT,HISTORY,STAGED,DISPATCHED,STARTED,COMPLETE}.json`:
  clearance, implementation parity and one-shot capture receipts.
- `d0024/{SCORE,INDEX-SCORE,LEDGER-AUDIT}.json` and both complete miss streams.
- `d0025-midpoint-alias-certificate.json`: exact bounds, every enclosed state,
  common endpoints and source hashes.

All 26 arithmetic/solver unit tests pass under the existing Z3-enabled
interpreter. An initial run under the system Python failed three imports
because Z3 is absent there; the correctly provisioned interpreter passes.
The separate compressed-guard, synthetic pipeline and mutation-scoring tests
pass without hardware. Clang, sanitized Clang and GCC 15 candidate selftests,
syntax checks and `git diff --check` pass. These checks do not replace a final
full-corpus delivery audit or further hard-rounding verification.
