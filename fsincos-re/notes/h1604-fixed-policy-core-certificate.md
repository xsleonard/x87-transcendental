# H1604: independently verified two-output fixed-policy contradiction

Date: 2026-09-04. This is an exact exclusion of a specified finite arithmetic
family, not a closed-form impossibility result or a new selector. No hardware,
C-model execution, inferred observation, emulator/default change, handoff edit,
or paper/PDF update was performed.

## The two recorded outputs already suffice

The following two authenticated FCOS tuples have disjoint policy sets:

| Operand | Architectural mode | Recorded result | Provenance |
| --- | --- | --- | --- |
| `3ffc:b0000000044ca2bf` | RN | `3ffe:fc3a6170f7389cfa` | H1091 comb7 index 452822 / H1378 old-02 |
| `3ffc:cdcc0585c940196f` | RU | `3ffe:fad8efc715aca496` | H1580 E007 |

For every policy vector in the audited family, matching b000's RN output is
equivalent to matching all four of its actually recorded modes. Matching
cdcc's RU output is equivalent to matching that output plus its recorded C1=1
(status `3a20`), under the conditional ordinary-final-round C1 interpretation
used in H1599. Thus the contradiction requires **neither b000's additional
RC observations nor cdcc's C1**. The proof uses only the two output bit strings
above; no assumption about C1 hardware provenance is needed for that proof.

## Arithmetic family and compact contradiction

The graph is the explicit H1592/H1595 thirteen-cut schedule: shared square and
fourth power, two split Horner factors, terminal left/right products, and their
correction sum. All multiplications and the correction retain 67 bits; the
four Horner additions retain 64 bits. Final reconstruction is ordinary
architectural `RC64(1 + correction)`. Each internal cut receives its own fixed,
input-independent and RC-independent policy chosen from:

- CHOP: magnitude truncation (toward zero).
- RN-even and RN-away: nearest, with the stated tie rule.
- AWAY: away from zero when inexact.
- JAM: round to odd when inexact.

All intermediates are recomputed from altered upstream values; square/fourth
are shared by both arms. No arm is perturbed in isolation. The 1,220,703,125
vectors (`5^13`) count named policies, not distinct numerical behaviors.

Write `S,F,N,P,L,R,C` for the policies at square, fourth, negative factor,
positive factor, left product, right product, and correction. Let
`T = {RN-even, RN-away, AWAY}` and define:

```text
B = (S in {AWAY,JAM}) or (N in {AWAY,JAM}) or (P = CHOP)
    or (L in T) or (C in T)
```

The complete acceptance predicates for these exact observations are:

```text
b000, either payload variant: B
cdcc, omitted payload:        not B
cdcc, frozen numeric payload: not B and ((F in T) or (R in {AWAY,JAM}))
```

Consequently no common vector can satisfy both operands: it would require
`B and not B`. These expressions describe this finite core's acceptance sets;
they are not rules for predicting unobserved operands or proposed chip logic.

Payload-omitted means zero at every input. Frozen-numeric means the original
consumed empirical payload is held fixed even when upstream values change:
b000 uses `-2 * 2^-81`, cdcc uses `-4 * 2^-80`, added to the signed correction
before its final 67-bit cut. The original left exponents are respectively -73
and -72. Positive-magnitude payload subtraction therefore appears here as a
negative signed correction. No gate, payload, or scaling exponent is rederived
on an altered path. This second variant is an explicit empirical scaffold.

## Independent verification, including omitted policy dimensions

`h1604_fixed_policy_core_certificate.py` imports no H1602 solver/MDD code and
executes no C. It spells out the operation graph and independently implements
all five internal integer rounding policies. H1592 exact dyadic add/multiply,
constants, decoding/encoding and architectural rounding are shared, so this is
not an independent recovery of those constants or a new physical contract.

At each operation the verifier groups all five policies by their exact numeric
result. The groups are disjoint and cover all five choices. Recursing through
all thirteen operations creates disjoint Cartesian policy boxes: a complete
policy vector belongs to exactly one box, determined by its first divergent
local choice. Every leaf box is checked numerically against the recorded
outputs and checked algebraically to be homogeneous under the compact
predicate. Box volumes sum to exactly `5^13` in each operand/payload case.
Thus choices at omitted dimensions cannot change **acceptance on these two
operands**, even though they may change intermediate arithmetic.

