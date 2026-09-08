# H1711–H1712: fresh paired materialization validation

2026-09-05. The minimal H1710 paired program passes the frozen adversarial
Xeon campaign with **zero misses**. The all-edge alternative also passes.
This supplies the fresh hardware evidence missing from H1710; it is not
another retained-label replay or an operand-fitted correction.

Standalone FSIN/FCOS and the confirmed standalone paper remain at H1708.
Paired main/default promotion has **not** occurred in this continuation.
The next implementation step is promotion of the minimal paired graph,
default-entry verification/regression, and then the confirmed paired paper
update. No additional physical-netlist or schedule-uniqueness gate is needed.

## Frozen hardware result

Every row is a distinct instruction/RC/PC/raw80 tuple. Exactly 1,150 fresh
operands were run at FSINCOS × RN/RD/RU/RZ × PC24/53/64 on the user-authorized
Skylake Xeon `45.32.204.118`: **13,800 observations, once each, zero retries**.

| Check | Archived paired graph misses | Minimal last-product cut misses | All-product cuts misses |
| --- | ---: | ---: | ---: |
| Sine, 13,728 outputs | 558 | 0 | 0 |
| Cosine, 13,728 outputs | 150 | 0 | 0 |
| External cosine C1, 13,728 indicators | 66 | 0 | 0 |
| C2, 13,800 responses | 0 | 0 | 0 |
| C2 operand preservation, 72 cases | 0 | 0 | 0 |
| Initial operand/control and final CW/stack mapping | 0 | 0 | 0 |
| Rows failing any frozen check | 750 | 0 | 0 |

There are 27,456 numerical lane outputs. The 750 distinguishing rows were
identified in software before capture, and every one selects the new result.
The aggregate archived miss columns overlap; do not add them as distinct rows.
These are failures of the **archived** graph, not failures of H1710.

Route counts are 11,400 polynomial, 1,584 table, 744 tiny and 72 C2 tuples.
Both signs, all four RC modes and all three standard precision-control
settings are observed. The campaign checks relevant values/C1/C2 and the
essential capture mapping, not undefined condition bits, unused register
payloads, pointer registers or arbitrary unmasked-exception state.

Together with H1710's zero misses over 23,838,534 retained lane appearances,
this is independent prospective support for the fixed program. Retained
appearances overlap, and this fresh test does not turn them into unique tuples.
No exhaustive input or hidden physical-circuit proof is claimed.

## What the discriminator tests

The minimal program makes the last sine Horner edge numerically symmetric
with the already materialized paired cosine edge:

```text
v = RN64(CHOP67(v*S) + K1),     S = CHOP67(r*r)
```

This is a fixed operation for every polynomial-domain input. It uses no input
identity, fitted threshold, coefficient change, selector tree or final-output
patch. Earlier Horner edges retain the archived fused numerical expression.
“Fused” describes the expression's rounding boundary, not a claim about a
physical FMA circuit. The tail and final signed RC64 program are unchanged.

At the final sine edge the small positive product is added to negative S1.
Truncating that product can make the RN64 factor more negative, lowering the
sine prevalue. The retained overestimates and the freshly predicted endpoint
changes follow from this arithmetic, not from post-hoc labels. Exact quadrant
transport also exposes the internal sine change in the external cosine lane;
the 150 archived cosine failures are therefore not a new cosine-factor fit.

The all-edge schedule remains numerically indistinguishable on these tests.
Selecting the minimal graph is a behavioral representation choice backed by
the tested domain, not a uniqueness assertion about hidden microoperations.
Neither more feature fitting nor proof of physical fusion is a prerequisite
to promoting the validated minimal representative.

## H1711 software search and independent proposals

The bounded deterministic C search examined 20,000,000 positive direct
polynomial operands: 32,768 local points around the two retained misses,
then seeded random points, primarily in the upper polynomial binade with
additional exponents through -32. It found 38 distinct proposal operands.
No minimal-vs-all endpoint/C1 separator was found in this finite search.

The proposal builder added both signs, neighboring operands, exact reduced
preimages, the polynomial exponent range, dispatch/binade and table boundaries,
and reduction-boundary brackets. The result was 1,182 software operands,
142 discriminating operands and no last-vs-all contrasts. All three program
predictions agreed with the independent integer/rational implementation:
14,184 instruction-row and 28,176 lane-output software checks.

Thirty-three positive reduced operands have exact preimage certificates;
their negative counterparts give 66 signed preimage operands. These are
genuinely exact residual transports. The 240 reduction-boundary controls use
nearby representable external values and remain labeled **brackets**, not
isomorphs. No endpoint-label assumption is used to construct either group.

## Freshness and capture discipline

H1712 conservatively rejected all previously visible significands, independent
of exponent, instruction, RC, PC or host. Public text and compressed history
were searched; only the explicitly software-only H1711 proposal directories
and the audit's own output were excluded. Sixteen public significands excluded
32 signed operands. The remaining 1,150 include 138 discriminating operands.

Private local text/compressed text and the enumerated exact numeric, paired
hex/decimal, UTF16, extracted-PDF and raw80 byte representations had zero
possible matches for the selected operands. Only aggregate private findings
are retained. No private names, contents, hashes or per-operand membership
lists were published. This is local checked-history coverage, not a claim to
decode arbitrary encrypted, image or unrecovered generated records. Existing
H1688 reservations and unresolved unrelated private records are not cleared.

