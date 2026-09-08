# H1715/H1716 — adversarial verification and reusable cross-CPU corpus

2026-09-05. User requested further adversarial verification and a full input
corpus reusable as new CPU IDs become available. This is a test/capture
deliverable, not a change to the numerical algorithm or paper.

## H1715 prospective verification

**Zero new misses** across 2,784 freshly generated signed operands, all
FSIN/FCOS/FSINCOS instructions, RN/RD/RU/RZ and PC24/PC53/PC64:

- 100,224 unique instruction/control/input tuples, observed once each.
- 133,440 numerical output lanes and 100,080 applicable C1 checks pass.
- All C2 checks pass, including 144 range-rejected tuples.
- Per instruction: 25,464 polynomial, 7,608 table, 288 tiny and 48 range rows.

The software search evaluated three million operands over 30 polynomial
binades and seven table strata, ranking two near-RN materializations, or a
near internal RN plus near final boundary. It emitted 444 ranking events.
The bank adds immediate neighbors, sign mirrors, near-center cancellation,
binade/dispatch edges and high-q controls. These are generation heuristics,
not learned branches in the algorithm.

Important selection limit: the C paired table route recomputes common table
work for each output lane. Its 14 paired-table two-RN ranking events have
equal first/second keys and can count that shared stage twice. They are not
certificates of two independent simultaneous ties. Standalone and paired
polynomial paths lack that duplicated-table-call issue. All rankings use
32-bit fractional keys rather than exact internal-tie proofs. The resulting
input selection and hardware observations remain valid; no uniqueness or
physical-microcontrol conclusion is drawn from these scores.

Default C and independent rational/integer predictions agree for the entire
proposal bank. Before freeze, default and UBSan replay plus independent
recomputation passed 66,816 compiler instruction checks. Scorer preflight
passed 100,224 synthetic rows and detected 534,192 numerical/control
mutations. Public/compressed and local private representation audits found
zero possible matches; private identities, contents, hashes and membership
lists are not published. Existing reservations remain reserved.

FREEZE SHA256:
`45928f061c8103f0d57609fe5856d1872123998c7749926d91af4a0f0b48ca49`.
The two frozen jobs contain 50,112 disjoint tuples each, assigned by operand
to the x86-64 and i386 builds of the new numerical harness. Both ran on the
authorized selected Xeon, **not two CPU generations**. The shared persistent
ledger was seeded with all 68,736 existing H1712/H1714 observations. A live
attempt to dispatch an already-recorded job was refused at the ledger check
before any numerical instruction. It executed only identity reading.

Score SHA256:
`5e235982e790f4e675b5be2478bb5efa8ffa05d15e195613ce8fe31d079abad0`.
OPENED SHA256:
`3d7a6b53139a33c453552ae2da8a2787a776a82b37b0b1fd419692e8294bcc1d`.
The kit is `transfer-tests/h1715/`; score and empty misses are under
`tmp/ledger33/current/h1715_score/`. The remote kit is
`/root/fsincos-h1715-suite/kit`, with a persistent ledger in its parent.
Never rerun these tuples. The raw outputs and per-job COMPLETE/CPU metadata
hashes are recorded in the score report. The root OPENED marker was copied
to the remote kit; both individual jobs are independently sealed complete.

## Portable numerical capture and CPU identity

`corpus-suite/capture_numeric.c` accepts the fixed depth1/clear/all-masked
raw80 contract, executes exactly one requested instruction, records status
before result pops, and emits raw80 numerical lanes without decimal or
host-floating conversion. It does not use FXSAVE or timing instructions.
The inspected x86-64 and i386 programs each have exactly one opcode site per
instruction followed by the waiting status store and control-word read.
No SIMD, FXSAVE or RDTSC appears in their inspected disassemblies.

Source SHA256:
`c02d30fa4204bfb952302e9cc309132b5e21bfc32035b94feb3d2c24e81f7e3b`.
x86-64 ELF SHA256:
`fd96d6ce1270cb37e327a1a28f4494753e529732b91638fa5741e63b0682fdfd`.
i386 ELF SHA256:
`7bf061b8f9fe82ebe020ea0613842114de7b840913c473cd68e6adf7b595f263`.
They were compiled with Debian GCC12.2, `-O2 -std=c11 -Wall -Wextra -Werror
-fno-builtin`; i386 additionally uses `-m32 -march=pentium -mno-sse
-mno-sse2 -mno-mmx -mfpmath=387`. These modern dynamic-runtime builds are
not asserted to run on an original Pentium: i386 startup code includes
modern runtime markers, and libc/OS compatibility must be established on
the actual target. The distribution supplies source and build instructions,
not a supposedly universal retro prebuilt.

The runner pins one logical CPU and records before/after CPUID identity,
vendor, signature, family/model/stepping, microcode when available,
hypervisor information, core-type information when available and ABI/kernel
context. The selected reference reports signature `00050654`, F6/M85/S4,
microcode `0x1`, and a hypervisor-present bit. Its reported identity is not
independent verification of physical silicon. Future bare-metal observations
must retain their own provenance rather than being equated by brand string.

The distribution runner additionally checks an optional job-pinned binary
hash before reservation and closes its ledger connection on overlap refusal.
Those are post-capture guard/resource improvements; the exact runner used
for H1715 remains frozen in the kit. Capture arithmetic/protocol and the
frozen predictions are unchanged.

## H1716 corpus

