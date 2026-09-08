# H1722 — fresh, frozen two-CPU adversarial verification

2026-09-05. PASS: the unchanged promoted policy-2 program matches all
444,960 new instruction observations on i7 and Skylake. No new miss,
algorithm change, fitted correction, selector, or paper/PDF edit.

## Results

| Observation CPU | Fresh tuples | Output lanes | Applicable C1 checks | Misses |
| --- | ---: | ---: | ---: | ---: |
| i7-6700, F6/M94/S3, microcode 0xf0 | 222,480 | 296,640 | 222,480 | 0 |
| Xeon Skylake, F6/M85/S4, microcode 0x1 | 222,480 | 296,640 | 222,480 | 0 |

Each CPU observed the same 6,180 operands under FSIN, FCOS and FSINCOS,
RN/RD/RU/RZ, and PC24/53/64. All C2-clear predictions and capture contracts
match. This normal-finite panel does not add fresh C2-set/special-value tests;
those remain covered by earlier saved evidence. Portable comparison finds
222,480 common cases and no output, C1, C2 or full-status difference.
These are separate silicon observations, not shared-label software replays.

The selected CPU is pinned before identity/capture and checked afterward.
i7 context is `ddd2d03e833f2e7f9a4da7a13c4cca36283523e3b2b5c353f91910859668e829`;
Xeon context is `89f941c5697ee2da398533fafa8372e0d6ba481db280ae5e70cb2c40f458e66f`.
Xeon reports a hypervisor; this is not independently authenticated bare-metal
provenance. Both are Skylake-era contexts, not validation across old Pentium
generations. No logical-core repeat was used as new evidence.

## Input selection and coverage

H1720 first audited attributable coverage rather than adding overlapping
replay totals. The old core's 64,889 operands imply 2,336,004 control tuples;
normalized evidence establishes 257,136 historical-FMS and 100,224 full-CPUID
tuples in separate identity-quality groups. The local i7 legacy projection
maps 89 jobs, with 60 other legacy jobs explicitly unmapped by that audit.
An unmapped row is not asserted never observed. Legacy PC is not inferred
from filenames. The 31 absent RZ bank files are not 31 absent tuples.

H1720 passively instrumented a copy of the unchanged model and screened
12,000,000 full-precision raw80 inputs across all 30 polynomial binades.
Each of 11 RN64 stages, 13 CHOP67 stages and four final-boundary categories
has a separate identity. Independent exact arithmetic verifies all 840
selected stage identities and ranking keys. Ranking keys truncate distances;
a zero key is not asserted an exact tie. The bounded H1721 bank adds signed
adjacent inputs, exponent/dispatch controls and exact reduction transports
or explicitly labeled brackets. Its 6,170 proposals pass 74,040 independent
instruction/mode predictions before labels.

H1724 supplied a focused panel from a separate 16,000,000-input software
search: 4,194,304 inputs in a neighborhood of a known regression, then
deterministic full-width sampling of the top polynomial binades. Already
recorded inputs were excluded. The 18 fresh focused operands cover both
signs and adjacent controls; their paired outputs and C1 agree with the
promoted algorithm under every tested RC/PC setting on both CPUs.

Current verification evaluates only the promoted algorithm against hardware
and independent arithmetic. Comparisons with retired variants are not part
of its correctness evidence or future test-selection objectives. Sealed
historical artifacts retain their original provenance without alteration.

## Freshness, freeze and capture integrity

Local public/compressed history and the private supplemental ledger were
checked before freezing. Private possible matches were zero; private file
identities, contents, hashes and per-operand membership were not published
or exported. No private implementation was used. Remote public audits cover
870 files /1,416,651,370 stored bytes on Xeon and 24,089 files /
31,304,115,679 bytes on i7. Four prior significands found only in the mapped
remote history remove eight signed broad-panel operands. Three known local
significands remove six operands from the small focused panel.
Final selection: 6,162 broad operands plus 18 focused/control operands.

Every selected significand has nonzero low eleven bits, excluding the
previous binary64 hardware-search domain. The generator also conservatively
excludes every possible counter of the observed public raw80 generator's
default seed. Presence of a compiled comparator is not proof it ran.
Unknown override seeds, unavailable history and arbitrary encrypted/image-only
records remain explicit audit limits; global unseen-history completeness is
not claimed. The slow i7 Python read-only audit was replaced by native search;
no hardware job was interrupted or retried.

