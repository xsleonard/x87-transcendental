# H1652–H1655: exception staging and the next observable

2026-09-04 local date. Analysis-only progress toward the full goal, which
remains active/unachieved. No new hardware tuple was attempted, no private
history was accessed, and no manifest was frozen. The Xeon work in this turn
was source copy, compilation, disassembly and read-only verification only.
Production source/defaults, H1645, the paper/PDF and old frozen artifacts are
unchanged. The preceding H1649 hardware campaign remains OPENED_ONCE.

## Why masked output alone is not the unmasked state

Intel SDM089 Vol.1 §§4.9.2, 8.5.1–8.5.2 distinguish pre-computation invalid/
denormal exceptions from post-computation exceptions. With an unmasked early
exception, TOP and operands remain unchanged. Section 8.5.6 allows an unmasked
precision exception to store the result. Section 8.5.5 describes a register
underflow result with an exponent bias of +24576. Sections 8.3.12 and 8.7.1
place pending #MF delivery before a waiting instruction's primary operation.
Section 8.1.3.3 specifies ES for unmasked flags and B mirroring ES.
Source: [Intel SDM](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html),
using the previously authenticated local revision089 text/PDF.

Those distinctions require an exception-stage model, not simply the masked
answer plus an error flag. In particular, scaling an already rounded masked
answer does not recover the unmasked prevalue in general. H1647's numerical
underflow-domain theorem identifies the relevant input class in the fixed
program, but does not prove its unmasked stored value or instruction behavior.

## H1652: isolated candidate, explicit unknowns

`experiments/h1652_exception_transition.py` adds an analysis-only interface.
Its optional condition-write-mask flag defaults to false. With the flag off,
the masked wrapper returns H1645 unchanged. With it on, the H1649-observed
classes use `H1645.status_bits | (before_SW & 0x4100)`, filling previously
unknown exceptional C2/range C1 with zero. Zero/infinity retain H1645's partial
known-bit mask because H1649 did not observe them. This remains retrospective
evidence, not a globally proven status rule or a production change.

The unmasked transition proposal has explicit phases:

1. A coherent prior pending exception returns `MF_BEFORE`, unchanged state,
   delivery at the attempted instruction, without requesting a numerical result.
2. Unmasked invalid or denormal handling returns `MF_AFTER`, retains raw ST0
   and tag/TOP, and sets only the early new flag (plus SF for empty-stack).
   Delivery is predicted at the next wait. Most condition bits stay unknown;
   empty-stack C1=0 is explicit. Empty-stack priority precedes encoding class.
3. Other paths use the fixed masked numerical program and class flags. A new
   unmasked precision event predicts a committed result with pending ES/B.
   Unmasked underflow has an explicitly null endpoint and partial status mask.

Unmasked underflow is confined to true-denormal FSIN in the specified graph.
Three candidate endpoints are retained as discriminators: unchanged masked
input, normalized input scaled by 2^24576, and the scaled leading value or its
64-bit predecessor according to sign/mode. No alternative has been selected
using hardware labels. The scaling helper normalizes the original significand
exactly; it does not claim that scaling is the chip's numerical behavior.

Reserved PC and incoherent ES/B/flags/masks reject rather than being silently
normalized. Their recovery, arbitrary untested state, full physical tags and
instruction-pointer semantics remain part of the goal. The interface is not
a claim of full architectural-state closure.

## H1653: software and retrospective validation only

All 16,128 retained H1649 full-status observations match the opt-in masked
candidate; all 16,128 disabled-wrapper comparisons equal unchanged H1645.
These remain retrospective checks, not additional hardware evidence.

Software checks cover 45,056 clean-initial transitions across 64 masks, eight
TOP positions, two instructions, signs, representative classes and empty/nonempty
ST0. They include 17,408 pre-computation-priority checks and 512 explicit unknown
underflow endpoints. Another 44,352 checks establish that coherent pending
delivery preempts classification/numerical evaluation in the software program.
Three unsupported control/state cases reject explicitly. Exact Fraction checks
cover all 63 true-denormal normalization shifts, two signs and four modes:
504 scaled-endpoint equalities. These prove implementation properties, not
silicon behavior on all inputs or any new unmasked hardware tuple.

## H1654: audited capture path, never executed

