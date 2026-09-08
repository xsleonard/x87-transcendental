# H1570–H1571: one-shot exact-preimage transfer

**24/24 transfer exact; 18/24 model misses; no quotient-pair split.** The
frozen transfer prediction was the previously observed direct anchor value,
not the current model value and not a new fitted selector. All 24 fresh
external inputs reproduced that anchor value on the Skylake Xeon oracle.
This is finite transfer evidence, not a universal selector or a proof that
the physical machine has no reduction-history-dependent state.

H1569's algebraic enumeration supplied 122 same-positive-residual candidates
over twelve anchors. The conservative freshness gate rejected one previously
seen significand, even though a differently encoded tuple could in principle
be distinct. It selected minimum fresh q and then maximum fresh q with the
opposite mathematical reduction carry64 when available, otherwise maximum
fresh q. The selected 24 unique operands comprise ten FCOS and fourteen FSIN
tuples, one already-observed anchor rounding mode each; no anchor was recaptured.
Nine pairs separate carry64, and all twelve separate quotient.

The freeze is immutable. Immediately before execution the repository and
private supplemental ledger checks again found zero selected collisions.
Only aggregate freshness counts are retained; no private-ledger identity or
contents are published. The runner's hash, input hashes, and frozen manifest
were checked locally and remotely. It refuses an existing output directory,
including after a partial run, and checks the established capture binary hash
before any x87 instruction. The new remote campaign directory was reserved
without overwriting a prior directory. The standing user authorization covers
the copy and one-shot execution; no other research-host processes were touched.

Host mapping is the user's corrected mapping: `142.132.217.24` is the i7;
`45.32.204.118` is the Skylake Xeon VM used here. The latter reports family 6,
model 85, stepping 4, `Intel Xeon Processor (Skylake, IBRS)`. Capture binary
SHA-256 is `9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1`;
source SHA-256 is
`aededbaea438dbd1526aca4926530b655d6c9a1ad0f0bac82ad58fcbe3d824d1`,
matching the local capture source. The runner completed all 24 observations
once; raw outputs and metadata are preserved under
`transfer-tests/h1570/hardware-output/`. **Never rerun H1570.**

| Instruction | Observed | Anchor transfer exact | Model exact | Model misses |
| --- | ---: | ---: | ---: | ---: |
| FCOS | 10 | 10 | 0 | 10 |
| FSIN | 14 | 14 | 6 | 8 |
| Total | 24 | 24 | 6 | 18 |

All eighteen model misses require forced final carry 1; the six controls
require carry 0. There are no values outside the two forced endpoints. The
two members of each low/high-q family agree exactly, including all nine pairs
whose mathematical carry64 differs. Thus that carry64, or its complement,
cannot itself be the unconditional missing final-carry selector. This does
not exclude every gated/history-dependent mechanism. The comparisons use
R84-off models and retain the H1412 distinction between a model ledger overlay
and an actual arithmetic dependency.

Together with H1568 this explicitly reconciled bank has **75 captured rows
over 74 operands, of which 51 rows over 50 operands fail the ledger-off
model**. The failures comprise 43 FCOS rows and eight FSIN rows. H1568's
33/32 count remains correct for its direct q=0 subset; eleven/ten is only the
older H1378 subset. These are lower bounds from named evidence sources, not
a claim to have recounted every artifact in the repository. No unobserved
mode was inferred. Every one of the 75 observations still has exactly one
matching forced final-carry endpoint.

H1568 and H1569 reproduced byte-for-byte from software-only replays. H1571's
scorer independently verifies all frozen hashes, positional inputs, exact
raw counts, and remote raw checksums; its local replay reproduces both score
and report byte-for-byte without hardware. Python syntax checks, runner shell
syntax/checksums, the normal C build, model selftest, and diff checks pass.

Authoritative artifacts:

- `experiments/h1570_freeze_exact_preimage_transfer.py`, SHA-256
  `1c7cf6bba49787bcfff38722ed35e3e47fdb1cd823d780456e507d1733f28e59`.
- `experiments/h1571_score_exact_preimage_transfer.py`, SHA-256
  `45d1ef20f7ea93010b5d733f282959677ab3cadb7fab6ebf4ad90e896fd9136d`.
- `transfer-tests/h1570/FREEZE.json`, SHA-256
  `0a3bef19b31be3beb81017a4241e22db6039f71576c681d8f62ded25611d1d75`.
- `transfer-tests/h1570/OPENED.json`, SHA-256
  `6327128f0317d59da9b180ad52f43161f917b83f0a40e4db4350a6856be3baef`.
- `tmp/ledger33/current/h1571_exact_preimage_transfer_score.tsv`, SHA-256
  `40f15b0dc587c57bcbcd6b2f04675204772a56ecbba3f53a0ac64b06aeac4f30`.
- `tmp/ledger33/current/h1571_exact_preimage_transfer_report.json`, SHA-256
  `7f2b8d156e175bd54c0bc192bb3dc5ea799473de22083c160858b705578fb857`.

No emulator defaults, existing solver artifacts, or academic paper/PDF changed.
R96 remains empirical/incomplete; R1382, QX, Q, and the falsified pair/tree
selectors remain off. Absolute control-state recovery or a genuinely new
post-reduction observable remains the stronger direction. The successful
preimage transfer is not grounds to promote any of the rejected selectors.
