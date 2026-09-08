# H1725 — full corpus-v1 two-host campaign

## FINAL — both selected campaigns and portable outputs reconciled, 2026-09-07

Permanent report/index snapshot:
[`reports/h1725-20260907/`](../reports/h1725-20260907/README.md), with SHA256
checksums and an explicit user-requested no-rerun policy. Preserve the original
large datasets and reservation state; use saved observations for offline replay.

**705,480,464 selected native observations; zero misses.** Both native services
exited successfully, and every corresponding portable dataset is materialized
and independently checksum/count-reconciled. Final authoritative summary:
`fsincos-re/tmp/ledger33/current/h1725_full_campaign/FINAL-REPORT.json` at the
repository root. This completes H1725's authorized selected-campaign work.

| Reported CPU context | Selected observations | Shards | Native misses |
| --- | ---: | ---: | ---: |
| i7 F6/M94/S3, microcode 0xf0, no reported hypervisor | 216,382,204 | 6,387 | 0 |
| Skylake F6/M85/S4, microcode 0x1, reported Hyper-V | 489,098,260 | 8,303 | 0 |
| Total per-host observations | 705,480,464 | 14,690 | 0 |

Coverage is FSIN, FCOS and actual paired FSINCOS, RN/RD/RU/RZ, PC64.
Exact numerical lane checks: 952,349,799; applicable C1 checks: 702,117,316;
C2 checks: 705,480,464. All output/sine/cosine/C1/C2 miss counters are zero.
i7 native finished 21:56:13 UTC; Skylake 23:21:43 UTC. Skylake's final native
audit reconciled its 7,251 legacy-prefix + 1,052 autonomous shards, including
58,573,060 autonomous observations. Final portable audit finished 23:27:24 UTC.

Per-host `native-completion-20260907/REPORT.json` authenticates the frozen
remote package/cutover, prefix scores/checkpoints, every native-delta archive,
CPU/capture identity, frozen-plan chunk rows, and cumulative final totals.
`PORTABLE-COMPLETE.json` verifies all dataset checksums, decompressed TSV row
counts, CPU contexts, legacy raw gzip hashes, and each autonomous archive plus
decoded native-text hash/count. `PORTABLE-INDEX.json` lists the portable
observation datasets; only these listed datasets are export material, not
unrelated private/working campaign files. Original observations, receipts,
frozen models, input plans, and all reservations remain retained.

Limits remain explicit. These totals count observations on two hosts, not
distinct inputs across hosts, and are evidence for the pinned H1725 artifact,
not automatic validation of arbitrary later source edits. Per-host frozen
matrix size is 507,477,240. The following are NOT newly observed passes:

| CPU | Historical exclusions | Binary64-domain holds | Ambiguous/generated holds |
| --- | ---: | ---: | ---: |
| i7 | 240,356,216 | 12,440 | 50,726,380 |
| Skylake | 2,267,068 | 7,225,076 | 8,886,836 |

`full_matrix_complete=false` remains correct. This is not a universal proof,
not validation of untested CPU IDs, and not promotion of a new selector.
No native tuple was repeated, and no algorithm, corpus membership, private
material, LaTeX or PDF was changed by this verification closeout.

Completed Mac dispatcher/exporter/status services are retired. Both native
services are inactive/successful and disabled at boot, with service files,
packages, receipts and reservation state retained. Only their boot-enable
symlinks were removed (reversible by enabling the existing service); do not
restart completed campaigns. The temporary marked H1725 SSH multiplex block
was removed after checking the current config and making a fresh private
backup; all unrelated/later SSH settings and mode 0600 were preserved. No
shared SSH connection was killed; idle masters expire naturally. The
`finish-two-host-x87-verification` heartbeat is confirmed PAUSED via the app
and its saved configuration; no further native or decoding work remains.

## 2026-09-07 22:53 UTC — i7 native AND portable reconciliation complete

