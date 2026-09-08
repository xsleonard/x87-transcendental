# H1678–H1683: distinct restore paths and a summary-bit normal form

2026-09-04 local date. The preceding goal turn made concrete progress by
falsifying identity restoration and proving a pending-gate observability limit.
This turn tests distinct setup and observation paths. H1680 completes 1,008
fresh restoration-only observations once, with zero frozen-check misses and
independent raw verification. No FSIN, FCOS or FWAIT executes. No new numerical
or pending-delivery credit, production change, paper/PDF change or closure.

## Source and instrument boundary

The [Intel SDM revision 089](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf)
motivates separate tests of legacy environment/state loads, control-word loads,
and FNSTENV's post-save masking. Its status description relates B to ES. It
does not establish that these paths preserve deliberately inconsistent bits.
Condition codes marked undefined for FLDCW/FNSTENV remain unpredicted. See
Vol. 1 §§8.1.3.3/8.6 and the corresponding Vol. 2 instruction entries.

The standalone H1678 source has five setup methods: FXRSTOR64, FLDENV, FRSTOR,
FLDCW from an all-masked seed, and FNSTENV after restoring a coherent seed.
Normal raw operands and exact stack sentinels are loaded under all masks.
Legacy environment layout comes from FNSTENV in the same execution mode;
FRSTOR also receives the saved logical data-register order. Only state setup
is under investigation; no transcendental result is generated.

Each setup is followed by either FNSTSW/FNSTCW then FXSAVE64, or FXSAVE64 then
FNSTSW/FNSTCW. Both cuts finish with non-waiting FNCLEX. GCC 12.2 compiles the
source warning-clean on the authorized model-85 Xeon. The pinned ELF contains
no transcendental or FWAIT opcode. A machine-code control-flow audit checks
all five setup sites, both acyclic integer-only paths to the observation cuts,
and their no-wait instruction sequences. Potentially waiting setup operations
start from an all-masked state. No test or smoke execution precedes the freeze.

## Freeze, scope and execution

H1679 proposes 1,008 signed operands, 504 unique significands, 18 flag/mask
profiles, varying CC/depth/RC/PC, and both observer orderings. The three restore
methods receive four requested ES/B settings; FLDCW/FNSTENV test mask changes
instead. The prospective hypothesis is ES=B=bool(flags & ~final_masks &63).
Pointers, empty-register contents and the specified undefined CC are unknown,
not predicted successes.

H1681 tests all 1,008 synthetic positives, detects 1,008 mutations each of
FX status, direct status, saved status and operand, leaves 144 undefined-CC
mutations uncredited, and rejects three malformed inputs. H1682 independently
reconstructs all predictions without importing the primary proposal/scorer.
H1680 replays those checks, then audits compressed public and local private
history. Zero public/private collisions; 26 private files, aggregates only.
Every selected operand has one setup/observation path. No private content,
identity or hash is published or copied remotely.

The immutable kit is `transfer-tests/h1680`, remote directory
`/root/fsincos-h1680-restore-paths`, using the separately built H1678 ELF.
Capture completes at 2026-09-05 03:11:28 UTC, one invocation and zero retries.
It is OPENED_ONCE locally/remotely: NEVER rerun. H1670 remains on hold; H1675
remains opened and is not repeated. i7 and unrelated remote services are
untouched. Host mapping remains i7 `142.132.217.24`, Xeon `45.32.204.118`.

## Observed results, not a universal state theorem

| Setup method | Rows | Actual 000 | Actual 111 |
|---|---:|---:|---:|
| FXRSTOR64 | 288 | 160 | 128 |
| FLDENV | 288 | 160 | 128 |
| FRSTOR | 288 | 160 | 128 |
| FLDCW | 72 | 40 | 32 |
| FNSTENV | 72 | 72 | 0 |

Here the three bits are U, ES and B. All 1,008 known-status, CW, raw operand,
occupied-stack, TOP, abridged-tag and saved-image checks pass. Direct and FX
status observations agree completely, including the unpredicted CC values;
that last agreement is an observed relation, not new prospective CC credit.
H1682 independently confirms every raw row and every frozen prediction.

Each of FXRSTOR64/FLDENV/FRSTOR disagrees with identity restoration on 216
rows. In 324 of those rows, the direct status read precedes the post-restore
FXSAVE. Thus a change caused solely by that later FXSAVE cannot explain the
disagreement. This does not isolate restoration versus a direct-read projection
or asynchronous state handling, nor prove all state-loading paths equivalent.

