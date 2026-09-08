# H1552--H1553 Pentium Pro three-exception minimum

> **H1555 correction (2026-09-04):** these audits consume H1467's now-falsified
> 19-eight-dword body partition. Their exact minimum-three result applies only
> to that mispartitioned dataset and does not constrain the actual
> 21-seven-dword Pentium Pro bodies. See
> `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **exact minimum of three rows outside the current public opcode
language inside the rejected direct mapper family; no physical decoder or
R59 selector.**

## Exact neighborhood search

H1550 supplies an independently replayed four-exception mapping for the
recovered `0x611`/`0x612` Pentium Pro bodies, while H1549 proves that every
one of the 703 possible two-row omissions remains UNSAT. H1552 searches the
declared local K=3 neighborhood consisting of every three-row omission set
that shares at least two rows with H1550's four-row set
`{2, 11, 19, 35}`.

There are exactly 208 such triples: the four three-element subsets of the
four-row set, plus `C(4,2) * 34 = 204` triples with two rows from that set and
one of the other 34 rows. Every retained 35-row instance is solved by H1546's
compiled exact no-Hall engine. Results are 2 SAT, 206 UNSAT, and 0 UNKNOWN.
Both SAT mappings pass H1546's independent Python replay over all retained
rows.

The SAT omission sets are:

- `0x611` group 11, `0x612` group 0, and `0x612` group 8; and
- `0x611` group 11, `0x612` group 0, and `0x612` group 15.

Their signed-literal mappings are respectively:

- `[249, 133, 328, 448, 159, 142, 433, 135, 244, 52, 235, 339]`; and
- `[73, 384, 327, 139, 428, 387, 367, 133, 26, 305, 53, 183]`.

## Independent full-row replay

H1553 reconstructs both H1552 mappings independently and evaluates them over
all 38 recovered rows, including the three rows excluded from each solver
instance. It requires twelve distinct physical channels, exact agreement with
H1552's retained-row opcode lists, and equality between the omitted-row set
and the full-replay unrecognized-row set.

Both mappings pass. Their complete exception sets are:

| mapping | body/group | decoded value |
|---|---|---:|
| first | `0x611` group 11 | `B63` |
| first | `0x612` group 0 | `D36` |
| first | `0x612` group 8 | `B36` |
| second | `0x611` group 11 | `295` |
| second | `0x612` group 0 | `F97` |
| second | `0x612` group 15 | `CBC` |

H1549 proves that no mapping in this family can have zero, one, or two such
rows. H1552/H1553 supply mappings with exactly three. Therefore

`minimum exception rows = 3`

is an exact theorem for the bounded model. The earlier H1550 K=3 UNKNOWN and
three-to-four bracket remain accurate descriptions of that solver run, but
they are superseded as the final bound by this constructive result.

## Boundary

"Exception" means only that the decoded twelve-bit value is outside the
current 459-value public-P6 recognized-opcode set under that particular
mapping. It does not establish that any row is invalid, padding, or unused.
The two SAT mappings differ substantially and are feasibility witnesses, not
a recovered physical serialization. The theorem remains confined to an
injective fixed-polarity direct selection of twelve physical channels and
does not validate that abstraction for Pentium Pro.

H1554 applies both mappings unchanged to the exact held-out `0x617` and
`0x619` bodies. They recognize only 4/38 and 5/38 rows, respectively, versus
35/38 on `0x611`/`0x612`. This exact transfer failure confirms that neither
mapping is a validated general decoder under the current public-language
test. See `notes/h1554-k3-mapping-sibling-transfer.md`.

No absolute ROM/control-state observable or R59 selector follows. No x87
instruction or hardware capture ran, no H1488 label or private ledger was
opened, and no manifest, emulator behavior/default, or academic paper/PDF
changed. H1488 remains `FROZEN_UNOPENED`, R96 remains empirical/incomplete,
and the authoritative frontier remains 11 rows over ten operands.

## Artifacts

- `experiments/h1552_ppro_k4_exception_neighborhood.py`, SHA-256
  `978eda416a4c0607dba53bcfd357ad50ecd2f33485a245844a5299af365e131b`;
- `tmp/ledger33/current/h1552_ppro_k4_exception_neighborhood.json`, SHA-256
  `3da9b1017bc76d5f6474cc86bda6c852e20df5af3e8ba2ad387847a67b14637b`;
- `experiments/h1553_replay_k3_exception_mappings.py`, SHA-256
  `e0bab341d924ea96065cf4bc808d51579e28f16132f7dc404a3ab1d165384674`;
- `tmp/ledger33/current/h1553_replay_k3_exception_mappings.json`, SHA-256
  `53f10035b4c579217cc1b15f83425a8a330463250255a46b7a3ec48d291c81c3`.