`h1725_reconcile_portable.py --host i7` independently verified all 6,387
portable datasets and their decompressed TSV row counts: **216,382,204 rows**.
Checks include every dataset file checksum and CPU context, every legacy raw
gzip checksum, and every autonomous archive checksum plus reconstructed native
text SHA256/row count. All 2,757 autonomous datasets (103,381,079 rows) are fully
materialized. Native misses remain zero; exclusions/holds remain unchanged.

Durable final per-host artifacts: `i7/PORTABLE-COMPLETE.json` and
`i7/PORTABLE-INDEX.json`, under the original H1725 campaign data directory.
The index names ONLY portable observation datasets relative to its directory;
do not export unrelated campaign working files. The final audit performed no
hardware instructions or paper/model changes.

The completed `com.steve.x87.h1725.export.i7` service was removed to end
redundant successful rescans. No data or reservation was deleted, and native
i7 remains successfully completed/inactive. Do not restart either i7 runner
or exporter. Skylake native execution and its serial software exporter remain
healthy, with zero native misses; keep their services and the heartbeat active.
After Skylake finishes, run the same native-receipt and portable reconciliation
tools for that host, then reconcile the two-host result and retire monitoring.

## 2026-09-07 22:16 UTC — i7 native completion reconciled; Skylake continues

i7 finished at 21:56:13 UTC, native service exit 0 / `Result=success`, no
failure latch and empty stderr. Exact selected total: **216,382,204 rows**,
zero output/sine/cosine/C1/C2 misses. Counts: 216,373,924 applicable C1 checks,
216,382,204 C2 checks, 131,077,197 standalone output checks, and 85,296,727
checks of EACH paired lane. All 6,387 shards reconcile: 3,630 Mac-prefix
shards plus 2,757 autonomous shards (103,381,079 autonomous rows).

`experiments/h1725_reconcile_native_completion.py --host i7` authenticated
the unchanged remote package and cutover, every prefix score/checkpoint,
every final autonomous receipt/archive hash and embedded capture/score/CPU
metadata, exact frozen-plan chunk row counts, cumulative totals and held-case
accounting. All final native archives are copied locally. Evidence:
`i7/native-completion-20260907/REPORT.json`, `RUN_COMPLETE.json`,
`remote-evidence.json`, and `archive-hashes.json` under the H1725 data directory.
No hardware was repeated or invoked by reconciliation. Do not restart the
successfully completed native i7 service.

This is selected-campaign completion, NOT full-matrix or universal closure:
240,356,216 historical exclusions, 50,726,380 ambiguous/generated holds and
12,440 binary64-domain holds are not credited as fresh PC64 passes. They and
the selected cases sum to the frozen 507,477,240-case matrix.

Portable i7 materialization is separately ongoing (1,790 / 2,757 autonomous
shards sealed at audit; current exporter PID 70599). The Skylake native service
remains healthy/running with zero misses; its software exporter has caught up
and is decoding new completed shards. These launchctl-submitted export jobs
are observed to re-invoke SERIALly after successful exits, refreshing their
inventory automatically; do not start a duplicate manual decoder. A transient
dash/no PID with last exit 0 is not an export failure. Once native and portable
coverage are both reconciled, remove the completed export service rather than
leaving redundant successful scans running. Neither exporter controls hardware.
Heartbeat remains active until Skylake and final portable reconciliation finish.
Paper, model and frozen corpus are unchanged.

## 2026-09-07 21:38 UTC — portable export overlapping autonomous capture

The repository was reorganized by separate work: authoritative research notes
and tools now live under `research/fsincos-re/`. The original `fsincos-re/tmp/`
campaign data remains in place; compatibility links connect experiments,
corpus tools and the research tmp path. Both remote native services continued
unchanged throughout the move, with the same PIDs and zero misses. Do not
undo this reorganization or modify/rebuild the frozen server packages.

