# H1630–H1632: shared sine/cosine polynomial operators

2026-09-04. Analysis only. No fresh hardware, private-history access, manifest,
canonical/default change, or paper/PDF edit. The full solution remains open.

## Result and limits

One explicit multiply/add contract now accounts for both six-coefficient
polynomial families on the tested records. H1631 independently replays all
578,292 actual polynomial output/C1 appearances from H1630. H1632 also passes
all 53 unique retained historical test tuples and the current 81-row frontier
across O0/O2/O3/UBSan. This is a fixed arithmetic program, without an operand
ledger, error-state selector, terminal carrier or history correction.

This is not a full FSIN/FCOS solution or proof of physical port wiring. Table,
tiny/special, complete status, and all-input silicon correctness remain separate
obligations. R96 remains empirical/incomplete in the unchanged incumbent.
The frontier is unchanged: 50 positive-direct failing mode/residual rows over
48 residuals; 81 external failing rows over 79 operands. These are incumbent
failures, all matched by the analysis candidate, not new misses in it.

## The fixed program

Let Tn mean normalized n-bit magnitude truncation, RN64 nearest-even, and
RC64 final architectural rounding including the result sign. For positive
residual magnitude x and the selected native coefficient family K1..K6:

```text
M(a,b) = T67(T67(a) * T64(b))
A(a,b) = RN64(a+b)
S = M(x,x)
F = M(S,S)
N = A(K1, M(F, A(K3, M(F,K5))))
P = A(K2, M(F, A(K4, M(F,K6))))
L = M(S,N)
R = M(F,P)

cosine: RC64(1 + T67(L+R))
sine:   RC64(x + M(x, RN64(L+R)))
```

The terminal schedules are deliberately distinct. Existing reduction,
quadrant/sign and polynomial/table/tiny dispatch remain. The internal sine
branch can serve external FCOS after reduction, and vice versa; branch counts
below must not be read as external instruction counts.

H1630's header defaults `G_H1630_POLYNOMIAL` to zero. Its driver assembles an
isolated translation unit in memory, intercepting only the existing polynomial
function. Canonical source is not rewritten. R84 is OFF in all comparisons.
The plain accumulator bypasses incumbent FADD/history classifiers. An observer
reports residual, branch, precision, final magnitude-rounding C1, and optional
stage values. Fallback gets no new arithmetic/C1 validation credit.

H1629's grid proof bounds all reachable direct polynomial inputs to 64
significant bits and reduced inputs to 63. Both coefficient families preserve
the width induction: multiply results fit 67, Horner sums fit 64; native sine
K5/K6 fit 63/64 and cosine K5/K6 fit 59/64. Consequently the only nonidentity
input-port cut in either program is `F.Y=T64(S)`. Sine's final multiply also
has identity input cuts. This is a numerical-program equivalence argument,
not a formal verification of every C execution or a silicon theorem.

With experimental controls/history modes off, the default R86 sine code is
already the same numerical program: it unconditionally clears the normalized
67-bit square's low three bits on one input to fourth. No new sine activation
gate is needed or introduced. The native constants are shared pinned ROM data,
not independently recovered silicon constants in this audit.

## H1630 retained-bank and software checks

Four enabled builds (O0/O2/O3/UBSan), plus a disabled O2 build, pass selftests.
The software-only preflight has 64 operands, both instructions and four modes:
2,048 row checks across the four enabled builds, with 10,496 independently
computed stage equalities. Disabled outputs equal the incumbent. Preflight RZ
is software validation, not an imputed hardware observation.

Twenty retained banks contribute 2,927,595 actual RN/RD/RU appearances:

| Branch | Output checks | Known C1 checks | Misses |
| --- | ---: | ---: | ---: |
| Sine polynomial | 289,914 | 289,914 | 0 |
| Cosine polynomial | 288,378 | 288,378 | 0 |
| Incumbent fallback | 2,349,303 | Unscored | 0 output misses |

These are overlapping bank appearances, not a cross-corpus unique tuple count.
H130 contributes 1,536 sine-polynomial appearances. H140 and both instructions
in H285/H292/H301/H307/H314/H320/H347 all take TABLE fallback. Their historical
"sine terminal" purpose must not be mistaken for polynomial coverage. The
remaining polynomial observations come from H110 sweep/dense raw streams.

The H110 raw aliases and positional input provenance inherit H1627's pins.
H285–H347 inputs/captures pass their retained SHA256SUMS and shared-input checks.
H130/H140 sources are pinned before scoring and backed by their retained runner;
these directories do not supply a complete historical checksum manifest.
All detailed source/stream hashes are in the prepared record and report.

