# Verification expansion

The user requested that the verification-gap review be divided into separate
sessions. These four sessions fork the completed discussion and share the
current checkout, including saved research files and uncommitted work.

The four assignments have finished. All six prepared hardware jobs completed
once and were authenticated and scored. See the
[combined results](verification-expansion-results.md) for the findings,
tested corrections and remaining integration work.

## Sessions and ownership

| Session | Thread ID | Owned work directory |
| --- | --- | --- |
| Verify F2XM1 coverage gaps | `01a07c2d-b475-7520-a4a4-4d75edbd77dc` | `tmp/verification-expansion/f2xm1/` |
| Verify FPTAN coverage gaps | `01a07c2d-cb8e-7d60-96a6-d7ad220e97d2` | `tmp/verification-expansion/fptan/` |
| Verify logarithms on i7 | `01a07c2d-dbd1-7c40-859e-45a733b9b642` | `tmp/verification-expansion/logarithms/` |
| Audit trig and FPATAN coverage | `01a07c2d-eb87-7e62-9b86-51c5fa6142f6` | `tmp/verification-expansion/coverage/` |

Paths in this document are relative to `fsincos-re/` unless stated otherwise.
Each session owns its work directory and a report in
`docs/verification-expansion/` with the same short name. Keep candidate changes,
test utilities and proposed patches in the owned directory. Do not modify
shared numerical sources, the manuscript, publication evidence, release files
or this dispatch document concurrently. Integration follows review of the
individual results.

## Shared requirements

- Never put the user's name or email into code or documents without explicit
  permission. Original-work licensing remains undecided.
- Never force deletion or use a force flag for a destructive action. Preserve
  code comments unless removing their whole section. Do not commit, push,
  rewrite history, publish or delete research records as part of this work.
- Start with saved evidence. An absent file or an input excluded by a history
  check is not proof that the input was never tested. Authenticate input,
  instruction, RC, PC, processor identity and the fields actually checked.
- Respect all permanent no-repeat reservations, including started, uncertain
  and failed captures. Reuse saved hardware outputs; never recapture consumed
  tuples. Keep private history local and preserve third-party notices.
- Both the Core i7-6700 and the Xeon have substantial validation. The i7-6700
  is also Skylake. Name the two processors explicitly and distinguish their
  coverage per instruction. Do not describe the entire project as Xeon-only.
- Do not count historical overlap, software search candidates, proposed inputs,
  ambiguous history holds or mathematical impossibility claims as new hardware
  observations. Separate numerical differences from provenance gaps.
- Preserve the ongoing H1725 campaign and existing automation. Do not restart,
  interrupt or duplicate it. Read current status rather than reusing an old
  progress count.

## Hardware coordination

The coverage session is the sole dispatcher of new hardware captures for these
four forks. The other sessions prepare complete, reviewable requests in their
owned directories and notify that session. This serializes new dispatch work;
it does not replace the existing per-processor history ledgers or guards.

Each request must identify the exact inputs and controls, source and input
hashes, independent input construction, local history checks, expected fields,
capture protocol, intended processor and bounded runtime. Keep requests
input-only wherever the existing workflow requires it; do not export private
models or history. Freeze predictions before new hardware results.

The dispatcher checks authorization, existing reservations, remote history,
resource availability and the capture guard before execution. Reserve the
whole job before its first target instruction. Preserve any partial result
and uncertain reservation without retrying it. Do not start overlapping jobs
from these forks. Use the existing approved capture workflow rather than
inventing a weaker guard. If safe dispatch must wait, continue local work and
report the exact dependency without treating a prepared request as a pass.

Workers should send a concrete handoff to the dispatcher when a request is
ready, and send their findings when complete. The dispatcher should return
capture receipts to the owning worker for scoring. Internal task messages
are part of this delegation; no messages to outside people are authorized.

## F2XM1

Audit the historical H245-H259 and H403 material before declaring missing
coverage. The large binary64-derived campaigns and current publication replay
cover RN/RD/RU, while agreement for raw80 subnormal inputs remains unestablished.
Check whether later records already establish RZ, full-width significands,
precision-control behavior or exception flags.

