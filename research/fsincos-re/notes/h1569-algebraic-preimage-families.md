# H1569: exact algebraic external preimages, not a selector solution

For a direct `3ffc` significand R, an exact positive external preimage below
2^63 satisfies, in units of 2^-66,

    S * 2^t = 2*q*M + epsilon*R,
    M = 0x3243f6a8885a308d3,
    q >= 1, epsilon in {-1,+1}, 2^63 <= S < 2^64.

Here R lies in [2^63,2^64), M is the exact M66 reduction constant, and
`t = external_se - 0x3ffc`. Nonzero reduction quotient implies the external
magnitude is at least pi_M/2 - 1/4 > 1, so t >= 3; the architecture's strict
external bound gives t <= 65. `pi_M/2` here denotes the model's finite
constant `2*M*2^-66`, not infinite-precision pi/2.

Odd R is impossible by parity. For even R, let n = 2^(t-1). Since M is odd,
its inverse modulo n exists, and every solution is in the single class

    q0 = -epsilon*(R/2)*M^(-1) mod n.

Normalization independently gives

    L = max(1, ceil((2^(63+t) - epsilon*R)/(2*M))),
    H = floor((2^(64+t) - 1 - epsilon*R)/(2*M)).

The first candidate is `q = q0 + max(0, ceil((L-q0)/n))*n`. It is a solution
exactly when q <= H. The normalization interval is shorter than n because
M > 2^63, so there cannot be a second solution for that sign and exponent.
Iterating the two signs and 63 possible exponents is therefore exhaustive;
there is no solver timeout, sampled search, fitted threshold, or unbounded
quotient enumeration. Each emitted encoding is checked against the original
integer equation and quotient rounding.

On H1568's 50 distinct anchors this yields 509 exact preimages for 26 anchors;
the other 24 have no exact preimage in this domain. The independent H1404
results reconcile exactly: 3 SAT, 7 UNSAT, and all three previously preserved
witnesses are members of the enumerated sets. H1404/H1410's separate fresh
endpoint-separator UNKNOWN results are **not** resolved by this construction.
All original SAT/UNSAT/UNKNOWN artifacts remain untouched.

An independent brute-force check at significand widths 3, 4, 5, and 6 checks
all 256 external encodings in the corresponding domain and all 60 possible
normalized residuals; the enumeration agrees exactly.

There are 122 same-positive-residual cosine candidates across 12 anchors:
positive residual with q mod 4 = 0 uses FCOS, and q mod 4 = 1 uses FSIN.
All 122 have exactly the same exposed arithmetic diagnostics and baseline
endpoint as their direct anchor in RN/RD/RU/RZ. Only the `DI_IN` input identity
line and `DI_FIN`'s ASLR-dependent `ra` token are omitted; all remaining `DI_`
prefixes and fields, including `DI_RC2` and `DI_FIN`, are compared. Both forced
final-carry endpoints also agree in the selected, previously observed anchor
mode. This is a statement about exposed model state, not complete silicon state.

All model binaries have R84 off. H1412's causal correction still applies:
the default R84 literal ledger can create an apparent direct/preimage split
after identical arithmetic; that is not evidence that the model consumes a
reduction carry. No reduction history survives `sky_reduce_rc`/`wv_from_rc`.

For subsequent experiments the histories are computed from the actual
reduction equation `X - 2*q*M = R`, not from the inverse-construction addition
`2*q*M + R = X`. Both borrow and complementary-add carry chains are retained
at width 130 and their opposite polarity is verified. These are mathematical
ripple histories, not physically recovered wires or a proposed selector.

The H1570 bank freezes two fresh preimages per eligible anchor: minimum q,
then maximum q with opposite mathematical carry64 when available, otherwise
maximum q. Collision checks remove any previously seen significand regardless
of instruction, exponent, or mode. The prediction to test is transfer of the
already observed anchor value, not a new fit to the fresh inputs.

Artifacts:

- `experiments/h1569_algebraic_preimage_families.py`, SHA-256
  `1d9caabef7abe0e411064938fc2e6561f187b4963fe1bbcf1c953f206bd2004c`.
- `tmp/ledger33/current/h1569_algebraic_preimage_families.json`, SHA-256
  `fd23b62346554ccdc9ab88d1e513c8db05b11df7d48e933249ed58b80ea15b8e`.

Reproduce with `--root fsincos-re --models DIR --output NEW_REPORT.json`,
using the ledger-off baseline/carry0/carry1 models described in the H1568 note.
The script verifies their source and binary hashes against H1568.
No hardware, emulator changes, or paper/PDF changes are part of H1569.
