# Goldmont–Pentium x87 transcendental lineage

Investigation date: 2026-09-03

## Result

The public Goldmont base microcode is **strong evidence of algorithmic and
constant-ROM lineage from the P5 design to the Skylake behavioral model**.
It does not establish bit-exact behavioral reuse.
The bit-exact Goldmont/Skylake question remains **undetermined** until a real
Goldmont result capture is supplied; static similarity cannot answer it.

The strongest facts are:

- all twelve 68-bit P5 six-term sine/cosine coefficients, projected to
  their upper 64 bits, occur exactly at Goldmont FP-ROM rows `0x1c..0x27`;
- seven of the eight unmodified P5 four-term coefficient projections occur
  exactly at `0x28..0x2f`.  The apparent exception, `P5S4_4` at `0x2b`, is
  instead an exact match for the model’s effective coefficient:
  the model subtracts significand bit 60 before use, changing the visible
  projection from `BAEAE2DCC1E64248` to Goldmont's
  `B8EAE2DCC1E64248`;
- all sixteen sine/cosine table-value projections for the eight P5
  breakpoints occur exactly at Goldmont rows `0x65..0x74`;
- a high-confidence paired transcendental path consumes the six-term rows in
  interleaved reverse-Horner order, selects a four-term path, and explicitly
  reads paired table rows with bases `0x65` and `0x6d` before producing two
  x87 results;
- the independently audited 506CA arrays keep the two candidate xlat stubs
  byte-for-byte identical while relocating their bodies; the relocated code
  re-establishes the same reducer, coefficient orders, table bases, and
  paired-versus-scalar result arities; and
- Goldmont rows `0x3f`, `0x41`, `0x42`, `0x56`, and `0x115` contain
  `C90FDAA22168C234`, exactly the upper 64 bits of the Skylake model's
  66-bit pi/2 significand `3243F6A8885A308D3` (the two omitted low bits are
  `3`).  The shared candidate reducer reads row `0x56`.

That combination is too structured to be explained by generic Taylor-series
similarity.  The exact coefficient payloads, the nonuniform eight-cell table,
the table order, and their use in matching paired kernels show implementation
ancestry or deliberate reuse.  It does **not** prove the same internal widths,
rounding history, quotient selection, final carry/borrow logic, or one-ulp
corner behavior.

The individually hash-checked 506C9 update collection contains revisions `0x2e` through `0x46`
(eight published revisions and 447 decoded match/patch hook records).  None
of those hooks targets a reconstructed entry, reducer, polynomial/table
kernel, route, or result block.  This preserves the relevance of the audited
base paths for that published update set; it does not cover later or absent
updates.

Evidence language in this note is deliberate:

- **Exact** means a byte/value/control-flow fact reproduced by
  `audit_goldmont_lineage.py`.
- **High-confidence identification** means the static shape uniquely fits an
  architectural instruction family but public data lacks the decoder trace
  needed to attach the instruction name directly.
- **Suggestive** means compatible with reuse but insufficient for a bit-exact
  claim.

## Primary artifact inventory

The repositories were inspected at these exact revisions.  The links are to
the primary repositories and pinned commits, not mirrors.