Prepare focused checks for native raw80 tiny inputs, the subnormal/normal
boundary, signed zero, all RC settings, and relevant PC combinations. Inspect
the extra truncation when storing subnormal results. Include direct/table
joins and full-width inputs where the existing evidence warrants it. Use
independent arithmetic and saved processor outputs first. If a discrepancy is
found, reproduce it locally and prepare a general fix in an isolated copy,
with regression checks and a patch for review.

Start with `notes/f2xm1-reconstruction.md`,
`notes/sibling-exhaustive-validation.md`, `paper/verify_siblings.py`,
`paper/evidence/f2xm1-pseudocode-replay.json`, and `src/fsincos_skylake.c`.

## FPTAN

Audit special encodings, raw80 subnormals, exception flags and precision-control
interactions. Older campaigns already tested NaNs and corrected their push
behavior; do not present that as wholly untested. T0002/T0003 check normal
finite values, push, C1/C2 and stack transitions but do not validate a full
exception model.

Reconcile historical results for the missing members of the proposed adjacent
windows and boundary brackets. Only 9 of 32 signed windows and both endpoints
of 3,361 of 4,108 signed brackets survived that campaign's exclusions. Missing
members are not necessarily fresh. Prepare targeted requests only after
reconciliation. Include complete RC/PC groups around important boundaries.
The `a0051-e16` search remains unresolved; use bounded exact work and report
UNKNOWN honestly if no witness or exclusion proof is obtained.

Start with `fptan-re/ANALYSIS-T0001-T0003.md`, its corpus and coverage audit,
`notes/sibling-exhaustive-validation.md`, and `paper/verify_siblings.py`.

## FYL2X and FYL2XP1

Check all current records for i7 results before preparing another capture.
At the reviewed cutoff, acceptance was Xeon-only: 941,808 saved tuples and a
420,212-case prospective final challenge. Reconcile processor-specific history;
a Xeon observation does not establish an i7 result, and a missing i7 report
does not prove a tuple is safe to execute there.

Prepare a bounded i7 confirmation covering both instructions, all branches,
all four RC modes, selected complete PC groups, near-one and table boundaries,
tiny inputs, underflow/overflow, exceptional classes and stack-pop behavior.
Use the existing final C and independent rational reference. Keep FYL2XP1
within the documented API domain. Preserve earlier failed predictions as
discovery history. Submit new capture requests to the dispatcher; compare
authenticated results on both processors and report any remaining omissions.

Start with `fyl2x-re/ACCEPTANCE.md`, `fyl2x-re/verify_archive.py`,
`paper/evidence/logarithm-replay.json`, and `tmp/fyl2x-re/l0005/`.

## Trig, FPATAN and capture dispatch

Reconcile actual covered input/control/processor combinations for the current
trig corpus using H1719, H1722 and completed H1725 shards. Keep ambiguous holds
and unknown historical PC settings separate from passes. The 31 absent RZ
bank files are not 31 missing tuples. Do not restart the large campaign.

For FPATAN, authenticate the 28,456 older tie-discriminator tuples with
Xeon-only results and determine which still need i7 confirmation. The four
targeted RN64 addition tie rules have already been resolved by later work;
do not reopen the stale D0027 acceptance gaps as current facts. Audit the
remaining `a0064-below` mathematical-boundary query without treating failure
to construct a witness as a proof of impossibility.

Coordinate new hardware requests from the other three sessions as described
above. Keep a dispatch record and return receipts to the requesting session.
Track requests through preparation, reservation, capture and scoring; a clean
capture must still be authenticated and scored before receiving pass credit.

Start with `notes/h1719-two-host-final-verification.md`,
`notes/h1722-policy2-adversarial-confidence.md`,
`notes/h1725-full-corpus-campaign.md`,
`tmp/ledger33/current/h1725_full_campaign/`,
`fpatan-re/ANALYSIS-D0065-D0070.md`, and
`fpatan-re/corpus-v1/CATALOG-D0066.json`.

## Deliverables

Each report should say which suspected gaps were already covered, which were
closed by this work, which remain unknown, and whether any incorrect result
or flag was found. Link the exact saved receipts and local checks. Include
reviewable patches if needed, without applying them to shared production
sources. Use plain language and explain why a test exercises a missing case;
large input totals alone do not establish completeness.
