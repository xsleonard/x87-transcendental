# D0023: V7 passes the prospective midpoint challenge

**V7 passes this fresh challenge; FPATAN is not yet promoted.** All 194,808
one-shot observations match in output, C1, exception flags and pre-load flags.
All 748 three-PC groups agree. The complete saved corpus now contains
**2,353,704 observations across twelve jobs**. The main C/library remain V4;
the paper and existing trigonometric models are unchanged.

## Fixed arithmetic change

V7 retains V6's source-guided split polynomial and changes only the index law:
choose the nearest integer to `32*min(|y|,|x|)/max(|y|,|x|)`, with exact ties
going to the lower integer. Equivalently, use `ceil(32*r - 1/2)`. A selected
index below two takes the direct polynomial, including the midpoint `3/64`.
No operand, failing-ratio or table-cell exception is used.

The standalone `fpatan_candidate_v7.c` first replayed all 2,158,896 prior
observations with zero differences. That replay was explicitly discovery
agreement. D0023 froze new inputs, V7 predictions and all seven competing
index hypotheses before its hardware execution. Sanitized Clang and GCC 15
independently matched all 194,808 frozen Python predictions.

## Prospective results

| Frozen index rule | Output misses | C1 misses | Any affected rows |
| --- | ---: | ---: | ---: |
| Nearest, ties lower (V7) | 0 | 0 | 0 |
| Nearest, ties upper | 2,206 | 1,682 | 3,608 |
| Nearest, ties even | 2,206 | 1,682 | 3,608 |
| Nearest, ties odd | 0 | 0 | 0 |
| CHOP67 reciprocal, CHOP67 multiply, ties upper | 0 | 0 | 0 |
| RN67 reciprocal, CHOP67 multiply, ties upper | 978 | 750 | 1,604 |
| RN64 reciprocal, CHOP67 multiply, ties upper | 1,012 | 788 | 1,672 |

All hypotheses have zero exception/pre-load-flag differences. Lower, odd and
the CHOP67-reciprocal rule predicted identical endpoints on this bank, so
their three clean scores are **not three independently distinguished laws**.
No universal hidden-index claim follows from this result.

## Coverage and the next discriminator

The generator selected 48,328 fresh raw pairs: all 31 midpoint boundaries
from 3/64 to 63/64, varied denominator significands, both signs, all octants,
wide common exponent scales and immediate/64-step one-sided neighbors.
The conservative local checks held 248 possible private and 24 possible
public pairs. The remote guard checked every prior FPATAN tuple, reserved
this batch, and executed each new tuple once. No hardware observations were
repeated. The ledger reports integrity `ok`, all twelve jobs `OBSERVED`.

The exact-midpoint denominator generator zeroed six low bits to guarantee
representability. This is sufficient but not necessary: valid raw80 pairs
can retain additional denominator bits. Such pairs also approach midpoint
boundaries more closely than a one-step neighbor of the aligned construction.

`d0024_index_residue_mining.py` therefore scans unmasked low-byte residues at
seeded high words and y-binade transitions in every cell. Its 238,030
software-only pairs include 24,947 index disagreements and 2,704 endpoint
disagreements, with 689 retained witnesses across 112 signatures. This finds
endpoint-visible separators from the CHOP67-reciprocal hypothesis. No odd-tie
separator was found in this bounded search. No hardware labels were read by
the miner; D0024 is a new frozen prospective challenge, not a post-label fit.

## Reproducible artifacts

Under `../tmp/fpatan-re/`:

- `d0023-v7-full-corpus-replay.json`: authenticated prior-corpus C replay.
- `d0023/MANIFEST.json`, `INDEX-HYPOTHESES.json`,
  `STRUCTURAL-HYPOTHESIS.json`: immutable pre-execution input/prediction pins.
- `d0023/{C-PREFLIGHT,GCC15-PREFLIGHT,HISTORY,STAGED,DISPATCHED,STARTED,COMPLETE}.json`:
  implementation checks, clearance and one-shot execution receipts.
- `d0023/{SCORE,INDEX-SCORE,LEDGER-AUDIT}.json`: authenticated scoring and
  aggregate ledger audit. Both primary and alternate miss streams are retained.
- `d0024-index-residue-mining.json`: bounded software-only witnesses and counts.

D0023's raw hardware SHA256 is recorded in `COMPLETE.json` and both scores.
`DISPATCHED.json` pins the structural descriptor, which transitively pins the
local-only alternative predictions and unchanged scorer. Neither model code
nor alternate predictions nor private history were uploaded.
