# H1713: paired promotion and numerical-goal completion audit

2026-09-05. The prior goal turn made concrete progress: H1712 supplied fresh
adversarial paired evidence. This turn promotes the validated minimal graph,
verifies the actual main executable and updates the confirmed academic paper.
No hardware, private data, new labels or remote operations were used this turn.

## Delivered implementation

`src/fsincos_skylake.c` now defaults both `G_GENERAL_STANDALONE=1` and
`G_GENERAL_PAIRED=1`, with `G_ROUND84=0`. The paired entry immediately invokes
the fixed program in `src/general/paired.h`. Historical bodies remain isolated
source; no operand ledger, learned selector or history correction is evaluated
on the promoted routes. The native ROM is unchanged.

The minimal graph has four RN64 exact product-plus-coefficient Horner steps
on each arm, then CHOP67 of the last product before the K1 RN64 addition.
Both arms share CHOP67(r*r). Sine uses CHOP67(RN64(p*S)*r), cosine CHOP67(q*S),
then the respective leading term, exact phase/sign mapping and final RC64.
The external cosine lane supplies the numerical C1 observer. Shared table,
tiny, reduction and encoding arithmetic is unchanged. Special C1 remains
explicitly unclaimed; this is not a full architectural-state interface.

Only nine lines were inserted into the preceding main C: the paired default,
prototype/comment, early entry dispatch and new header include. No existing
main-source line or comment was removed. The new paired header eliminates
the experimental schedule choice, combines the independent p/q loops, renames
the functions and exports C1 metadata; its numerical graph is the H1710
minimal graph. The three standalone kernel headers are unchanged and their
arithmetic identity to the original component programs is reverified.

Build and use from the repository root:

```sh
make -C fsincos-re/src all
fsincos-re/src/fsincos_skylake --selftest
fsincos-re/src/fsincos_skylake --batch --rc=rn
fsincos-re/src/fsincos_skylake --batch --fsin-standalone --rc=rd
fsincos-re/src/fsincos_skylake --batch --fcos-standalone --rc=rz
```

Input lines are hexadecimal `sign_exponent significand` raw80 fields.
Plain `--batch` selects FSINCOS; output is `OK sin_se sin_sig cos_se cos_sig`
or `C2`. Single-instruction modes return their one result. RN/RD/RU/RZ are
supported; the numerical operation is independent of PC24/53/64. PC is not a
software mantissa-width override. `--general-trace` exposes optional arithmetic/
C1 metadata; normal output is quiet. Historical experimental CLI options are
not part of the validated interface.

The existing `general-candidate` target remains a restricted standalone CLI,
not a second paired delivery. Its source/header pins were updated; its selftest
now suppresses paired diagnostics. All 12 invalid-option tests plus help and
selftest pass. Main and both exhaustive build targets depend on `paired.h`.

## Current evidence, checked after promotion

| Requirement | Inspected authoritative evidence | Result |
| --- | --- | --- |
| Runnable C for all three instructions | Actual Makefile binary; default entry dispatch; selftests and batch execution | Delivered |
| Preserve standalone solutions | Unchanged headers, 200,768 compiler-isolation rows, full main-output/C1 regression | No regression |
| Resolve the standalone frontier | H1713 frontier file: 81 frontier and 53 legacy rows | Zero output/metadata misses |
| Validate paired independently | Separately implemented integer/rational graph; 6,274 software operands at four RC modes and O0/O2/O3/UBSan | 100,384 instruction rows / 198,592 lane outputs pass |
| Retained standalone regression | 72 authenticated bank/mode inventories; actual quiet main stdout plus equivalent trace build | 3,379,017 outputs / 3,378,987 C1 pass |
| Retained paired regression | 15 retained banks scored against raw hardware by the actual main binary | 23,838,534 lanes / 11,919,267 cosine-bound C1, six C2 pass |
| Fresh adversarial paired evidence | Immutable H1712 freeze/raw/OPENED and current main replay | 13,800 tuples / 27,456 outputs / 13,728 C1 / 72 C2 pass |
| Prior fresh standalone evidence preserved | H1624/H1641/H1694 component records and H1713 opened boundary replay | Replayed 7,056 outputs / 5,136 frozen C1 pass; no recapture |
| General rules rather than exception fitting | Fixed paired/standalone arithmetic, native ROM, exact structural dispatch, no new operand constants in the promoted header | Satisfied |
| Domain and implementation reasoning | Established reduction/conversion/helper/standalone bounds; new paired interval certificate | All 30 paired polynomial binades, 600 operation bounds pass |
| Relevant RC/PC, sign and reduction behavior | H1712 all four RC and PC24/53/64; direct/reduced signed discriminators and domain controls; prior standalone campaigns | Preserved and independently tested |
| Confirmed paper, not an ongoing notebook | Updated LaTeX, clean Tectonic build, 12 rendered/visually checked pages | Delivered |
| Capture/privacy/preservation rules | No new capture/private access; H1712 immutable; pre-promotion backups; diff inspection | Preserved |

