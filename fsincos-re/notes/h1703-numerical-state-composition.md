# H1703: numerical-return and partial state composition

2026-09-04 local date. A new explicitly enabled analysis-only interface connects
the unchanged numerical candidate to the existing H1652/H1659/H1660 partial
state model. No numerical fit, production/default change, hardware capture,
private-ledger access or academic paper/PDF update.

## Result and scope

The composed interface matches all 106,656 retained rows from H1649/H1656/H1662
in output, known status, TOP, abridged tag, CW/deeper-register preservation and
recorded delivery site where available. In these particular retained banks the
current model's status mask is full, and all full-SW comparisons pass. That
does not extend the mask to absent zero/infinity cases or arbitrary histories.

It also passes 165,888 software state cases. The numerical dependency is the
actual four-build H1638 candidate, not an operand correction table: 27,632
distinct instruction/RC/raw-input software keys give 110,528 C comparisons,
all independently checked by the rational graph or tiny/special specification.
These keys are not new hardware observations or fresh-tuple clearance.

The goal remains unachieved. This is a usable **partial, default-off composition**
and finite integration audit, not a universal physical-state emulator, all-input
silicon theorem, proof of all state histories or a production promotion.
No new candidate numerical miss is known; the previously matched 81 external
incumbent-frontier outputs remain matched, not 81 unresolved candidate misses.

## Interface and writeback distinctions

`h1703_composed_transition.compose` requires `enabled=True` and an explicit
numerical backend. It returns the existing transition, whether a numerical
call occurred, its optional numerical result, a writeback decision and commit
kind. The raw input is retained separately throughout; it is not reconstructed
from a canonicalized numerical output.

| Path | Numerical backend | Writeback | Endpoint |
| --- | --- | --- | --- |
| Previously pending exception | Not called | No | Original raw operand |
| Early unmasked invalid/denormal exception | Not called | No | Original raw operand |
| Masked empty stack | Not called | Yes | Indefinite; existing tag rule |
| Numerical C2 return | Called, returns no value | No | Original raw operand |
| Ordinary or late-precision completion | Called once | Yes | Numerical candidate endpoint |
| Late unmasked true-denormal FSIN underflow | Called once | Yes | Separate H1659 input-scaled endpoint |

The numerical result is explicitly `OK + value` or `C2 + no value`. C2 is not
a rounded output and never copies an uninitialized/stale result into state.
The bridge asserts that the state model agrees with that response. For ordinary
completion it checks that the architectural endpoint equals the C endpoint.

Wrapped underflow is a separate rule, not generic scaling of a rounded masked
answer. This branch requires original true-denormal FSIN, its verified bypass
endpoint/C1, and the existing exact input-scaling rule. The H1659 63-interval
theorem establishes that formula's scaling, not universal silicon selection.
Early faults and pending delivery bypass arithmetic completely.

The audit records callback calls and checks request/writeback decisions against
the existing transition result independently of the bridge's planning flag.
The backend test cache contains only outputs computed from the fixed software
graph; it is not a lookup-based emulator repair and contains no hardware labels.
The interface itself accepts a callable rather than a stored operand table.

## Tests and preserved unknowns

The synthetic bank covers all four RC, PC24/53/64, all 64 exception masks, six
old-flag patterns, varied TOP/tags/condition bits/SF, empty/occupied cases and
18 encoding/path representatives. It is not exhaustive over all state/input
combinations or a new universal priority proof. Its 165,888 rows yield:

- 55,968 numerical requests;
- 51,288 ordinary, 9,768 masked-empty and 936 wrapped-underflow writebacks;
- 103,896 no-writeback cases, including C2 and early/pending faults;
- 14,808 rows whose status mask deliberately remains incomplete.

Negative controls verify that default-off use, reserved PC01 and incoherent
ES/B/flags/masks reject before numerical execution. Zero retains known mask
0xbeff and infinity 0xbaff in the tested controls; neither is filled to0xffff.
Unknown bits are not silently assigned zero or assumed preserved.

A pseudo-denormal and its equal-valued E=1 counterpart show why raw classification
must precede canonicalization. With DM unmasked, the pseudo-denormal takes an
early DE fault with no numeric call/writeback, while the normal alias computes
and commits with PE. The equal numerical values do not imply equal state effects.

