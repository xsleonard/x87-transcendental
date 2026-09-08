# H1656–H1659: one-shot unmasked/pending-state evidence

2026-09-04 local date; capture metadata is UTC. All frozen predictions survive
the 36,864 fresh Xeon tuples, including every predicted output, delivery site,
known status bit and stack/control relation. An independent parser, numerical
program and exception-stage algebra reproduce every result. This is finite
prospective evidence, not all-input silicon closure. Production source/defaults,
H1645/H1652, earlier frozen artifacts and the paper/PDF are unchanged.

H1656 is **OPENED_ONCE** locally and remotely. Never rerun its hardware tuples.
The preceding goal turn made progress through the staged model and audited
capture implementation. This turn completes that campaign and derives a new
default-off underflow completion without rewriting the frozen null predictions.

## Freeze, freshness and execution

H1657's scorer was tested and pinned before hardware. All 36,864 synthetic
valid records pass. Mutations detect 36,864 known-status and prestate failures,
36,768 known-output failures and 11,952 fault-context failures. Ninety-six
unknown outputs and 3,168 partial-status records receive no invented credit;
three malformed records reject. Synthetic data is software testing only.

H1656 replays the H1655 bank, checks all source/binary evidence and searches
compressed public/private history before freezing. All 1,536 operands / 288
significands are accepted with zero prior-visible public or private collisions.
The private audit examines 26 local files; no private names, contents or hashes
are published or transferred. Only the declared H1655 software-generation
directory and new kit are excluded from public history. New mask/state fields
do not exempt old instruction/RC/PC/operand tuples; those narrower keys remain
unique and fresh too. The conservative freshness policy is unchanged.

The 36,864 tuples comprise both instructions, all four RC modes, PC24/53/64,
48 profiles and 16 signed operand/stack kinds. Profiles include all 16
IM/DM/UM/PM combinations (ZM/OM masked), every initial CC pattern, eight
sticky/SF profiles and eight pending profiles including each exception flag.
The exact previously audited H1654 binary executes on `45.32.204.118` in
the isolated `/root/fsincos-h1656-exception-state` directory. Every requested
prestate is checked before the instruction attempt. The atomic output-directory
guard prevents restart, including after partial runs. Execution completes all
36,864 rows with zero retries. The i7 `142.132.217.24` is not used in this
campaign; no unrelated service is touched.

## Frozen results

| Check | Count | Result |
| --- | ---: | --- |
| Requested before state, delivery, CW, TOP, tag and deeper-register checks | 36,864 each | All exact |
| Predicted numerical/raw retained outputs | 36,768 | All exact |
| Known status bits | 36,864 | All exact |
| Completely predicted status words | 33,696 | All exact |
| Original fault-context equality relations | 11,952 | All exact |
| Deliberately unpredicted underflow outputs | 96 | Not counted as passes |

All 12,288 PC groups have identical output, full observed SW/tag and delivery
behavior. This does not prove universal PC independence. The instruction-level
stage counts are:

| Observed stage | Rows |
| --- | ---: |
| Completes without an unmasked fault | 24,912 |
| Old pending fault delivered before instruction execution | 6,144 |
| New unmasked invalid/stack fault, no result commit | 2,304 |
| New unmasked denormal fault, no result commit | 768 |
| New precision fault after result commit | 2,640 |
| New underflow fault after result commit | 96 |

Every pending fault has an invalid after snapshot and a fault snapshot equal
to the original before state. Every newly generated fault is delivered at the
deliberate FWAIT; its fault snapshot equals the earlier no-wait FXSAVE snapshot.
The 11,952 equality checks include CW/SW/TOP/tag, all eight raw registers and
recorded FOP/FIP/FDP. Thus cleanup/signal recovery did not replace the observed
state with a repaired state. No instruction was retried. All observed traps
are the predicted #MF vector16; Linux `si_code` is retained descriptively, not
interpreted as an internal FPU control signal.

H1658 imports neither H1652's transition implementation nor H1657's parser/
scorer. It independently reconstructs raw classes, prestate, priority, new
flags, commit/noncommit and the known-bit masks. All 36,864 records agree with
the original scorer, with zero misses. Its four pinned C builds agree on
49,152 software point evaluations, and the separate rational/integer graph
checks 12,288 points. Point evaluation remains distinct from pending/early
fault semantics: a software point calculation is not credited as executed
hardware arithmetic when the hardware stopped before it.

## New underflow observation and exact scaling candidate

The 96 frozen-null outputs all select `scale_input` among the predeclared
alternatives; unchanged input and mode-directed predecessor alternatives do
not survive. Their C1/C2 are zero, and C0/C3 match preservation. This covers
four significands / eight signed operands in profiles U02/U03/U10/U11 across
all modes and PC24/53/64: 72 observations require normalization shift1 and24
require shift2. It does NOT yet cover the other61 normalization shifts.

H1659's analysis-only completion defaults off. For true-denormal FSIN with
DM masked, UM unmasked and no prior pending fault, it proposes:

```text
s = 64 - bit_length(original_significand)
output_significand = original_significand << s
output_exponent_field = 24577 - s
output_sign = original_sign
C1 = C2 = 0
```

The exponent change is +24576 after normalizing the original raw denormal.
No operand ledger, fitted threshold or rounding-mode selection is involved.
The original H1652 null endpoint remains unchanged when the completion is off;
all 36,864 disabled-completion identity checks pass. Enabled completion matches
the 96 newly observed outputs/full SW retrospectively. Another768 early
denormal full-SW observations match C0/C3 preservation and C1/C2 clearing.
None of these formerly unknown fields becomes a retroactive frozen success.

A separate all-encoding scaling certificate partitions nonzero 63-bit
significands into the 63 intervals [2^k,2^(k+1)-1]. Throughout each interval,
s=63-k and exponent=24514+k are constant; shifting loses no bits and gives
a normalized 64-bit significand. Equality of the power-of-two exponents proves
exact multiplication by2^24576 for the whole interval, not just test points.
The regions cover all 2^64-2 signed nonzero true-denormal encodings, with
output exponent fields24514..24576. This proves the proposed formula's exact
scaling semantics. It does NOT prove silicon selects that endpoint everywhere.

## An explicitly unresolved condition-bit distinction

For unmasked invalid/empty-stack cases, C2 clearing, C3 preservation and the
applicable C1 clearing are distinguished by both initial values. But all2,304
unmasked-invalid cases start with C0=1: mask/profile construction correlated
this bit with the invalid mask. Both `preserve` and `set` therefore survive.
Do not claim physical C0 preservation from these rows. Pending cases do not
execute the invalid operand and cannot fill that missing comparison. Masked
condition-bit coverage is distinct and received its prospective holdout here.

NEXT: fresh unmasked invalid/empty inputs with C0=0, and fresh unmasked
underflow discriminators across additional leading-zero/normalization shifts
and significand boundaries. Freeze the new endpoint/bit predictions before
observing them. Audit exact retained provenance where conservative signature
freshness blocks tiny finite sets; never silently relax the policy or recapture.
Zero/infinity, incoherent ES/B state, reserved controls, complete physical tags/
pointer semantics, remaining exact-center provenance and all-input silicon
equivalence remain obligations. No production promotion or paper update.

## Reproduction and anchors

The scorer preflight and H1657/H1658/H1659 output directories reproduce
byte-for-byte in software-only replay; no freezer or hardware runner is rerun.
Python/runner syntax, build, both emulator selftests and diff/whitespace checks
pass. The remote OPENED_ONCE marker is copied only after checking it was absent.
Canonical source0339a7d6…26f2b and speculative-off defaults remain unchanged.
R96 is still empirical/incomplete; the documented incumbent numerical frontier
is still direct50/48 and external81/79. This is not a new complete incumbent
census. No fixed-candidate miss is found; the full goal is active/unachieved.

All paths below are relative to `fsincos-re`, and digests are SHA256.

| Artifact | Digest |
| --- | --- |
| `tmp/ledger33/current/h1657_scorer_preflight/report.json` | `0598fd4f826862982257ede5fa2d1513e6eb9e7d4576547e68a0355c2d238af5` |
| `transfer-tests/h1656/FREEZE.json` | `5cf29bfe745c0752c6d1f6556517cbd29619f2409c81f1245820c7e67e3050a5` |
| `transfer-tests/h1656/manifest.json` | `abcb6a74b0aed0c0d41468a183f078cb7258ae622f42603e97b1ca94578901b6` |
| `transfer-tests/h1656/hardware-output/state-output.txt` | `1074ffca4a37a5d217247603c3d8439ef2a19238c42612b011b0d30d0dd4d555` |
| `tmp/ledger33/current/h1657_score_exception_state/report.json` | `0cfd3b90654563a10e2edf35d0b13b58ba8c299761edadf55b7d8fffef4fcb6f` |
| `tmp/ledger33/current/h1658_independent_exception_state/report.json` | `57c3d5da389ccd8b2c9a5e762e13ef2437c6ecca18e2805b08e0a345e57cfe4d` |
| `tmp/ledger33/current/h1659_wrapped_underflow/report.json` | `5f4df6828352e787f5f5e5814c2d659d2466ce8c093f92dc3dffd5521f638a04` |
| `experiments/h1656_freeze_exception_state.py` | `1f4b40ec130b051e7303ea98aa804f997e784d69ca569029c2885ddbb085ed61` |
| `experiments/h1656_run_capture.sh` | `1f63d0f13aa86d3f498147084e54a054119fa18033db290dcfcdc74195e3cd96` |
| `experiments/h1657_score_exception_state.py` | `40f7babbf2799a3b268e4888cd277cca159dc53b6602fb4b69e0bde7578b6808` |
| `experiments/h1658_independent_exception_state.py` | `bf17e44e01292a47aea2b334bd0ca12aefd4f56e90132229d41b5afeb6a2e473` |
| `experiments/h1659_wrapped_underflow.py` | `e80ed534a8b1300fe68c6f6e8c9be0fb569797311e4534ebca4f63bb6046b004` |
