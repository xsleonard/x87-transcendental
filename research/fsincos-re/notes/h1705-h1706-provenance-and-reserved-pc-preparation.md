# H1705-H1706: provenance limits and reserved-PC probe preparation

2026-09-05 local date. The previous turn completed conditional planner evidence.
This turn returns to physical-evidence gaps and prepares an isolated PC=01
experiment. No hardware capture, new label, manifest freeze, candidate/default
change or academic paper/PDF update. Full closure remains unproved.

## H1705: structural localization, not semantic clearance

The read-only private audit reproduces the H1697 aggregate exactly:26 files,
6,425,428 bytes and188 nonunique possible syntax/layout occurrences. It now
localizes those occurrences without emitting any private names, contents,
hashes, identifiers or per-operand membership:

- All170 text occurrences are embedded on single lines in four UTF8 files:
  88 possible hexadecimal pairs and82 possible decimal pairs. No match fills
  its entire line. Of these,169 contain a comma,164 are
  followed by another comma/numeric field, and two hex matches touch a decimal
  point. These are context facts, NOT proof that they cannot be operands.
- Comma parsing of the four files yields1,583 rows and three uniform-width
  files. Only one parsed field contains an entire possible pair; the other
  pairs cross comma-field boundaries. No header or column meaning is guessed.
- Six byte-layout occurrences lie in one desktop-metadata-magic file, and12
  in one still-unparsed NUL-containing binary. Recognized magic is not a
  semantic interpretation of the bytes and does not silently dismiss them.
- Two PDFs yield27 nonempty page texts. Neither raw PDF bytes nor extracted
  text has a target occurrence under the checked patterns. This is not an
  image-content or arbitrary-encoding absence claim.

The PDF skill constrained this to local read-only extraction. No PDF was
authored, rendered for publication, changed or re-exported. Private diagnostics
are suppressed on failure; only aggregate context categories are serialized.
Five public synthetic context tests and four magic-category tests pass.

Status is `STRUCTURALLY_LOCALIZED_SEMANTICALLY_UNRESOLVED`. The188 occurrences
are neither verified hardware tuples nor cleared false positives. H1688's
historical reservations and H1697's lack of complement eligibility remain.
The result identifies the remaining formats/record-role work; it does not
authorize any smallest-denormal recapture.

## Historical archive checks

A new bounded read-only connection to i7 `142.132.217.24` times out on port22;
session15555 exits255. The known `/root/h491/specials` archive is not reached.
No remote instruction or file modification occurs on that host.

The authorized Xeon answers. A read-only directory search under `/root`, depth
at most5, finds no directories named `specials`, `h491`, `h638_mirror` or
`fsincos-re`. This is absence under that exact bounded query, not proof that
all remote archives or compressed copies are absent. Local filename discovery
under the current repository and configured worktree directory finds the known
public specials generator/runner, not a newly recovered archive. Missing
records remain missing; there is no new output/status/prestate credit.

These archive checks are terminal, not live recovery jobs. Do not repeatedly
poll their old handles or infer permission to repeat previously reported inputs.
The full goal is not globally blocked on that archive.

## H1706: isolated all-masked PC=01 harness

`capture-kit/x87_reserved_precision_capture.c` is a separate copy of the pinned
H1654 harness. Historical capture sources are untouched. Exact source-delta
checking permits only three changes:

1. A header declaring the probe unexecuted/unfrozen.
2. An active parser that accepts `pc01` as bits0x0100 and delegates standard
   PCs to the unchanged original parser. The included archived main retains
   the original parser and is not on the active main's call path.
3. A stricter input gate requiring all masks3f and pending0.

The instruction sites, signal handler, raw packing, restored-state check and
comments otherwise match H1654 exactly. The target was compiled on the
authorized Xeon, in the new isolated directory
`/root/fsincos-h1706-reserved-pc-build`, using GCC12.2.0 and
`-O2 -std=c11 -Wall -Wextra -Werror -fno-builtin`.
Only the two public C sources were uploaded. The binary was disassembled and
retrieved; it was **never executed**, including for a warmup or selftest.

The source and ELF audit checks each straight-line observation cut:

```text
FSIN or FCOS -> FXSAVE64 -> mark snapshot valid -> FWAIT -> FNCLEX -> return
```

