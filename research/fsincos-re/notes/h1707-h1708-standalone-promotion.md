# H1707–H1708: default standalone promotion

2026-09-05. Explicitly authorized by the user after the 81/81 frontier and
retained-corpus success. Standalone FSIN/FCOS arithmetic is now default-on;
the LaTeX paper contains the confirmed program. Paired FSINCOS is unchanged
and remains a separate required implementation/validation task. The full goal
is active; this is a standalone milestone, not three-instruction closure.

## What changed

`src/fsincos_skylake.c` defaults `G_GENERAL_STANDALONE=1`, `G_ROUND84=0`.
The standalone entries use the fixed H1630 polynomial, H1633 table and H1638
tiny program. Historical ledger, fitted selector and history corrections
remain as inactive research source, not components of the promoted route.
Existing code comments are preserved. Native ROM/constants are unchanged.

The new headers in `src/general/` preserve the experimental arithmetic
byte-for-byte. Only a promotion comment, C1 export and opt-in diagnostic guard
are added. `--general-trace` enables numerical metadata; the default CLI is
quiet. This is a value-level interface, not a complete architectural state API.

A dedicated active-entry bit is essential: the old paired table path sometimes
sets the historical standalone flags internally. Gating solely on those flags
would inadvertently alter paired FSINCOS. The new bit is saved/restored around
actual standalone entries. Paired entry source and its numerical schedule are
not promoted. The raw encoding guard precedes numerical canonicalization.

Normal build: `make -C fsincos-re/src all`. Use `--batch` with
`--fsin-standalone` or `--fcos-standalone`, plus `--rc=rn|rd|ru|rz`.
The restricted `general-candidate` target packages the same promoted source;
its wrapper rejects experimental or conflicting arguments and excludes FSINCOS.
The builder now pins the promoted source/headers directly, rather than applying
historical experimental hooks to the old source.

## Validation, without hardware recapture

H1707 first checked the original packaged graph. H1708 then independently
rebuilt the promoted default translation unit and scored the same authenticated
72 retained bank/mode inventories against raw hardware:

| Scope | Output appearances | Applicable C1 | Misses |
| --- | ---: | ---: | ---: |
| Polynomial | 723,546 | 723,546 | 0 |
| Table | 2,472,906 | 2,472,906 | 0 |
| Tiny | 182,535 | 182,535 | 0 |
| Special/range | 30 | 0 | 0 |
| Total | 3,379,017 | 3,378,987 | 0 |

All 81 external incumbent-frontier rows over 79 operands and all 53 retained
legacy tuples match the archived candidate outputs and metadata. They are not
remaining candidate misses. Retained bank appearances overlap; no unique or
fresh-observation count is inferred, and these are not a rerun of the complete
historical 182,737,480-result suite. Historical excerpt/positional provenance
limitations remain in the component records.

The promotion audit uses 4,799 software operands covering source-bank samples,
signed finite ranges, high reduction exponents and special encodings:

- 153,568 output/metadata equalities against the archived candidate across
  O0/O2/O3/UBSan, both instructions and four modes.
- 38,392 equalities through the normal, quiet default executable.
- 19,196 paired FSINCOS equalities against the pre-promotion C source.
  These establish isolation, not paired hardware correctness.
- Six build selftests pass. The restricted wrapper's 12 rejected-argument
  checks and its help/selftest checks pass.
- 93 compiler warnings remain; the warning multiset equals the old build's.
  There are zero newly introduced warnings. This is not a warning-free build.

A separate authenticated raw replay of the already-opened H1641 and H1694
campaigns passes 7,056 outputs and 5,136 frozen C1 predictions. All four RC
modes and PC24/53/64 tuples are retained. This reuses labels; it adds no new
hardware observation or prospective credit. Unknown fields stay unscored.

The actual Makefile-built canonical CLI is additionally rechecked on all
3,379,017 retained outputs and all 134 frontier/legacy appearances: zero
differences and quiet stderr throughout. See `canonical_cli.json` and
`h1708_canonical_cli_regression.py`. The stdin-source audit executable and
file-source Makefile executable need not have identical binary hashes
(assertion source strings differ); runtime parity, not an unsupported byte-
identity claim, is recorded. This third replay adds no unique hardware credit.

