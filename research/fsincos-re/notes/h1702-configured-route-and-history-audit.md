# H1702: configured route and rounding-history dependency audit

2026-09-04 local date. This checks the actual configured analysis candidate's
source dependencies. It changes no numerical formula, production default,
hardware record or academic paper/PDF. Full silicon equivalence remains open.

## Result and precise scope

For both standalone instructions, the enabled H1630/H1633/H1638 candidate
passes a conservative compiler-parsed call-graph audit combined with explicit
H1700/H1701 entry invariants. Each instruction reaches 34 defined functions in
43 constant-argument contexts. There are no unexpected numerical functions,
unsupported control-flow constructs, indirect calls or `.rh` member expressions
in the retained reachable bodies. The R84 lookup returns before its operand
ledger; the polynomial/table hooks return before the legacy fitting code.

The two possible legacy tiny calls are excluded by seven source-backed route
lemmas, all UNSAT in both Z3 4.15.3 and CVC5 1.3.1. Two deliberately weakened
contracts yield SAT. Disabling only the polynomial hook exposes 19 additional
legacy functions in each instruction's graph, including `r59_apply`,
`fcos_low3_terminal_correction`, carry/history classifiers and the legacy adder.
Thus the audit does not pass merely because the intended helper names appear.

This is conditional implementation evidence, not a general C verifier,
automatic C/LLVM memory proof, compiler correctness theorem or proof that
silicon implements the graph. The limited AST walker, manual semantic
correspondence and fixed configuration are trust boundaries. No numerical
execution, hardware observation or new unique-input credit is added here.
All 81 known external incumbent-frontier outputs remain candidate-matched;
no new candidate numerical miss and no full-goal closure are claimed.

## Configuration and source correspondence

The source string is exactly the previously tested H1638 candidate:
SHA7c1eda2a245b9da3f4c24fa1abb06b8d929a24059909795b2303aa3bc9a22a4a.
Production source, arithmetic headers, ROM and source builders are pinned.
Clang parses it with all three candidate hooks enabled and R84 disabled.
The raw invalid gate and standalone operation-class selectors are enabled;
the selected instruction's standalone flag is 1 and the other's is 0.
Other globals retain their actual initializers, including internal tracing0.
This does not cover arbitrary CLI perturbation options, disabling a required
hook, paired FSINCOS, or a caller that omits the standalone configuration.

Apple Clang17.0.0 produces the AST. The walker follows direct calls, prunes
known constant branches and code after unconditional returns, and otherwise
keeps both branches. Loops are conservative overapproximations. Unsupported
switch/goto/indirect calls fail the audit instead of being silently ignored.
Variables bind by declaration identity, not name: a shadowing local cannot
inherit a global constant. Extern declarations are unknown rather than zero;
forward declarations share the actual later initializer. A separate local
shadowing check confirms unknown/overridden identities behave as intended.

The only actual external dependencies in the retained graphs are `fprintf`,
the assertion failure routine and the SDK assertion macro's `__builtin_expect`
branch hint. Assertion success and ordinary noninterfering I/O are assumed;
these are not further numerical kernels. The audit does not execute x87.

## Semantic exclusions connecting the entry hooks

For a valid nonzero finite in-range operand, let xt be the input leading-bit
exponent and rt the exact residual leading-bit exponent. H1700/H1701 provide:

- Direct input: rt=xt<=-1 and c=0.
- Reduced input: -65<=rt<=-1, residual nonzero, and c!=0 implies rt=-1.
- The rounded leading part and reconstructed wide residual have the same
  leading-bit exponent under those split bounds.

The tiny override therefore succeeds exactly when rt<-32. If it declines,
the operation-class core cannot take its direct sine-tiny, direct cosine-
bypass or residual-tiny route. Its exact-zero branch is also unreachable for
the nonzero finite domain. Remaining residuals partition into polynomial
[-32,-3] and table[-2,-1], with no gap or overlap. Invalid, special, zero and
out-of-range inputs follow their earlier gates, not that finite contract.