Software-only portable decoding has begun in parallel with remaining native
work, so it does not add its entire duration after hardware completion.
Local OS-managed observers `com.steve.x87.h1725.export.i7` and
`com.steve.x87.h1725.export.skylake` run the existing collector with `--decode`.
Logs: `{host}/portable-export-20260907.{stdout,stderr}.log` under the original
H1725 data directory. Initial exporter PIDs: 70599 / 70605. Inspect actual
processes and manifests, not those historical PIDs, on later checks.

These programs ONLY copy already-sealed archives and decode/hash-check them;
they never dispatch native instructions, change reservations, or delete remote
data. Mac sleep can delay portable materialization, but cannot delay either
server's capture or local lossless retention. Do not start another decoder
for the same host while its exporter is active. Each invocation freezes the
sealed inventory available at startup; after it exits successfully, run the
collector again to include newer receipts, reusing validated portable outputs.
Reconcile final native completion plus complete portable coverage before
pausing the heartbeat. Native runs were still healthy/incomplete at this check.

## 2026-09-07 18:56 UTC — server-owned autonomous continuation (CURRENT)

This supersedes all historical instructions below requiring an awake Mac or
restarting Mac capture controllers. User correctly rejected the workstation
dependency. Both hosts now own their entire remaining loops under an enabled
`h1725-autonomous.service`, with no SSH/network calls in the execution loop.
The Mac is only an optional status observer and result collector. Sleep,
shutdown, logout, loss of SSH, or loss of this chat cannot pause server dispatch.

Exact drained cutover, without recapturing any completed tuple:

| Host | Last Mac-owned job | Verified prefix | First server-owned job |
| --- | --- | ---: | --- |
| i7 / 142.132.217.243 | job-003629 | 113,001,125 | job-003630 |
| Skylake / 45.32.204.118 | job-007250 | 430,525,200 | job-007251 |

`h1725_cutover_autonomous.py` paused ONLY each Mac coordinator at a fully
prepared shard, drained/reused its pending capture through the existing
one-shot protocol, verified/scored/offloaded it, and sealed `CUTOVER_READY.json`.
It did not signal the native worker. `h1725_activate_autonomous.py` authenticated
the exact predecessor receipt and all staged public package bytes, retired the
two drained launchd dispatch services, and enabled the server services. Old Mac
PIDs 67512/67513 are gone. New remote PIDs were 1117027 (i7) and 2741509
(Skylake), both PPID 1; use current service state rather than assuming those
PIDs are permanent. Both have completed new independent batches, zero misses.

Server package on EACH host: `/root/h1725-full-corpus/autonomous-20260907/`.
Local staged public packages: `autonomous-i7-20260907/` and
`autonomous-skylake-20260907/` under the H1725 campaign directory. Each contains
the ORIGINAL isolated public C/headers, an ordinary `gcc -O2 ... -lm` build of
the original saved-label predictor wrapper, original capture guard/scorer,
the deterministic generator, and a compact exact remaining input plan. No
private supplemental ledger, scanning code, inventory, paths, or credentials
were exported. Capture binary, old SQLite ledger and original `RESERVED.bits`
are unchanged; no new empty freshness ledger was substituted.

Input generation is deterministic expansion of the SAME frozen finite corpus
and already-cleared per-host masks: `<QHQH>` ordinal/se/significand/mask records,
independently compressed per 5,000 operands. Each expanded chunk is hash-checked
against the exact selected stream. The i7 staged suffix is 77.38 MiB; Skylake
57.24 MiB, including a small already-completed overlap that is never executed.
`CUTOVER.json` selects the exact next ordinal range. This is not a newly seeded
random campaign and does not pretend unknown historical bank seeds are known.
FSIN, FCOS, and actual paired FSINCOS (both lanes), all four RCs, remain PC64.

Lossless native observation retention, necessary for the hosts' small disks:

- Every actual B_SW and A_SW bit is stored. The frozen predictor is a compression
  dictionary for value fields, and any differing raw line is retained verbatim.
- The on-disk archive is decoded and compared against EVERY original native
  output byte before scratch release, and retains its native-text SHA256, CPU,
  capture/score receipts and model/input identities. A missing observation has
  no archive: model predictions alone are never counted as hardware labels.
- The native text is lossless; the original transient gzip container bytes are
  not promised to be reproducible across zlib versions. Its original checksum
  remains in the capture receipt. Decoded containers get fresh provenance.
- Only newly generated, verified autonomous scratch is released. All prior
  Mac-offloaded observations and remote legacy receipts remain unchanged.
  All new observations are recoverable from package + immutable per-job archive.
- A real mismatch retains the complete original scratch and detailed score and
  stops before another shard. An uncertain/partial job is never recaptured.
  Low disk stops safely with observations/reservations intact. The service is
  enabled at boot, but has no blind failure/retry loop (`Restart=no`). A sealed
  checkpoint is reusable; an uncheckpointed attempt requires inspection.

Evidence: 13 local codec/lifecycle tests PASS (including both-lane/C1/C2
mutations, short/extra/corrupt records, completed restart and uncertain-job
refusal). Exact input/index expansion and native-text roundtrip PASS on 168,919
saved observations across four historical shards. Both Linux builds produced
predictor SHA256 `dd69f9949a6c00562492ea5b7bb544d58d7c9e4dbc245f37f7d57cdae22448d9`;
all their replay predictions and original scorer counts match the Mac artifact.
Each server also passed five original reservation controls, without hardware.
Remote PREFLIGHT copies are under `{host}/autonomous-activation/PREFLIGHT.json`.
The first TWO newly observed batches per host were copied back and decoded on
the Mac: 50,000 i7 + 119,984 Skylake rows, byte-exact native hashes and valid
portable observation manifests. This check performed no native instructions.

Current operation / completion:

- `h1725_status.py` now only reads server status and latest sealed DONE. Local
  `LIVE_STATUS.json` says `execution_location=remote_server` and
  `mac_required_for_execution=false`. The existing watcher was replaced with
  observer-only mode; its new logs are `status-autonomous.{stdout,stderr}.log`.
  An unreachable observer is NOT evidence that server execution stopped.
- Inspect remote `STATUS.json`, `STOPPED.json`, `RUN_COMPLETE.json`, service
  state and `service.{stdout,stderr}.log`. New permanent receipts/observations
  are `observed/job-NNNNNN.DONE.json` + `.json.gz` INSIDE the autonomous package.
  They supplement—not replace—the old `receipts/`, bitmap and SQLite registry.
  Missing old-style job directories still do not mean freshness.
- `h1725_collect_autonomous.py --host i7` (or `skylake`) copies all currently
  sealed archives, without remote deletion or affecting progress. Add `--decode`
  to materialize portable datasets; `--limit 2` was used for initial validation.
  Local copies: `{host}/autonomous-observed/`; decoded datasets:
  `{host}/autonomous-portable/job-NNNNNN/observations/`. Transfers and decoding
  may repeat; hardware may not. Complete collection/decoding and verify totals
  after both services finish, before marking the monitoring task complete.
- Never relaunch the Mac capture controllers. `h1725_resume_full.py` now exits
  without dispatch if `AUTONOMOUS_CUTOVER.json` exists. Do not remove that marker,
  alter a frozen remote package, clear a reservation, or rerun an uncertain job.
- Both final selected totals remain 216,382,204 (i7) and 489,098,260 (Skylake).
  Historical exclusions/ambiguous holds are NOT passes; full matrix closure
  remains false. Live C, corpus membership, paper/LaTeX/PDF are unchanged here.

## 2026-09-07 18:17 UTC — clamshell sleep delayed both runs; recovered

