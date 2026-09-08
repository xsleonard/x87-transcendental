# H1619: the fixed candidate passes the complete retained stage-A raw wall

Date: 2026-09-04. Status: **CACHED_RAW_PASS_NOT_CLOSURE**.

With R84 disabled, the exact H1618 candidate matches all **56,393,031 actual
RN/RD/RU output and C1 row appearances** in the eight retained stage-A banks.
Every row enters the candidate hook. The incumbent misses four appearances;
the candidate repairs all four and has no regressions. A separate scorer,
with no producer/parser/arithmetic imports, independently verifies every
saved output and C1 comparison against the raw captures.

This is a broad cached regression wall for the stated domain, not fresh
validation, an unbiased input sample, a complete status implementation or a
proof of the hardware's arithmetic. No model/default, hardware, private
ledger, manifest or academic paper/PDF change was made.

## Scope and provenance

The eight banks are `comb`, `comb3`, `comb4`, `comb5`, `comb6`, `comb7`,
`comb8`, and `comb9`. All operands are positive normal direct FCOS, exponent
`3ffc`, in `[1/8,1/4)`. Each bank's input sequence is reconstructed from the
first field of `ties_BANK.txt`, normalized to external64, sorted in the C
locale and deduplicated within that bank. This follows the historical
capture-script protocol and H1204's retained-input reconstruction. Original
tie streams, actual status files and relevant historical scripts are hashed
before evaluation and checked unchanged at the end. The exact derived input
streams are retained and hash pinned. Counts and strict ordering are checked.

The historical complete eight-bank inventory supplies the expected counts,
not hardware labels or candidate predictions. Its old ledger-backed pass
is not reused as evidence. RN/RD/RU are actual captured files; no RZ label
is inferred. Hardware attribution is inherited from the historical Skylake
captures; these files do not independently supply per-row CPUID/PC metadata.

| Bank | Actual mode-row appearances | Baseline misses | Candidate output/C1 misses |
| --- | ---: | ---: | ---: |
| comb | 1,594,266 | 0 | 0 / 0 |
| comb3 | 3,825,000 | 0 | 0 / 0 |
| comb4 | 5,436,750 | 1 | 0 / 0 |
| comb5 | 823,782 | 0 | 0 / 0 |
| comb6 | 5,083,947 | 0 | 0 / 0 |
| comb7 | 5,843,946 | 1 | 0 / 0 |
| comb8 | 13,936,341 | 0 | 0 / 0 |
| comb9 | 19,848,999 | 2 | 0 / 0 |
| Total | 56,393,031 | 4 | 0 / 0 |

These are appearances, not 56,393,031 distinct external tuples. Banks can
overlap; do not claim a cross-bank unique census or add these totals to
earlier overlapping controls as if independent. The four fixes are cca/RN
in both comb4 and comb9, b000/RN in comb7, and d920/RN in comb9. All already
belong to the H1618 frontier. They do not add four new residual families.

## Instrumentation and checks

The canonical source is hash locked. The H1618 include/hook is assembled in
memory exactly as before, and the unchanged candidate header is included
with only its final-round call wrapped by a diagnostic observer. The
observer returns the original rounded result. It compares the magnitude of
that stored result with the exact pre-round accumulator and emits one C1
indicator. Exactly one diagnostic per input proves every row used the
candidate rather than fallback. Assertions protect accumulator sign and
alignment bounds; no arithmetic policy or parameter was changed.

The instrumented O2 build passes its selftest and 520 independent random/
endpoint software output-and-C1 checks across all four RC modes. Its output
also agrees with the uninstrumented H1618 candidate on that preflight bank.
Uniform index samples from the raw banks add 24,627 independent dyadic
output/C1 checks. These are software cross-checks, not additional hardware
observations. The C1 diagnostic remains an ordinary magnitude-increment
comparison, not a claim about all status bits.

The primary audit preserves complete per-mode output and C1 compressed
streams, every change/miss, per-bank checkpoints and a final complete report.
The separate `h1619_verify_raw_streams.py` verifies every source/artifact
hash, strict input ordering, four-stream row alignment, exact output bits
and actual status-bit9 agreement. It reproduces all 56,393,031 comparisons
and zero output/C1 misses without invoking a model or importing the producer.
This is an independent exhaustive scoring check, not a second full arithmetic
enumeration or a byte-identical full model rerun.

## Artifacts and reproduction

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1619_raw_stagea_candidate_audit.py` | `f7dd40373eeabc81df682387b92597ebed86fd3c65ba16cb0e59e1e8e0479f82` |
| `tmp/ledger33/current/h1619_raw_stagea_candidate_audit/prepared.json` | `5dac6bd6c624ab05a87ddebede9fa5be271591c06832ebfa60fd1f0a7c21ff1f` |
| `tmp/ledger33/current/h1619_raw_stagea_candidate_audit/report.json` | `5da7f73ac096acb4b3cdc44c018bd9e92772cc04c10a6f05c8766f11418abc3a` |
| `experiments/h1619_verify_raw_streams.py` | `f0ac9c16b536681d0b71783278a719dd7a4e7a08d169a355200fda400758b649` |
| `tmp/ledger33/current/h1619_raw_stream_verification.json` | `a084641f6196012894b6cbae8fec21058967052827db8659e34c4bbf5a55d95c` |

```sh
python3 fsincos-re/experiments/h1619_raw_stagea_candidate_audit.py \
  --root fsincos-re --output-dir NEW_COMPLETE_AUDIT
python3 fsincos-re/experiments/h1619_verify_raw_streams.py \
  --root fsincos-re \
  --audit fsincos-re/tmp/ledger33/current/h1619_raw_stagea_candidate_audit \
  --output NEW_VERIFICATION_JSON
```

The verifier pins the authoritative prepared manifest, so a separately
parameterized run is not silently substituted for this eight-bank result.
Python syntax, build/selftest, whitespace and diff checks pass. Canonical
source remains `0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`;
all speculative selector defaults remain OFF.

## Next

H1620/H1621 also complete the heterogeneous cache gate and reconcile three
additional cached incumbent misses; see
`h1620-h1621-heterogeneous-candidate-frontier.md`. The incumbent's known
frontier is now 47 positive-direct rows/46 residuals and 78 external rows/77
operands. The fixed candidate passes that frontier but remains isolated.

Next design genuinely fresh adversarial disagreements and agreement controls
for this fixed graph, audit full tuples against repository/private local
history, freeze predictions, and observe each fresh tuple once under the
existing i7/Skylake authorization. No such manifest or capture was made here.
Unseen inputs, remaining FSIN/FCOS domains, general mechanism and complete
status still require evidence. R96 stays empirical/incomplete in the
incumbent; cached successes do not close the full bit-exact goal or authorize
an experimental paper/PDF update.
