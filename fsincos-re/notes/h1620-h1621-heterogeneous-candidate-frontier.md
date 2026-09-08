# H1620–H1621: broader cached candidate audit and incumbent frontier correction

Date: 2026-09-04. The fixed H1618 arithmetic survives the complete listed
heterogeneous capture audit. This is cached evidence, not fresh validation,
a recovered silicon contract or full closure. Canonical emulator/defaults
and the paper/PDF are unchanged. No hardware or private ledger was accessed.

## H1620: actual raw captures, with explicit hook/fallback separation

The inventory is H1509's 240,000-input dense bank, H1510's nineteen targeted
banks, and H1511's sweep, H269 mismatch and H65 polynomial banks. Original
input and capture hashes are verified against those historical reports.
Their old model scores are not used as truth. Every actual retained mode
row is scored; no missing mode or status bit is inferred.

An analysis-only in-memory build adds a monotonically increasing batch-row
index and observes final rounding only inside the unchanged H1618 header.
It returns the original arithmetic result unmodified. Each emitted index/C1
pair identifies an actual candidate hook hit. Absence means incumbent
fallback, whose output must remain exactly unchanged. R84 is explicitly OFF.
The C1 diagnostic compares the magnitude of the stored result with the exact
pre-round accumulator; it is not a complete architectural status model.

| Complete 23-bank audit | Raw row appearances | Output misses |
| --- | ---: | ---: |
| Candidate hook | 1,493,831 | 0 |
| Incumbent fallback | 1,210,854 | 0 |
| Total | 2,704,685 | 0 |

Of the candidate rows, 1,491,831 have actual status words, and every recorded
C1 matches the ordinary magnitude-increment indicator. The remaining 2,000
are H65 RN rows without status; their C1 is unknown. There are three baseline
output misses, all repaired by the fixed candidate, with no regressions.
These totals are **appearances across banks**, not a cross-bank deduplicated
tuple count. In particular, do not add the 1,210,854 fallback rows to the
candidate's validated domain.

The audit independently checks 5,504 selected hook endpoints and C1 values:
the uninstrumented H1618 binary exposes the true reduced magnitude/sign,
the independent dyadic graph evaluates its exact64 positive anchor, and a
separate signed final-round calculation must agree. Both external input
signs and the actual cosine-branch dispatch are exercised. The rest of the
emulator, including the separate sine polynomial, remains outside this
candidate claim.

### Preserved initial reader failure

The first H1620 run completed twenty banks and then exited1 on the sweep's
actual `C2 SW 3c00` status-only row. The initial parser only accepted `OK`
rows. This is an audit-reader failure, not a candidate mismatch. The original
script, prepared evidence manifest, completed reports and partial sweep
outputs are preserved, with `run-status.json` and no fabricated complete
report. Version2 adds the explicit C2 status-only case and replays the
software audit into a separate directory. No hardware was repeated.

Version2's entire output directory, including its report, binary and all
compressed streams, reproduces byte-for-byte at
`/private/tmp/h1620-root-replay.vGDlpl/audit`.

## H1621: three more cached incumbent misses, not candidate misses

These raw rows were not in the H1618 frontier:

| FCOS / RU input | Baseline output | Recorded output and fixed candidate |
| --- | --- | --- |
| `3ffc:9f4c73dd0c97e0d1` | `3ffe:fce8989e151e2b3c` | `3ffe:fce8989e151e2b3d` |
| `3ffc:ece7d0833c94a11a` | `3ffe:f92ded470d2d9a79` | `3ffe:f92ded470d2d9a7a` |
| `bffc:ece7d0833c94a11a` | `3ffe:f92ded470d2d9a79` | `3ffe:f92ded470d2d9a7a` |

All three recorded status words are `3a20`, with C1=1, also produced by the
candidate's independent rounding calculation. H1621 rereads the exact
original indexed input/status rows. It verifies both positive residuals
with the independent fixed graph; the negative input is an observed
even-cosine alias, not a third residual family.

The reconciled **incumbent** frontier is now at least:

- 47 failing positive-direct mode/residual rows over 46 residual operands;
- 78 failing external instruction/mode/input rows over 77 external operands.

Those replace the current 45/44 and 75/74 counts, while preserving them in
historical entries. This is not a claim to have exhaustively enumerated every
incumbent miss. Baseline O0/O2/O3/UBSan builds reproduce all78 failing values;
candidate O0/O2/O3/UBSan builds reproduce the hardware values for all78.
The candidate was not modified in response to these newly reconciled rows.

The independent repeat reproduces every H1621 result field. The baseline O0
binary differs in48 bytes confined to its Mach-O UUID and signature blob;
every other byte is verified equal. The dedicated replay verifier preserves
and discloses both hashes rather than calling the whole reports identical.

## Artifacts

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1620_heterogeneous_candidate_audit.py` (preserved initial) | `73df9f3922cdfaeb947d1d97a80fb760ccc1c0397002cbd816dd968c03d9dcee` |
| Initial `tmp/ledger33/current/h1620_heterogeneous_candidate_audit/run-status.json` | `2f3cd77ae1d9055138eaaa6945e5b60da112bff3cb43dcc684b9f2daffd854d5` |
| `experiments/h1620_heterogeneous_candidate_audit_v2.py` | `432ca4cd27dd8abd04302c232d823e925ad9b69cfb10cae73bd3d9341ac9b383` |
| `tmp/ledger33/current/h1620_heterogeneous_candidate_audit_v2/report.json` | `7ea431b36610cd0c8b82cbe8edd6b3ec3b0df3abdfc55dc8038c56e568096b60` |
| `experiments/h1621_cached_frontier_extension.py` | `a8b94b95f0a9429d2e70d0f0da68f89a6b76a8877582c7001141ce57e07a911f` |
| `tmp/ledger33/current/h1621_cached_frontier_extension/report.json` | `19b344095df1edb7e26b73c061571323a2e3b1d1f8fb3e19ba5c64b77da71688` |
| `experiments/h1621_verify_replay.py` | `1a0f8554adac4135fa9ed4c6fc351fdd0ed629ed2d920823d50b1d42813a500d` |
| `tmp/ledger33/current/h1621_replay_verification.json` | `eb956c2120b20113a91f63186d4921e9587d0c6c59d0b59abfd5bc3f32c24f20` |

```sh
python3 fsincos-re/experiments/h1620_heterogeneous_candidate_audit_v2.py \
  --root fsincos-re --output-dir NEW_HETEROGENEOUS_OUTPUT
python3 fsincos-re/experiments/h1621_cached_frontier_extension.py \
  --root fsincos-re --output-dir NEW_FRONTIER_OUTPUT
```

H1619 subsequently completes its raw stage-A audit and independent scoring
verification: all56,393,031 actual RN/RD/RU output/C1 appearances pass, with
four baseline fixes. See `h1619-raw-stagea-candidate-audit.md` for exact scope.
Next prepare fresh adversarial disagreements and agreement controls under the existing
tuple-audit/freeze/one-observation policy. Broad cache success does not prove
unseen inputs, remaining domains, general mechanism or full status behavior.
R96 stays empirical/incomplete; the fixed candidate remains isolated/default-
off. No academic paper/PDF changes are warranted by this cached pass alone.