The original independent rational/integer component checks and fixed-before-
capture challenges remain the generalization evidence: H1624 passes 1,668
fresh outputs/C1; H1641 passes 6,432 outputs and 4,512 frozen C1; H1694 passes
624 outputs/C1 and completes the specified 672-key exact-center union. Read
their original scope/provenance notes. Promotion changes no arithmetic to fit
these observations. Domain/width/reducer/conversion/route certificates support
implementation correctness, not an assertion of recovered physical circuitry.

## Evidence anchors and reproducibility

Artifacts live under `tmp/ledger33/current/`:

- `h1707_packaged_candidate_regression/report.json`:
  `c4f29f7d95055a786d023f0ad21098611eaf7e2db964a19f3e7cb0f822e0870e`.
- `h1708_default_promotion/report.json`:
  `e047633abe3d59bf08fe63132068e9991950071568f2a851e2820719d37b4685`.
- `h1708_default_promotion/opened_boundaries.json`:
  `bbb51920b4556a0f3ecaf904a1b0df11745e086858e15ee3dfb66d7653511780`.
- Promoted main C:
  `e1e88e4ffa53f01f23ce11f678a17c5a9a699774decca632ecab072862b59029`.
- Pre-promotion main C:
  `0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.

`h1708_pre_promotion/` preserves the exact preceding main source, Makefile,
builder and paper source/PDF/README. Old experiments pinning the previous C
are historical: do not rewrite their hashes or imply they verified today's
source. The H1708 report records new binaries and all input/capture hashes.
Use `h1708_verify_promotion.py` with a new output directory for a software-only
replay; `h1708_opened_boundary_regression.py` requires a new output filename.

## Paper and continuation

The paper now states the general multiply/add operators, distinct terminals,
exact integer reducer, table reconstruction and tiny predecessor law. The
obsolete R96-as-current narrative and exploration chronology are replaced by
confirmed results, an explicit historical-evidence boundary and a brief record
of bounded selector falsifications. The pre-promotion text is preserved.
In particular, no statistical argument is called proof that deterministic
FSINCOS cannot be an operand function. No speculative mechanism is promoted.

The user's clarified objective accepts strong black-box numerical evidence,
not exhaustive input enumeration or proof of hidden circuitry. Do not restore
undefined condition bits, full pointer registers, obscure restore histories,
or cross-CPU parity as completion gates. Next: independently reconstruct and
validate paired FSINCOS. The runnable standalone C milestone is delivered;
optional source isolation or embedding API polish must not become a new
numerical completion gate. Preserve the general arithmetic and localize actual
new misses.

H1706's unexecuted PC01 harness is paused, not the mandatory next campaign.
All opened campaigns stay closed; H1688 reservations and unresolved private
history matches remain reservations. H1685 is paused and H1670 held. No private
material, new hardware, remote campaign or new label was accessed for H1708.
Standing remote authorization remains in effect for properly audited fresh
campaigns. The one selected reference is Xeon 45.32.204.118; i7 142.132.217.24
is authorized but parity is not required.

## Final integration checks

Canonical build and both emulator selftests pass. New Python scripts compile;
tracked diff and new-file whitespace checks pass. Existing warnings are
explicitly compared above, not ignored as a clean build. The LaTeX paper
builds with Tectonic without warnings, undefined references or overfull boxes.
All ten rendered pages were visually inspected using the PDF skill, with
the final changed pages re-rendered and checked. No active capture, solver,
build or regression process remains at this checkpoint. No files were deleted
and no commit was made.

Final canonical CLI report SHA256:
`1ce069107684ce62238235085d7d9e8ad37360c5ab23f9eef4613466740bc112`.
Final LaTeX SHA256:
`8fd12c838188899cb53db14baec7a9c60265feca0a878cf1020cc0ec8b60ac01`.
Final PDF SHA256:
`abd2ce6199d771123c8eaadd89f9739300b17aa83fca0f22ec571c3c0946d262`.