FNSTENV's saved pre-mask image has pending status in 32 records; after its
masking step, both observers show all masks set and ES/B clear. FLDCW produces
32 final pending states from its source-defined all-masked setup path. The
latter is not a separately captured before/after state pair.

Design limit: different orders use different fresh operands; they are not
repeated or paired captures. The bank couples scalar-first order to RN/RU and
FX-first to RD/RZ. It therefore does not independently estimate order versus
RC effects. Within each row, both observers do see the same control mode, and
the scalar-first causal ordering above remains valid. Any later campaign that
needs order/RC independence must use a balanced fresh design.

No off-diagonal state was observed, and no consuming opcode was tested.
Consequently this turn supplies no additional truth value for the 64 surviving
three-input pending gates. Do not count restoration matches as delivery or
arithmetic matches, or treat finite canonicalization evidence as a universal
unreachability theorem.

## H1683: closed form with an explicit proof boundary

The analysis-only function is:

```text
C(SW,CW) = (SW & 0x7f7f)
           | (0x8080 if (SW & ~CW & 0x3f) != 0 else 0)
```

It overwrites only the two summary bits. An exhaustive 4,194,304-case audit
of all 16-bit status words and 64 mask combinations proves non-summary-bit
preservation, ES=B=U, idempotence, independence from high CW bits, and clearing
on masking all exceptions. There are 1,048,576 fixed points. A further
1,048,576 factored cases prove composition:

```text
C(C(SW,CW1),CW2) = C(SW,CW2)
```

The factorization is exact for this function: it reads six exception flags,
overwrites two summary bits, and leaves the other eight status bits intact.
The exhaustive proof concerns the specified bit function, **not silicon**.
A reachable-state induction would follow if every architectural state writer
were proved to obey the required transitions; that universal premise is still
missing. The function is not installed in H1652, H1660 or production.

## Next work and verification

Static audit, bank, both preflights, primary score, independent raw verification
and algebra report reproduce byte-for-byte in
`/private/tmp/h1678-h1683-replay.lsgiTr`. No freezer or hardware run is repeated.
Python/shell syntax, production build, both emulator selftests, diff and new-
file whitespace checks pass. Frozen checksums and local/remote OPENED markers
agree. All command sessions are terminal. Canonical source and both paper-source
hashes match the previous turn.

The [SDM's XRSTOR/XRSTORS descriptions](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf)
distinguish loading, initializing and leaving the x87 component unchanged.
Those paths, compacted formats, 16-bit legacy formats and other execution modes
are not covered here. Next audit their support, layout and no-wait observation
safety before deciding on another balanced fresh discriminator. Privileged
paths are not permission to change the host kernel or unrelated services.

Do not keep adding unbalanced variations of already collapsed paths. Remaining
small normalization, zero/infinity, reserved-control, complete tag/pointer,
exact-center and all-input numerical/silicon obligations stay open. R96 remains
empirical/incomplete; the isolated numerical candidate and documented incumbent
direct 50/48, external 81/79 frontier are unchanged. The full goal stays active.

## SHA256 anchors

- H1678 source: `afbd0cf2efe33a091c165623a49c2c3941fcda81f6b2df8d128f05f383059f16`.
- H1678 ELF: `f093eb12fd2d2102bc5711618b69427b499d2bbdb907bfebbfc4700fbf134bee`.
- H1678 static report: `7db00cebb8b477ea727e8340b7c082c6b609e9884e9cbd6f701b80da171241f7`.
- H1679 bank: `40c1ac8271901364720dcfc81ad6c9f268f1fa75bf45299d36314d34a98a4dce`.
- H1680 freeze: `4a496faab3a3dbbc4e679ceeb32773f063cd9afb25fac920606b5bf5a7ea7b78`.
- H1680 manifest: `9a36a1444aaaff31c3008e93208bd5a6fd2b8e043c4feb3cf0c4aa98d020c0ed`.
- H1680 raw: `b40b0b78f569ec873a6172667d045d76bbecac037a6a6f31d06cdd86e6b85cfd`.
- H1680 OPENED: `9b047666c8a67bd0c63d7f66607dc4761115ae466568b411af316e88d00a330e`.
- H1681 primary report: `8dbc25db111e1ce56895d490993e5662fb9491aca230732e4996c47a759c4a1e`.
- H1682 independent report: `2511d74261cacae81cd8d5a2a4f529ea63995e48a4e727cf4d78f4ca7c5e423d`.
- H1683 algebra/audit report: `b0e6fc435e10b37fb86a620b91b46980a33aa07fe09a13ef03deac475ec84c70`.