Immediately before freeze, the C/independent predictions and public/private
checks were repeated without observing hardware. The scorer passed 13,800
synthetic rows and detected 96,456 deliberate mutations. The manifest preserves
baseline, minimal and all-edge predictions, including C1 and C2, unchanged.

The public `x87_state_capture.c` source was compiled in a new isolated remote
directory, without running the harness. Source, ELF and disassembly hashes
were pinned. Static review confirms the selected FSINCOS site executes once,
then FWAIT and FXSAVE without another transcendental before the snapshot.
All exceptions are masked, the stack depth is one and prior flags are clear.
There are no warmup or timing repetitions.

Remote directory: `/root/fsincos-h1712-paired`, frozen kit in `kit/`.
The runner checks checksums, CPU family/model, ELF identity, tuple count and an
absent `hardware-output`/`OPENED.json`, then consumes a directory guard before
execution. It returned `H1712_CAPTURE_COMPLETE tuples=13800 retries=0`.
The host reports GenuineIntel family 6/model 85/stepping 4/microcode 0x1.
Unrelated host processes were untouched. Only the Xeon was used.

The local and remote kits now have matching `OPENED_ONCE_DO_NOT_RERUN`
markers. FREEZE remains immutable with its original prospective state; OPENED
records consumption. A later read-only remote check matched FREEZE, OPENED and
raw-output hashes. **Never rerun this campaign or any of its tuples.**

## Post-capture software replay

All frozen operands were replayed through baseline/minimal/all programs at
O0/O2/O3/UBSan and the independent rational/integer graph. All 55,200
instruction rows, 109,824 lane outputs and 109,824 per-lane C1 indicators
agree with their respective frozen predictions. This is software replay,
not 12 new hardware captures and not evidence that the archived predictions
agree with silicon.

Main build, both existing selftests, Python syntax, shell syntax and diff
checks pass. The standalone source and paper hashes remain H1708. No main
candidate default changed, no historical evidence was overwritten or deleted,
and no paper/PDF work was performed during H1711–H1712.

## Artifact anchors

Paths below are relative to `fsincos-re`.

| Artifact | SHA256 |
| --- | --- |
| `tmp/ledger33/current/h1711_paired_discriminator_scan/report.json` | `05083f2eb159e235a82f82fbec5629923c31d904ce9bedc7403411a5ddbd4f37` |
| `tmp/ledger33/current/h1711_paired_challenge_bank/bank.json` | `236dab47e446c825e4d2c777eb276179d2c9fd21beb92c8c0ad1aa046cf04da1` |
| `tmp/ledger33/current/h1712_paired_freshness/report.json` | `2555145dca2c419b94734b281e7f4b5ea39f4e547c171a87995355f9dcb9197f` |
| `transfer-tests/h1712/FREEZE.json` | `3138415249016c51047ad56110826c2f700e7ec09037c292de22bae35e4a36fa` |
| `transfer-tests/h1712/manifest.json` | `4a2c5bf75f12c3b498efb03d47c9af95e09fec46d8aea47d0329aef99d32d0cc` |
| `transfer-tests/h1712/provenance.json` | `69433c4dd96763e821af9ab56b084c238495b22a6637cd507941c67d1afc45c7` |
| `transfer-tests/h1712/hardware-output/state-output.txt` | `c617a6851407bb5a890219e26883b582c2609c2a5c49c4a8cbcc86e457b6081e` |
| `transfer-tests/h1712/OPENED.json` | `6fc7c613d4e24ff68d0db37ed156cf8310045ae1f0d31e9487f18db02259a34b` |
| `tmp/ledger33/current/h1712_paired_score/report.json` | `03f82b7b352a9b7a69e9f73770a02ba1d15afde4971313823280691143345896` |
| `tmp/ledger33/current/h1712_paired_score/misses.json` | `2516293bddaeb1718d5ebbb2c4bd5e1b7107dab2cf49903ca55ac00981e2b388` |
| `tmp/ledger33/current/h1712_frozen_compiler_replay/report.json` | `b6b0117fabd0c5f27b384a376184b4ad74d8257c5c3e8aa8012010b235d46545` |
| `tmp/ledger33/current/h1712_capture_build/x87_state_capture` | `2a2adae7cf86348e78c6c5a3cd35c18762971b19542fdafcee52d9fabf369a82` |

Generators, verifier, audit, freezer, scorer and runner are the `h1711_*` and
`h1712_*` files under `experiments/`; their sources are pinned by the reports
and freeze. Replays must use new software-output directories. The hardware
runner is not a replay tool.

## Next continuation

Promote the **minimal last-product-cut** paired program as the tested behavioral
representative. Preserve the H1708 standalone route, remove the experimental
policy choice from the promoted paired route, and verify default CLI isolation
and retained/fresh-label regression without recapture. Then update the paper
with the confirmed paired arithmetic and these exact evidence limits, render
and inspect the PDF. The all-edge alternative can remain isolated evidence.

No known H1710 candidate numerical miss remains. The full goal remains active
because the paired program is not yet the delivered main/default algorithm
and its confirmed paper integration is still outstanding—not because the
completed fresh campaign needs more permission or physical-circuit proof.
