# H1525: public Pentium Pro mapper provenance audit

> **H1555 correction (2026-09-04):** this audit consumes H1467's now-falsified
> 19-eight-dword body partition. Its bounded result applies only to that
> mispartitioned dataset and does not constrain the actual 21-seven-dword
> Pentium Pro bodies. See `notes/h1555-ppro-public-layout-correction.md`.

Date: 2026-09-04

Status: exact source-scope audit; public old physical mapper not obtained; no
selector, emulator, hardware, or paper/PDF change.

## Public evidence

The available Peter Bosch `p6tools` repository publishes a physical/logical
scrambler described and titled as Pentium II. H1490 independently transcribed
that mapping, reproduced all 63 lower-72-bit operations in a paired public
fixture exactly, and then rejected transfer to all four recovered Pentium Pro
patch bodies. The separate public `patchtools_pub` repository likewise calls
itself a Pentium II patch tool and points back to `p6tools` for MSRAM
descrambling. It supplies no second old-format mapper.

Public sources audited:

- <https://github.com/peterbjornx/p6tools>;
- <https://github.com/peterbjornx/patchtools_pub>.

## Conclusion

The inspected repositories do not supply the missing Pentium Pro physical
serialization or its inverse. H1490's failed transfer applies to the published
Pentium II mapping. It does not prove that an older mapping cannot be
recovered from an independent observable.

No x87 instruction or fresh hardware capture ran, no private capture-ledger
label was opened, and no emulator behavior/default or academic paper/PDF
changed.  H1488 remains `FROZEN_UNOPENED`; R96 remains empirical/incomplete;
the authoritative frontier remains eleven mode rows over ten operands.
