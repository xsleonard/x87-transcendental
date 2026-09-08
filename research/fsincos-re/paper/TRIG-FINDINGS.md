# What the sine and cosine investigation established

FSIN, FCOS and FSINCOS are the main research contribution of the
[paper](x87-suite.tex). The result is a set of fixed numerical programs using
public constants, supported by experiments that distinguish their arithmetic.
The complete [pseudocode](../docs/TRIG-PSEUDOCODE.md) is the implementation
reference. This map explains why its less obvious rules are there.

| Finding | Why it matters | Research record |
| --- | --- | --- |
| Exact reduction by the finite 66-bit divisor | Preserves the residual and quadrant at large inputs; separates arithmetic exactness from error relative to mathematical pi | [Reducer contract](../notes/h1700-exact-reduction-contract.md), [domain transfer](../notes/h1627-h1629-polynomial-domain-transfer.md) |
| Standalone odd/even chains and unequal multiply input widths | The fourth-power product uses the retained square on one side and its 64-bit truncation on the other | [Shared polynomial](../notes/h1630-h1632-shared-polynomial.md), [domain transfer](../notes/h1627-h1629-polynomial-domain-transfer.md) |
| Distinct standalone sine/cosine terminals | The same coefficient-chain machinery ends with different rounding steps | [Standalone promotion](../notes/h1707-h1708-standalone-promotion.md) |
| A separate FSINCOS Horner program | Standalone calls cannot reproduce all paired results; every coefficient-stage product is cut before addition | [Paired schedule and exact separator](../notes/h1717-policy2-promotion.md) |
| Direct RN64 destination in the table calculation | RN64 of an already truncated 67-bit product is a different computation | [Independent table audit](../notes/h1633-h1635-shared-table.md) |
| Exact cells, centers, tiny and C1 rules | Branch decisions and status can distinguish schedules even when a rounded result agrees | [Center campaign](../notes/h1690-h1695-exact-center-campaign.md), [tiny rules](../notes/h1638-h1643-tiny-and-remaining-scope.md) |
| Reachable-width and integer-carrier bounds | Establishes that the bounded implementation can carry out the specified exact operations | [Integer helpers](../notes/h1698-h1699-integer-helper-and-carrier-proof.md), [paired interval bounds](../tmp/ledger33/current/h1717_carrier_bounds/report.json) |

## How the arithmetic is derived

The ROM coefficients and addition identities give the polynomial and table
forms. Exact dyadic evaluation specifies each product, sum and rounding point.
Hardware measurements constrain that calculation in several complementary ways:

- At reachable table centers, the correction vanishes, exposing the stored value.
- Inputs around cell and interval boundaries identify dispatch and subtraction.
- A nearest-even result places the final unrounded value between two midpoints.
  C1 and the directed modes further constrain its position.
- Exact inverse reduction finds legal external inputs for selected internal
  residuals, allowing the same kernel to be checked across quadrants and signs.

These constraints support the standalone odd/even chains, the paired Horner
chains with a 67-bit cut before each coefficient sum, and the table product
that rounds directly to RN64. The linked research records contain the exact
arithmetic and observations behind those rules.

The paired width certificate covers 30 polynomial binades and 840 operation
checks, with maximum accumulator width 139 bits and alignment shift 132.
It checks the specified arithmetic under the reducer and quantizer contracts;
it is not a proof of processor internals.

## How these details connect to the larger evidence

Completed native FSIN runs, standalone/paired archive replays, and frozen
three-instruction challenges provide broader coverage. The
[evidence register](EVIDENCE.md) identifies instruction counts, output values,
recorded flags and CPU contexts. Replays, original captures and overlapping
test sets are counted separately.

The interpretation is deliberately specific: the reconstruction supplies
operation order, widths and rounding points beyond the published constants.
It does not uniquely identify physical ports or microcode. FPTAN, FPATAN,
F2XM1 and the logarithms remain fully documented supporting implementations;
their routine integration history is kept in the corresponding records.
