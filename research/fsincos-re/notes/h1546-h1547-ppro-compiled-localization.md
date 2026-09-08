# H1546--H1547 compiled Pentium Pro mapper localization

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their exact UNSAT/localization results apply
> only to that mispartitioned dataset and do not constrain the actual
> 21-seven-dword Pentium Pro bodies. See
> `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **independent compiled replay and exact tail-row localization inside
the rejected direct mapper family; no physical decoder or selector.**

## H1546 independent compiled engine

H1546 implements H1506/H1544's exact opcode-domain recursion independently in
C. It intentionally omits H1543's Hall pruning. The generated instance
contains the selected recovered physical rows and the complete ordered list of
459 public-P6 recognized opcode values. For each partial mapping, the engine
maintains the exact allowed-opcode bitset for every row, computes every viable
signed physical-channel domain, and uses the same ambiguity-based MRV tie
break. SAT witnesses are checked in C and then independently replayed by the
Python driver.

On the complete 38-row instance, the compiled implementation reproduces
H1544's no-Hall proof counters exactly:

| result | nodes | dead ends | domain failures | maximum depth |
|---|---:|---:|---:|---:|
| UNSAT | 649,124 | 649,124 | 504,074 | 8 |

Exact agreement on all counters, together with separate source code and SAT
witness replay, independently supports the Python UNSAT result.

The compiled speed permits a complete aligned-prefix census:

| included groups from each body | rows | status | nodes |
|---|---:|---:|---:|
| 0--11 | 24 | SAT | 52,623 |
| 0--12 | 26 | SAT | 5,406,369 |
| 0--13 | 28 | SAT | 23,871,651 |
| 0--14 | 30 | SAT | 12,833,126 |
| 0--15 | 32 | SAT | 7,890,956 |
| 0--16 | 34 | UNSAT | 3,225,390 |
| 0--17 | 36 | UNSAT | 1,257,221 |
| 0--18 | 38 | UNSAT | 649,124 |

All SAT mappings pass independent Python replay. The exact monotone transition
is therefore between aligned prefix 16 and aligned prefix 17: adding physical
group 16 from both bodies first makes the bounded mapping impossible.

## H1547 tail-row decomposition

H1547 fixes the SAT base consisting of groups 0--15 from both bodies and adds
each remaining row alone. Results are:

| added row | patch addresses | status |
|---|---|---:|
| `0x611` group 16 | `3FEC`--`3FEE` | UNSAT |
| `0x611` group 17 | `3FF0`--`3FF2` | UNSAT |
| `0x611` group 18 | `3FF4`--`3FF6` | SAT |
| `0x612` group 16 | `3FEC`--`3FEE` | SAT |
| `0x612` group 17 | `3FF0`--`3FF2` | UNSAT |
| `0x612` group 18 | `3FF4`--`3FF6` | UNSAT |

Every one of the nine cross-body pairs formed from groups 16--18 is UNSAT.
Every SAT witness again passes independent Python replay. Thus the aligned
group-16 transition is not pair-only: relative to the common prefix-16 base,
the `0x611` group-16 row alone is already incompatible with the current direct
mapper language, while the `0x612` group-16 row alone is not.

The classifications do not follow a simple final-row or hook-destination
rule. In particular, group 16 spans patch addresses `3FEC`--`3FEE`, which
contain recovered hook destinations in both patches, yet the two single-row
statuses differ. That observation is a discriminator fact, not a decoded
semantic assignment.

## Subsequent exception-bound refinement

H1548 proves that all 38 single-row omissions remain UNSAT, and H1549 proves
that all 703 two-row omissions remain UNSAT. H1550 supplies a four-exception
SAT witness with independent replay, while its bounded three-exception search
remains UNKNOWN. H1552 subsequently finds two three-exception mappings, and
H1553 independently replays both over all 38 rows. Together with H1549, this
resolves the exact bounded minimum as three. See
`notes/h1548-h1550-ppro-opcode-exception-bound.md` and
`notes/h1552-h1553-ppro-three-exception-minimum.md`.

## Boundary

H1546/H1547 do not recover the old physical format. They strengthen the
evidence that a shared direct bit-selection into the current later-P6 opcode
catalogue is the wrong abstraction. A different Pentium Pro opcode language,
non-selection transform, shared fields, unused/padding lanes, or combinations
remain possible. The result does not identify an absolute Skylake ROM state or
an R59 selector.

No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
R96 remains empirical/incomplete, and the authoritative frontier remains 11
rows over ten operands.

## Artifacts

- `experiments/h1546_ppro_opcode_csp.c`, SHA-256
  `81c3892ddbfd56d1a34583ae5f88385993a887e174e1956a7beff9ec2bbcd1fb`;
- `experiments/h1546_ppro_compiled_csp.py`, SHA-256
  `1ca6f46778ac8c5e74326fc49ceaf5c6f65296a57da08327874432fca9d2557f`;
- compiled binary, SHA-256
  `6da00e3e238c539e737361d12b9e0b634a31278e7c9f34ab70ebecf0ab4657fe`;
- `tmp/ledger33/current/h1546_ppro_compiled_csp.json`, SHA-256
  `fab75758afd8551d2b4c0769f8b2bfd864c898b3679db3acacf432b7da2aa385`;
- `experiments/h1547_ppro_mapper_tail_pair_localization.py`, SHA-256
  `2c06f2442cc39e72b3c2de8939f52f997de5ef59d46c78a4a55b897fb1e9721f`;
- `tmp/ledger33/current/h1547_ppro_mapper_tail_pair_localization.json`,
  SHA-256
  `e0aa95d4e5eb7be3eb1a91f9e3ec7f162e3f6b83b431df11efa7bfcbb14d6098`.
