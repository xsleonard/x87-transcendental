# H1714 — fresh rounding-boundary challenge, 2026-09-05

## Result

**No new miss.** The promoted, unchanged FSIN, FCOS and FSINCOS programs
match all **73,248 numerical outputs** and **54,936 C1 indicators** from
**54,936 fresh instruction/RC/PC/raw80 tuples** on the selected Skylake Xeon
(`45.32.204.118`, family 6, model 85). There are 1,526 distinct signed operands,
18,312 executions per instruction, all four RC modes and PC24/53/64.
All capture-control, C2-clear and essential stack-mapping checks also pass.

This is additional prospective falsification evidence, not exhaustive input
enumeration, physical-datapath uniqueness, or a proof that no further miss
exists. The main algorithm, constants, LaTeX and PDF were **not changed**.
Boundary targeting belongs only to the test generator; it adds no fitted
branch to the algorithm.

## Why these inputs are adversarial

1. **Inverse final-rounding brackets.** A passive accumulator probe in an
   analysis-only copy of the current C model bisects cosine's final integer
   and half-ulp thresholds separately for the paired and standalone graphs.
   It covers every polynomial binade from exponent -32 through -3. The two
   returned operands are adjacent external 80-bit numbers; an independent
   exact-rational implementation checks that their pre-store values bracket
   the same threshold. This certifies local brackets, not global monotonicity
   of the quantized graph. There were 235 bracket certificates before
   freshness filtering; 232 complete pairs survive it.
2. **Exact ties and very small margins.** Among retained positive
   graph/operand certificates there are 27 exact half-ulp ties, 19 exact
   representable endpoints and 173 nonzero distances below 2^-40 ulp.
   These are certificate-event counts, not disjoint operand counts. The
   closest nonzero margin is **3/2^66 ulp**: standalone cosine at
   `3fdf:ddb3d742c265539e`, just below its independently certified final
   half-ulp threshold. These distances refer to the fixed behavioral graph's
   exact pre-store value, not to mathematical cosine or an observed internal
   silicon signal.
3. **Software-mined final boundaries.** One million software operands were
   screened: 500,000 upper-polynomial inputs and 500,000 stratified direct
   table inputs. Selection ranks closeness to the final integer/half-ulp
   boundaries of both lanes, then adds immediate input neighbors. Table
   sampling is not uniform in the full reduced lattice, and the normalized
   scanner key is only a ranking key; the selected margins are recomputed
   exactly by the independent rational implementation.
4. **High-quotient and signed transport.** Modular congruences construct
   external operands with exactly specified 65-bit reduction residuals,
   using external exponents 0, 4, 16, 32, 48 and 62 and both residual signs.
   Where that residual exactly equals its direct seed, the relationship is
   an exact preimage (62 signed operands). Otherwise it is explicitly a
   nearby residual bracket (428 signed operands), not an isomorph. Seven
   bounded lift attempts found no witness within the chosen search window;
   this is not an unreachability result. Every selected operand also gets
   its sign-reflected counterpart.

The final hardware bank contains 1,300 polynomial and 226 table operands.
It covers all 30 polynomial binades and table rows b=18,26,30,36,52. This new
campaign does not cover b=22 or b=44; their prior retained validation is not
being counted as fresh H1714 evidence. Each instruction has 15,600 polynomial
and 2,712 table executions. No tiny, exceptional-value or arbitrary-state
extension is claimed by this particular campaign.

## Independence, freshness and one-shot discipline

- All 1,536 proposed signed operands were checked against the independently
  implemented rational/integer specification in all instructions and RCs:
  18,432 software instruction rows / 24,576 output lanes. The native constants
  remain shared pinned evidence; they were not independently recovered anew.
- Public history checks conservatively rejected five significands, removing
  ten signed operands regardless of instruction, exponent, RC, PC or host.
  Existing unopened reservations remained reserved. Local private text,
  compressed-text, numeric, raw80, UTF16 and PDF-representation checks found
  zero possible matches. Only aggregate private findings are retained; no
  private identities, contents, hashes or membership lists are published.
  This is a local-visibility audit, not a claim about encrypted/image-only
  or arbitrarily generated history.