Only one output changes from the incumbent: the already-known 9f4c/RU sweep
miss. No new frontier input is discovered. Zero-valued fallback C1 counters
are bookkeeping placeholders, not C1 observations or modeled status.

## H1631 full independent rational replay

The verifier uses only the Python standard library, with a separate Fraction
quantizer, complete graph, raw parser, final rounding, and external M66
reducer. It imports no producer arithmetic/scorer/parser. It checks every
source/stream hash and positional alignment; every hit's signed reduction,
quadrant, magnitude, width, output and C1; and all fallback outputs.

All 578,292 polynomial output/C1 appearances pass. Sine has 249,432 direct and
40,482 reduced appearances, including 144,624 negative results. Cosine has
249,432 direct and 38,946 reduced appearances, including 19,479 negative results.
The arithmetic cache has 192,758 prevalue keys, not that many unique hardware
tuples. Fallback remains outside the new operator/status claim.

## H1632 retained R86 discriminators and current frontier

The hash-pinned `r84_misses.tsv` and `r85_rz_misses.tsv` contain 56 historical
hardware-line appearances, deduplicating to 53 tuples over 47 operands. Three
duplicated tuples agree. Actual modes are RN17/RD4/RU29/RZ3; 30 tuples contain
status and 23 do not. Their provenance is weaker than full indexed raw streams:
original corpus streams are not reauthenticated by this experiment. No new
labels are opened and absent status stays unknown.

All four candidate builds match all 53 outputs and all 30 available C1 bits.
All are polynomial hits: 42 cosine and 11 sine. The R84-off incumbent matches
44/53; additionally disabling R86 reduces that to 33/53. Exactly 11 extra
sine-branch failures appear with R86 off, each matched by the shared formula.
This is a software ablation against retained observations, not a hardware
intervention or evidence that the physical chip contains a named R86 switch.

H1632 separately imports H1626's authenticated 81-row frontier. All four
candidate builds match every output, with identical per-row metadata; both
baseline builds miss all 81. These are all cosine-branch hits, unaffected by
R86 ablation. Frontier status is not reimported here and receives no extra C1
credit. Nine frontier tuples overlap the 53 historical tuples; do not sum the
two banks as disjoint observations. Disabled candidate outputs match baseline.

## Verification and artifacts

H1631's report and the complete H1632 output directory reproduce byte-for-byte
in a separate software replay at `/private/tmp/h1632-root-replay.zqKfYh`.
H1630's full hit data is independently recomputed by H1631, not a claimed
second full H1630 C-build/report run. Syntax, canonical build/selftests and
diff/whitespace checks pass.
The canonical source remains SHA256
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.
All speculative-off defaults remain unchanged.

Paths below are relative to `fsincos-re`:

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1630_shared_polynomial.h` | `5c279565bf3ab5b1a02d92a24fb2e40dc3b12ab23498522768118890cf5c5310` |
| `experiments/h1630_shared_polynomial_audit.py` | `706a7ed6a2556cb8aa03ca9c7842ece37d70f99f0cbe01479eb9e76e58828834` |
| `tmp/ledger33/current/h1630_shared_polynomial_audit/report.json` | `5dc548a52e2d46749548011b2e4c2fa8ce919d2a7ab618fc4f4c2746fa54bd79` |
| `experiments/h1631_independent_shared_polynomial.py` | `8d9566045c32272915fdc4d72e530f1377a281813034ec65cd6f50122e794bcf` |
| `tmp/ledger33/current/h1631_independent_shared_polynomial/report.json` | `fa26fb2bb6194b8a22816003a9069583e1feffc32b18adbf9c1e6f4a573f0682` |
| `experiments/h1632_legacy_and_frontier_transfer.py` | `aaa9a9ee128066ee171f740af5b27c95f0f5b09e477b17ee0835b3885815650f` |
| `tmp/ledger33/current/h1632_legacy_and_frontier_transfer/report.json` | `6889b6f933c226e4722d12ac28106ed1dd5ac22deb2c5a62ce11479c092d34b7` |

## Next

Audit the table-path arithmetic explicitly, with isolated hit accounting and
independent raw output/status replay. In particular, read the four-coefficient
Horner helper's operand order and its RN64 cosine-tail multiply before asserting
that the polynomial M/A contract transfers unchanged. Native table constants
are intrinsic model data, unlike error-state correction ledgers. Then address
tiny/special and full architectural status. Keep the polynomial candidate fixed;
do not resume input-boundary fitting or repeat old hardware tuples.
