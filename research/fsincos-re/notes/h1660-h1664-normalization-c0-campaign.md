# H1660–H1664: normalization and invalid-C0 challenge

2026-09-04 local date. All 53,664 fresh frozen output/full-status predictions
pass, including 22,224 unmasked-underflow FSIN results across normalization
shifts 1–59 and 4,608 invalid/empty cases beginning with C0=0. A separate raw
parser and exact-rational implementation confirm every row. This is a wider
prospective validation of the same scalar completion, not an all-input silicon
proof. Production source/defaults, earlier frozen artifacts and the paper/PDF
are unchanged. The full goal remains active/unachieved.

H1662 is **OPENED_ONCE** locally and remotely: never rerun its hardware tuples.
The preceding goal turn made progress through H1656's state campaign and the
normalization/bias candidate; this turn challenges its explicitly identified
coverage gaps without using new labels to adjust the formula.

## H1660: fixed completion before observation

The isolated `h1660_scalar_state_completion.py` wrapper defaults off. When
enabled, it composes H1652's staged exception model with H1659's exact wrapped
underflow formula and proposes C0/C3 preservation plus C1/C2 clearing on early
invalid/denormal faults. Invalid C0=0 was a deliberately new prediction: H1656
had only C0=1 there. Zero/infinity retain earlier partial masks, and unsupported
control states still reject. No default behavior was silently expanded.

All 36,864 retained H1656 output/full-SW records match the enabled completion;
all disabled-completion comparisons are identities. Those are retrospective
checks only. The new campaign is what supplies prospective evidence for the
previously ambiguous C0 and broader underflow normalization cases.

The underflow formula remains the fixed normalization operation:

```text
s = 64 - bit_length(original_significand)
output_significand = original_significand << s
output_exponent_field = 24577 - s
original sign retained; C1 = C2 = 0
```

This is a shift and exponent bias, not a fitted boundary or operand lookup.
H1659's exact 63-region certificate still proves the formula performs
value ×2^24576 for every nonzero true-denormal encoding. That mathematical
identity is distinct from proof that silicon uses it on every input.

## H1661/H1662: proposals, exclusions and immutable selection

The pre-audit bank contains 2,518 operands and 60,432 proposed tuples.
Normalization probes cover every shift 1–63 using binade endpoints, neighboring
significands, midpoint neighbors and deterministic random interior values.
Invalid probes cross two IM-unmasked configurations (3e/0c), all 16 initial CC
patterns, six invalid/empty kinds, both signs and varying stack depths. Thus C0
is no longer correlated with the invalid mask. Each operand has only one
prestate/mask and both instructions × four RC × PC24/53/64; even the narrower
old instruction/RC/PC/operand keys are unique.

Before freeze, every prediction is recomputed using four pinned C numerical
builds and the separate rational/integer graph. All 60,432 synthetic scoring
records pass; all 60,432 output mutations and C0 mutations are detected by the
pinned raw helper. The scorer, runner, source and target binary are locked
before the first hardware observation.

The compressed public/private audit rejects 141 distinct proposed significands:
122 appear in public history and45 in private history, with overlap. Only
aggregate private counts are published; 26 private files are examined locally,
with no private identities, contents or hashes transferred. Selection uses
freshness only, never observed outcomes. Excluding the declared software-bank
directory and the new kit, the accepted set has zero public/private collisions.
The conservative prior-visible-significand policy is unchanged.

The retained bank has 2,236 operands / 53,664 tuples: 1,852 signed normalization
operands and384 signed invalid-C0 operands. All invalid probes survive, with
192 operands starting C0=0 and192 starting C0=1. Normalization shifts1–59
survive; shifts60–63 do not. Those four shifts correspond exactly to positive
raw significands1–15 (and both signs). Prior visibility excludes them here;
rejected proposals receive no new hardware credit.

The existing audited H1654 binary executes once on the authorized Xeon
`45.32.204.118`, isolated in `/root/fsincos-h1662-normalization-c0`.
Requested prestates are checked before each attempt. The consumed directory
guard prevents retries/restarts, including after partial execution. All53,664
rows complete with zero retries. The i7 `142.132.217.24` is not used in this
campaign, and no unrelated service is touched. Immutable bank/freeze states
remain historical; the OPENED_ONCE sidecar records completion.

## Prospective results and independent verification

| Check | Count | Result |
| --- | ---: | --- |
| Output and complete status word | 53,664 each | All exact |
| Before state, delivery, CW, TOP, tag and deeper registers | 53,664 each | All exact |
| Original fault-context equality | 42,336 | All exact |
| True-denormal FSIN scaled outputs, shifts1–59 | 22,224 | All exact |
| Corresponding FCOS controls | 22,224 | All exact |
| Unmasked invalid/empty probes | 9,216 | All exact |

