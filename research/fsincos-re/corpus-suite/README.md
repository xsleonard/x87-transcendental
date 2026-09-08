# x87 cross-CPU verification suite

Content-addressed revisions of corpus v1, with separate observations for each reported
CPU context. FSIN, FCOS and FSINCOS are all tested independently. The suite
does not assume that another Pentium generation must match Skylake.

Corpus ID: **`x87-trig-v1-2126cf9ff5272e9d`** (H1723 confidence revision).
The preceding `d641d37292814c79` release and archive are preserved under
`releases/h1718-v1-policy2/` and `deliverables/h1718-v1-policy2/`.
All 42,283,466 previous operands and profile/source memberships are retained.
The prior `40620ee30e943c81` release is preserved in the repository under
`releases/h1716-v1-original/` and `deliverables/h1716-v1-original/`.
All of its 4,010,549 operands and stable case IDs are retained.

| Profile | Unique raw80 operands | Default executions | Precision controls |
| --- | ---: | ---: | --- |
| Smoke / mandatory regressions | 289 | 10,404 | 24, 53, 64 |
| Core adversarial / domain coverage | 71,193 | 2,562,948 | 24, 53, 64 |
| Full finite adversarial union | 42,289,770 | 507,477,240 | 64 |

`jobs-core/` contains 26 ready-to-run shards; `jobs-smoke/` contains one.
Choose **core** for a useful first CPU comparison. Smoke is a smaller
alternative, not an additional set to run blindly before core: its tuples
overlap core. If you run smoke first, export core with its observations
excluded, as shown below. The ledger rejects overlap rather than recapturing.

“Full” includes the original retained-input union plus all 20 imported i7
banks: comb3 through comb19, comb13n, hostv1 and randv1. This includes the
comb9/comb10 banks omitted by the previous delivery and the new paired miss.
It also includes the explicit public H1400-H1715 campaign operand union,
eight bounded theoretical proposal banks, all 15,700 independent-review
operands, known-miss/legacy fixtures, signed +/-16-ulp neighborhoods and
same-significand transports through all 30 polynomial binades. All targeted
fixtures and proposal/campaign operands are in core; all 121 mandatory
miss/legacy inputs are in smoke as well. Source hashes, membership
bits and coverage are in `corpus-v1/sources.json` and `coverage.json`.
The finite source list is explicit: not every conceivable adversarial input,
exhaustive raw80 enumeration or billion-input exploratory search expansion.
Raw operands from architectural-state campaigns are tested under this suite's
numerical contract; their stack histories/unmasked state tests are not imported.
The package contains only the public artifacts listed in its manifest.

H1723 adds 6,304 unique inputs to both core and full: individually identified
policy-2 internal cuts, adjacent raw80 values, signed reduction brackets,
exponent/dispatch controls, and focused paired-output/C1 cases
with adjacent controls. The 28-million-input software searches that selected
these bounded panels are not expanded into the default corpus.

## What is covered

The core includes every polynomial binade, direct and reduced paths, all
reachable table regions, tiny-path boundaries, cancellation near table
centers, range rejection, sign/quadrant variants, zeros, subnormals,
pseudo-denormals, infinities, NaNs and invalid raw encodings. New H1715
proposals target two internal rounding boundaries at once, or an internal
and final boundary together. H1714 adds exact ties, certified adjacent-input
rounding brackets, and high-quotient reduction transports.

The H1715 rankings are search heuristics, not internal-tie certificates. In
particular, the C paired table route recomputes shared stages for its two
lanes: 14 paired-table double-RN ranking events can count the same shared
stage twice. They must not be presented as two independent simultaneous
ties. This limits that selection heuristic, not the validity of the fresh
hardware observations. Standalone and paired-polynomial probes do not have
that duplicated shared-table-call issue.

The numerical capture contract is fixed: all six exceptions masked, one
input at stack depth1, clear initial state, raw 80-bit memory input. C1 and
the full status word are recorded before result pops. C2 returns no new
result and its preserved input is checked. Arbitrary stack histories,
unmasked signal delivery, pointer registers and timing are outside this kit.

## First run on a new CPU

The guarded runner requires **x86 Linux, Python3.8+ with SQLite support, and
a compatible C compiler/runtime**. It pins the process to one allowed logical CPU and reads
identity before and after capture. It writes only the chosen output/ledger
paths. It installs nothing and requires no root privileges.

From this directory on the target:

```sh
make
python3 test_suite.py -v
python3 suite.py verify .
python3 suite.py verify corpus-v1
```

The unit tests are synthetic: they do not execute the transcendental
instructions. `capture_numeric --identity` also executes no transcendental
input. To capture the core shards, substitute a descriptive label for
`my-cpu` and keep the same ledger across all runs:

```sh
for job in jobs-core/job-*; do
    shard=${job##*/}
    python3 run_capture.py --job "$job" --binary ./capture_numeric \
        --ledger captures/ledger.sqlite \
        --output "captures/my-cpu/$shard" --label my-cpu || break
    python3 suite.py import-numeric "captures/my-cpu/$shard" \
        --output "observations/my-cpu/$shard" || break
done
```