| Payload | Operand | Numeric leaf boxes | Accepted full vectors | Full coverage |
| --- | --- | ---: | ---: | ---: |
| omitted | b000 | 7,936 | 1,164,453,125 | 1,220,703,125 |
| omitted | cdcc | 7,680 | 56,250,000 | 1,220,703,125 |
| frozen numeric | b000 | 8,192 | 1,164,453,125 | 1,220,703,125 |
| frozen numeric | cdcc | 7,936 | 42,750,000 | 1,220,703,125 |

There are also direct integer replays of every assignment of the retained
variables. The omitted-payload five-variable projection has 3,125 assignments:
2,981 satisfy b000, 144 satisfy cdcc, and zero satisfy both. The frozen-payload
seven-variable projection has 78,125 assignments: 74,525 satisfy b000, 2,736
satisfy cdcc, and zero satisfy both. The lifts through the remaining dimensions
are respectively `5^8` and `5^6`, reproducing the full counts above. These are
exhaustive projected replays, not samples. Their acceptance additionally agrees
with a read-only interpretation of H1602's saved diagrams, used only as a
cross-check after the independent arithmetic and box certificate.

Each single operand is satisfiable. An all-CHOP vector satisfies b000 in both
variants. For cdcc, use all CHOP except positive-factor RN-even; frozen numeric
also needs right-product AWAY for this particular witness. These witnesses,
including every exact/rounded stage and final output, are preserved in the
report. Since both singleton subsets are satisfiable and the pair is not,
the two-operand core is cardinality-minimum in this family.

The independent quantizer passes 30,660 signed integer/reference cases,
including an exact rational nearest-neighbor check of RN-away. The Boolean
box-range checker passes 2,000 exhaustive checks over deterministic small
Cartesian boxes spanning all seven relevant dimensions, including all-false,
all-true, and mixed boxes for every operand/payload predicate. Full numeric
box coverage and exhaustive projected replay are the proof; unit tests are
additional checks.

## Artifacts and reproduction

Authoritative output directory:
`tmp/ledger33/current/h1604_fixed_policy_core_certificate_v2/`.
The initial output directory is retained unchanged. Input hashes are checked
against pinned H1602/H1600 evidence, including the preserved source snapshot
`tmp/ledger33/current/h1598_source_before.c` with SHA-256
`de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.
No current C execution is needed.

| Artifact | SHA-256 |
| --- | --- |
| experiment script | `0d24e387cf10a6b218fa45f7bca53c5c0b0dc7ba7cebab8c293e6410fabb5463` |
| `report.json` | `ce8412a6f99cc7610890b148739949da5e3f3df0a60e7e3e751a29be61c96024` |
| `policy_boxes.jsonl.gz` | `005c2d2dfce289a1dcecfa300794d94d0ce5bd61e5e999b20d52380e7a16720f` |
| `projected_assignments.tsv.gz` | `b20b9a64e077aaac8cc7320febc738a92359b40daa5f301ab2df7f370bf4c83c` |

From the repository root, choose a fresh output directory:

```sh
python3 fsincos-re/experiments/h1604_fixed_policy_core_certificate.py --selftest
python3 fsincos-re/experiments/h1604_fixed_policy_core_certificate.py \
  --root fsincos-re --output-dir /private/tmp/NEW-H1604-DIRECTORY
```

The program refuses an existing output directory. A separate local rerun
reproduces the report and both gzip certificates byte-for-byte. Syntax and
whitespace checks pass.

## Claim boundary

This independent core excludes the five listed fixed per-node policies only
at the stated widths, operation sequence, final-rounding contract and two
payload variants. It does not exclude different precision, forwarding/fusion,
a different graph, input/control-dependent operation semantics, regenerated
payload logic, or a general closed-form solution. Because this particular core
uses RN and RU observations, it alone does not exclude RC-dependent internal
policies; the separate `h1605-same-mode-policy-core.md` certificate supplies
that consequence with two actual RD observations.
No new selector is promoted and no emulation failure is repaired here.
