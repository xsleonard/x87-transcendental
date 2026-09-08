# H1684–H1685: capability evidence; XRSTOR preparation paused

2026-09-04 local date. No FSIN/FCOS capture or label opening. No production,
default or paper/PDF change. H1685 is **compiled, unexecuted, not frozen**.

The user directed a return to compositional numerical/domain closure rather
than further campaigns on the same collapsed summary-state support. Preserve
this preparation, but do not generate/freeze/run an XRSTOR campaign now. It is
not blocked on authorization: research campaign authorization already covers
i7 `142.132.217.24` and Skylake Xeon `45.32.204.118`.

## H1684: read-only enumeration

`capture-kit/x87_xsave_capabilities.c` ran on the Xeon in the isolated directory
`/root/fsincos-h1684-xsave-capabilities`. It uses CPUID and one XGETBV(ECX=0),
after checking XSAVE/OSXSAVE support. Its machine-code audit finds no x87,
restore, state-setting or privileged register instruction. This is capability
enumeration, not a new transcendental observation or processor-setting change.

The host reports GenuineIntel family 6/model 85, XCR0=0x2e7, standard state-area
size 0xa88 and CPUID.0D.1.EAX=1. Standard XRSTOR and XSAVEOPT are advertised;
compacted XRSTOR/XSAVEC, XRSTORS and XGETBV(ECX=1) are not. The retained
CPUID.0D.1.EBX=0x988 is an enumeration anomaly against the documented zero
without XSAVEC/XSAVES; it is not permission to execute an unsupported form.
The audit pins the already retained Intel SDM revision 089 text as its source.

The request-bit0/image-present-bit0 branch classification is skip if request=0,
initialize if request=1/present=0, load if both=1. That is a documented branch
classification, **not an observed validation of those three XRSTOR behaviors**.
The immutable H1684 report's `next_scope` records the plan at audit time; this
note and the current handoff supersede that scheduling suggestion.

## H1685: retain the unexecuted instrument

`capture-kit/x87_xrstor_paths_capture.c` includes the pinned H1678 restore
instrument, adds standard XRSTOR/XRSTOR64 with masks 0/1 and a zero-reserved
aligned header, and reuses the no-wait observations. GCC 12.2 compiled it with
O2, C11, Wall/Wextra/Werror and fno-builtin in the isolated Xeon directory
`/root/fsincos-h1685-xrstor-paths`.

The source, ELF, disassembly and compiler identification are retained locally.
The ELF was **never executed**. No bank, frozen manifest, input file or
hardware-output directory was created. A complete static CFG/safety audit was
not completed; do not relabel this as a static-verified capture. No parser,
scorer or freshness clearance exists. No claim about restore results, x87
initialization values, off-diagonal state reachability or pending delivery
follows from compilation.

H1680's 1,008 completed restoration-only rows remain useful negative evidence,
but add zero transcendental or pending-delivery observations. H1670 stays on
protocol hold. Neither that campaign nor any closed campaign may be rerun.

## Artifact anchors

Paths below are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `capture-kit/x87_xsave_capabilities.c` | `23ec5cf8af023869a6b451fe5000042025f5b36a8447814094f4fad79c17c802` |
| `tmp/ledger33/current/h1684_xsave_capabilities/capabilities.txt` | `17a60568824e046b1cea51320519118c1288f9b1d091bca4aef48e025da709dd` |
| `experiments/h1684_xsave_capability_audit.py` | `88e36a5f838722e5bcad7c35c0f39b01292ae2933c12c8b7b2b16f596f79d8ee` |
| `tmp/ledger33/current/h1684_xsave_capability_audit/report.json` | `c5756330fca49686ad1d44b8e7d3724d50ccf4b90e9f116662eedeb51a349747` |
| `capture-kit/x87_xrstor_paths_capture.c` | `532480d44493d1bfff4d686cceb525c9c0853d74aa7b4f194561e5918672b8e6` |
| `capture-kit/x87_restore_paths_capture.c` | `afbd0cf2efe33a091c165623a49c2c3941fcda81f6b2df8d128f05f383059f16` |
| `tmp/ledger33/current/h1685_capture_build/x87_xrstor_paths_capture` | `655a7fed264a8a8dda376d46ab46aaed14987606fae09c79f1e4c083f11b9008` |
| `tmp/ledger33/current/h1685_capture_build/capture.disassembly.txt` | `33ab044ff3659e0497f25d9af489870b2023fa8f8c5dbc4721117d2d1146dfe5` |
| `tmp/ledger33/current/h1685_capture_build/compiler.txt` | `8c59c3b7b9051484db9a6b6576edf12a3aca7381a06a174a2d4dbfd6ce08681f` |