| Project | Pinned revision | Role in this audit |
|---|---|---|
| [`chip-red-pill/glm-ucode`](https://github.com/chip-red-pill/glm-ucode/tree/59f3b0a116807171862a25a163098b4c25a5c65e) | `59f3b0a116807171862a25a163098b4c25a5c65e` (2020-05-27) | Original five-array Goldmont 506C9 dump. Its [README](https://github.com/chip-red-pill/glm-ucode/blob/59f3b0a116807171862a25a163098b4c25a5c65e/README.md) uses early, partly conjectural array names. |
| [`chip-red-pill/uCodeDisasm`](https://github.com/chip-red-pill/uCodeDisasm/tree/ffc9070233a6e7a26dbabe723289259f087ee20b) | `ffc9070233a6e7a26dbabe723289259f087ee20b` (2024-01-18) | Defines the three-48-bit-uop triad plus 30-bit sequence-word format and supplies `ucode_glm.txt`. The [authors explicitly warn](https://github.com/chip-red-pill/uCodeDisasm/blob/ffc9070233a6e7a26dbabe723289259f087ee20b/README.md) that names and opcode meanings are incomplete. |
| [`pietroborrello/ghidra-atom-microcode`](https://github.com/pietroborrello/ghidra-atom-microcode/tree/705ff0663ae958c6f6b1330e77deb0258af97bae) | `705ff0663ae958c6f6b1330e77deb0258af97bae` (2023-03-13) | Ghidra processor module. Its [converter](https://github.com/pietroborrello/ghidra-atom-microcode/blob/705ff0663ae958c6f6b1330e77deb0258af97bae/lib/txt2ghidra.py) combines each uop with its sequence word into a synthetic 16-byte Ghidra instruction; this is a tooling container, not a native Goldmont instruction width. |
| [`pietroborrello/CustomProcessingUnit`](https://github.com/pietroborrello/CustomProcessingUnit/tree/4237524fe7545c66e42dd986113f220662c06f6a) | `4237524fe7545c66e42dd986113f220662c06f6a` (2023-03-13) | Dynamic tracing/patching framework, 506C9 and 506CA base arrays, update collection, hard-immediate dump, and FP-ROM dump. Its [README](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/README.md) states testing on CPUIDs 506C9/506CA and documents tracing. |

Downloaded commit tarball SHA-256 values:

| Repository | Archive SHA-256 |
|---|---|
| `glm-ucode` | `2859010744e0368f99bfe8c065b45837b297d2a497f34569157a1b801320729e` |
| `uCodeDisasm` | `256ef4353a14d759ca23abdd151d552aa34c4a2e0590e26621121f8fd07ed80a` |
| `ghidra-atom-microcode` | `d2434f99059efe62c4e7dd32aa0d0e8ce96aff1b02d69ea3e0bb9f82c562e0b6` |
| `CustomProcessingUnit` | `1934099c29b0e1786226198293218bf986173ef3d1204ba2ed68930f9a8e96dc` |

Reproduction download form:

```sh
curl -L https://github.com/OWNER/REPOSITORY/archive/COMMIT.tar.gz -o REPOSITORY.tar.gz
```

### Base ROM, sequence ROM, patch arrays, and other ROMs

The same five 506C9 files are byte-identical in `glm-ucode`,
`uCodeDisasm/ucode`, and `CustomProcessingUnit/uasm-lib/0x000506C9`:

| Later name | Original name | Meaning used by later tooling | SHA-256 |
|---|---|---|---|
| `ms_array0.txt` | `ms_rom.txt` | base MSROM, three 48-bit uops per addressed triad | `a5b6ca20c8466504d525bc78505ed47b57843f94e72969d13535b8b8386118b0` |
| `ms_array1.txt` | `ms_irom.txt` | base 30-bit sequence words; despite the original README's early “immediate ROM” guess, both later disassembler and Ghidra converter consume it as sequence control | `24e43b97f042f78848042ed1436710367481aba43313d603a0db2145bf6d7b95` |
| `ms_array2.txt` | `ms_patch_imm.txt` | patch-associated sequence/immediate array, not base MSROM | `f3cf26e4662907393d8798b2bbedc07f2a86a83e3e7c24b9e4618382e61ca315` |
| `ms_array3.txt` | `ms_match_patch.txt` | match/patch routing registers | `9ea94cec57af01a16fcac9a3d98bbd6ee22424e10f33de48cf95ac79a38705ec` |
| `ms_array4.txt` | `ms_patch_ram.txt` | patch-RAM uops | `c79fd231bdd7052f0ea26138cc9a2d1224575043beaecba4f82b53dc8aacdfae` |

The generated `uCodeDisasm/ucode/ucode_glm.txt` used here has SHA-256
`46fb61bfaf174765c117de65b036b73ae4433b9c2b9871d5289fd02d4867067e`.

Two other artifact classes must not be conflated with those arrays:

- `CustomProcessingUnit/ucode_collection/*.bin` and their decrypted patch
  records are signed microcode **updates**, not the base MSROM.
- [`bios/dumps/rom.txt`](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/dumps/rom.txt)
  is a 512-row FP constant-ROM projection, SHA-256
  `87b9ee93e0c7a1f988906d8fd79d886590aa41a7368d06ef1954be8d5aca14db`.
  The [dump code](https://github.com/pietroborrello/CustomProcessingUnit/blob/4237524fe7545c66e42dd986113f220662c06f6a/bios/custom-processing-unit.c#L1476-L1520)
  patches in `FPREADROM_DTYPENOP`, moves only 64 bits through
  `PINTMOVDTMM2I_DSZ64`, and invokes it for indices `0..0x1ff`.  Therefore the
  file does not expose a constant's exponent, sign/control metadata, or bits
  below the returned 64-bit payload.
- `bios/dumps/imms.txt` is a separate 1,024-row hard-immediate dump, SHA-256
  `6b25df6b7ad557ea7587b7a4302d9ae15c1b7db67ba6e509fb519aef6f5aa07e`.

The Ghidra module at its pinned head is byte-identical to the
`CustomProcessingUnit/ghidra-processor-module` subtree at that repository's
pinned head (`diff -qr` is empty); `lib/txt2ghidra.py` in each has SHA-256
`5809399ca368cd770083db698021b82e28a3966c97b0e51bcfdcff1dec4d3124`.
The module improves navigation but does not supply a missing x87 dispatch map,
resolve register aliasing, or define the opaque floating operations used by
the candidate kernels.

CustomProcessingUnit also includes a distinct 506CA five-array set.  It is not
byte-identical to 506C9.  The audit now checks it separately rather than
transferring 506C9 addresses into it:

| 506CA file | SHA-256 |
|---|---|
| `ms_array0.txt` | `b9f93d01c81983758f97be8071b450029928627b9c9dec81b4926bc6d4214798` |
| `ms_array1.txt` | `b747966ed8b0126a571707352c181cc0883021f4f72732ff8f8657a8205c8403` |
| `ms_array2.txt` | `b8728f19170e76e6d0fa4c5bb1a53fe68ca3ccb40fbff9eb8c95f16a0cf5a996` |
| `ms_array3.txt` | `ebf31d06fc120852d7b9e8dbd228450324cbb0fffa812e17a330444742be3c48` |
| `ms_array4.txt` | `1b34aeb115b830f2c2bbc9212bf52329fe0346339f6b58e2b70bd3a2f40aef94` |

The repository supplies one FP-ROM dump without a stepping-specific filename.
The exact value comparison below is therefore a fact about that checked dump.
The 506CA static code independently proves use of the same coefficient row
numbers and table bases, but a separate 506CA FP-ROM dump would be required to
promote the 506CA *values* from a stepping-lineage inference to an exact fact.

## Static entry and control-path reconstruction

No checked artifact contains the strings `FSIN`, `FCOS`, `FSINCOS`, `FPTAN`,
or `transcendental`, and no public trace binds macro-opcodes to the paths
below.  Missing labels therefore cannot be treated as missing routines.
Identification instead uses incoming xlat blocks, calls/returns, constant
indices, path shape, and architectural result count.

### Xlat-entry binding strengthened

The uCodeDisasm authors give three structural properties for an x86 xlat
entry: it is below `U1000`, is aligned to a multiple of eight, and has no
microcode references to its entry address.  `U0a58` and `U0a60` satisfy all
three: they are consecutive aligned eight-address-slot stubs, and each
address occurs only at its own definition in the pinned 506C9 listing.  The
next entry, `U0a68`, is the already labeled `sldt_r16_xlat`, consistent with
this being an xlat-table region.

The independently hashed 506CA MSROM contains exactly the same uop words at
`U0a58..U0a66`.  Only the sequence targets change, from `U3e41/U3c99` on
506C9 to `U3f05/U3d91` on 506CA, as expected when routine bodies relocate.
This establishes that both are stable x86 instruction entries and makes the
paired/scalar trigonometric-family identification stronger.  It still does
not reveal the unavailable macro-opcode-to-entry decoder table, so the exact
mnemonic binding remains high-confidence rather than direct.

### High-confidence paired FSINCOS candidate

The path is:

```text
U0a58 -> U3e41
             -> U3cbc                  shared candidate reducer
             -> U3e6d..U3e99           paired six-term kernel
          or -> U643d -> U6d84..U6da8 paired four-term/table kernel
             -> U649e -> U2b09/U64aa   phase/sign/lane routing
             -> U64b1 and U64b6        two x87 result writes
          or -> U4ad1 and U4ad6        alternate two-result finalizer
```

Key exact observations:

- `U3e60` saves return `U3e61` and transfers to `U3cbc`.
- `U3e6c` selects between the six-term body and `U643d`.
- The six-term body's immediate-indexed unknown opcode `0x6a0` reads rows in
  this interleaved order:

  ```text
  21 27  20 26  1f 25  1e 24  1d 23  1c 22
  ```

  These are respectively the reverse-Horner pairs
  `(P5S6_6,P5C6_6)` through `(P5S6_1,P5C6_1)`.
- `U6441` calls `U6d84`.  That block reads four-term rows in order:

  ```text
  2b 2f  2a 2e  29 2d  28 2c
  ```

  It then performs explicit `FPREADROM_DTYPENOP` operations at `U6da2` and
  `U6da6` using `tmp3 + 0x65` and `tmp3 + 0x6d`.
- `U64b1/U64b6` perform two final writes after one parity/phase route;
  `U64ac` selects the alternate `U4ad1/U4ad6` pair.  Thus both normal
  finalization branches have two computed architectural results.
  FPTAN also has two architectural stack values, but its second is exactly
  1.0; this path computes and finalizes two nonconstant lanes.  Together with
  the paired sine/cosine ROM use, that makes FSINCOS the high-confidence
  identification.

Special/exception paths leave through `U3e9c..U3ea8` and `U059c`; their
opaque operations should not be used to infer normal arithmetic.

### High-confidence shared scalar FSIN/FCOS candidate

The neighboring xlat block follows:

```text
U0a60 -> U3c99 -> U3cbc -> return U6ce4
                              -> U6cf8..U6d12
                           or -> U679a..U67b6
                           or -> U6d75 -> U6d84 table helper
                              -> one x87 result write
```

`U3cba` establishes `U6ce4` as the continuation of the same `U3cbc` helper.
The branch at `U6cf6` selects two complementary three-read chains:

```text
U6cf8..U6d0c: 20 21 1e 1f 1c 1d
U679a..U67a9: 26 27 24 25 22 23
```

Those are the even/odd halves of the same sine and cosine coefficient sets.
The table route enters the same `U6d84` helper.  `U6d12` and `U67b6` are
single-result terminals; the table continuation similarly ends in the
single-result `U5a2d` or `U5844` branch.  This is a high-confidence combined
scalar FSIN/FCOS implementation; which macro-opcode selects which initial
parity state is not recoverable from the available static labels.

### Independent 506CA path reconstruction

The distinct retail-stepping image reproduces the same structure at relocated
addresses:

```text
paired: U0a58 -> U3f05 -> U3db4 reducer
                    -> U3f31..U3f59 six-term kernel
                 or -> U657d -> U6ec5..U6ee9 four-term/table helper
                    -> U3f65 -> U3f66 plus U3f6c/U05a6 two result writes

scalar: U0a60 -> U3d91 -> U3db4 reducer -> return U6df2
                    -> U6e06..U6e21 sine half/result
                 or -> U68a2..U68be cosine half/result
                 or -> U6eb6 -> U6ec5..U6ee9 -> U5af5..U5b01 table result
```

Its four coefficient-read sequences are identical to 506C9, and its explicit
table bases remain `0x65` and `0x6d`.  This is a fresh control-flow check, not
an address transplant.  It corroborates the instruction-family binding
across both published Goldmont steppings while leaving exact FSIN-versus-FCOS
decoder selection and FPTAN unresolved.

### FPTAN remains unbound

The coefficient/table facts support a shared trigonometric family, and the
local model evaluates FPTAN using the same sine/cosine pair before one
final divide.  The Goldmont listing, however, contains no occurrence decoded
as the published `FDIV` opcode `0x646`, and the remaining `0x6xx` floating
operations are insufficiently named.  No static candidate is promoted to
FPTAN here.  A one-shot instruction trace is the shortest way to bind it.

## Constant comparison

The authoritative local comparison set is
[`../src/p5_rom_constants.h`](../src/p5_rom_constants.h).  The local
Skylake reconstruction uses these P5 ROM constants; see
[`../notes/algorithm-description.md`](../notes/algorithm-description.md) and
[`../notes/fptan-reconstruction.md`](../notes/fptan-reconstruction.md).

Goldmont's dump returns 64 bits while the local P5 constants have 68-bit
significands.  Every “exact” comparison below is therefore
`goldmont_payload == p5_significand >> 3`, not equality of a complete encoded
floating value.

### Coefficients

| Family | Goldmont rows | Result |
|---|---|---|
| `P5S6_1..P5S6_6` | `0x1c..0x21` | 6/6 exact upper-64 projections |
| `P5C6_1..P5C6_6` | `0x22..0x27` | 6/6 exact upper-64 projections |
| `P5S4_1..P5S4_4` | `0x28..0x2b` | 3/4 exact as unmodified P5; `P5S4_4` exactly matches the effective model coefficient |
| `P5C4_1..P5C4_4` | `0x2c..0x2f` | 4/4 exact upper-64 projections |

The current model constructs its effective leading four-term sine
coefficient as:

```c
p5c_t p6s4_4 = P5S4_4;
p6s4_4.sig -= (u128)1 << 60;
```

That produces the 68-bit significand `5C75716E60F321240`, whose upper-64
projection is exactly Goldmont row `0x2b`, `B8EAE2DCC1E64248`.  Consequently
the checked FP-ROM has 35/36 exact unmodified-P5 trig projections but **36/36
exact projections of the effective coefficient/table set used by the current
model**. This resolves the apparent static incompatibility
in the constant comparison.  It does not establish the coefficient's hidden low
three bits or the arithmetic that consumes it.

### Eight-cell lookup table

The exact row mapping is:

| `b` | `sin(b/64)` row | `cos(b/64)` row |
|---:|---:|---:|
| 18 | `0x69` | `0x71` |
| 22 | `0x6a` | `0x72` |
| 26 | `0x6b` | `0x73` |
| 30 | `0x6c` | `0x74` |
| 36 | `0x65` | `0x6d` |
| 44 | `0x66` | `0x6e` |
| 52 | `0x67` | `0x6f` |
| 60 | `0x68` | `0x70` |

Thus the contiguous hardware index order is
`36,44,52,60,18,22,26,30`, identically in both lanes.  The Goldmont helper's
two base reads select the corresponding sine/cosine pair with the same
three-bit index.  This joint data-and-control match is stronger than merely
finding familiar constants in a large ROM.

### Range reduction

`U3cae/U3cb0` load rows `0x41/0x42` before input/range comparisons.
`U3cbc` loads row `0x56` and applies opaque floating operations `0x6c9`,
`0x57f`, and `0x487`, then returns quotient/parity metadata used by both the
paired and scalar paths.  Each row has payload `C90FDAA22168C234`, matching
the visible high part of the legacy 66-bit pi/2 constant.

This is suggestive of the same limited-pi reduction family, not proof of the
same reduction.  The visible Goldmont FP-ROM and hard-immediate dumps do not
contain the local model's 128-bit `2/pi` pair
`A2F9836E4E441529 FC2757D1F534DDC0`; it may be encoded elsewhere, derived, or
replaced by another mechanism.  The exact quotient rule and residual low bits
are unresolved.

## Exact matches, similarities, and incompatibilities

### Exact static matches

- 12/12 six-term upper-64 coefficient projections.
- 8/8 effective-model four-term upper-64 coefficient projections (7/8 against
  the unmodified P5 set).
- 16/16 eight-cell table upper-64 projections.
- Interleaved paired coefficient consumption in reverse-Horner order.
- A shared four-term kernel followed by paired table reads.
- The visible high 64 bits of the legacy 66-bit pi/2 significand.
- A reducer helper and table helper shared between paired and scalar paths.
- Identical 506C9/506CA xlat-stub uops and, after relocation, the same four
  coefficient-read sequences, table bases, and result arities.
- No candidate-path hook among the 447 decoded hooks in the eight pinned
  506C9 update records.

### Suggestive, not exact

- Quadrant/parity manipulation around the reducer and final lane swap is
  compatible with the numerical model’s organization.
- FPTAN may share the paired state and table helper, but the public static
  decode cannot bind its entry or final division.
- The ROM layout makes reuse of P5 mathematical constants clear, while the
  exact internal exponents and carried low bits remain hidden.

### Incompatibilities and hard limits

- Goldmont uses three 48-bit uops plus a 30-bit sequence word.
  Its opcode/register namespace is generation-specific; a shared numeric
  opcode across processors would not itself prove shared semantics.
- The FP-ROM dump exposes a 64-bit transfer, not the model’s 66/67/68+
  bit carriers.  Even the exact effective-model projections leave the low bits
  and metadata unknown.
- Opaque operations `0x649`, `0x6e1`, `0x6c9`, `0x689`, and related modes
  contain the very multiply/add/finalization behavior needed to decide
  last-bit equivalence.
- Static terminal-shape inspection cannot recover Goldmont's rounding history,
  hidden sticky state, final carry/borrow confirmation, C1 behavior, or known
  Skylake one-ulp corner rules.  The separate narrow audit
  [`../experiments/h1454_goldmont_terminal_control.py`](../experiments/h1454_goldmont_terminal_control.py)
  appropriately makes no cross-generation semantic claim.

Consequently this investigation supports **ancestry/reuse of the
transcendental design**, not equivalence of FSIN/FCOS/FSINCOS/FPTAN results.
No selector or emulator default should change from this evidence.

The present behavioral verdict is therefore **not determined**, rather than
“different” or “bit-exact.”  No checked Goldmont result file exists in this
workspace, and static artifacts cannot supply one.  The frozen 96-tuple
comparison remains the decision gate.

## Reproducible static audit

After downloading the four pinned repositories, run:

```sh
python3 audit_goldmont_lineage.py \
  --glm-ucode /path/to/glm-ucode-59f3b0a \
  --ucode-disasm /path/to/uCodeDisasm-ffc9070 \
  --custom-processing-unit /path/to/CustomProcessingUnit-4237524
```

The script verifies source hashes and three-way 506C9 array identity, hashes
all five 506CA arrays and all eight 506C9 update records, parses the 512-row
FP-ROM dump, and parses the local 68-bit P5 constants and the frozen
bit-60 adjustment rather than copying them,
reports all coefficient/table projections, checks both steppings' candidate
control transfers and constant-read order, and rejects any pinned 506C9
update hook inside a reconstructed block.  Its expected final line is:

```text
AUDIT PASS
```

## Minimal Goldmont hardware validation

Hardware is required to decide behavior.  The prepared corpus has six
existing public h384 adversarial operands: zero-based rows `14..19` of
`capture-kit/inputs/constraint_fcos_payload_h384.txt`.  They are the positive
and negative values at relative offsets `-1, 0, +1` around one table-path
scaled-tail separator.  Three adjacent magnitudes are enough to expose
rounding transitions without turning this into another large capture.

[`validation-inputs.txt`](validation-inputs.txt) has SHA-256
`fe15a672aa1719caafac52315b2d1938741dcaaf4a136a7d6282a1d699456573`.
The matrix covers:

```text
6 operands x 4 instructions x 4 rounding modes = 96 unique tuples
instructions: FSIN, FCOS, FSINCOS, FPTAN
modes: RN, RD, RU, RZ
precision-control: PC64
```

[`p6-expected.tsv`](p6-expected.tsv), SHA-256
`16ccc4feeb8583e5ebd44041f320d4ba5f665cebfa2106e46e7810a7b73c0a33`,
contains exact expected result fields.  RN/RD/RU results and status words are
copied from the checked-in i7-6700 Skylake h384 hardware captures.  Those 72
result rows also match the current model.  The original public h384 run did
not include RZ, so its 24 RZ result rows are generated by the current exact
model source at SHA-256
`a844951c2c5193142e5520d709c3dc6b2f8d947c1cd266a7288c3ec3614058d2`;
RZ status words are intentionally left unspecified.  This provenance boundary
is recorded per row and must not be blurred into a hardware claim.

To reproduce that matrix locally:

```sh
cc -std=c11 -O2 -o /tmp/fsincos-skylake ../src/fsincos_skylake.c
python3 generate_validation_expectations.py --model /tmp/fsincos-skylake \
  | cmp - p6-expected.tsv
```

On one Goldmont machine, use the existing x86-64 capture binary or build
`capture-kit/x87_capture.c`, then run exactly once:

```sh
sh run_goldmont_validation.sh \
  ../capture-kit/bin/x87_capture_x86_64 \
  goldmont-506c9-output

python3 compare_goldmont_capture.py goldmont-506c9-output
```

The runner refuses to overwrite an output directory, does not enable timing,
and feeds each tuple once.  The instruction is deterministic; no repeated
captures are requested or useful.  It also records CPU/microcode identity and
per-file checksums.  By default the comparator refuses a `cpu_info.txt` that
is not GenuineIntel family 6, model 92, stepping 9 or 10 (CPUID
506C9/506CA); `--allow-non-goldmont` exists only for testing the tool.  The
comparator reports result and status matches without treating a genuine
cross-generation difference as a tool failure.

## Recommended next steps

1. On a Red-Unlocked 506C9 machine, use CustomProcessingUnit's documented
   tracer for one execution each of FSIN, FCOS, FSINCOS, and FPTAN.  Confirm or
   refute `U0a58`, `U0a60`, `U3cbc`, `U6d84`, and the terminal blocks.  One
   trace per instruction is enough to establish dispatch; repeated numerical
   captures are unnecessary.
2. Run the 96-tuple corpus once.  Classify result differences by instruction,
   mode, lane, and magnitude before expanding the corpus.  Exact agreement is
   evidence of behavioral reuse; any difference brackets the changed stage
   but does not negate the static lineage result.
3. Trace FPTAN first if hardware time is scarce.  Its entry and final divide
   are the largest static gaps, while its table/helper reuse is the most
   discriminating sibling question.
4. Decode the semantics and mode bits of the `0x649/0x6e1/0x6c9/0x689`
   floating families from traced operand/result states.  Those operations, not
   the already-matched constants, decide the one-ulp corner cases.
5. Obtain a stepping-identified 506CA FP-ROM dump.  The fresh 506CA
   control-flow audit confirms the same row indices, but the currently pinned
   `rom.txt` does not name the stepping that produced its values.

This milestone intentionally leaves emulator defaults, academic documents,
and selector/equivalence claims unchanged.