All17,888 PC comparison groups agree in output/full SW/tag/delivery. Invalid
and empty kinds are unnormal, pseudo-NaN, signaling NaN, empty-normal,
empty-denormal and empty-SNaN. For each kind/instruction,384 rows start at C0=0
and384 at C0=1. All preserve the initial value. Therefore the unconditional
`set C0` alternative is rejected by all4,608 zero-initial cases, while an
unconditional clear alternative is rejected by the4,608 one-initial cases.
This resolves the prior preserve-vs-set ambiguity in these tested paths; it
does not prove every possible mask/history combination has been observed.

H1664 imports neither H1660/H1659's completion functions nor H1663/H1657's
raw parser. It decodes the original subnormal as the exact rational
sig/2^16445, multiplies by2^24576 and independently encodes the resulting
normal value, checking that no remainder is discarded. It recomputes1,852
unique signed scaled operands and all22,224 underflow rows, then independently
checks all53,664 raw output/full-SW/stage/stack records against the frozen
predictions. Its zero-miss result agrees exactly with the primary scorer.

This is not a comparison against mathematical sin/cos rounding: the proposed
microcode bypass/scaling semantics are the object being tested. No candidate
adjustment, threshold, operand ledger, rounding-mode exception or new selector
was introduced after opening the labels.

## Remaining work and verification

Next reconcile exact retained tuple provenance for significands1–15 before
considering any further observation. A prior-visible significand is not by
itself evidence of a particular unmasked tuple, but the existing conservative
policy must not be silently relaxed and no previously observed full tuple may
be repeated. Also retain zero/infinity, incoherent ES/B, reserved controls,
complete physical tag/pointer behavior, remaining exact-center provenance and
all-input silicon equivalence as open requirements. Do not redefine closure
as agreement with these finite campaigns.

H1660/H1661/H1663/H1664 output directories reproduce byte-for-byte in separate
software-only replay. No freezer or hardware runner is repeated. Syntax,
production build, both emulator selftests, diff/whitespace checks and frozen
hash checks pass. The remote OPENED_ONCE marker is verified after copying it
to a checked-absent destination. Canonical0339 source, speculative-off defaults,
empirical/incomplete R96 and documented incumbent frontier direct50/48 and
external81/79 remain unchanged. This is not a new complete incumbent census.
No fixed-candidate miss is found, no production promotion occurs, and the
academic paper/PDF remains untouched.

## SHA256 anchors

Paths are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1660_scalar_state_completion.py` | `ca97e612effca75c47d592e9bdaca360c95f219cee8a736072b623c464dd17c9` |
| `tmp/ledger33/current/h1660_scalar_state_completion/report.json` | `eae6396f2839d2a5dd84542194b44e1337333d234d866d6a0f23b68439d5fbe3` |
| `tmp/ledger33/current/h1661_normalization_and_c0_proposals/bank.json` | `2060d02cb018df0e9a21b25d7a090cda20e1fb57f93dbe1cc8eec5305e3eeb10` |
| `transfer-tests/h1662/FREEZE.json` | `544ab1fb1a62b4d0a9d496077dd829f18ee8cfdff69f7b1bb51fc93828c94a53` |
| `transfer-tests/h1662/manifest.json` | `90ddbdf8ec19f3be57307d061a5812e57734f25b22dc08d66303427a90264e45` |
| `transfer-tests/h1662/hardware-output/state-output.txt` | `5d56fc2803d9a0b4d60ece5d79ab766c7c1e0de660e984eb1c8c69a0aaab6321` |
| `tmp/ledger33/current/h1663_score_normalization_c0/report.json` | `3bcea0b93a77cb8e17c77d25607a1f76ec4806969499687364b3b16c46f486e2` |
| `tmp/ledger33/current/h1664_independent_normalization_c0/report.json` | `31eab946c270bc649b3e4a2bd1825fc3f134dbdcbad5f2971febb14d23733c8f` |
| `experiments/h1662_freeze_normalization_c0.py` | `8ccd9125178cf66a543fbe03b330ce3542146bf028a4d4097c89c25d3e01a579` |
| `experiments/h1662_run_capture.sh` | `48fdbced62d223e2354be1e8161af549c455ddf93c8769d24db6995edfc259c9` |
| `experiments/h1663_score_normalization_c0.py` | `8effa5634c585bb6b3f73493da9ede511fed9b44e669da61c8148bd14f095441` |
| `experiments/h1664_independent_normalization_c0.py` | `137ae7561a3a985e120604b2f82ae5d149c41eb2796acd665d76f7b2997d31a0` |
