# h1466: exact mathematical truth is not the R59 carry selector

Date: 2026-09-03

Status: closed negative mechanism result.  No hardware was executed, no
private ledger or new label was read, no manifest was frozen, and no selector
or emulator behavior changed.  This result belongs in the handoff only; the
academic paper/PDF remains frozen.

## Question

The h1400 causal audit established that every one of the eleven current
ledger-disabled FCOS residual legs can be repaired by choosing the other exact
final-R59 subtraction carry endpoint.  A general software rule could in
principle choose that endpoint from exact mathematical truth rather than a
recovered hardware wire:

1. choose the endpoint whose binary80 value is nearest the unrounded
   transcendental value `cos(x)`; or
2. choose the endpoint equal to correctly rounded binary80 `cos(x)` in the
   architectural rounding mode.

These rules are closed mathematical predicates, not fitted input boundaries.
H1466 tests them against the complete causal endpoint wall rather than only the
eleven positive rows.

## Method

The current source was compiled three times with the exact-operand R84 overlay
disabled:

```text
baseline: G_ROUND84=0
carry 0: G_ROUND84=0, G_R99CARRY=0
carry 1: G_ROUND84=0, G_R99CARRY=1
```

The input is the same ten target operands/four modes and the disjoint 149,764
cached h1107 control legs used by h1400.  The 11 target misses use the frozen
h1378 hardware values; their other 29 mode legs use the already matched
ledger-disabled baseline.  H1466 first verifies the baseline against every
recorded value and then keeps every row on which the two forced endpoints
differ and exactly one endpoint equals hardware truth.

There are 39,464 such rows: all eleven residual legs plus 39,453 controls.
The other 110,340 rows are architecturally insensitive to the forced carry.
The smaller 34,474-row bank used by the named-wire/recurrence searches is a
feature-complete constrained subset; it is not the full force-differing wall.

`h1466_mpfr_carry_selector.c` evaluates `cos(x)` with MPFR and compares the
two endpoint errors.  It also rounds the high-precision value to 64-bit
binary significand precision under RN/RD/RU/RZ and identifies the matching
endpoint.  Independent 768-bit and 1536-bit runs classify every row
identically.

## Result

Neither mathematical rule is the hardware selector.

| Rule | Correct endpoint | Wrong endpoint |
|---|---:|---:|
| Nearest to unrounded `cos(x)` | 20,334 / 39,464 | 19,130 / 39,464 |
| Equals correctly rounded binary80 | 20,055 / 39,464 | 19,409 / 39,464 |

On the eleven unresolved rows alone, nearest truth selects only 5/11 required
endpoints.  Its six failures are d0d0 RD/RZ, d920 RN, and all three far-corner
RU rows.  Correct rounding selects 9/11; it fails d920 RN and the
`ffffc00024077827` RU corner.  It also selects the wrong endpoint on 19,407 of
the 39,453 controls, so its 9/11 target score is not promotable.

The older h1004 audit independently points in the same direction over a
different historical comparison: among 37,441 hardware/model disagreements,
hardware was nearer MPFR truth on 21,626 and the model on 15,815.  H1466 is
stronger for the present question because it compares the exact two causal
R59 endpoints and knows the required hardware carry on every retained row.

## Bounded conclusion

The final carry is not an accuracy arbitration bit.  Skylake sometimes chooses
the endpoint farther from exact `cos(x)` and sometimes chooses the endpoint
that is not the correctly rounded binary80 result.  Therefore an MPFR-backed
closed rule cannot replace the missing physical selector, even as a software
shortcut for the current wall.

This closes the strongest non-structural general rule.  The remaining useful
directions are recovery of an actual hidden data/control wire, absolute
ROM/control-state recovery, or a new observable.  It gives no support to more
input-boundary fitting.

## Artifacts

- `experiments/h1466_exact_truth_carry_selector.py` (SHA-256
  `39ad24c586035773e25f43e7a2fa0eeae4bef09942cb2392da383bcf5ef297d0`)
- `experiments/h1466_mpfr_carry_selector.c` (SHA-256
  `303641a0e3d8e0d1bf750933ddd63d8942aefed801f5a8536ac1127f35d3a174`)
- `tmp/ledger33/current/h1466_exact_truth_carry_selector.json` (SHA-256
  `f9731613946df3e2b2247f4864355a1988bcc851b6cf133d180813466a035486`)
- `tmp/ledger33/current/h1466_exact_truth_carry_selector_failures.tsv`
  (SHA-256
  `e6e71a7a08e427f2237bc2cf96884e8f868134989a623270ecdb9e26d8477dc5`)

