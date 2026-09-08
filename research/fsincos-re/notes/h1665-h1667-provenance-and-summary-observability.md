# H1665–H1667: provenance audit and the ES/B observability gap

2026-09-04 local date. The preceding goal turn made concrete progress through
H1662/H1664's fresh normalization/C0 challenge. This continuation establishes
a different, exact limit on the retained evidence and prepares an isolated
capture instrument. It does not select a new emulator rule, close the goal,
or alter the paper/PDF or production defaults.

## H1665: small-denormal provenance, not clearance

The conservative signature check that excluded normalization shifts60–63 is
not itself evidence that those operands were captured. The new read-only
audit separates occurrences of significands1–15 from lexical raw-operand
pairs and then from actual structured capture prestates. It searches public
and private local history, including compressed text. Private output is
aggregate-only: no private identifiers, contents, membership lists or hashes.

An independently invoked structured portion verifies the manifest sizes and
OPENED_ONCE markers for H1649/H1656/H1662. Across their106,656 actual B_R0
records (16,128+36,864+53,664), there are **zero** true-denormal inputs with
significands1–15, of either sign. This is a claim about these three campaigns,
not every historical experiment. Their raw hashes remain the established
49ae75/1074ff/5d56fc anchors.

The broad lexical scan completed successfully in exec session23420; that
session is terminal, not a live job. Its output directory is
`tmp/ledger33/current/h1665_small_denormal_provenance_v2`. It finds15 public
significands across519 files and9,197,985 matching lines, overwhelmingly
internal arithmetic/metadata. There are159 lexical-pair candidate files,
not159 verified capture sources. The private local scan examines26 files:
five have75 signature-only lines involving six candidate significands, and
zero lexical operand-pair lines. Only these aggregate counts are published.
The first attempt failed closed on a binary-text JSON record before producing
evidence; its empty directory is retained. The completed scanner handles those
records without exposing their contents.

The independent padded-syntax refinement eliminates formatting coincidences
such as a zero-valued field followed by an identifier beginning with B. Of
159 broad candidate files,45 contain actual padded raw-operand spellings:
43 are the declared H1597/H1598/H1638/H1661 software-only artifacts and two
are H1618 source/bytecode. The H1597/H1598 reports explicitly record no
hardware execution; H1638 labels exceptional preflight coverage as software;
H1661 remains SOFTWARE_ONLY_NOT_FROZEN. H1618's source comment and software_ops
construction independently identify that guard/fallback check as software.
No file in this refined inventory supplies a hardware capture of the target
domain. This is a syntax/provenance result, not clearance to run those inputs.

Even a completed lexical scan is not a proof about arbitrary binary, decimal,
cross-line or dynamically generated operand encodings. Review any positive
public provenance before claiming hardware coverage. No freshness convention
has changed, no small-domain tuple is cleared, and no new manifest is frozen.

## H1666: what coherent captures cannot identify

Let U = bool(SW.exception_flags & ~CW.exception_masks), E = SW.ES, and B =
SW.B. Reparse the original90,528 H1656/H1662 records and measure delivery at
the transcendental opcode, separately from new exceptions delivered at FWAIT.

- 84,384 records have (U,E,B)=(0,0,0), with no pending opcode fault.
- 6,144 records have (U,E,B)=(1,1,1), with pending opcode fault and A_VALID=0.
- None reaches any of the other six states.

An arbitrary Boolean gate of these three inputs has eight truth values. The
observed diagonal fixes only two, leaving exactly2^6=64 consistent gates.
The script exhaustively enumerates all256 gates and verifies that both
outcomes remain possible at each unobserved state. This is an exact finite
identifiability proof, not an inference from a best-fitting tree.

Six illustrative gates—E, B, U, E|B, E&U, E|U—all agree on the retained rows.
Three inconsistent states suffice to distinguish these six specifically;
the minimum sets, using index4U+2E+B, are {1,2,4}, {1,2,5}, and {2,4,5}.
Identifying an unrestricted three-input Boolean gate needs all six missing
states. Restricting the silicon gate to these observables is itself unproved.

Intel SDM Vol.1 §8.6 describes ES as the pending check. This motivates an E
hypothesis, but it does not prove that inconsistent requested states survive
FXRSTOR unchanged or how this target consumes them. Restoration and subsequent
execution must be observed separately. The current H1652 implementation
explicitly rejects inconsistent ES/B/flags/masks and remains unchanged.

