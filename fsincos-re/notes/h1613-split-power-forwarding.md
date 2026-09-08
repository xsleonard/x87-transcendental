# H1613: consumer-specific raw/materialized power forwarding fails

Date: 2026-09-04. No new solution, selector, hardware capture, private-ledger
action, emulator/default change or academic paper/PDF update.

## Distinct hypothesis and exact scope

H1608 sent one selected value to every consumer of an intermediate. H1613
instead keeps both the exact raw operation result and its selected result
for square and fourth power. Seven routing bits independently choose which
version each consumer receives:

| Bit | Producer | Consumer |
| --- | --- | --- |
| 0 | square | fourth |
| 1 | square | left product |
| 2 | fourth | negative multiply 1 |
| 3 | fourth | negative multiply 2 |
| 4 | fourth | positive multiply 1 |
| 5 | fourth | positive multiply 2 |
| 6 | fourth | right product |

Bit 1 means raw; bit 0 means selected. Both operands of the fourth operation
use the same chosen version of square. Its raw value is the exact square
of that chosen source, **not necessarily the mathematical fourth power of
the external input**. Mixed raw/selected legs are outside this experiment.

Each of all thirteen operations still independently chooses CHOP,
nearest-even, nearest-away, AWAY, JAM or exact. Initially both routing and
policies are common across all inputs and RC. The eight multiply operations
and correction retain 67 bits when materialized; four Horner adds retain
64 bits. Coefficients, operation order and ordinary final RC64 remain fixed.
The two payload treatments are absent or the original consumed signed
numeric value frozen at its original scale. No payload is regenerated.

There are 128 route programs, each quantifying all `6^13 = 13,060,694,016`
policy vectors: 1,671,768,834,048 named programs per payload. This is a count
of labels, not distinct physical circuits. Numerically equivalent labels
are retained in the complete acceptance functions while arithmetic states
are shared. Raw exact forwarding is a mathematical hypothesis, not a
recovered bus width or a claim about the chip's actual wiring.

## Result and exact two-output certificate

**All 256 route/payload cases fail on the same two RD outputs alone.**

| Direct FCOS input | Recorded RD output | Original source |
| --- | --- | --- |
| `3ffc:e73ffffd2c52df71` | `3ffe:f97ff2968a37b8b1` | H1587 Q008 |
| `3ffc:fcbfffffcee1bd36` | `3ffe:f83dc8dae4171d48` | H1587 Q015 |

Recorded C1=0 is available for both, but is not needed for the contradiction.
The source bank contains 36 operands, 64 actual mode observations and 27 C1
constraints. Each routing case stops after these two operands; later rows
are not scored or silently counted as successes. No target survivor reaches
the cached controls. No best-fit rule or input-dependent routing is mined.

The companion certificate checker authenticates the two observations,
accounts for every route/payload identity exactly once, and reconstructs
the false output-only and joint conjunctions from the saved full diagrams.
For each case it also replays a complete satisfying policy vector for each
singleton. Thus two is a **minimum-cardinality contradiction for each fixed
route/payload case**, not merely the length of an arbitrary rejected prefix.
It does not mean the same singleton policy vector works across cases.

There is also a derived RC-only exclusion. Every possible routing mask has
no common RD policy vector. A rule that selects both routing and policies
solely from architectural RC must pick one such mask/vector in RD, so it
cannot match both recorded outputs. The companion report records this
implication explicitly. It is not a separate RC-family enumeration or an
exclusion of operand-dependent state.

## Verification

- The fully coupled route reproduces all 72 H1608 operand/payload cases,
  with both roots: 144 complete canonical-function equalities.
- Forcing both power policies to exact collapses every route back to H1608:
  1,024 complete cofactor-function equalities over the checked prefixes.
- The main solver represents 805,375,872 numerical paths through 3,514,432
  live states and performs 9,216 direct full-graph policy replays.
- Routing selftests check 1,664 stages against independently spelled rational
  dataflow, all 128 exact-power boundaries, and 972 cofactor truth-table cases.
  Inherited tests include 42,966 rational quantizer cases, 1,664 rational
  graph stages, 128 all-exact polynomial checks, 1,596 restriction checks,
  2,430 diagram cases and 6,132 nearest-away neighbor cases.
- The companion audit re-conjoins 1,024 prefix roots and validates 512
  singleton witnesses, with another 6,656 independent rational-stage checks.

The main compiler and inverse helpers are reused; neither the second run
nor the certificate checker is claimed as a second independent full-family
arithmetic solver. The separate rational execution checks witness stages,
not all assignments. Main report, complete compressed diagram stream and
companion report reproduce byte-for-byte in a separate run. Syntax, normal
build/selftest, whitespace and diff checks pass.

## Artifacts

Paths relative to `fsincos-re`:

| Artifact | SHA-256 |
| --- | --- |
| `experiments/h1613_split_power_forwarding.py` | `899e156f802dcfa6eb6a51ede71d2ce1413bbd1ca3159122dec37677860abcaa` |
| `tmp/ledger33/current/h1613_split_power_forwarding/report.json` | `a36ea9969e0c79bea9a613162b732c0b2913c792e20f24d75b48a098d333b95c` |
| `tmp/ledger33/current/h1613_split_power_forwarding/routing_diagrams.jsonl.gz` | `c561261243417223cc90dbedb7aa75543d74c4f3da8575c5a2c16c071ea84692` |
| `experiments/h1613_verify_routing_certificate.py` | `7a64796096ea98d0662bb64531998e4080c123c6ee8dc124362ceee44855e593` |
| `tmp/ledger33/current/h1613_verify_routing_certificate/report.json` | `6eac0a054e8ef1001793ef2172d8ebfde6c8a84a7f0971833608da75c7e25aaa` |

```sh
python3 fsincos-re/experiments/h1613_split_power_forwarding.py \
  --root fsincos-re --output-dir NEW_SOLVER_OUTPUT_DIRECTORY
python3 fsincos-re/experiments/h1613_verify_routing_certificate.py \
  --root fsincos-re --output-dir NEW_CERTIFICATE_OUTPUT_DIRECTORY
```

Both refuse existing output directories. The checker reads the pinned
authoritative solver artifacts, not an unverified replacement directory.

## Claim boundary and next direction

Do not repeat the fixed-routing family or its RC-only extension. This does
not exclude changed-width/bypass combinations, arbitrary per-cut precisions,
mixed fourth-power legs, a different polynomial evaluation graph, regenerated
payload or genuinely operand/history-dependent arithmetic. None of these is
established as a silicon mechanism here. A new structural hypothesis must
change and justify a held-fixed assumption; a fitted input decision tree is
not a replacement for that justification. Absolute operation/control-state
recovery or a genuinely new observable remains more informative than further
feature fitting. No new hardware campaign has been justified by this result.

R96 remains empirical/incomplete. Canonical C retains SHA-256
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`;
speculative selectors remain default-off. Direct 45/44 and external 75/74
failure frontiers are unchanged. The full bit-exact emulation goal is open.
