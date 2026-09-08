# REVIEW 2026-09-05 — independent reviewer verification of the H1713 delivery, 2026-09-05

Scope: a review session, asked to "take a look" at the claimed final FSIN/
FCOS/FSINCOS solution, re-ran the promoted default program (main source SHA256
`490039e7…e375e32`, `general/paired.h` `3eb19971…b151454`) against hardware
evidence the H1708–H1714 sessions had NOT rerun, plus fresh silicon. Nothing in
the promoted source, headers, paper or PDF was changed. One new reproducible
paired miss was found; its explanation is the already-existing all-edge
schedule alternative (H1710 policy 2), which is NOT promoted here.

## Result summary

| Check | Where | Rows / observations | Misses |
| --- | --- | ---: | ---: |
| Full standalone suite wall (`h1081_suitewall.sh` as written: randv1/hostv1 FSIN+FCOS x RN/RD/RU/RZ, comb7/9/11–18 FCOS x 4 modes) | i7 `142.132.217.243`, banked h491 labels | 180,717,132 results | **0** |
| The two corpora the wall script skips (comb8, comb10 FCOS x RN/RD/RU) | i7 | 33,760,629 results | **0** |
| Fresh random stratified bank, 3 instructions x 4 RC x PC64, both signs, 7,850 operands (tiny/denormal/bypass, all 30 polynomial binades, table, pi/4 neighbourhood, all reduction binades to 2^62, C2 region, specials, invalid encodings) | Xeon `45.32.204.118`, pinned h1712 `x87_state_capture` (`2a2adae7…`), ONE run 13:49:47–13:49:50Z | 188,400 tuples / 248,160 lanes / 184,776 C1 / 2,280 C2 | **0** |
| In-process FSIN comparator (`fsin_exhaustive`, binary64 space, RN/RD/RU, seed 0x1716, start 0 count 3,000,000 then start 3,000,000 count 2^30) | Xeon | 3,230,225,472 observations (values, C1, C2) | **0** |
| Paired corpora comb7_sc / comb9_sc / comb10_sc (FSINCOS, RN/RD/RU) — NOT among the 15 retained paired banks of H1709/H1713 | i7 | 45,517,233 instruction rows (91.0M lanes) | **1** |

The single miss: FSINCOS, RN, operand `3ffc e79000000c3e46e7` (direct
polynomial path, top binade). Hardware sine lane `3ffc:e5980e1fae54d858`,
promoted model `…d857`; cosine lane `3ffe:f97b7761040745d2` matches; SW 3020
(C1=0) matches. Re-observed fresh on BOTH hosts (Xeon pinned harness, i7
freshly compiled harness), identical. RD/RZ give `…d857`, RU `…d858` on
hardware and in the model; standalone FSIN RN gives `…d857` on hardware and in
the model. So the paired sine prevalue sits at or just above the RN midpoint in
silicon and just below it in the promoted graph: a schedule discriminator.

## Schedule test (analysis-only builds, `-DG_GENERAL_PAIRED=0 -DG_H1710_PAIRED=1`)

`experiments/h1710_paired_program.h` policies: 0 = archived fused sine graph,
1 = last sine edge materialized (== promoted `paired.h`), 2 = every Horner
product CHOP67-materialized before its RN64 coefficient add.

| Policy | miss operand, RN | comb10_sc rn/rd/ru | comb9_sc rn/rd/ru | comb7_sc rn/rd/ru | review bank (4 RC) vs promoted |
| --- | --- | --- | --- | --- | --- |
| 0 archived | `…d857` (wrong) | 9 / 7 / 7 | 5 / 5 / 5 | 0 / 1 / 0 | n/a |
| 1 promoted | `…d857` (wrong) | 1 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | identical |
| 2 all-edge | `…d858` (**hardware**) | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | identical (0 diffs, 62,800 rows) |

H1710/H1712 already recorded that policy 2 passes the full retained paired
census (23,838,534 lanes) and all 13,800 frozen H1712 tuples. With this
operand, policy 2 is the only one of the three fixed schedules consistent with
every paired observation known to this review. It is a fixed, operand-blind
graph, not a selector. Promotion of policy 2 is the user's call (the project's
promotions have been user-authorized); this review did not change the default.

## Standalone verdict

No counterexample found anywhere: the full historical suite (which the R96
model failed on 32 rows and which H1708/H1713 explicitly did not rerun), the
two skipped corpora, 3.2 billion binary64 FSIN observations, and 125,600 fresh
standalone tuples with C1. The previously known h1068 common miss
(FCOS RN `bffc 94332f6145084ae1`) is now reproduced: standalone `…361f` and
paired cosine lane `…361e`, both as hardware.

## Provenance and artifacts

- Builds: gcc 12.2 (Xeon) / i7 gcc, `-O2 -ffp-contract=off`, zero warnings,
  `--selftest` ok; binary SHA256 `3f53f420…44d0f` on both hosts.
- Repo: `transfer-tests/review-20260905/` — `bank/` (inputs, operands, CHECKSUMS,
  cpu-summary, start/complete UTC, `state-output.txt.gz` whose decompressed
  SHA256 `2fa66a32…8770da` matches CHECKSUMS), `pred/` (promoted predictions
  + traces, policy 1/2 replays), `score.json`, `gen_bank.py`, `score.py`,
  `run_review.sh`, `i7_suitewall/`, `xeon_fsin_exhaustive/`.
- Remote: Xeon `/root/fsincos-h1716-review/` (source, binaries, bank incl.
  uncompressed capture, variants); i7 `/root/h1716-review/`,
  `/root/r84/h1716_suitewall.{log,tsv}`.
- The 15,700 signed operands of the bank and the miss operand are now
  observed history for freshness audits. The 3.2B `fsin_exhaustive` inputs are
  reproducible from seed/start/count and are not enumerated.
- Process note: the H1700+ sessions computed predictions on the local Apple
  Silicon Mac; this review rebuilt and re-scored everything on the x86 hosts.

## Coverage accounting

- The suite wall script skips comb8/comb10 and totals 180.7M results, not the
  182,737,480 figure quoted in the notes; both sets pass.
