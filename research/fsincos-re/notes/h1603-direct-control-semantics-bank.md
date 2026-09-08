# H1603 — ready cached direct-FCOS wall for shared operation policies

The H1107 wall is ready for a genuinely shared fixed-operation policy that
survives the target constraints: **37,441 operands / 149,764 actual hardware
mode observations**, all positive normal direct FCOS in `[1/8,1/4)`, with all
four RC modes recorded for each operand. No policy was scored or promoted by
H1603. If no shared policy survives, this remains an explicitly prepared next
wall, not a success result.

No hardware, C model, remote retrieval, private-ledger access, tuple mutation,
new label, inferred mode, source/default change, or paper/handoff edit occurs.
The reusable loader is read-only; the CLI only writes a membership/provenance
manifest for already-observed data, not a capture manifest.

## Domain and observed coverage

Every input has clear sign, exponent `3ffc`, and an explicit normalized
64-bit significand. Independent rational decoding confirms the domain for
all 37,441 operands. Their observed bounds are
`3ffc:a820000000ae3841` through `3ffc:ffffffff0ed61bef`; this is a sparse bank,
not a contiguous or exhaustive interval.

| Original corpus | Distinct operands | Actual mode rows |
| --- | ---: | ---: |
| comb9 | 30,076 | 120,304 |
| comb16 | 7,365 | 29,460 |
| Total | 37,441 | 149,764 |

Each operand has exactly one RN, RD, RU and RZ row. Source locations agree
across modes, no tuple is duplicated, and every original `(corpus,index)`
maps to exactly one operand. The whole bank is disjoint by operand from both
the named 82-row bank and all 29 H1091 historical operands. All 149,764 tuples
are independently cross-checked against H1596's authenticated import.

## Provenance and an important old-artifact caveat

The authoritative output source is
`tmp/ledger33/current/h1107_controls_allmodes.tsv`, SHA-256
`3004f7187da5e0972c4359c49151b4c51570c9beeb18048dbe6982821425c1e8`.
H1590 and H1291 pin this table; H1596 pins their provenance. The H1107 importer
verifies every selected operand at its original corpus index and then reads
four existing hardware status streams. Thus RZ is a recorded row here, not
an assignment from RD.

The original `h1094_visible_controls.tsv` is incomplete structurally: it has
a nine-column header but all 37,441 data rows have only the first four fields.
It cannot supply valid corpus/index provenance. H1603 instead uses the
authenticated complete `h1094b_visible_controls.tsv`, SHA-256
`9a01217e0e893dd13cac77e148f94957b0ac55a82ae4b1f9c00cec0b8fe9c7be`.
Its location set equals H1107's exactly, and every selected operand and
hardware label matches the corresponding H1107 row. Its first four fields
also exactly match the old incomplete artifact, so no labels are silently
changed or recovered from model output.

This readiness audit rechecks authenticated local extracts and their
cross-links. It does not claim to have reread remote original status streams
or rediscovered their CPU provenance.

H1107 retained output values and corpus/index metadata, but **not** status
words, C1, precision-control settings, or per-row CPUID. Those fields remain
unknown. A future policy can be checked against all four output modes here;
it must not be tested against fabricated C1=0 labels or assumed PC settings.

## Selection bias: regression wall, not fresh validation

H1094's source script selected a deterministic sample of already-captured
rows whose two retained-correction probes gave different outputs and whose
incumbent output matched hardware in the selection mode. The complete
H1094b artifact confirms both properties for all 37,441 selected rows:
12,024 were selected in RN and 25,417 in RU. H1107 subsequently joined every
actual RC lane for those operands.

Consequently this bank is useful as a large cached regression wall. It is
not random, fresh, statistically representative, or independent of all
earlier searches. Passing it would not establish global generalization or a
100% solution. No existing capture tuple is made fresh by this manifest.

## Reusable interface and compact manifest

```python
from pathlib import Path
from h1603_direct_control_semantics_bank import load_controls, MODES

bank = load_controls(Path("fsincos-re"))  # verifies provenance; writes nothing
for observed in bank.controls:          # immutable, sorted by operand
    for mode in MODES:                  # rn, rd, ru, rz
        expected = observed.hardware(mode)
```

Each frozen `ObservedControl` also carries its original corpus/index and the
four exact one-based source-table line numbers. No model is needed to load
or use the bank. Missing modes, duplicate tuples, conflicting locations and
out-of-domain operands cause assertions rather than silent filtering.

`tmp/ledger33/current/h1603_direct_control_semantics_bank.json` records
membership by original corpus indices, ordered input/observed-tuple hashes,
coverage and provenance. It does not duplicate the hardware-output table or
contain private data. The ordered hashes are:

- Operands: `196201975604b38d7017007c35a7e89fbcec9f75ae2bea56a3cc8538e07c55ad`.
- Actual tuples: `0cb8043871c70af9edef83bce36f16fe7df92746f54bd067d223168bb4ced27a`.

## Review for duplication of H1602's exact policy family

No previously inspected experiment solves the same complete shared vector
of five policies at all thirteen H1595 cuts. This is a bounded source review,
not a proof that no overlooked historical script exists. The closest reviewed
work differs materially:

- H1595/H1600 exhaust faithful choices per operand; H1600 also joins actual
  RC/C1 labels. Neither requires one rounding-policy vector across operands.
- H1593 exhausts variable-precision policies only at three terminal cuts or
  the two last Horner additions, with the rest fixed.
- H1202 exhausts tiny round-history-tag recurrences, not full arithmetic
  per-node policies.
- H110 uses coordinate search for a different FSIN schedule; H128 exhausts
  ten binary exact/materialized edges for that schedule. H187 is a bounded
  paired P/Q coordinate beam search; H203 tests coherent route classes.

Those results should not be reused as proof that H1602's exact family is
already excluded. Conversely, an H1602 failure would only exclude its fixed
precision/sequence/payload/policy family, not every control-state or arithmetic
explanation.

## Verification

```sh
python3 fsincos-re/experiments/h1603_direct_control_semantics_bank.py --selftest
python3 fsincos-re/experiments/h1603_direct_control_semantics_bank.py \
  --root fsincos-re --output NEW_MANIFEST_PATH
```

Selftests cover domain endpoints/sign/normalization exclusions, a complete
four-mode group, and explicit rejection of missing modes, duplicate tuples,
and conflicting corpus indices. Full-bank checks verify 37,441 independently
decoded domains, exact H1596 parity on all 149,764 labels, source provenance,
and H1094b selection locations. No label or emulator behavior is modified.
