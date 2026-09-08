# H1599: cached C1 refines the arithmetic inverse

Date: 2026-09-04

Status: **a genuine additional constraint on the broader H1595 arithmetic
family, not a selector or a physical-cause proof.** On the old f410/RU row,
C1 excludes every path varying only the eight Horner materializations while
keeping square, fourth power and terminal operations ordinary. A square-only
departure and terminal alternatives remain possible. No hardware was run.

## Status provenance and contract

The primary bank is exactly H1580's eleven and H1587's fifteen observed
mode/operand tuples: 26 rows, not 27. H1599 verifies their OPENED_ONCE hashes,
freeze, manifest, ordered lane inputs, raw capture bytes, capture metadata,
and existing scores before reading status. All have TOP=7 and PE=1; sixteen
have SW=3820 and ten SW=3a20. No other status bit is set. The hash-verified
capture source reads `FNSTSW` after FCOS/FWAIT and before the result store/pop,
so these are instruction status bits, not status produced by that store.

A separate, explicit extension checks f410 using the already observed
H1412/D0092 `init_load` row. H1423's hash-verified raw context contains 23
f410 rows across H1406/H1410/H1412, all RU, all
`3ffe:f8c35790ef2cf9b8`, all SW=3820. These are prior observations, not new
executions. RN/RD/RZ C1 is not present in those files and is not inferred.

Intel documents C1 as FCOS's round-up indication when the result is in range,
and describes its precision-exception role in the architecture manual.
Sources: [SDM Vol. 2A, FCOS pp. 3-331--3-332](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf),
[SDM Vol. 1, section 8.5.6](https://cdrdv2-public.intel.com/843827/253665-sdm-vol-1-dec-24.pdf).
Those descriptions do not identify an internal subtraction or prove that a
particular proposed arithmetic graph is the chip's implementation.

The inference below is therefore conditional: the observed positive result
must be the ordinary architectural rounding of the proposed positive final
prevalue `x=1-c`, and C1 must report that rounding. This is not a comparison
with the correctly rounded mathematical cosine. PE is instruction-level
inexactness; it is **not** used to reject an exactly representable final
prevalue after earlier internal inexact operations.

## Exact closed-form refinement

For observed positive output `y`, let `d=1-y` and let `I` be H1593's ordinary
output inverse for correction magnitude `c`. Under the preceding contract,

```text
C1 = 1  iff  y > 1-c  iff  c > d

I_C1=1 = I intersect (d, +infinity)
I_C1=0 = I intersect (-infinity, d]
```

In particular, positive RU has `I=[d,d+ulp)`. Therefore **RU with C1=0
forces c=d exactly**, without requiring observations in other rounding modes.
RN splits at d with the original even/odd endpoint inclusions preserved;
positive RD/RZ C1=0 adds no restriction. The implementation checks 1,040
independent forward/inverse membership cases including both tie parities,
exact points, and impossible directed-rounding C1 combinations.

## Broader-graph result

H1599 replays only the already enumerated H1595 v2 output-matching masks.
Every mask's endpoint is checked again; each signed correction then supplies
an exact C1 comparison. Output-missing paths cannot become output-plus-C1
matches, so another full-graph search is unnecessary. All per-mask results
are preserved in the compressed TSV.

Only the following four observed rows lose graph paths:

| Operand, mode | Frozen numeric payload: output paths -> output+C1 paths | Omitted payload: output paths -> output+C1 paths |
|---|---:|---:|
| `3ffc:cf62ea1253ad3be5`, RU | 3,776 -> 960 | 3,520 -> 1,344 |
| `3ffc:de400000a2e32d2a`, RU | 3,776 -> 960 | 3,712 -> 1,152 |
| `3ffc:f9e0000229067583`, RU | 3,520 -> 1,472 | 3,584 -> 1,536 |
| f410 extension: `3ffc:f4100000059862dd`, RU | 7,680 -> 1,536 | 7,680 -> 1,536 |

For the primary 26 rows, frozen-payload candidates decline from 93,248 to
85,568 and omitted-payload candidates from 93,184 to 86,400. All 26 remain
reachable; none changes a tested family's reachability. C1 does narrow the
RN output intervals, but every H1595 output-matching path for these eight RN
rows already satisfies the recorded C1.

The f410 extension changes the conclusion for a specific arithmetic family.
Its exact correction magnitude is
`0x73ca86f10d3064800 * 2^-72`. Before C1, changing only the last negative
factor (mask 32) was an output-matching witness. It gives instead
`0x73ca86f10d306480d * 2^-72`, hence a prevalue below y by `13*2^-72` and
predicted C1=1. Actual C1=0 rejects it.

More strongly, **none of the output-matching paths restricted to all eight
Horner sites survives C1**, for either payload case. This permits adjacent
faithful 67-bit results at every Horner multiply and adjacent faithful 64-bit
results at every Horner add; it is not merely a constant-ulp perturbation or
a last-add-only test. Square/fourth and the terminal products/correction are
held to H1595's ordinary operations in this family.

The minimum upstream-only witness is now uniquely mask 1 (the square), while
terminal-only masks 1024 (left product) and 4096 (correction materialization)
also remain one-departure witnesses. All three yield the exact same final
prevalue y and C1=0. This is still per-input reachability: it supplies no
uniform square rule, terminal rule, selector, or silicon-equivalence proof.

## Relationship to earlier walls

H1419 found no C1 separation between the **two specified forced-R59 carry
endpoints** whenever their complete output vectors were identical. H1599
does not contradict that result: it tests the much larger set of upstream
arithmetic corrections, whose output equality need not imply equal C1.
The cached status-word census is H1423; H1422 is the stagewise LZA audit.
No further bit beyond C1 appears in the new raw status census.

H1596's all-mode f410 output intersection and this single-mode RU+C1
intersection independently impose the same singleton under their respective
final-rounding assumptions. Neither establishes where silicon physically
generated that prevalue. R1263 remains falsified, R96 empirical/incomplete,
and the full bit-exact emulation goal remains open.

## Artifacts and verification

- `experiments/h1599_c1_arithmetic_constraints.py`, SHA-256
  `d670389fbb9619aa1447646e26d33381057cf7f8fabfafc40f4528a7ef0dbe9c`;
- `tmp/ledger33/current/h1599_c1_arithmetic_constraints/report.json`, SHA-256
  `94f627f006c4ace3486899bb7ac6487d01eaf90f1428567ffb712b0f8422f4af`;
- `tmp/ledger33/current/h1599_c1_arithmetic_constraints/successful_output_paths_c1.tsv.gz`,
  SHA-256 `8e21821a55dd9138c6ea205964385cdd0aabeb8f8584eeb202050eb36dfc6704`.

The graph and independent-integer specification are hash-checked against
H1595 v2. Historical C-source identity is checked against the preserved
`h1598_source_before.c`; current source/defaults are neither executed nor
modified. The source audit and 1,040-case selftest pass. Independent replay
reproduces both the JSON and compressed per-mask TSV byte-for-byte. All sixteen
overlapping output inverses (fifteen H1587 plus f410/RU) agree exactly with the
hash-verified H1593 v3 report. Python compilation and whitespace checks pass.
No capture labels
were newly opened, no remote research host was contacted, no paper/PDF was
changed, and no commit was created.