| Retained bank | Rows | Numerical requests | Writebacks | Wrapped commits | Misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| H1649 | 16,128 | 14,976 | 14,976 | 0 | 0 |
| H1656 | 36,864 | 23,040 | 25,728 | 96 | 0 |
| H1662 | 53,664 | 44,448 | 44,448 | 22,224 | 0 |

These are retained appearances, not new unique tuples. H1656's 96 originally
unknown frozen underflow outputs remain counted as historical unknowns; this
retrospective integrated replay does not rewrite those predictions or upgrade
them into prospective successes. No original manifest, OPENED marker, score
or hardware-output file is modified. The selected before/after/fault records
are authenticated by their existing hashes and compared with original raw
input, instruction, RC and prestate. FOP/FIP/FDP, complete tag semantics and
all fault-context relations are not newly verified by this wrapper.

The 27,632 software numerical keys comprise 1,336 polynomial, 1,768 table,
19,728 tiny and 4,800 special/range keys. Special/range keys do not acquire
otherwise absent arithmetic C1 or full-state evidence. The software state
equivalence check uses the existing partial transition model, so it is not an
independent proof of that model's physical correctness. The retained hardware
comparison and independent numerical arithmetic are separate evidence.

## Artifacts and replay

Paths below are relative to `fsincos-re`. Reviewed results use the v2 directory;
the original first-pass directory is preserved unchanged.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1703_composed_transition.py` | `ccd3c802d5f28318f504e8d9dfc55c8dca0cc41d258fd5216b431172dc9fca87` |
| `experiments/h1703_composition_audit.py` | `03fd7d547e969a693284fbd2da3a5e8ca5603a7febec65206a1175b58fd23ab9` |
| `tmp/ledger33/current/h1703_composition_audit_v2/report.json` | `e82c9e115179b656b9a726a3d91d0f4d15bc96ad4981a670cf5cf2fbaba4ba7a` |
| `tmp/ledger33/current/h1703_composition_audit_v2/software.json` | `a7ad63a0410801acf1f765ef717389fa874b249816c76c9bcbc99cd1ceb2aee2` |
| `tmp/ledger33/current/h1703_composition_audit_v2/numerical_backend.json` | `b9a9b6141ecd2b13e4a35eb31764888da7b95e792d9342d933938a81c43bb2ed` |
| `tmp/ledger33/current/h1703_composition_audit_v2/negative_controls.json` | `6f0126929b698a5170f94c5b53019deb8bbf94774e8e45a2eceb3643c16a2328` |

Per-bank reports retain counts, every mismatch (none) and full composed-row
fingerprints. The backend report pins all four existing binaries and per-group
stdout hashes. Additional dependency hashes were checked locally unchanged:
H1634 rational graph41393ef2, H1637 tiny/special spec ea6e22d4, raw numerical
parser5e835094 and nativeROM2189e006; the audit directly pins its state model,
C runner, H1636 verifier, original model report and all three historical banks.

Replay `/private/tmp/h1703-replay.R0JgUS/h1703` matches the entire v2 directory
byte-for-byte. Syntax, canonical build, both selftests and diff/whitespace checks
pass. Source0339a7d6/headera5e9d085/ROM2189e006 and paper802fb3b6/README8096a84f
anchors are unchanged. Sessions79641/21079/31932 are terminal.

## Remaining work

The partial numerical/state interface is now explicit, but complete physical
state behavior is not solved. Next establish whole-contract stage/dependency
invariants beyond the finite software matrix, or resolve a genuinely missing
physical domain using existing evidence and the established freshness rules.
Keep PC01, incoherent summary states, zero/infinity condition bits, smallest-
denormal evidence, arbitrary histories and full pointer/tag effects unresolved
until supported. Do not turn accepted software controls into universal hardware
claims or let the completed composition substitute for the full objective.

H1697 private possible matches remain unresolved, H1688 reservations stand,
all opened campaigns stay closed, H1685 paused and H1670 held. No hardware/
remote/private action, new label, promotion or paper update. The full goal is
active/unachieved; this is concrete implementation progress, not a global blocker.