The frozen predictions agree with independent integer/rational evaluation,
the current C executable and UBSan on 74,160 instruction/mode cases. The
scorer passes 1,186,560 synthetic mutations before labels. Capture uses the
reviewed raw80 numerical harness, binary SHA256
`fd96d6ce1270cb37e327a1a28f4494753e529732b91638fa5741e63b0682fdfd`.
Each whole job is persistently reserved before its first target instruction;
partial failures would remain reserved. There were no partial failures or
instruction retries.

Xeon's existing `/root/fsincos-h1715-suite/ledger.sqlite` was preserved and
the applicable 357,360 public historical observations imported/reconciled.
i7's new persistent ledger is `/root/h1722-policy2-confidence/ledger.sqlite`;
its empty initial state was not used as freshness evidence—the completed
local/private and remote history audits provide that separate clearance.
All future campaigns must retain these reservations and new observations.

The actual captured intervals, including local runner validation, were
16:12:28.761776–16:12:31.291330 UTC on i7 and
16:12:33.069003–16:12:40.821431 UTC on Xeon. They are observed useful-job
times, not repeat benchmarks or promised rates for older CPUs. Transfers
contained only public test code/data and public prior observations, not the
model sources or private ledger. Tar emitted benign macOS extended-attribute
warnings; capture stderr is empty and decoded payload hashes match.

## Corpus, artifacts and claim boundary

Corpus v1 now has revision `x87-trig-v1-2126cf9ff5272e9d`: 42,289,770
unique operands, core 71,193, smoke 289, and 58 explicit source groups.
All 42,283,466 preceding operands and memberships are preserved. The 6,304
new bounded inputs include proposals excluded only from this capture's
freshness selection. Inputs are not hardware labels. The 28M exploratory
search inputs are not expanded into the default corpus.

Core has 2,562,948 tuples in 26 ready shards; full PC64 has 507,477,240.
Both new CPU observation datasets are in the public package. The prior
corpus, jobs, manifest, README and archive are recoverable under the
`h1718-v1-policy2` release directories; nothing material was deleted.

Pristine extraction passes all package/dataset hashes and eight synthetic
toolkit tests. All 2,562,948 exported core lines are checked for their
canonical capture contract, and all new captured cases occur in core and
both packaged CPU datasets. The main self-test, six saved paired regressions,
Python syntax and whitespace checks pass. Delivery evidence for the preceding
archive (before documentation-only repack) is
`tmp/ledger33/current/h1723_delivery_verify/report.json`. Read-only final
ledger checks confirm 222,480 new OBSERVED reservations on each CPU; total
Xeon reservations are 579,840, i7's new ledger 222,480.

Key artifacts:

- `transfer-tests/h1722/{FREEZE,manifest,OPENED}.json`, `run-i7/`, `run-skylake/`;
- `tmp/ledger33/current/h1722_score/{report,misses}.json` (sealed historical scoring record);
- `tmp/ledger33/current/h1720_coverage/report.json`, H1721/H1724 banks and audits;
- `corpus-suite/references/h1722-i7` and `h1722-skylake`;
- `deliverables/x87-trig-suite-v1.zip`, 263,512,725 bytes /89 allowlisted files.

Freeze SHA256: `520be2617b630f3ff218b4dcac6e3861ffc2a5810161b0414e78fc40fbd8518c`.
Score SHA256: `c3f91349a89c11073c4439695854f82f0bf8c2ca6b50acd86760926e21c1c3bb`.
Archive SHA256: `ace2d751ac1d21b1f9880e39b5a7425b7e2da572572cee464847bd6106a6090f`.

Documentation-only repack: only the packaged README changed; corpus inputs,
jobs and captures are unchanged. The preceding archive and distribution
manifest remain under `h1723-before-reporting-cleanup` preservation directories.

Main source remains `490039e7...e375e32`; paired header `4eeb6715...15b9a5d`.
Paper TeX remains `9d11c734...829ff`, PDF `e08a5657...36e0`.
The result is substantially stronger finite adversarial support, not a proof
over all raw80 inputs, a silicon-internal reconstruction proof, or closure
of every historical control-matrix gap. H1719 replay totals are not added to
these new-observation counts. No known current-policy miss was found.
