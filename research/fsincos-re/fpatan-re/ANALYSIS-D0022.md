# D0022: V6 prospective challenge and exact-midpoint localization

**FPATAN remains unsolved. V6 is falsified as a complete implementation and
is not promoted.** This campaign did not change the main C/library, trig code
or paper. Original predictions and results are retained without alteration.

## One-shot hardware result

The independently frozen bank selected 126,432 new raw operand pairs and
509,664 RC/PC observations. All prior 1,649,232 FPATAN tuples, plus private
and public/corpus possible-pair histories, were checked before capture.
Sanitized Clang and GCC 15 independently matched all frozen Python predictions.
Only the generic harness/guard and cleared inputs/metadata were uploaded.

On the authorized Skylake Xeon (CPUID `00050654`, reported microcode `0x1`):

- 12 result differences and 8 C1 differences;
- union: 18 affected observations over six raw operand pairs;
- zero exception or pre-load-flag differences;
- all 1,968 matched three-PC groups agree in output/status;
- 2,000 underflow observations retained; and
- remote ledger integrity `ok`, all eleven jobs OBSERVED.

The complete saved corpus now contains **2,158,896 observations** across
D0001--D0009, D0013 and D0022. No native tuple was repeated. No capture,
download, solver or analysis process remains running at this checkpoint.

Raw hardware SHA256:
`a025fbb3b249479867981e26cf3b4508a51f29886bbb1678f68420c020d9a52e`.
Receipts and immutable data are under `../tmp/fpatan-re/d0022/`, including
`MANIFEST.json`, `C-PREFLIGHT.json`, `GCC15-PREFLIGHT.json`, `HISTORY.json`,
`STAGED.json`, `DISPATCHED.json`, `STARTED.json`, `COMPLETE.json`, `SCORE.json`,
`LEDGER-AUDIT.json`, and `candidate-misses.jsonl.gz`.

## The residual is one exact table midpoint, not the old polynomial frontier

All 18 new discrepancies have the **same exact reduced ratio 19/64**, with
sign/octant and common-scale variations. A representative positive pair is:

```text
y = 0f13:fd28b6282f47299d
x = 0f15:d52fc1d0ff6458f0
```

This is exactly between atan table cells 9/32 and 10/32; it is not merely
near the boundary. The V6 baseline's upward tie selects index 10. Evaluating
the unchanged V6 polynomial using index 9 instead matches **all 24 saved
four-mode observations** for the six affected raw pairs. Forced-index use
here is causal localization, not an operand-conditioned correction.

`d0022_midpoint_localization.py` authenticates all 2,158,896 original rows
and audits every eligible exact midpoint in the saved corpus. It finds
728 midpoint observations over 15 distinct ratios: 710 cannot distinguish
the neighboring cells, while 18 require the lower cell. All 18 decisive
observations are at 19/64. None requires the upper cell on this bank.
At 3/64, the additional direct-kernel alternative matches all 208 saved
observations, so its boundary remains observationally ambiguous.

This is **not yet a general tie-law proof**. Lower-cell preference, odd-index
preference and a denominator-dependent approximate index quotient have not
been separated. Truncating or rounding the exact ratio to 64--67 bits does
not distinguish these operands: 19/64 is already exactly representable.
Do not install a special case for 19/64 or retroactively call V6 validated.

Artifact: `../tmp/fpatan-re/d0022-midpoint-localization.json`, including all
728 midpoint observations, source hashes and the 24-row new frontier.

## Next decisive work

Prepare a fresh exact-midpoint discriminator bank for every `(2*n+1)/64`,
using varied exactly representable denominators, both signs, swapped octants
and all RC modes. Explicitly target lower-index parity and variation in
denominator significand. Include the 3/64 direct-versus-table ambiguity.
Use the public `U7099..U70c1` index-construction/control block as independent
evidence; its `0x6a7` and `0x69d` numerical semantics remain unknown.

Freeze competing general hypotheses before any labels. A new candidate must
pass **all eleven** saved jobs, independent C/Python/architecture checks and
a fresh challenge before promotion. D0023 is not yet created or reserved.

## Local verification

All 22 arithmetic unittest groups, syntax compilation and diff checks pass.
The compressed guard/pipeline and scorer mutation scripts pass when invoked
directly. An initial unittest-discovery invocation found zero tests in those
script-style files; it was not counted as a pass, and their actual `main()`
checks were then run successfully. Main C remains byte-identical to the
D0009 frozen baseline. D0017–D0020's negative evidence remains unchanged.