The default shard size is 100,000 executions. Core's last shard has 62,948.
Use `--logical-cpu N` to select a different allowed core; this matters on
hybrid CPUs. Do not run the same tuples on another core merely as a repeat.
Only collect a separate core type/context when that is the intended new
comparison, and retain its distinct identity metadata.

**Do not restart an interrupted capture.** The complete input batch is
transactionally reserved before its first numerical instruction. Failure or
interruption leaves those tuples reserved; there is no force/retry option.
Successful jobs have `COMPLETE.json`. After interruption, inspect the
records and run only untouched jobs, not the original loop from the start.
Do not discard or replace the ledger to bypass this protection.

The ledger protects the history it contains, not unknown history elsewhere.
For an already-used CPU, import all existing observations and check any
additional local/private reservations before selecting fresh inputs. A new
empty ledger is **not** proof of freshness. The supplied ready-made jobs
are intended for a genuinely new CPU context, not for recapturing the
current Skylake reference.

## Merge shards and compare CPUs

After all intended shards are complete:

```sh
python3 merge_observations.py observations/my-cpu/job-* \
    --output observations/my-cpu-core
python3 suite.py compare references/h1715-skylake observations/my-cpu-core \
    --output comparisons/skylake-vs-my-cpu-h1715
python3 suite.py compare references/h1712-h1714-skylake observations/my-cpu-core \
    --output comparisons/skylake-vs-my-cpu-earlier
python3 suite.py compare references/review-20260905-skylake observations/my-cpu-core \
    --output comparisons/skylake-vs-my-cpu-review
python3 suite.py compare references/h1722-skylake observations/my-cpu-core \
    --output comparisons/skylake-vs-my-cpu-h1722
python3 suite.py compare references/h1722-i7 observations/my-cpu-core \
    --output comparisons/i7-vs-my-cpu-h1722
```

For two newly collected full/core datasets, use their two merged observation
directories as the `compare` arguments. The report separates numerical/C2
differences, observed C1 differences and full-status differences. It includes
both CPU descriptions and the exact case IDs for disagreements. Missing
cases are reported as missing, never counted as passes. No common cases is
`NO_COMMON_CASES`, not “identical.” Special or undefined status differences
are observational facts, not automatically numerical algorithm failures.

Merge accepts only the same CPU context and rejects conflicting observations
for the same case. Historical FMS-only records are deliberately not merged
with newer full-CPUID records by guessing missing identity fields.

## Reuse existing observations, or export smaller/full jobs

If smoke or another subset has already been observed on this CPU:

```sh
python3 suite.py export corpus-v1 --profile core \
    --exclude-observations observations/my-cpu-smoke \
    --output jobs-core-remaining
```

Then capture those jobs with the same ledger. You can additionally pass
`--known-observations observations/my-cpu-smoke` to `run_capture.py` when
initializing/importing an existing ledger. CPU identity is checked before
the observations are registered. Existing reserved-but-unobserved jobs must
also remain in the ledger; exclusion files alone cannot replace it.

Full defaults to PC64, all four RC modes and all three instructions. Core
continues to test all three PCs. This keeps every full operand while avoiding
three precision-control passes over the largest input bank. To plan the run:

```sh
python3 suite.py plan corpus-v1 --profile full \
    --executions-per-second 1000 --max-hours 168
```

This estimate is 141.0 hours (5.9 days) at 1,000 executions/sec, or 7.05 hours
at 20,000/sec. These are assumptions, not guaranteed performance on an old
Pentium. Measure the first useful shard's elapsed wall time without repeating
it, then update the rate. Planning returns exit status 2 when over budget.
Core takes about 43 minutes at 1,000/sec. Substantially slower CPUs should use
core or bounded portions of full; the kit does not promise every CPU finishes
the complete set in a week.

To generate full jobs, optionally testing all PCs explicitly:

```sh
python3 suite.py export corpus-v1 --profile full \
    --output jobs-full-pc64
python3 suite.py export corpus-v1 --profile full --pcs 24 53 64 \
    --output jobs-full-all-pcs
```

The full PC64 matrix is 507,477,240 executions, roughly 132 GB of uncompressed
input/output text **plus** ledger/index space. All-PC full is 1,522,431,720
executions and may take weeks on a slow CPU; it is opt-in, not the default.
Use bounded exports to avoid creating hundreds of gigabytes of jobs at once:

```sh
python3 suite.py export corpus-v1 --profile full \
    --start-operand 0 --operand-count 100000 --output jobs-full-part-000
```

This emits 1,200,000 tuples. Use `next_operand` from its `EXPORT.json` as the
next start offset. Offsets refer to the selected profile before exclusions;
keep the corpus ID fixed while progressing through ranges. Continue using
the same persistent capture ledger and exclude earlier core/smoke observations
if appropriate. Range/exclusion selection does not make repeated tuples fresh.
Export and planning execute no hardware. Only compact full operands are
distributed; the expanded full matrix is generated on demand.

