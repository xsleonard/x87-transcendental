# D0015/D0016: representation and shared-coefficient exclusions

FPATAN is **not solved or promoted**. This continuation made progress by
testing previously unexamined arithmetic representations and resolving wider
shared-coefficient families. It performed no native capture. Main C/library,
the existing trig implementation and the paper were not changed. The saved
hardware corpus remains 1,649,232 observations across D0001--D0009 and D0013.

## D0015: three different arithmetic mechanisms

Every tested program is fixed across inputs. There is no operand ledger,
error-state predicate, fitted boundary selector or per-input coefficient.
Each rejected program retains a concrete saved counterexample.

| Mechanism | Fixed programs | Survivors |
| --- | ---: | ---: |
| Compensated high/low quotient evaluation | 9,720 | 0 |
| Architectural RC feeding internal operations | 15,552 | 0 |
| Sticky-jammed producer/read values | 5,832 | 0 |
| Total | 31,104 | 0 |

### Compensated quotient

`d0015_split_quotient_audit.py` writes z=a+b, with a obtained by CHOP or RN at
64, 65 or 66 bits. It evaluates the polynomial at a and carries the low part
through the atan derivative, the derivative of the stored polynomial, a
retained-width derivative, or the exact polynomial increment. A no-correction
control is included. The exact split identity is independently checked by
binomial expansion. Tail order, correction cuts and fixed recombination
layouts vary globally. None passes the 279-group direct frontier.

This excludes the specified implementations, not every compensated algorithm.
The exact increment is algebraic; the derivative variants are approximations
and are never presented as exact identities.

### Architectural rounding control

`d0015_internal_rc_audit.py` does not require one common prevalue for all four
rounding modes. It tests RC64/RC67 operations at fixed square, Horner and tail
roles, using either raw RC or its sign-reflected magnitude-domain form.
Horner changes can affect all stages, the last stage, or the prefix.
All 1,116 saved direct output/C1 observations are available to each program.
No survivor exists. Rejections occur in RN (9,984 programs), RU (4,680), RD
(872) and RZ (16). Thus the common-prevalue assumption is not the sole reason
these particular programs fail. This does not prove that hardware ignores RC
internally or that the earlier shared-prevalue exclusion covers every RC-driven
graph.

### Sticky representation

`d0015_sticky_datapath_audit.py` tests round-to-odd at 67/68-bit producers,
including RN64 reads of jammed carriers. A nonzero discarded remainder sets
the retained low bit; this differs from both CHOP and RN below halfway points.
Square, Horner and tail roles vary globally. None passes the direct frontier.
This is not an exclusion of richer metadata forwarding or redundant carriers.

Artifacts: `../tmp/fpatan-re/d0015-{split-quotient,internal-rc,sticky-datapath}-audit.json`.

## D0016: free shared constants with wider accumulators

D0014 rejected one MR-square/h64 graph. D0016 asks a distinct question: can
wider accumulators and different shared constants rescue the CHOP67(z*z)
square family?

`d0016_wide_coefficient_family.py` tests all **70** recipes in the earlier
243-recipe terminal audit that admit some final carrier for every saved
direct state. Other recipes were already rejected by terminal feasibility.
The new families have:

- square u=CHOP67(z*z);
- Horner accumulator width 64, 67 or 69, with RN adds at that width;
- CHOP67 Horner products;
- three Horner square reads: full u, CHOP64(u), or RN64(u);
- the admitted terminal product orders, 64/67/69-bit cuts and z reads;
- six shared **continuous** coefficients, each within +/-2^60 of its own
  69-bit-grid ULP around the public P5 value; and
- independent closed rounding-error intervals at every operation/input,
  including errors that may be physically unattainable.

The same 137 unrotated direct states constrain each query. The half-widths in
absolute coefficient units are 2^-10 for A118, 2^-11 for A119/A120, and 2^-12
for A121/A122/A123. Coefficients are not restricted to a representable ROM grid.
Largest-binade ULPs make the error envelopes safe when coefficient variation
crosses an intermediate binade. This is a necessary relaxation, not a concrete
candidate generator that is allowed to choose errors per input.

**All 210 queries are UNSAT; none is SAT or UNKNOWN.** Every query was frozen
before execution, with a 3-second internal bound and a separate external
deadline. All workers exited normally without reaching the external deadline.
No rounded constant-bank candidate was produced. This excludes the stated
families inside the coefficient box; it does not exclude all coefficients,
all accumulator schedules or all polynomial representations.

Artifacts are in:

- `../tmp/fpatan-re/d0016-wide-coefficient-family-b60/`
- `../tmp/fpatan-re/d0016-wide-coefficient-family-b60-chop64/`
- `../tmp/fpatan-re/d0016-wide-coefficient-family-b60-rn64/`

Each directory retains 70 SMT2 files, per-query JSON results and SUMMARY.json.
The generator gained the two narrowed-square read options after the initial
family completed; the original formulas and reports are unchanged and pinned
by their hashes.

## Independent verification

CVC5 independently parsed and confirmed UNSAT for representative original-
family queries t000, t021 and t069, covering h64/h67/h69. These three checks
must not be described as independent solver checks of all 210 queries.

`verify_d0016_family.py`, without importing a solver, graph, terminal-inverse
implementation or D0016 generator:

1. Authenticates all 1,228,664 original D0008/D0009 observations and all 1,140
   saved frontier rows against their receipts.
2. Reconstructs quotient and square values with the independent integer rounder.
3. Checks both endpoints of every allowed final-carrier interval and their
   immediately adjacent disallowed carriers. Monotonicity of positive CHOP
   products makes this a complete preimage check on the specified lattice.
4. Independently reconstructs each signed rounding-error envelope across the
   full coefficient box.
5. Checks every frozen query hash and terminal worker receipt.

It passes **9,590 unique terminal preimages and 28,770 point envelopes** across
the 210 graphs. The verifier initially tried its below-one direct-angle helper
on unrelated rotated/table frontier rows and stopped by assertion before
writing a result. It was corrected to construct those intervals only for the
selected direct points. The second run passes; no original observation,
formula or solver result was altered. Verification result:
`../tmp/fpatan-re/d0016-independent-family-verification.json`.

Five new test groups pass: split/derivative identities, round-to-odd signs and
idempotence, architectural RC behavior, saved counterexample replay, and broad
coefficient-box error checks using the independent rounder. These tests are in
`test_d0015_d0016.py`.

## Next work and limits

Do not repeat these constant-bank solves or treat any of their failures as a
proof that FPATAN cannot be reconstructed. They constrain the post-quotient
arithmetic, not the existence of a solution. Still-unexamined directions
include signed fixed-point truncation semantics, richer rounding metadata,
or a different coupled dataflow whose state cannot be described by one scalar
Horner recurrence and these terminal products. Independent FPATAN control/ROM
provenance would also be valuable. The separate table-path failure remains.

No selector is promoted. Any genuine candidate must pass all ten saved jobs
and then a fresh frozen challenge. Never repeat a native tuple. The paper is
reserved for confirmed solutions, not these experiments.

Final checks: all sixteen D0011/D0012/D0014/D0015-D0016 test groups pass,
Python compileall and `git diff --check` pass, and the existing sanitized C
candidate/library selftests pass. Main C is byte-identical to its frozen
D0009 source. All query, verifier and test handles are confirmed terminal.
