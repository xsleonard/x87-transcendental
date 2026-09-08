# H1704: closed stage predicates against the actual planner

2026-09-04 local date. Analysis-only, no numerical fit or new physical claim.
No hardware, private-ledger access, labels, remote action, production/default
change or paper/PDF update.

## Result and exact boundary

Both Z3 4.15.3 and CVC5 1.3.1 return UNSAT for all 11 stated obligations and
SAT for the three deliberately false alternatives. A separate execution audit
matches the actual Python planner on 1,179,648 cases. The complete artifact
directory replays byte-for-byte.

The primary equivalence covers the entire 121-bit **planner input space**:
raw80, instruction1, SW16, abridged physical tag8 and CW16. Reserved PC01 and
incoherent summaries have explicit rejection outcomes. This is not a claim
that all these controls are physically supported, nor a complete machine-state
domain. The remaining registers, pointers, histories and other machine state
are not encoded in those 121 bits.

Unlike a second handwritten copy of the planner, the checked expression is
generated from the actual pinned `classify` and `plan` Python ASTs. The small,
restricted AST translator and its correspondence to Python remain trusted.
Writeback and wrapped-underflow conclusions additionally depend on the prior
numerical/state contracts; `compose` and the state model are NOT automatically
translated here. This does not establish universal silicon fidelity or expand
the existing partial state model. No new candidate numerical miss is known.

## Formulas

Let E be the original 15-bit exponent, J the explicit integer bit, Q significand
bit62, s the complete raw significand, and O physical ST0 occupancy selected by
SW.TOP from the abridged tag. Let M=CW&63, with I/D/U mask bits numbered0/1/4.
Boolean expressions below concern the original raw encoding, not a canonical
numerical representation.

```text
P = ((SW & 63) & ~M) != 0                 # previously pending exception
A = PC != 01 and (SW & 0x8080) == (P ? 0x8080 : 0)
I = not O or (E != 0 and not J) or (E == 0x7fff and not Q)
D = O and E == 0 and s != 0
F = (I and not M.I) or (D and not M.D)    # early fault
R = O and J and 0x403e <= E < 0x7fff      # numerical C2 range
T = A and not P and not F

numerical_request = T and O
writeback         = T and not R
wrapped_underflow = T and O and E == 0 and s != 0 and not J
                    and instruction == FSIN and not M.U
```

The planner's ordered outcomes are: reject PC01; reject incoherent summary;
pending; early; masked-empty if not O; otherwise number. `A` denotes software
acceptance only. The range predicate uses raw valid-normal classification;
invalid encodings are not accidentally treated as out-of-range numbers.

Numerical request is derived directly from AST equivalence. Writeback uses a
separate manual summary of the H1703 return branches, assuming numerical C2
iff R and the existing state-result contract. Wrapped underflow uses the
H1659/H1660 class/exception contract. Its two implications prove that this
formula requires DM masked and implies evaluation plus commit; they do not
independently prove the physical underflow selector or translate `compose`.

The planner is invariant under raw sign changes, CW nuisance/RC bit changes
masked by0xfcc0, and condition-code/SF changes masked by0x4740. These are
**stage-only software invariants**: they say nothing about numerical RC/sign
independence, output status independence, or unused physical control bits.

## Translator review and negative controls

The translator accepts only the syntax present in the pinned two functions:
bounded integer/string constants, names, bitwise operations and shifts,
predicate Boolean operators, unsigned comparisons/membership, conditional
expressions, `bool`, `raw.classify`, assertions, name assignments, if/return,
and the two exact NotImplementedError outcomes. Unsupported syntax fails.
Guarded branch paths preserve assignments and early returns. Accepted calls
have no side effects; the translated Boolean contexts do not depend on Python's
operand-valued `and/or` behavior or side-effectful short-circuit evaluation.

