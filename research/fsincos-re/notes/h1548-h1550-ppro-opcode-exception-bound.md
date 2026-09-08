# H1548--H1550 Pentium Pro opcode-exception bound

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their exact exception bounds apply only to
> that mispartitioned dataset and do not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **exact three-to-four-row exception bracket at H1550, subsequently
resolved to three by H1552/H1553; no physical decoder or selector.**

## Question

H1543/H1544 prove that no shared injective fixed-polarity selection of twelve
physical channels maps all 38 recovered `0x611`/`0x612` rows into the current
459-value public-P6 recognized-opcode language. H1548--H1550 ask how many rows
must be allowed to decode outside that public language before the bounded
mapping becomes feasible.

An "exception" here is not an assertion that a recovered row is padding or
invalid. It means only that the row's decoded twelve-bit value is outside the
current public-P6 recognized set under a candidate mapping.

## Exact lower bound

H1548 omits each of the 38 rows in turn and solves the remaining 37-row
instance with H1546's compiled exact no-Hall engine. All 38 cases are UNSAT;
there are no SAT or UNKNOWN cases. Therefore no single unsupported or padding
row can repair the bounded mapper.

H1549 exhausts all `C(38,2) = 703` two-row omissions. Every remaining 36-row
instance is UNSAT, again with no SAT or UNKNOWN case. Therefore any mapping in
this family must have at least three rows outside the current recognized-opcode
language.

## Joint bounded-exception solver

H1550 independently extends the H1546 C recursion. Each row retains its exact
recognized-opcode domain while bits are assigned. When an assignment empties
that domain, the row is necessarily unrecognized for every completion of that
partial mapping and is charged to the exception budget. Consequently every
complete mapping is represented, and its charged rows are exactly its final
unrecognized rows; the search does not choose to discard a still-compatible
row.

At exception bound zero, H1550 reproduces H1544's complete proof counters
exactly: 649,124 nodes, 649,124 dead ends, 504,074 domain failures, and maximum
depth eight. Bound one is independently UNSAT after 17,947,513 nodes. These
checks support the implementation independently of H1548/H1549's row-subset
censuses.

The bound-three run uses a known four-exception mapping only to order branch
values. That ordering does not remove any branch, but the run reaches its
300-second bound before exhausting the search: 93,798,400 nodes, maximum depth
eleven, status UNKNOWN. This is neither SAT nor UNSAT evidence for three
exceptions.

At bound four, the preferred mapping is reproduced as SAT and passes an
independent Python replay. Its twelve signed literal indices are:

`[495, 63, 315, 477, 285, 115, 135, 142, 224, 368, 156, 239]`.

All twelve physical channels are distinct. Exactly these four rows decode
outside the current recognized set:

| row index | body | group | decoded value |
|---:|---|---:|---:|
| 2 | `0x611` | 2 | `6DF` |
| 11 | `0x611` | 11 | `1BF` |
| 19 | `0x612` | 0 | `A80` |
| 35 | `0x612` | 16 | `A8B` |

The exact minimum is therefore bracketed as

`3 <= minimum exception rows <= 4`.

There is no claim that the minimum is four. The K=4 mapping is an upper-bound
feasibility witness, not a recovered decoder.

## H1551 branch-order cross-check

H1551 retains H1550's domains and complete recursive tree but ranks literals
by the fewest newly forced exception rows first, followed by the same opcode-
mass and literal-index order. At bound zero it again reproduces H1544's exact
649,124-node counters. At bound three it reaches the 300-second bound after
90,193,920 nodes, at maximum depth ten, and returns UNKNOWN.

This is a search-order cross-check only. It supplies neither a witness nor an
UNSAT proof, does not improve the three-to-four bracket, and is the stopping
point for cosmetic value-order changes.

## Subsequent exact resolution

H1552 solves all 208 three-row omission sets sharing at least two rows with
H1550's four-row witness. Two are SAT and independently replayed. H1553 then
replays both mappings over all 38 rows and proves that exactly their three
omitted rows decode outside the public opcode set. Combined with H1549's
global K<=2 UNSAT census, this resolves the exact bounded minimum as three.
See `notes/h1552-h1553-ppro-three-exception-minimum.md`.

## Boundary

The bracket applies only to an injective fixed-polarity direct selection of
twelve physical channels into the current 459-value public-P6 opcode language.
It strengthens the conclusion that this direct-selection/current-language
abstraction is wrong or incomplete. It does not distinguish a different
Pentium Pro opcode catalogue from non-selection logic, shared fields, unused
lanes, or other old-format semantics. It supplies neither an absolute
Skylake ROM/control-state observable nor an R59 selector.

No x87 instruction or hardware capture ran. No H1488 label or private ledger
was opened. No emulator behavior/default and no academic paper/PDF changed.
H1488 remains `FROZEN_UNOPENED`, R96 remains empirical/incomplete, and the
authoritative frontier remains 11 rows over ten operands.

## Artifacts

- `experiments/h1548_ppro_mapper_leave_one_out.py`, SHA-256
  `c0ceada2a56f1e1d04ea7516356208e469ad034f72f82b8e07a8fe5862fb55a8`;
- `tmp/ledger33/current/h1548_ppro_mapper_leave_one_out.json`, SHA-256
  `f2603ddfd5ec56e074d919069372c4d4a51b2e4595c3455b0b2bd526d017034c`;
- `experiments/h1549_ppro_mapper_leave_two_out.py`, SHA-256
  `9916e817662fc1f22bca2f919f0912a353663fd89db924c25cb916834e67ca53`;
- `tmp/ledger33/current/h1549_ppro_mapper_leave_two_out.json`, SHA-256
  `598a4966757d34acde0f780754ba101fbc332388b88a0e0213bbd80605a829be`;
- `experiments/h1550_ppro_opcode_exception_csp.c`, SHA-256
  `80d7c942d6895f96d54a5da69bd77a0e05e055d5efea2b358822ee318b96f261`;
- `experiments/h1550_ppro_opcode_exception_audit.py`, SHA-256
  `369247de3cd9160bd3b3905adb5fd503438e65c3a5d20efed0eac90d4f6e3db7`;
- compiled H1550 binary, SHA-256
  `4a3c81ec9700e4c00bf7090194c1d01cb2d38eff892949c771aaeb125ecfc70f`;
- `tmp/ledger33/current/h1550_ppro_opcode_exception_audit.json`, SHA-256
  `2cfe114c702701476062ae2a652a5406ac3f78b668aa4dac82a32ad39187589c`;
- `experiments/h1551_ppro_exception_minfirst.c`, SHA-256
  `fdff5bae00a842d039e45a4ae0b32446d4c4f92b8d3c94af6ea654f81e14e055`;
- `tmp/ledger33/current/h1551_ppro_exception_minfirst.json`, SHA-256
  `5c87414b614fad11a83bed61fe1e53e239155d58121c2473d6e3193c7a1780c4`.