Case IDs are stable across profiles, shards, CPUs and future corpus versions:
`n1-INSTRUCTION-RC-PC-SESIGNIFICAND`. They encode the complete fixed numerical
contract and original raw bits. Changing the order, CPU label or executable
does not make a tuple fresh. New corpus versions may add cases without
renaming existing ones. This user-authorized v1 revision has a new content ID;
the old release remains recoverable and must not be relabeled as the new one.

## CPU identity and old Pentiums

`cpu.json` retains the raw CPUID leaves, vendor/signature, decoded
family/model/stepping, microcode when available, hypervisor information,
core-type leaf when available, selected logical CPU and kernel/ABI context.
The context key keeps microcode, virtualization and core-type differences
separate. Intel documents the processor signature as family/model/stepping
information, not a unique physical-processor identifier:
[Intel CPUID identification](https://www.intel.com/content/www/us/en/support/articles/000006831/processors/intel-processor.html),
[Intel CPUID enumeration reference](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/technical-documentation/cpuid-enumeration-and-architectural-msrs.html).

The present reference reports `GenuineIntel`, signature `00050654`,
family6/model85/stepping4, microcode `0x1`, and a hypervisor-present bit.
Do not treat a VPS CPUID/brand string as independently verified physical
silicon provenance. Bare-metal captures will make the lineage picture
stronger; virtualized captures remain explicitly labeled.

The numerical core uses ordinary x87 instructions and **does not require
FXSAVE, SSE or timing instructions**. `make pentium` requests 32-bit Pentium
code generation. However, the compiler, C startup code, libc, kernel and
Python environment must also support the actual target. The modern Debian
32-bit test build contains modern runtime code; an i586 compiler flag alone
does not certify that binary for an original Pentium. Build with a compatible
target toolchain/runtime. This turn validated 32-bit and 64-bit executions on
the current Xeon, not on an original P5. No untested universal retro binary
is presented as working.

## Supplied observations and verification

- `references/h1715-skylake`: 100,224 fresh tuples, full reported CPUID
  metadata; 2,784 operands. Both capture builds used disjoint inputs.
- `references/h1712-h1714-skylake`: 68,736 earlier observed tuples. Original
  FMS/microcode metadata is retained; raw CPUID was unavailable in those
  records and is not invented. This is a separate identity-quality group.
- `references/review-20260905-skylake`: 188,400 saved review tuples. Original
  FMS/microcode summary is retained; raw CPUID and verified affinity were not
  retained, so neither is asserted. This is an import, not a fresh capture.
- `references/h1722-skylake` and `references/h1722-i7`: 222,480 new tuples
  each, over the same 6,180 operands, all instructions/RC/PC settings. Full
  reported CPUID and pinned-affinity metadata are retained separately for
  Xeon F6/M85/S4 and i7-6700 F6/M94/S3. These are two hardware observations
  per cross-CPU case, not shared-label replays on two execution hosts.
- Raw hardware data remains in the original sealed capture directories in
  the repository. The portable observations retain raw80 outputs, status,
  source hashes and provenance. They are not regenerated model labels.

H1715 matched all 133,440 numerical outputs and 100,080 applicable C1 checks,
including 144 C2 tuples, with zero misses. Its generation screened three
million software operands; freshness checks found zero public/private
possible matches. Existing H1714/H1712 observations were reused without
recapture. The H1717 revision promotes all-product paired arithmetic; the
input corpus itself remains independent of model predictions.

H1722 matches all 444,960 new instruction observations, 593,280 output lanes,
and 444,960 applicable C1 checks, with zero numerical/C1/C2 misses and zero
cross-CPU disagreement. Verification concerns the promoted algorithm's
agreement with hardware and independent arithmetic, plus explicit coverage
gaps. Retired algorithm variants are outside the current verification scope.
This is finite adversarial evidence, not exhaustive raw80 or cross-generation
proof. No algorithm or paper was changed for this campaign.

The full corpus's uniqueness, profile counts, source membership and all
adversarial input inclusions were audited. Independent rational/integer
verification of the prior H1718 core passes 778,668 instruction rows,
1,026,848 output lanes and 745,836 known C1 checks, recorded in the H1718
verification report. This is **software** verification, not a
claim that the full core/full Cartesian matrix was already observed on the
reference CPU. H1722 additionally pins 74,160 independent/C/UBSan prediction
checks before its labels, plus 840 exact stage-identity/ranking checks and
1,186,560 synthetic scorer mutations. Eight toolkit tests cover parser mutations, missing/different
results, checksum failures, merges, export deduplication, atomic overlap
refusal, bounded exports, runtime budgets and partial-run reservation. The live ledger also refused an
already-recorded job before numerical execution.

The package manifest hashes every distributed file. `catalog.sqlite`,
per-observation working indexes, local ledgers, temporary build trees and
private material are excluded from the archive. Keep the original sealed
corpus/observations; put new captures in new directories.