Corpus ID: `x87-trig-v1-40620ee30e943c81`.
Corpus manifest SHA256:
`ffd65866df27828ba45ccef54febe5c4d7d422324f4d78623d54ac267fe58059`.

| Profile | Unique operands | All instruction/RC/PC tuples |
| --- | ---: | ---: |
| Smoke | 168 | 6,048 |
| Core | 10,701 | 385,236 |
| Full | 4,010,549 | 144,379,764 |

The full input union has 31 explicit public source groups and 4,239,645
source appearances, removing 229,096 duplicate appearances. It includes all
input banks used in H1713's promoted paired/standalone regressions, the
historical frontier/legacy inputs, the public legacy crossgen bank,
structured raw80 coverage, and every H1712/H1714/H1715 adversarial operand.
The full *new Cartesian matrix* extends these operands to every instruction
and RC/PC; it is not falsely described as already observed hardware data.

Stable canonical case IDs encode instruction, RC, PC and original raw80 bits
under the versioned fixed numerical contract. They do not depend on CPU,
case ordering, shard, model output or corpus release. Source memberships and
profile selections live in a separate hashed input dataset. All hardware
observations live in separate datasets with identity and source provenance.
No model predictions are installed as missing hardware labels.

Core coverage includes all 30 polynomial binades, direct/reduced polynomial,
table and tiny paths, range rejection, both signs, zero, subnormal,
pseudo-denormal, NaN, infinity and invalid encodings. The standalone archive
contains compact full input data plus ready-made core/smoke jobs. Full jobs
are expanded on demand; the full matrix needs substantial disk space and is
not suitable for blindly running on a nearly full remote host.

Every adversarial operand was verified present in core. Core and smoke
exports have no within-profile duplicate case IDs; smoke is explicitly a
subset of core, so it must be excluded after observation before collecting
the remainder. The persistent transactional ledger reserves whole jobs
before execution, refuses any overlap, and leaves partial/failed jobs
reserved. There is no force/retry/delete-ledger escape in the runner.
Unknown or private history still requires local audit; an empty ledger is
not global freshness clearance.

Independent core software verification passed 128,412 instruction rows,
170,064 numerical lanes and 126,804 known C1 checks. Full sorted uniqueness,
membership masks, profile counts, source inclusion and exported job hashes
passed. See `tmp/ledger33/current/h1716_corpus_verification/report.json`.

Portable observations reuse 168,960 existing/new captured tuples without
recapture:

- `references/h1715-skylake`: 100,224 rows with full reported CPUID context.
- `references/h1712-h1714-skylake`: 68,736 rows with historical FMS-only
  metadata. Missing historical CPUID leaves were not invented or merged into
  a stronger identity claim.

Per-job imports and merges retain hashes; mismatching contexts and conflicting
same-case observations are rejected. Comparator tests detect disagreements
and missing cases; zero overlap cannot yield an “identical” conclusion.
Six synthetic tests pass, including 360 protocol/control mutations, export
deduplication, checksum integrity, merge/context guards, atomic reservation
rollback and persistent refusal of failed-job retries. The merged H1715
reference self-comparison passes all 100,224 rows in software.

## Delivery and invariants

Start with `corpus-suite/README.md`. It documents Linux capture, identity,
old-CPU runtime limits, shard merging, cross-CPU comparison and profile
exclusion. `corpus-suite/MANIFEST.json` authenticates the distributed
allowlist. The ZIP and external SHA256 sidecar are under `deliverables/`.
Scratch databases, local ledgers, private material and the paper are not
included. The existing dirty worktree is preserved; no commit or deletion.

Final ZIP: 29,122,801 bytes, 32 files; SHA256
`3230c2a836d0d9b641d221227f3d1dad4cf0b7da93ffedef0a6648804134ad24`.
Distribution manifest SHA256:
`3b239ce4fcf8ec76efa2bca2818c103d22d19e2ec95f964ef90ca7c7e8a40571`.
The final archive was extracted into a new temporary directory, all 31
payload hashes were verified there, and all six synthetic tests passed with
ResourceWarnings treated as errors. Only README wording and its manifest
changed from the preserved first package. Remote final hashes match local
H1715 FREEZE/OPENED/raw files. The ledger reports 68,736 imported observations,
100,224 new observations, two complete jobs, and no partial reservations.
The refused overlapping dispatch created no output directory.

Main source SHA256 remains
`490039e787a89b4efa4df58f0804356cc47c9e882f0e6427b16923217e375e32`.
At the start of this task, LaTeX was
`f3b3371287510c834aa02c4f79e25990d2c4fb714c0b112d97bb21786ba5dec6`;
PDF was
`09c3192104cd0a2451d6c77388f3abb21129b39392756c1cacd6af1945b1f790`.
Final checking detected concurrent external paper edits at 07:59:48/49 CST:
LaTeX became `b6a160f2cd3d4580a056614cc1c674f647a073759afda07c40f6f65ce672b2ae`,
PDF became `c0fe38743b947672f061f84b9d4bd2e179ae20e454f946755be9447519a59a5d`.
This task made no paper edit and preserves those unrelated changes. It made
no model selector, coefficient or default-behavior change. The initial
package build is retained under `deliverables/h1716-initial-package/`; the
delivered ZIP clarifies that paper non-modification describes this task's
actions, not an assertion that no other task edited the shared workspace.
No new current numerical counterexample was found. Future CPU differences
are observations to localize, not errors to erase by fitting input identities.