The counts are retained appearances and software checks where stated. They
are not summed into a unique-input count or credited as fresh captures.
H1712 originally ran once per new tuple on the selected Xeon, family 6/model
85/stepping 4. Its 750 predecessor failures (558 sine, 150 cosine, 66 C1,
overlapping) all select the frozen new predictions. The current candidate has
no known miss in this evidence. The old full 182,737,480-result suite is not
claimed as newly rerun. Historical i7 invalid-encoding evidence is explicitly
labeled historical in the paper, not assigned to the new Xeon campaign.

### Domain argument and representation boundary

Exact M66 reduction, quotient/sign/phase mapping, conversion grids and tiny/
table contracts are reused unchanged from the previously checked program.
In the paired polynomial domain every input has a normalized 64-bit carrier.
The new exact interval analysis includes the initial native 67-bit coefficient
times 67-bit square, all signed product-plus-coefficient alignments, terminal
products and final C1 re-encoding. At most 205 accumulator bits and a 137-bit
alignment shift are needed; scale bounds are -229 through -72. Final prevalues
remain positive and normal, so sign mapping and RC64 have the stated meaning.

This is source-backed graph transcription, relying on the established helper/
reducer contracts and compiler checks, not automatic formal verification of
the C translation. The independent implementation and fresh hardware challenge
provide separate checks of graph fidelity and silicon behavior. The all-edge
schedule's finite equivalence does not identify physical fusion. None of these
limitations is silently upgraded into a netlist or exhaustive-input proof.

The scope remains the user's general numerical algorithm on one reference
Pentium4-or-newer CPU. Full pointers, undefined flags, obscure restore state,
unmasked-delivery machinery and multi-CPU parity are not new completion gates.
Optional library/API/source isolation is packaging work, not a missing formula.
Future counterexamples require revising the general rule, never hiding them
with a captured-operand patch. Existing unopened reservations stay reserved.

## Verification details and artifacts

H1713 uses `h1713_promoted_regression.py` for the actual main standalone/paired
censuses, `h1713_verify_promotion.py` for independent/compiler/isolation and
opened-H1712 checks, and `h1713_paired_carrier_bounds.py` for interval bounds.
The first compiler verifier attempt stopped on an overly strict no-stderr
selftest assertion: trace-enabled paired selftests emit two signed-zero
diagnostic lines. No numerical test failed. That incomplete output directory
is preserved. The verifier now explicitly checks those two lines; the clean
default and restricted selftests remain quiet. Successful artifacts use
`h1713_promotion_checks_v2/`.

All four compiler builds have the same 93 historical warnings, with zero new
diagnostics. No claim of a warning-free C translation unit is made. Both
existing model selftests, syntax checks, restricted CLI tests and diff checks
pass. The paper had one initial overfull line in Availability; shortening the
filename list removed it. The final PDF has no TeX warnings. All 12 pages were
visually reviewed; the final wording correction changed only pages 1 and 3,
which were rendered and reviewed again. The other ten page images are
byte-identical to the reviewed render.

Pre-promotion source, main binary, Makefile, paper source/PDF/README, standalone
builder and restricted wrapper are preserved under
`tmp/ledger33/current/h1713_pre_promotion/`. H1708's older archive is untouched.
No unrelated work was reverted, no comments deleted, no files deleted and no
commit created. The main-source diff contains only the nine intended additions.

| Current artifact | SHA256 |
| --- | --- |
| `src/fsincos_skylake.c` | `490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32` |
| `src/general/paired.h` | `3eb199714a2a6d2b67f501ab11a80427d7f389df4df43ed9a6a68329db151454` |
| `src/fsincos_skylake` | `07f8d3ce19ff368ae57573294e2e0c134bca7d94369ef182599d3562d9e1af8f` |
| `tmp/ledger33/current/h1713_paired_regression/report.json` | `e4d451aa8f8f86a032826ca84a9672c38d5d5113d6291762c675f2e3aa5266cc` |
| `tmp/ledger33/current/h1713_standalone_regression/report.json` | `12ca6d515b1fa9270c345f6292f5418235864aa30d92d37c4e3e52f8b25c3cb2` |
| `tmp/ledger33/current/h1713_promotion_checks_v2/report.json` | `16b54b9b0505088dc29dd2ca3416ba0d5089e6baa2a130c8fc73efc08cc39a73` |
| `tmp/ledger33/current/h1713_paired_carrier_bounds/report.json` | `2b7f8431d615b9aef691fc6bd58af9dfdca360a7f511924b2d5406c02c32a34c` |
| `tmp/ledger33/current/h1713_standalone_regression/opened_boundaries.json` | `874d97067f42828d797b1d85d0d9d0790895653e8f448436cded5f4eb5193e17` |
| `paper/skylake-x87.tex` | `f3b3371287510c834aa02c4f79e25990d2c4fb714c0b112d97bb21786ba5dec6` |
| `paper/skylake-x87.pdf` | `09c3192104cd0a2451d6c77388f3abb21129b39392756c1cacd6af1945b1f790` |

`h1713_completion_audit/report.json` records the final machine-checkable
artifact, requirement and runtime audit. Paper authoring used the PDF skill's
one-time artifact marker, clean build, page rendering and visual verification.
The final audit authenticates the retained inventory's original source hash
against the preserved H1708 pre-promotion archive, and the delivered source
against its separate H1713 hash. The shared pathname is not treated as an
unchanged source epoch. No historical source or capture checksum was rewritten.
