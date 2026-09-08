# H1614–H1617: a fixed asymmetric-power candidate survives cached direct tests

Date: 2026-09-04. **Candidate, not confirmed silicon closure.** No emulator
default, academic paper/PDF, hardware capture or private-ledger change.

The fixed numerical program below matches **150,351 distinct recorded
mode/input observations over 37,823 positive direct-FCOS operands**, plus
all 27 available C1 constraints. An independently spelled graph and separate
integer quantizer reproduce the result. These are previously opened captures,
not fresh blind validation. The 52 exact reduction aliases remain untested
under the new program; other domains and complete status behavior remain open.

## Fixed formula

Let `T_p` be magnitude truncation to p normalized significant bits, and `R_p`
be nearest-even at that precision. Coefficients C1…C6 are the unchanged native
P5 cosine constants pinned by the H1592 arithmetic specification.

```text
S = T67(x*x)
F = T67(S*T64(S))
N = R64(C1 + T67(F*R64(C3 + T67(F*C5))))
P = R64(C2 + T67(F*R64(C4 + T67(F*C6))))
L = T67(S*N)
R = T67(F*P)
C = T67(L+R)
Y = architectural_RC64(1+C)
```

No operand table, input classifier, fitted threshold, R59 selector or payload
is present in this candidate. This is the ordinary split graph with an
asymmetric fourth-power input and ordinary terminal arithmetic. It is **not**
an instruction to change just F in the incumbent while retaining its carrier,
payload and final-selector machinery.

For a normalized 67-bit square `S=s*2^e`, write `t=s&7`. Then the raw fourth
product is exactly `(s*s-s*t)*2^(2e)`, followed by T67. This is a fixed integer
recurrence, not a fitted boundary. It is not an exact real-polynomial
regrouping: materializing one input changes finite arithmetic.

## Why this is outside the preceding exclusions

H1608/H1609 varied post-operation materialization and exact forwarding;
H1613 let power consumers choose raw or selected values, but both legs of
the fourth operation always used the same version. Neither includes
`S*T64(S)` with a 67-bit S on its other leg. H1610/H1612 likewise changed
result precisions, not the two multiply-input precisions independently.
Same-graph fusion obtained merely by omitting intermediate roundings was
already included by the exact choices; it was not searched again here.

The structural motivation is the existing asymmetric-port recurrence used
in R86/R1378's specific domains, not newly decoded Skylake controls. H1358
already falsified replacing the shared fourth alone: the effective `_pc`
report changes 144/370 old legs and leaves 94 errors. The earlier un-suffixed
H1358 report is an inert build (zero changes), not that falsifier. Both the
historical placement failure and the current candidate's different terminal
composition must be kept in view. No earlier domain gate is assumed to
transfer automatically.

## H1614: broader port family, intentionally unfinished

H1614 implements X=CHOP67, Y=one shared conventional 64-bit rounding policy
at all eight multiplies. Six unequal-operand multiplies each have a fixed
orientation bit. All thirteen output policies independently retain the
five conventional-or-exact choices. The planned family has 640 orientation/
Y-policy/payload cases. This is a numerical test family, not a recovered
physical-port contract.

The first case—orientation zero, Y=CHOP64, absent payload—admits 51,840
shared vectors on all 36 target operands (64 actual modes, 27 C1 constraints).
Its ordinary original output-policy vector is one of them. That vector uses
CHOP67 at the eight multiplications/correction and RN64 at the four Horner
adds; it was tested before inspecting new regression scores.

The full enumeration was deliberately stopped with SIGINT after H1615's
fixed-vector regression pass, while it was compiling cached-control functions.
It returned exit 130. No completed case verdict had been emitted, and there
is **no full 640-case result**. The partial compressed stream and
`tmp/ledger33/current/h1614_asymmetric_multiplier_ports/run-status.json`
are preserved. No hardware observation was interrupted or repeated. Do not
resume this enumeration merely because its full report is absent; prioritize
verification of the fixed candidate.