The call walker explicitly records rather than conceals the semantic exclusions:
`p5_fsin_standalone_tiny` in the sine core and
`fsin_operation_class_tiny_residual` in both cores. The seven solver queries
prove the stated abstract route relations, not every C statement automatically.
Two SAT controls show why the tiny override and c/nonzero-residual contracts
cannot be dropped. All nine formulas/results are preserved.

## Rounding-history finding

`wv_from_rc` still leaves its legacy `rh` field uninitialized. It is not fixed,
assigned zero or promoted here. In the configured candidate, polynomial and
table arithmetic use plain `h1630_add` and `p5_wv_mul_round`; neither reads
incoming rounding history. Every retained helper body has zero `.rh` member
expressions after the stated constant/semantic exclusions. New rounded carriers
may compute and initialize an `rh` scalar, but that is not consumption of the
uninitialized incoming member. The legacy history-sensitive adder is absent.

This source-member nondependence does not prove absence of padding/ABI copies,
all compiler memory issues or initialization safety for every legacy caller.
Do not generalize it into a whole-repository undefined-behavior certificate.

## Artifacts and verification

Paths are relative to `fsincos-re`; v3 is the reviewed final audit.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1702_candidate_route_audit.py` | `5ce3bdef7d24d9e787d8cde9eb05b6addca30075cd898891525d07dea7087974` |
| `tmp/ledger33/current/h1702_candidate_route_audit_v3/report.json` | `59927246c7d044a801460f9fa9026cad38d2d783a5f389212169e59ae0b81658` |
| `tmp/ledger33/current/h1702_candidate_route_audit_v3/solver_results.json` | `88691f8427c9a02e509bbba479a10f652887a078cdae16971169391189bae379` |
| `tmp/ledger33/current/h1702_candidate_route_audit_v3/candidate_callgraph.json` | `f00ea056c63e0443121e1ceb099792ff4158ba83ae701d2ce2d5ed019584e441` |

The final directory also retains normalized ASTs of every reached function,
per-function fingerprints and the disabled-polynomial negative graph. AST ids,
declaration addresses and locations are omitted from the normalized representation;
node kinds, operators, types, values and named references remain. Source hashes
and the Clang version pin its provenance.

The first `h1702_candidate_route_audit` directory remains intact with status
UNRESOLVED_OR_FAILED: it rejected the then-unreviewed `__builtin_expect` external
dependency. Inspection of the actual SDK assert.h resolved that dependency;
this was a verifier inventory issue, not a candidate arithmetic failure.
Its report SHA399a515a4ed4f4b64e117e8f255f10d288cd4e662224cf9f5c3cb619a3ffa723
and every SAT/UNSAT artifact are preserved. Intermediate v2 is also retained;
v3 additionally handles extern and forward-declaration bindings explicitly.

Replay `/private/tmp/h1702-replay.v2xxMd/h1702` is byte-identical to the entire
v3 directory, including both normalized ASTs, all formulas/answers and negative
graphs. No Mach-O exception is needed: this audit parses source and does not
emit an executable. Syntax, canonical build, both selftests and diff/whitespace
checks pass. All immutable source/ROM/paper anchors remain unchanged. Sessions
33161/77722/56670/72508 are terminal; no solver/capture/replay remains running.

## Next composition

The numerical route no longer needs an assumed hidden legacy fallback under
the stated configuration. Next connect actual numerical returns to the existing
state-transition contract: C2/no-writeback, raw E/J, pre-computation noncommit
versus late commit, and masks/PC ordering. Keep unsupported controls, incomplete
condition bits, arbitrary histories and physical fidelity explicitly unresolved.
Do not reinterpret these implementation certificates as fresh silicon evidence.

No hardware/private/remote action, new labels, default promotion or paper update.
H1697 possible private matches remain unresolved, H1688 reservations stand,
all opened campaigns closed, H1685 paused and H1670 held. The full goal stays
active/unachieved; this is concrete progress, not a global blocker.