- Immediately before freeze, independent predictions were recomputed and
  both the actual default binary and the current UBSan binary replayed the
  eligible bank: 36,624 compiler instruction checks. The scorer passed
  54,936 synthetic rows and detected 347,928 deliberate mutations.
- Freeze: `2026-09-05T13:29:35.022328+00:00`. The already inspected and pinned
  capture ELF was reused without warmups or selftest executions. Its one
  opcode site per instruction is followed by FWAIT and the common FXSAVE
  block. The atomic output-directory guard prevents a second execution.
- Actual capture began `2026-09-05T13:30:42Z` and finished
  `2026-09-05T13:30:43Z`: one observation per tuple, **zero retries**.
  `transfer-tests/h1714/OPENED.json` and the remote marker both say
  `OPENED_ONCE_DO_NOT_RERUN`. Local/remote FREEZE, OPENED, score and raw-output
  hashes were checked equal. The remote kit is
  `/root/fsincos-h1714-rounding/kit`.

A separate post-freeze, pre-label **software-only** diagnostic compared the
pre-existing all-Horner-cuts alternative with the promoted minimal paired
program. They agree on all 6,104 operand/RC rows. That diagnostic is not a new
selector, was not part of frozen hardware predictions, and adds no claim of
physical or universal equivalence.

## Reproducible evidence

Software generation and certificates:

- `experiments/h1714_rounding_boundary_scan.c`
- `experiments/h1714_build_rounding_scan.py`
- `experiments/h1714_rounding_challenge.py`
- `tmp/ledger33/current/h1714_rounding_scan_v2/`
- `tmp/ledger33/current/h1714_rounding_challenge/bank.json`
- `tmp/ledger33/current/h1714_rounding_challenge/boundary_certificate.json`

Freshness, freeze, capture and scoring:

- `experiments/h1714_freshness.py`
- `experiments/h1714_freeze.py`
- `experiments/h1714_score_capture.py`
- `tmp/ledger33/current/h1714_freshness/report.json`
- `transfer-tests/h1714/` — immutable frozen predictions and opened raw capture
- `tmp/ledger33/current/h1714_score/report.json` and `misses.json` (empty)

Key SHA256 values:

| Artifact | SHA256 |
| --- | --- |
| Proposal bank | `b276ca32af0c9f1d9834d6eda9e7a4e9b02ebfbcd9517edf649ee0b73edce776` |
| Boundary certificate | `705dd657fdcf512608b73688a527ebc05e96992780c1aaa22f2bc2345fad3cf4` |
| Freshness report | `af3af42f3d49b320b0b3f88f651a569ff6780dfda51b8619fd2520d7e6ca1c5a` |
| FREEZE | `e5bfa95ffde09a8756fb7912d3d919b574a35ba277628bb3fd1ae53eb42c1563` |
| Manifest | `a0f8bd548574e18738f5ccf9af960eb5c3450e4fb208bac3f0790d9e7446851d` |
| Raw capture | `a8ae65c2136185adfa179c9095f9ec1fb1bb67e338549cfc7409092265358430` |
| Score | `977c89220c17f59578cbf9f9fec9fd47d98b4947eecd20bb9273c370553955b9` |
| OPENED | `dad2fd22ac0d46d97d1ab028ccd18c76fed7e67abf12ff30ae2eaad26d83052e` |

Syntax compilation of all five new Python programs, shell syntax validation
of the frozen runner, `make -C src all`, the default software `--selftest`,
and `git diff --check` pass. The initial scanner build failed solely because
the inserted probe preceded the original assert header; its incomplete
`h1714_rounding_scan/` directory is retained. The corrected, pinned build is
`h1714_rounding_scan_v2/`; there was no hardware run from the failed build.

Unchanged source SHA256:
`490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32`.
Unchanged LaTeX SHA256:
`f3b3371287510c834aa02c4f79e25990d2c4fb714c0b112d97bb21786ba5dec6`.
Unchanged PDF SHA256:
`09c3192104cd0a2451d6c77388f3abb21129b39392756c1cacd6af1945b1f790`.

H1713's delivered status is unchanged: no current numerical counterexample
was found. The next distinct adversarial direction would be simultaneous
internal-stage rounding thresholds or a fresh observable that separates
numerically agreeing execution graphs, rather than reobserving these tuples.