## H1615: regression gate, not just target fitting

H1615 reconstructs the first case's full target acceptance
function, then uses a counterexample-guided regression procedure. Each failed
shared policy vector would add the full observed-input constraint, not a new
input predicate. The first tested vector is the original natural policy
vector above, not the lexicographically first fitted witness.

That first vector passes all 370 old high-q observations over 261 operands,
then all 149,764 H1603 control observations over 37,441 operands. Combined
with target modes, the checked tuple union is 150,198. The lexicographic
target witness is also recorded, but **only the natural vector** receives
this complete regression pass. The 51,840 still-unrefuted target assignments
are not all certified on the control bank. H1603 remains an old
model-selected endpoint-visible bank, not fresh or unbiased validation.

Selftests cover 4,160 independently spelled rational stages, 2,560 input-width
checks, 320 disabled-port graph identities, 320 ordinary asymmetric fourth
identities, and the inherited quantizer/diagram tests. The complete target
diagram and every actual regression replay are retained. Report, policy
certificate and compressed replay reproduce byte-for-byte in a separate run.

## H1616: independent graph and wider direct bank

Production arithmetic is separately written and uses H1604's independently
implemented normalized integer quantizer, not H1614's port, graph or rounding
functions. Positive final RC and external encoding are also implemented
separately. Exact signed-dyadic addition/multiplication and the coefficient
values are shared with H1592; this independence boundary is explicit.

The new replay adds the whole current named direct bank, authenticated
historical all-mode observations, and H1363's previously opened 28-row
challenge. H1363 labels are checked against all original input/output streams
and pinned score hashes; no labels are newly opened.

| Source membership | Actual mode/input rows | Output misses |
| --- | ---: | ---: |
| Current named direct bank | 82 | 0 |
| H1091 historical all-mode bank | 116 | 0 |
| H1315/H1326/H1352 old high-q banks | 370 | 0 |
| H1363 previous blind bank | 28 | 0 |
| H1603 cached control bank | 149,764 | 0 |

Nine duplicated tuples agree, giving **150,351 unique observations over
37,823 operands**. All 27 actually recorded C1 constraints pass; missing C1
is unknown, not zero. This does not establish the full status word.

All 150,198 earlier predictions agree independently. All thirteen stages for
the original 36 targets agree numerically (468 equalities). The independent
quantizer passes 30,660 tests; 2,000 inherited Boolean-range checks also pass.
The report and complete compressed per-operand stage/output stream reproduce
byte-for-byte. There is no C execution or assumed alias projection in H1616.

## H1617: general numerical equivalence to one effective input cut

Under the fixed natural output policies, every multiply result has at most
67 significant bits and every Horner-add result at most 64. External x has
64. The literal C5 has 59 significant bits (67-bit container, eight trailing
zeros); C6 has 64 (67-bit container, three trailing zeros).

Consequently all X=CHOP67 cuts are identities, and every Y=CHOP64 cut is an
identity **except square feeding fourth**. In topological order, removing
those identity cuts preserves each later exact operation and rounding. This
is an inductive numerical-program equivalence for the stated input domain,
not a silicon-correctness theorem and not an equivalence for arbitrary H1614
policy choices. It proves the displayed simpler formula represents the
natural all-port candidate without relying on how well it fits the captures.

The simplified program also reproduces all 491,699 saved stage values and
150,351 observed outputs across the 37,823 operands. Its report reproduces
exactly in a separate run.

## Artifacts and reproduction

All paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1614_asymmetric_multiplier_ports.py` | `fa8bd43d0d6f5b0a4a7c6cb71f70ad6b99672c99f67b3ed88a9dbef994e5f52a` |
| `experiments/h1615_asymmetric_port_regression_gate.py` | `7b2d53b5ca3bc2888ba0d79b384209ccd596ceafdcd781f5399f833667a81e95` |
| `tmp/ledger33/current/h1615_asymmetric_port_regression_gate/report.json` | `dcc1f291289c1423f5b4426f21dccd1b741251a217ac3d1a1db8f9c5860275b7` |
| H1615 `policy_certificate.json` | `7449411fd6a1df6945a44b5323b5ce9e5c5eef9bef0100d67aa38f52b9a81a55` |
| H1615 `witness_regression_replays.jsonl.gz` | `b15e1c16ccbc52ae45a4a35ce297367a3b389f6d84b24fbfceea43b2621554cc` |
| `experiments/h1616_independent_asymmetric_direct_audit.py` | `407883c2e4e25c55ab66a41f4e1d1b3960ea5b3ac1fe42f8acecd29930944d6e` |
| `tmp/ledger33/current/h1616_independent_asymmetric_direct_audit/report.json` | `51f70688d18c6fcc0aa524b9cbf8da9f631f5ea4a86079d7397173b1fd77e3c4` |
| H1616 `independent_direct_replay.jsonl.gz` | `1005ae7ec625589250d75b7761b4481355a9b1fab67d2041e94f6d51aa0745de` |
| `experiments/h1617_asymmetric_width_reduction.py` | `179c24db05a6ca8935d7b5b86658ffd518de1a5ac43b0f6f13c92d7c72e7a97d` |
| `tmp/ledger33/current/h1617_asymmetric_width_reduction/report.json` | `38f763ecb098758c47475efaa1cd0877a0f4fe67a3c6f52d1a4498ed2d5cb6fa` |

```sh
python3 fsincos-re/experiments/h1615_asymmetric_port_regression_gate.py \
  --root fsincos-re --output-dir NEW_REGRESSION_OUTPUT
python3 fsincos-re/experiments/h1616_independent_asymmetric_direct_audit.py \
  --root fsincos-re --output-dir NEW_INDEPENDENT_OUTPUT
python3 fsincos-re/experiments/h1617_asymmetric_width_reduction.py \
  --root fsincos-re --output-dir NEW_EQUIVALENCE_OUTPUT
```

These refuse existing output directories and consume pinned authoritative
predecessor artifacts. Syntax, build/selftest, whitespace and diff checks
accompany integration. H1614's unfinished exhaustive command is deliberately
not the recommended next action.

## Required next gates—do not call this solved

H1618 subsequently completes gate1 below: the isolated C graph passes all
150,403 cached outputs, including all52 exact reduction aliases, with
independent stage/sign/RC checks. See `h1618-isolated-cosine-transfer.md`.
Gates2–4 remain open; this update does not change the original H1614–H1617
artifacts or promote the candidate.

Later H1619–H1621 complete the listed broader raw-bank checks in gate2,
without establishing all remaining domains or changing this fixed candidate.
Read their current handoff entry before repeating any cache wall. Fresh
adversarial validation and the general mechanism/full-status gates remain.

1. Build an isolated implementation of this exact fixed graph, preserving
   ordinary terminal arithmetic and omitting the incumbent's selector/payload
   rather than changing only F. Cross-check its stages/outputs, then evaluate
   all 52 already-opened exact reduction aliases with correct sign/RC handling.
2. Score the broader retained hardware corpora, not only the H1603 selected
   wall, and establish the supported domain. The current proof/audit is only
   positive normal direct FCOS in `[1/8,1/4)`; do not infer FSIN or other bins.
3. Design fresh adversarial disagreements and agreement controls against this
   fixed program. Audit full tuples against repository and private local
   capture history, freeze predictions, then observe each fresh tuple once.
   Standing i7/Skylake authorization is already granted; no recapture needed.
4. Verify complete required status behavior and the general mechanism before
   promotion or any academic paper/PDF update.

The unmodified incumbent still has the recorded direct 45/44 and external
75/74 frontier, and R96 remains empirical/incomplete. The candidate's current
cached direct success is not a source-level closure. Canonical C remains
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`,
speculative selectors remain off, and the full bit-exact goal stays open.