There is no retry/back-edge within either six-instruction cut. The handler
copies the fault context before repairing it solely for safe return, has only
two fail-closed `_exit` calls and no x87/vector instructions. Active main calls
only the two intended once-sites, never the archived included main or older
execution helper. Source-delta and cut checks are not a general machine-code
control-flow, kernel-delivery or silicon proof.

A separate portable C program extracts ONLY the actual two precision parser
bodies and executes16,394 string/integer cases locally. It contains no capture
source include or x87 assembly. PC01 accepts0x0100 only in the new parser;
pc24/pc53/pc64 retain0/0x200/0x300, and rejected strings leave the output word
unchanged. This tests parsing, not physical acceptance of a reserved control.

The numerical/state model still rejects PC01. Parser acceptance is not a model
promotion. PC01=PC64 is a possible experimental hypothesis, not a confirmed
rule or an explanation of silicon. Even successful restoration of CW0100
would not by itself establish instruction-output equivalence.

## Artifacts, replay and checks

Paths relative to `fsincos-re`:

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1705_private_match_context.py` | `c371bd02d8b303d0dfb7cda44361fa4df28fc6bd0fabd78b99ebed7f7f8c1199` |
| `tmp/ledger33/current/h1705_private_match_context/report.json` | `bc8b41cf9a940c30e0a9cfe29b76c2122e0a67be2ec1285654a68c701f563bd4` |
| `capture-kit/x87_reserved_precision_capture.c` | `28459c28ccea803905945f001578fb9f31dc0064872c255eecf52456faad0175` |
| `experiments/h1706_reserved_pc_static_audit.py` | `bd5f1fcbb25860db84f0d84ccde14f3c30a4d28c77999d3087c216698c96df3b` |
| `tmp/ledger33/current/h1706_capture_build/x87_reserved_precision_capture` | `05627412309d580122365eeb88006c9e84de88c1e153d42cb96a1125aabdea4b` |
| `tmp/ledger33/current/h1706_capture_build/capture.disassembly.txt` | `9ebeeb0806cf7d674629afa08e2dd8739a636defe611dbe58846099d898da518` |
| `tmp/ledger33/current/h1706_reserved_pc_static_audit/report.json` | `0068b94be4c1c02ac224d5de781b8950e686e8e11b11c2ca2b6f0e17a6b68b00` |

Remote/local source, ELF and disassembly hashes agree. H1705's full report
replays byte-identically at `/private/tmp/h1705-replay.TDGXmQ/h1705`. H1706's
entire static/parser artifact directory, including the portable parser binary,
replays byte-identically at `/private/tmp/h1706-replay.myacDg/h1706`.
The capture ELF itself is not run by either audit/replay.

Syntax, canonical build, both emulator selftests and tracked diff checks
pass. A later untracked-file whitespace check found an extra blank EOF line
in the frozen H1706 probe; its exact source/binary artifacts are preserved.
At this historical checkpoint, source0339a7d6, headera5e9d085, ROM2189e006,
paper802fb3b6 and README8096a84f
anchors remain unchanged. SCP sessions66936/80785 completed; session15555 is
terminal after timeout. There is no live capture, build, scan or replay.

## Concrete next step

Superseded by the clarified numerical objective and H1708 standalone
promotion. The following PC01 work remains paused, not a completion gate.

Prepare a genuinely fresh PC01-vs-standard-PC bank spanning the existing
numerical domains and raw classes, with output/rounding discriminators and
independent fixed standard-PC predictions. Keep PC01 predictions explicitly
hypothetical. Reconcile public/private/generated history, exclude old operands
conservatively, freeze the selected tuples and all predictions, then use the
ordinary once-only guard under the standing Xeon authorization. Do not execute
the current bare harness before those steps. No bank/manifest/runner exists yet.

This can address an unsupported-control gap without reopening old small inputs
or the deferred summary-state tangent. H1685 remains paused and H1670 held;
all opened campaigns stay closed. All81 external incumbent-frontier outputs
remain candidate-matched, with no new candidate numerical miss. Full numerical/
state silicon closure remains active and unachieved; no claim is promoted into
the academic paper or production defaults.