`capture-kit/x87_exception_transition_capture.c` installs a Linux SIGFPE
handler and records the kernel's saved FP context before altering anything
for safe return. The three-argument signal interface supplies that saved
context through `ucontext_t`; see [sigaction documentation](https://man7.org/linux/man-pages/man2/sigaction.2.html).
The target's actual glibc header was inspected, and compile-time assertions
check the FP-state size and field offsets.

The input includes masks, explicit CC/sticky flags, pending state, stack depth,
empty-ST0 tag and raw operand. Loading occurs masked. FXRSTOR64 establishes
the requested coherent prestate; FXSAVE64 and comparisons verify it before
the attempted instruction. A failure aborts, without repair or retry.

Each assembler path has six instructions: FSIN/FCOS, FXSAVE64, set A_VALID,
FWAIT, FNCLEX and RET. Pending-at-entry faults skip the transcendental; faults
at FWAIT skip the wait. Both resume directly at cleanup, never at the faulting
instruction. The handler accepts only these two exact instruction addresses,
copies 512 bytes using volatile scalar accesses, records the signal/trap data,
then clears the saved exceptions/masks solely to return safely. The repaired
context is not counted as an observed hardware result. Unknown fault sites or
duplicate delivery terminate the harness. No signal handler prints or allocates.

H1654's static audit pins source, target ELF and disassembly. It confirms the
six-instruction sequences, no retry edge, the copy before cleanup, no vector/
x87 handler instructions and only two fail-closed `_exit` library calls.
The active main does not call the archived included H1400 main/execute routine.
Recorded cuts: FSIN 0x1870 / snapshot0x1872 / wait0x1880 / resume0x1881;
FCOS 0x1890 / snapshot0x1892 / wait0x18a0 / resume0x18a1 (ELF-relative).

Build: GCC12.2.0 on Xeon45.32.204.118 with O2, C11, Wall/Wextra/Werror and
fno-builtin. Remote directory `/root/fsincos-h1654-exception-state` contains
only the two sources, binary and disassembly. Read-only checks confirm no
inputs, freeze or hardware-output directory. The binary is NOT selftested or
run, and must not be run on old tuples for harness validation. Static auditing
does not validate actual signal delivery; fresh campaign observations must do so.

## H1655: proposed discriminators, NOT frozen or freshness-audited

The software-only bank contains 1,536 unique operands / 288 significands and
36,864 proposed full tuples. Each operand receives exactly one prestate/mask,
then both instructions × four RC × PC24/53/64. Even old narrower instruction/
RC/PC/operand keys remain unique. The 48 profiles cover all 16 IM/DM/UM/PM
combinations (ZM/OM masked), all 16 initial CC patterns, eight masked sticky/SF
patterns and eight pending patterns, including each of the six exception flags.
Empty normal, denormal and SNaN slots challenge priority over payload class.
Zero/infinity are absent. Every numerical point prediction is checked against
four pinned C builds plus the separate rational/integer numerical program.

Predicted delivery counts: none24,912; next-wait5,808; pending-at-instruction
6,144. There are33,696 full-SW predictions and96 deliberately null underflow
outputs with explicit alternatives. Unknown condition bits keep clear/set/
preserve/invert discriminators; they are not credited as predicted successes.
The bank predicts before/after/fault snapshot validity and relevant equality
relations, preserving FOP/FIP/FDP for a separate provenance check. Linux
`si_code` is recorded, not assumed to be a physical microarchitectural signal.

This bank is `SOFTWARE_ONLY_NOT_FROZEN`, not fresh audited hardware evidence.
NEXT: prepare and pin its scorer/once-only runner, independently review the
fault-state predictions, repeat the conservative compressed public/private
significand audit locally, then freeze accepted fresh tuples before the first
one-shot execution. Standing research authorization already covers the hosts;
no redundant authorization request is needed. Preserve nulls and failed
predictions rather than fitting after observation. Do not repeat old tuples.

H1653/H1654/H1655 output directories reproduce byte-for-byte in separate
software-only replay. Python syntax, target compile/static audit, production
build, both emulator selftests and diff/whitespace checks pass. Canonical0339
source, speculative-off defaults, empirical/incomplete R96 and documented
frontier direct50/48, external81/79 remain unchanged. No new hardware miss
claim is possible in this turn: no hardware was observed. The paper is untouched.

## SHA256 anchors

Paths are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1652_exception_transition.py` | `67d212535064d10b2be5e1d872d6ae7bd55a2f7bfd911c03258ddd3ccf51b1a1` |
| `tmp/ledger33/current/h1653_exception_transition_audit/report.json` | `c59a590dbda99a9fb445353c6e2f8c24efec6cf313f07eb2e4915b7b1cdad12e` |
| `capture-kit/x87_exception_transition_capture.c` | `7ac8b93ff9361fd4160d969c3fb4f750f1caa310479e8f282abc8131782e6fb7` |
| `tmp/ledger33/current/h1654_capture_build/x87_exception_transition_capture` | `1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e` |
| `tmp/ledger33/current/h1654_capture_build/capture.disassembly.txt` | `eebc646467582d364cd6770d90895d7adf735f6f7c5851b9c2a53fa2b975e12f` |
| `tmp/ledger33/current/h1654_capture_static_audit/report.json` | `7a5b0198db87093a708e7c8c513eea63c5cce82e6ddcc0dbf5296c4302689cc7` |
| `experiments/h1655_exception_state_proposals.py` | `97364c89404793fe16d6f17fd8210c2e194eb9d154aa6d79a5bd4e01ae9549cd` |
| `tmp/ledger33/current/h1655_exception_state_proposals/bank.json` | `b67f477ad99d2fdc5e14dc9c4b422d0173e5953eee77f26f81c6176c6ebdb80b` |
