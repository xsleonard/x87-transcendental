# Independent FPTAN challenge: T0001–T0003

## Confirmed result, 2026-09-06

The unchanged `fptan_ref` implementation passes **495,432 new observations
on each of Skylake and i7**, with zero tangent, pushed-value, C1 or C2
differences. The two complete raw output/status streams are byte-identical.
Stack depths and final balance are verified for every observation.
No algorithm, pseudocode, LaTeX paper or PDF was modified.

| Check | Skylake T0002 | i7 T0003 |
|---|---:|---:|
| Observations | 495,432 | 495,432 |
| Tangent / pushed value / C1 / C2 misses | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Successful FPTAN calls | 355,636 | 355,636 |
| C2 returns, input preserved, no push | 139,796 | 139,796 |
| Complete three-PC comparison groups | 1,916 | 1,916 |
| Three-PC value/status differences | 0 | 0 |

The numerical model's SHA256 is
`490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32`.
Each observation stream covers 122,900 signed operands in RN/RD/RU/RZ.
Every mode has 123,858 observations. PC64 has 491,600 observations; PC24
and PC53 have 1,916 each.

The recorded contexts are Skylake Xeon `00050654:0x1` and i7
`000506e3:0xf0`. This is a two-context result, not proof for all Pentium
descendants. Previous binary64-space trials remain separate evidence;
their billions of observations are not added to this raw80 pack's count.

## Independent selection

The generator does not import, evaluate, or use the candidate's internal
arithmetic. It constructs inputs from directed mathematical bounds and a
frozen raw-bit seed, then freezes the cleared stream before predictions.
This directly addresses the concern that selecting only the candidate's
own internal boundaries could reproduce its blind spots.

1. MPFR bounds at 384 and 768 bits enclose `atan(y)` and pi, with nested
   bounds and optimized/sanitized agreement. Targets include mathematical
   RN midpoints and directed output boundaries. Adding integer multiples
   of pi transfers those boundaries across the argument range.
2. Mathematical `n*pi/2` brackets challenge poles and zeros. Every
   certificate encloses the exact mathematical point between adjacent
   external raw80 values; neighbors and both signs are proposed.
3. Exact floor-sum residue counts and binary subdivision find external
   significands exceptionally close to selected mathematical boundaries.
   This searches a number-theoretic condition, **not** a supposedly
   monotonic hardware-miss predicate.
4. Raw-significand strata cover every generated normal exponent field,
   with separate active-range and large-reduction samples. Thirty-two
   signed windows enumerate every offset from -128 through +128.

The generated pool contains 123,838 distinct signed operands and 2,054
adjacent mathematical-boundary certificates. Mathematical correctness is
used for selection only: the expected silicon result is the unchanged
reconstruction, compared with captured hardware, not an assumption that
FPTAN is a correctly rounded mathematical tangent.

### SMT and exact arithmetic: what is established

Thirty bounded external-significand/period queries were emitted as SMT2.
All original unconstrained Z3 attempts returned UNKNOWN after 500 ms.
Those queries, results and timeout explanations are preserved unchanged.

The independent residue construction found 106 exact external witnesses.
Each is within 2^-16 input ULP of its certified mathematical boundary;
the 768-bit enclosures prove that proximity. Exact integer checks and
witness-pinned Z3 runs establish SAT for 29 of the original 30 queries.
The remaining `a0051-e16` query has no constructed witness under this
bounded search. It is **unresolved**, not UNSAT or unreachable. The search
examined at most eight filtered candidates per query and is not an
all-external-input exclusion.

## Cleared versus generated coverage

Local clearance held 54 binary64-domain operands, 418 possible known
generator operands and 466 public-history/corpus operands. Private history
was checked locally; no private details were exported. Visible public
history audits scanned 7,454 files / 3,120,387,855 decoded bytes on Skylake
and 22,900 files / 18,296,920,278 bytes on i7, with no additional holds.
Unavailable records and unknown raw80-generator seeds remain visibility
limits; fresh means cleared against these recorded checks.

| Admitted primary family | Operands | Observations per CPU |
|---|---:|---:|
| Inverse mathematical output boundary | 5,518 | 22,248 |
| Mathematical pole | 1,202 | 4,856 |
| Mathematical zero | 577 | 2,316 |
| Exact residue boundary | 1,263 | 5,092 |
| Raw exponent stratum | 65,506 | 264,064 |
| Raw active range | 16,295 | 65,700 |
| Raw large reduction | 16,292 | 65,656 |
| Adjacent window | 16,247 | 65,500 |

Families are assigned on first occurrence; overlapping mathematical
certificates need not correspond to distinct external operands. All 212
signed exact-witness instances survived clearance. Both endpoints remain
for 3,361 of 4,108 signed bracket instances. Nine of 32 generated signed
windows remain complete; the other 23 have recorded holes. The admitted
pool spans 32,754 normal exponent fields versus 32,766 generated fields.
Neither removed members nor missing exponent fields receive capture credit.

## Execution and independent checks

The common stream was immutable before candidate prediction. Complete
optimized and ASan/UBSan prediction streams agree byte for byte, with clean
stderr. Each host compiled a public native capture containing exactly one
FPTAN opcode. The guard reserved the complete job before execution;
completed SQLite ledgers report 495,432 observed tuples and pass integrity
checks. No capture was repeated.

The capture starts from FNINIT with masked exceptions and one operand;
records CW, before/after FPTAN status, outputs and post-store status; and
checks TOP transitions. Protocol and scorer mutation tests deliberately
alter mapping, controls, stack state and every predicted field. Synthetic
guard tests verify success, duplicate rejection, failure reservation and
no retry. Exact residue helpers were checked against brute force on 1,000
random small domains. A separate rational-arithmetic audit rechecks every
certificate and witness.

The adapter predicts tangent, pushed value, C1 and C2. It does **not**
predict all exception latches. Hardware sets PE on the 355,636 successful
observations and no exception bits on the 139,796 C2 returns; these complete
captured status words agree across CPUs. That is cross-CPU evidence, not
a full exception-model verification. This normal-finite pool does not
test special encodings, subnormals, arbitrary initial state or unmasked
exception delivery.

## Retained artifacts

- [Corpus v1](corpus-v1/README.md), including hashed inputs and categories.
- `../tmp/fptan-re/t0001-inputs/`: recipe, directed bounds, original SMT2
  queries, UNKNOWN receipts, exact witnesses, window and bracket metadata.
- `../tmp/fptan-re/t0001-clearance/`: local and public-history audit receipts.
- `../tmp/fptan-re/INPUT-CONSTRUCTION-AUDIT.json` and
  `INPUT-COVERAGE-AUDIT.json`: independently checked generated/admitted scope.
- `../tmp/fptan-re/t0002/` and `t0003/`: freeze, preflight, manifest, start,
  completion, captured data, scores and empty miss streams.
- `../tmp/fptan-re/FINAL-VERIFICATION.json`: terminal two-CPU verification.

Numerical source snapshots and predictions are local-only and are
not part of the public corpus. All corpus observations on these two
contexts are already consumed: reuse retained labels rather than recapture.
