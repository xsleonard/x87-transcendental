# H1545 Pentium Pro mapper prefix localization

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its exact subset results apply only to that
> mispartitioned dataset and do not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: **exact SAT/UNSAT localization inside the rejected direct mapper
family; no physical decoder, selector, or promotion.**

## Scope

H1543/H1544 prove that no shared injective fixed-polarity selection of twelve
physical channels maps all 38 recovered `0x611`/`0x612` rows into the current
459-value public-P6 recognized-opcode language. H1545 replays the same exact
CSP on selected row subsets to determine whether that contradiction belongs
to either body alone or to a final-group special case.

Each case is solved in a separate process. The report is emitted only after
all six cases reach their predeclared SAT or UNSAT outcomes; UNKNOWN cannot be
silently promoted.

## Results

| case | `0x611` rows | `0x612` rows | status | nodes | maximum depth |
|---|---:|---:|---:|---:|---:|
| `0x611` only | 19 | 0 | SAT | 908 | 12 |
| `0x612` only | 0 | 19 | SAT | 2,667 | 12 |
| aligned groups 0--11 | 12 | 12 | SAT | 52,398 | 12 |
| aligned groups 0--17 | 18 | 18 | UNSAT | 1,250,283 | 9 |
| omit only `0x611` group 18 | 18 | 19 | UNSAT | 806,050 | 8 |
| omit only `0x612` group 18 | 19 | 18 | UNSAT | 974,347 | 9 |

The SAT cases contain mappings that are replayed over every included row and
validated against the public opcode recognizer. They are feasibility controls,
not claims that any returned mapping is the real physical serialization.

## Interpretation

Neither recovered body is internally inconsistent with the bounded language;
the contradiction appears only when a single mapping must serve both bodies.
The aligned prefix through group 11 is still feasible, while the aligned
prefix through group 17 is not. Monotonicity therefore localizes the added
cross-body incompatibility to at least one of groups 12 through 17.

Both group-18 rows may be removed simultaneously while retaining UNSAT, and
removing either one individually also retains UNSAT. The result is therefore
not caused by a last-line or integrity-adjacent special case.

H1545 does not compute a minimum unsatisfiable core and does not classify
aligned prefixes 13 through 17 individually. More importantly, the result
still applies only to the rejected direct-selection/current-public-language
model. It supports the conclusion that the old bodies require a different
opcode catalogue, a non-selection transform, shared fields, or some
combination; it does not choose among those explanations.

## Subsequent compiled refinement

H1546 independently reimplements the no-Hall search in C, reproduces H1544's
full UNSAT counters exactly, and decides every aligned prefix. Prefixes through
group 15 are SAT; adding aligned group 16 makes the instance UNSAT. H1547 then
shows that, relative to the prefix-16 base, `0x611` group 16 alone is UNSAT
while `0x612` group 16 alone is SAT. See
`notes/h1546-h1547-ppro-compiled-localization.md`.

No absolute ROM/control-state observable or R59 selector follows. No x87
instruction or hardware capture ran. No H1488 label or private ledger was
opened. No emulator behavior/default and no academic paper/PDF changed. R96
remains empirical/incomplete, and the authoritative frontier remains 11 rows
over ten operands.

## Artifacts

- `experiments/h1545_ppro_mapper_prefix_localization.py`, SHA-256
  `f72159856f3a65c69a421c45182be64fde8fc9222591129639a112c19a7da85b`;
- `tmp/ledger33/current/h1545_ppro_mapper_prefix_localization.json`, SHA-256
  `579d3424aaeee228027bbcae8d0f8c5bf6d6dc9ed872c990641fd0fdbcba6c96`.