Read-only `pmset -g log` identified lid-close sleep on battery from 11:39:49
to 12:17:00 local (-0600), with brief notification/maintenance wakes. This
matches the simultaneous long controller gaps: i7 job-003500 / job-003502
and Xeon job-007065 / job-007067. The roughly 37-minute elapsed delay was
Mac sleep, not slower native execution or another controller crash. Both
controller PIDs 67512/67513 remained unchanged and recovered their captured
results without native repeats. At the check, i7 job-003503 had 108,926,661
cumulative PASS cases; Xeon job-007069 had 420,139,000, all miss counts zero.
SSH masters were automatically reestablished and fresh shards were advancing.

The Mac-hosted orchestration still requires power, networking, and an awake
Mac. `caffeinate -i` prevents idle sleep, not lid-close sleep on battery.
User action: keep it plugged in with the lid open while these campaigns run.
Do not silently alter system-wide sleep settings or reinterpret sleep gaps
as sustained processing time. Recent whole-window ETA now includes this
gap; separate awake throughput from elapsed-time delay. No power settings,
algorithm, captures, reservations, paper, or source were changed here.

## 2026-09-07 live SSH transport optimization — no controller restart

User requested fixing the observed orchestration bottleneck. A 60-shard
baseline measured 37.01 seconds/shard on i7 versus 18.58 on Xeon; the remote
capture/validation/compression windows were only 0.53 versus 2.51 seconds.
Separate fresh SSH no-op commands cost 2.243 versus 0.744 seconds. These are
different selected input streams, not a same-workload FPU benchmark.

At Unix time 1788802233, a reviewed, host-specific OpenSSH configuration
enabled `ControlMaster auto`, `ControlPersist 600`, and a private `%C` socket
path under `/Users/steve/.ssh/h1725-control/` (mode 0700) for ONLY
142.132.217.243 and 45.32.204.118. The SSH config remains mode 0600. The
original is backed up locally at
`/Users/steve/.ssh/config.before-h1725-multiplex-20260907`; do not publish that
config or backup. Installation was atomic after checking the original had
not changed. Existing unrelated host settings were verified unaffected.

Both controller PIDs 67512/67513 stayed running: new SSH children picked up
the settings without restart, checkpoint revalidation, or capture replay.
The masters authenticate the same hosts/users and only share transport;
native binary, model, frozen inputs, dispatch, guards, reservation state,
scoring and receipt protocols are unchanged. Active connections are not
terminated; unused masters expire after ten idle minutes. Working warm SSH
no-op medians measured 0.406 seconds on i7 and 0.151 on Xeon.

Read-only profiling tool: `experiments/h1725_transport_profile.py`. Baseline
receipt: `ssh-before-multiplex-20260907.json` in the campaign directory. For
post-change samples use `--since 1788802252` to exclude transition shards;
the cumulative LIVE_STATUS rate still includes slower historical work.
Initial complete-shard verification is saved in
`ssh-after-multiplex-20260907.json`: 11 i7 shards averaged 15.75 seconds
(versus 37.01 before; 2.35x faster), and 16 Xeon shards averaged 10.86 seconds
(versus 18.58; 1.71x faster). Similar mean batch sizes, all PASS. Last sampled
jobs were i7 job-003477 and Xeon job-007032; fresh remote archives were
confirmed beyond the change with unchanged controller PIDs. At this short
sample's rates, remaining-work projections span 12.7–14.9 hours for i7
(batch versus case extrapolation) and 3.8 hours for Xeon. Treat these as
initial measured projections, not fixed deadlines; keep checking recent
rates rather than reusing the pre-optimization cumulative estimate.
After BOTH selected runs finish, remove only the marked H1725 block from
the live SSH config, preserving any later user edits; do not blindly restore
the complete backup or kill shared SSH sessions. Let idle masters expire.

## 2026-09-07 recovery: isolate the actual frozen model from live edits