Integers use a 128-bit carrier. Inputs are nonnegative and at most64 bits; the
largest assertion constant is2^64. Every shift/intermediate in these functions
fits. The sole complement occurs in `before_status & ~masks & 63`; the bounded
nonnegative status removes high complement bits, so the finite complement has
the same result as Python's unbounded complement. String identities are
injective codes; no translated comparison mixes string and numeric domains.
These are reviewed source-specific arguments, not a general Python verifier.

All SMT queries and solver outcomes are retained, with Z3 models for SAT:

- Request is not writeback: occupied FCOS `403e:8000000000000000`, SW3800,
  tag80, CW0000 requests the numerical C2 result but does not commit.
- Erasing the pseudo-denormal class before planning: FCOS
  `0000:c1c0fd73948a3d95`, SW2000, tagd7, CW0000 must take early DE. The
  mutated class incorrectly reaches numerical evaluation.
- Replacing pending delivery with numerical evaluation: FCOS
  `7fff:8000804010010001`, SW80a9, taga5, CW0000 is a retained SAT witness.

These are software counterexamples, not newly executed hardware tuples or
freshness clearance. Their full original models remain unchanged in results.

## Runtime audit, artifacts and checks

Nine raw-class representatives × two occupancies × two instructions ×64 masks
×64 prior flag sets ×four PCs ×two summary alternatives =1,179,648 calls.
RC, TOP, condition codes and SF vary as specified in the script. This finite
execution bank is not exhaustive over all raw significands or all state bits;
whole-planner-domain coverage comes from the conditional SMT equivalence.
Counts: reserved-PC294,912; incoherent-summary442,368; pending363,636;
early20,412; masked-empty26,244; number32,076. Zero mismatches.

Paths relative to `fsincos-re`:

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1704_stage_predicate_certificate.py` | `46e942a12865f16b9af3f813a21dce9f87444640b29feddb27fce3e9c654b241` |
| `tmp/ledger33/current/h1704_stage_predicate_certificate/report.json` | `803a652626aa9178d48ffe03a096db38cfba3c4d6b222e96b4cdfa32f06e4e78` |
| `tmp/ledger33/current/h1704_stage_predicate_certificate/solver_results.json` | `92b5fa8653bdad6352b1f01863b378c5a227aa76d5655f87ca9073042dd156f6` |
| `tmp/ledger33/current/h1704_stage_predicate_certificate/source_AST.json` | `24c29fb47258aa2aab89bb8aa1f906f2e6b1cdd92315d53b36089d15e484549c` |
| `tmp/ledger33/current/h1704_stage_predicate_certificate/runtime.json` | `3bf7a2fa5b1827abf4374917b349340e91ce28c5a6abdb1044ee5bb806008ccb` |

The report pins H1645 raw classification, H1703 composition and H1700 solver
driver. Each query has its SMT file, result and digest. Outcome-stream SHA256
is3f99e159b4689f2070dde86e0e2bffc9e2579587336475f8eeec4427f47225d2.
Replay `/private/tmp/h1704-replay.LLt49Q/h1704` matches every artifact exactly.
Syntax, canonical build, both selftests and diff/whitespace checks pass.
Source0339a7d6, headera5e9d085, ROM2189e006, paper802fb3b6 and README8096a84f
anchors remain unchanged; speculative defaults remain off. Sessions90272 and
91617 are terminal. No live solver, replay or capture remains.

## Next physical obligations

This discharges the bounded planner-equivalence question, not the full goal.
Return to genuinely missing physical evidence/interfaces rather than repeating
the same planner theorem: smallest-denormal and zero/infinity retained tuple
provenance, unsupported controls, payload/history coverage and full pointer/tag
effects. Recover existing records before considering fresh hardware, and keep
numerical correctness separate from unknown architectural status bits.

All81 incumbent-frontier outputs remain candidate-matched. H1697 possible
private matches remain unresolved; H1688 reservations stand. No recapture of
opened campaigns, no H1670 held runner, and no H1685 XRSTOR work. The full goal
remains active/unachieved; these are real conditional implementation results,
not a closure claim or a global blocker.