## H1667: compiled instrument, NOT executed

`capture-kit/x87_summary_transition_capture.c` is a separate, reviewed
derivative of H1654; the original source and frozen binaries are unchanged.
Its twelve input fields replace boolean pending with an independent summary
mask restricted to0000/0080/8000/8080. It records requested SW as REQ_SW, then
the actual restored B_SW before attempting FSIN/FCOS. CW, SW outside ES/B,
FTW and raw ST0 must still restore exactly. Summary normalization is measured,
never silently repaired or credited as execution of an inconsistent state.

The output has61 fields: the former PENDING field becomes SUMMARY and REQ_SW
is added. Do not feed it to the unchanged60-field H1657 parser. A new pinned
parser/scorer, synthetic mutation tests, fresh proposals and a once-only runner
are still required before any campaign.

The source is copied and compiled, but never run, in the authorized Xeon
directory `/root/fsincos-h1667-summary-state`. GCC12.2.0 accepts
`-O2 -std=c11 -Wall -Wextra -Werror -fno-builtin`. The local static audit
verifies each six-instruction path:

```text
FSIN/FCOS -> FXSAVE64 -> mark A_VALID -> FWAIT -> FNCLEX -> RET
```

The original signal-context copy precedes recovery; handler calls are only
the two fail-closed _exit sites, with no vector/x87 handler instructions or
retry. The active main calls only the new once functions, not the archived
included H1400 entry point. The remote directory is verified to contain only
the two public sources, ELF, disassembly and compiler metadata. There is no
input file, manifest, freeze or hardware-output directory. No i7 activity or
unrelated service action occurred.

## Verification and next action

The H1665 refinement, H1666 and H1667 reports reproduce byte-for-byte under
`/private/tmp/h1666-h1667-replay.5QrywV`. Python syntax, production build, both
emulator selftests and diff checks pass. The canonical0339 source, empirical/
incomplete R96, speculative-off defaults, documented incumbent frontier
direct50/48 and external81/79, and paper/PDF remain unchanged.
All audit, replay and remote build/copy sessions are terminal. No process or
capture campaign is awaiting completion. The broad live-filesystem inventory
is preserved as observed, not claimed to be an atomic or byte-replayed census.

NEXT: preserve H1665's honest syntax/coverage limits and prepare a fresh ES/B
restoration-versus-consumption
discriminator, recording unknown fields as unknown and checking actual
restored states. Standing host authorization already applies; no renewed
permission question is needed. Do not run the compiled harness as a test,
reuse old tuples, or treat the Boolean identifiability theorem as a winning
physical selector. Small normalization shifts, zero/infinity, reserved controls,
complete tag/pointer semantics, exact-center provenance and all-input silicon
equivalence remain open; the goal stays active/unachieved.

## SHA256 anchors

- H1665 scanner: `b9278373dd02b9eb43346aae99edb90b15e01342e63ceffe539d267a004843fe`.
- H1665 report: `e1313f2af7a5a8cb4154b3ac4f304d894a5db89aabdb380357795552874fe110`.
- H1665 public inventory: `a02695d489680b8418cb1a03154d64c7c17c7cb7d5844308a85c15c2613ea051`.
- H1665 refinement script: `4fb19684f00db172dbd726b2d559c901a1472d062476f5a399de4e60c6b97be3`.
- H1665 refinement report: `0fc3ae7f08878ec27038f1ce7df3dbfe0ed648dad41249c63e673b371da870a2`.
- H1666 script: `c961bd8acc9f1ba9cffaffd41755ad13601cc4771116090fab661b6d9ee861c5`.
- H1666 report: `c9f4acb78a9e5cce0d946a360dec658dbfff924c2a451f8d177e6bd792ac3c20`.
- H1667 source: `175a9d19f9bd2996834d24d9b1be142e74d198b955b1eaf36d9432da286092d4`.
- H1667 ELF: `04147ce0b5f38b122dd46c2dfcf7c4b4dca3cbd846040de3873b91910115a296`.
- H1667 disassembly: `d8e54c1d7e85c5f3e9ba604c7f47c2aa86da26b11d6baaff9327d82ef80fa7b2`.
- H1667 static checker: `45b1ba8d23f3a75bdb5a7ed0405502ee16d4e2dba4b5732e52c940d3c54f6ab8`.
- H1667 static report: `7d242427fc131b1866f3de70459af6ffadc3876a27c6c3ba825ff2ea33a5ec5b`.