At 15:55 UTC both controllers stopped at the per-shard whole-source checksum
guard. The complete delta from the authenticated original C is a new
`f2xm1_tiny_raw80` helper and its F2XM1-only call; removing those two additions
reconstructs the original C byte-for-byte. The four pinned trig headers and
the actual campaign predictor are unchanged. This was an over-broad live
worktree dependency in orchestration, NOT a numerical mismatch.

User explicitly requested immediate resumption without interruptions for
unrelated source edits. The controller now authenticates the original model
under `tmp/ledger33/current/h1725_full_campaign/frozen-model/` and checks the
actual, unchanged predictor SHA256 before every shard. It never rebuilds that
predictor from the editable worktree. Original CAMPAIGN, PREFLIGHT, selection,
JOB pins, capture binaries and reservation guards are unchanged. A future live
edit cannot affect this frozen experiment; an altered campaign executable or
frozen provenance still fails before capture. Results remain attributable to
the ORIGINAL H1725 artifact, not automatically to arbitrary later live code.

Source isolation evidence: `model-isolation-h64at6rf/REPORT.json` and its exact
`source-change.diff` in the campaign directory. Five isolation/mutation checks
PASS, plus the complete 14-check recovery suite, original 216 CLI comparisons,
five reservation controls and seven hostile scorer mutations. Replayed 59,932
sealed rows PASS; no hardware was executed for these checks. The snapshot CLI
was built only for tests; the campaign predictor was NOT rebuilt or replaced.
An additional software-only build of the current F2XM1-edited source matched
the frozen predictor byte-for-byte on all 59,932 saved job-000440 inputs across
all twelve instruction/RC streams, including C1 metadata. The campaign still
uses the original predictor, not this comparison binary.

Before resumption, last completed local and remote receipt archives matched:
i7 `job-003333`, cumulative 103,490,777 cases; Skylake `job-006782`, cumulative
404,145,624 cases. All output/C1/C2 miss counts zero. There were no next-job
directories or archives; native freshness is still enforced by the original
ledger and bitmap, not inferred solely from absence. Both original failure
latches are preserved as `RESUME_STOPPED-source-pin-20260907.json`; no receipt,
reservation, source edit or hardware observation was removed/repeated.

Only the two failed launchd services were removed and resubmitted with the
same arguments. The status watcher was left running. Resumed controllers
revalidate completed checkpoints before advancing to genuinely unexecuted
shards; `VERIFYING_EXISTING_CHECKPOINTS` reports progress every 100 shards.
Use current receipts/status for subsequent progress, not the counts above.
Paper/PDF and live C/F2XM1 edits were left untouched by this recovery.

Resumption confirmed, not merely scheduled: all 3,334 i7 and 6,783 Skylake
completed checkpoints revalidated. i7 resumed at job-003334 (45,000 new PASS)
and reached job-003348 (103,959,566 cumulative; 468,789 new since recovery).
Skylake resumed at job-006783 (58,412 new PASS; 404,204,036 cumulative) and
advanced into job-006784. Both are actually taking fresh captures again,
with zero output/C1/C2 misses. Controller PIDs at this checkpoint: i7 67512,
Skylake 67513, both launchd-owned. Early new-session ETA includes the one-time
checkpoint review and is temporarily pessimistic; do not present it as a
fresh steady-state hardware throughput measurement.

## 2026-09-06 recovery: both hosts resumed under launchd

The user's status request exposed that both original foreground controllers
had exited and the old live-status watcher had stopped. The precise exit
cause is not established; there was no recorded model miss. Before recovery,
Skylake had 24,895,664 scored cases (441 shards, including a scored shard
without its final offload acknowledgment), and i7 had 5,829,986 scored cases
(157 shards) plus 40,028 captured-but-undownloaded cases. All scored cases
were clean. Do not interpret the stale status file as continued execution.

