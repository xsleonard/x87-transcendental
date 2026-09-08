# H1718 — additive adversarial corpus-v1 revision, 2026-09-05

User requested that miss-producing inputs and the full practical theoretical
adversarial set become part of corpus v1. The new content-addressed revision
is `x87-trig-v1-d641d37292814c79`; the preceding `40620ee30e943c81` release
is preserved, not relabeled or deleted. All original 4,010,549 operands and
profile/source memberships survive. Stable numerical case IDs are unchanged.

## Coverage and size

The 57 explicit public source groups contain 55,909,669 input appearances,
deduplicated to **42,283,466 raw80 operands**. The additions are:

- all 20 saved i7 input banks: comb3..comb19, comb13n, hostv1 and randv1;
  51,603,326 input appearances authenticated against read-only remote hashes;
- 14,999 unique raw operands from the explicitly listed H1400-H1715 public
  campaign manifests, including numerical inputs used by state experiments;
- 6,358 unique operands from eight bounded theoretical proposal banks,
  including proposals rejected only by freshness selection;
- all 15,700 signed independent-review operands;
- 121 mandatory known-miss/legacy fixtures, including both earlier paired
  misses and the policy-1 separator; every one is in smoke, core and full;
- 7,920 signed +/-16-significand-unit neighbors and 21,600 same-significand
  transports through all 30 polynomial binades, also in core.

These counts overlap. The transports are not exact reduced preimages or
assertions of further misses. State-campaign inputs inherit this suite's
depth1/clear/masked numerical contract, not the old restore/unmasked histories.
No private directory was searched and no hardware labels or model predictions
were inserted into the input corpus.

| Profile | Operands | Default instruction tuples |
| --- | ---: | ---: |
| Smoke | 289 | 10,404 |
| Core | 64,889 | 2,336,004 |
| Full | 42,283,466 | 507,401,592 |

All profiles test FSIN/FCOS/FSINCOS and RN/RD/RU/RZ. Core/smoke default to
PC24/53/64; full defaults to **PC64**, retaining every operand without tripling
the largest pass. Full all-PC remains explicit opt-in: 1,522,204,776 tuples.
At an assumed 1,000 executions/sec, full PC64 is 140.9 hours (5.9 days);
at 20,000/sec, 7.05 hours. Core is 39 minutes at 1,000/sec. These are planning
rates, not universal speed guarantees; a sufficiently slow CPU can take longer.
The all-PC expansion could take weeks on a slow CPU and is not the default.

The suite's `plan` command checks a rate/budget without running hardware.
Bounded exports accept `--start-operand` and `--operand-count`; progress is
recorded as `next_operand`. A 100,000-operand full chunk is 1.2M tuples.
The full PC64 text would occupy approximately 132 GB plus ledger/index space;
it is not pre-expanded in the package. Run useful shards once, use their
actual wall time for subsequent estimates, and never benchmark by repeating
an already captured tuple. No billion-input exploratory search is expanded
into the default corpus. "Full" is the explicit finite adversarial union,
not every possible mathematically adversarial raw80 input.

## Validation and preservation

- Sorted uniqueness, all original operands/profile flags/source bits and
  complete 2,336,004-case core / 10,404-case smoke exports verified.
- Every mandatory miss/legacy input is in smoke and core.
- Independent exact arithmetic verifies 778,668 core instruction cases,
  1,026,848 output lanes and 745,836 known C1 checks against promoted main.
- Eight synthetic protocol, mutation, merge, identity, no-repeat, partial-run,
  bounded-export and budget tests pass. No hardware executed.
- The archive contains 77 explicitly allowed files, 256,565,514 bytes.
  It is authenticated after writing and again from a pristine extraction.
- Original corpus and zip remain under `corpus-suite/releases/h1716-v1-original/`
  and `deliverables/h1716-v1-original/`. Nothing material was deleted.

The review's 188,400 saved tuples are normalized into a separate
`references/review-20260905-skylake` dataset, alongside the older 168,960
reference tuples. Only the original FMS/microcode summary was available;
raw CPUID and verified affinity were not invented. The new separator's saved
i7 observations remain in H1717 regression evidence, not relabeled as Xeon
or synthesized into the review dataset. The full Cartesian matrix has NOT
been observed; missing labels remain missing.

No remote reservation ledger was changed. Before any future capture on an
already-used CPU, import all applicable observations, retain reservations,
and perform the required local private/supplemental history check. The
supplied ready-made jobs are for a genuinely new CPU context, not a license
to recapture the current reference. The review's seed-based billion-input
history is not enumerated in the portable reference and must also remain
part of any future reference-host freshness audit.

## Evidence anchors

- Builder: `experiments/h1718_build_corpus.py`; explicit source inventory in
  `corpus-suite/corpus-v1/sources.json` and `mandatory-misses.json`.
- Remote input authentication: `h1718_import_inventory.py` and
  `tmp/ledger33/current/h1717_i7_inputs/SNAPSHOT.json`.
- Corpus verifier: `h1718_verify_corpus.py`; report SHA256
  `8027456a6666b9d4ca3ff4feb2a0a3e8ef84e9d6a2232faff79e462386bda75f`.
- Corpus manifest SHA256:
  `e9f9439954e7a04f145308e0f8f91b053519f379a73dc476225aefc916b230ec`.
- Distribution manifest SHA256:
  `20c5ce5ceedd986b2928d81e3ae7bb00d1a258f5e76f895ba268ecb5f948dd6c`.
- Final zip SHA256:
  `a0bd816120c97b942b0d7f813ec8864588ba7d117bacfee0bba6bf4a4cd5fcb3`.
- Packaging/pristine checks: `h1718_package_suite.py`,
  `h1718_delivery_audit.py` and their output reports.

The public `corpus-suite/README.md` is the run guide. H1717's arithmetic and
paper correction are separate from input selection and CPU observations.