`h1725_resume_full.py` now validates the original frozen selection, unchanged
predictor/source pins, every existing shard's exact input/index mapping,
capture checksums, portable observation manifest, and cumulative DONE totals.
It recovered i7 job-000157 and acknowledged Skylake job-000440 without any
instruction replay. The recovered i7 40,028 cases PASS. Both hosts then
executed genuinely new shards (i7 job-000158 onward; Skylake job-000441 onward),
which are passing at this checkpoint. Full selected runs are NOT complete.

OS-managed services (not chat-owned exec sessions):

- `com.steve.x87.h1725.i7`
- `com.steve.x87.h1725.skylake`
- `com.steve.x87.h1725.status`

Controller processes were confirmed parented by launchd (PPID 1).
`caffeinate -i` inhibits idle sleep for their lifetime. The Mac still needs
power and network connectivity; a shutdown/logout is not a completed run.
Persistent logs are `{host}/launchd.stdout.log` and `launchd.stderr.log`.
`CONTROLLER.json` records actual stages; `RESUME_STOPPED.json` is a failure
latch that requires inspection, never blind removal/restart. The updated
LIVE_STATUS includes pending scored shards, actual controller PID presence,
controller update age, and live recovery stage. Watcher writes are atomic.

`h1725_dispatch_remote.py` starts each individual unchanged guarded capture
in an independent remote session. A durable DISPATCHED marker precedes process
creation; dispatch is never repeated for a started, failed, complete, or
uncertain job. Only transfers and idempotent guarded control requests retry.
The old reservation bitmap and original ledger remain authoritative. A real
model miss stops the host before any subsequent shard is dispatched.

After verified local offload, new job metadata is losslessly packed into
`/root/h1725-full-corpus/receipts/job-NNNNNN.json.gz`; a second copy is retained
locally as `jobs/job-NNNNNN/remote-receipts.json.gz`. It contains the exact
base64-encoded bytes of the original metadata/log files. Original per-job
metadata files and empty directories are removed ONLY after verification of
that permanent archive. Numeric payloads stay in the local job directory.
Future audits MUST inspect these receipt archives alongside RESERVED.bits and
the ledger's full_corpus_jobs table: an archived job directory's absence is
NOT evidence of a fresh tuple. Existing pre-recovery job directories remain.

Skylake space reclamation removed ONLY the redundant uploaded file
`/root/h1719-policy2-verifier/retained.zip` (220,327,102 bytes), after checking
its SHA256 against the preserved local original:
`tmp/ledger33/current/h1719_local_checks/retained.zip`, SHA256
`4351394266f9af1df1298d28eec2873dabbc1a5d1d7a1999287c0345c2e29ab1`.
The archive is fully recoverable from that local original; no historical
capture, ledger, source or report was removed. A subsequent independent disk
check reported 4.3 GiB free; that larger change is not attributed solely to
the 220 MB archive removal.

Recovery preflight: 14 local checks PASS, including duplicate/failed/uncertain
dispatch rejection, lossless receipt packing and replay, unknown-file refusal,
local-payload reuse after remote offload, and exact re-score of 59,932 sealed
Skylake observations. Original preflight also re-passed: 216 default CLI
comparisons, five reservation controls, seven scorer mutations. No native
hardware was executed for these preflight checks. Old reports are preserved;
`RECOVERY_PREFLIGHT.json` identifies the newest report and source hashes.
The last local-payload recovery improvement was made after the controllers
started; it applies on their next invocation, without interrupting current
captures. Main C/defaults, corpus inputs, paper TeX and PDF remain unchanged.

Thread heartbeat `finish-two-host-x87-verification` is active every 30 minutes:
check real progress, recover orchestration safely, report meaningful failures
or completion, and pause when both selected runs are reconciled. Do not run
old h1725_run_full.py again; it is intentionally not a resume implementation.
No new authorization is needed for these already authorized host campaigns.

## Original launch checkpoint (historical; not current status)

User explicitly requested execution, not another proposal. Started preparation
on 2026-09-05 for corpus `x87-trig-v1-2126cf9ff5272e9d`: 42,289,770 operands,
three instructions, four rounding modes, PC64, 507,477,240 cases per host.
No algorithm, corpus input, paper or PDF changes.

ACTUAL HARDWARE STARTED on Skylake. The frozen selection is 489,098,260
fresh cases over 41,513,558 operands. First 12 scored shards: 719,868 fresh
cases, zero output/C1/C2 misses; initial observed end-to-end throughput
about 3,056 cases/s projects roughly 44 hours, not the earlier capture-only
planning estimate. i7 remains in public-history audit at this checkpoint;
its live pipeline automatically proceeds to selection and capture afterward.
Read `LIVE_STATUS.json` for current counts rather than treating these first
shards as a final result. The status watcher never executes or retries inputs.

Current durable state: `tmp/ledger33/current/h1725_full_campaign/`.
`CAMPAIGN.json` pins the source, corpus and host selection. Per-host
`SELECTION.json`, `RUN_STARTED.json`, job `DONE.json` files and
`RUN_COMPLETE.json` distinguish preparation, actual capture and completion.
Do not call a running history audit a hardware run.
`LIVE_STATUS.json` is updated by `experiments/h1725_status.py --watch`.

Existing observations and reservations must be reused/excluded. Legacy
instruction/RC coverage without authenticated PC is a recapture exclusion,
not a PC64 pass. Unknown public/private or generator-history matches are
held, not silently counted as fresh or passed. Completing the cleared
selection is not necessarily completion of every full-matrix case.

The local machine has ample archive space. Initial remote free space was
approximately 1.1 GiB on i7 and 317 MiB on Xeon. The new runner therefore
uses bounded shards, compressed local offload and a permanent 63,434,655-byte
remote reservation bitmap rather than a hundreds-of-millions-row SQL ledger.
Existing SQLite ledgers are preserved and checked before each batch. Their
new `full_corpus_jobs` table links the permanent bitmap and per-job receipts.
Never ignore this registry when preparing another campaign.

Remote campaign directory: `/root/h1725-full-corpus` on both hosts.
Default capture binaries and existing ledgers are retained. Only public
capture/audit code and cleared public inputs are transferred; no private
source, private audit membership or model source is uploaded. Model
predictions use the unchanged default C graph locally, before each capture.
Every result is retained and checked. A miss or capture error stops that
host's controller; reserved bits are never cleared, and no instruction is
retried. Scratch payloads are unlinked only after checksum-verified local
offload; their local copies, remote reservations and receipts remain.

Preflight checks ordinary default CLI equivalence, duplicate/out-of-range
reservation rejection and synthetic scorer/control/stream mutations.
The initial scorer test caught a portable observation-header case mismatch;
it was corrected before any H1725 hardware execution, and the failed
synthetic artifacts are preserved. The initial public read-only audit was
replaced by an input-focused scan to avoid treating output-only `OK` records
as candidate input history; interrupted audit artifacts remain preserved.
The first private decimal parser conservatively stopped on an out-of-raw80
exponent. The corrected range analysis handles such literals without large
integer allocation; `PRIVATE_RANGE_EQUIVALENCE.json` confirms the subsequent
zero-padding refinement leaves the actual private exclusion set unchanged.
No hardware was executed by these parser/audit checks. Both public alias
audits found zero extra copies outside the mapped/declared software roots.

Scripts: `h1725_full_campaign.py`, `h1725_setup_history.py`,
`h1725_public_history.py`, `h1725_select_full.py`, `h1725_remote_capture.py`,
`h1725_run_full.py`, and `h1725_preflight.py` under `experiments/`.

Claim boundary: finite corpus verification on these two reported Skylake-era
contexts, not exhaustive raw80 correctness or old-Pentium generation parity.
No historical alternative-policy comparisons are part of this campaign.
