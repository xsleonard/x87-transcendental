# H1633–H1635: explicit table arithmetic and its rounding discriminator

2026-09-04. Analysis-only continuation. No new hardware observation, private
history access, manifest, canonical/default change, or paper/PDF edit.
The full FSIN/FCOS goal is still unachieved.

## Outcome and scope

The table path can be expressed with the same X67/Y64 input-port convention
as the fixed polynomial, provided its distinct multiply destinations are
preserved. H1633's explicit table program passes 2,276,661 retained output/C1
appearances; H1634 independently recomputes every hit using a separate rational
graph, parser and external reducer. All 578,292 polynomial appearances remain
exact too. The table rewrite changes no output from the existing table path.

This is a numerical equivalence to the specified incumbent table arithmetic,
not independently measured table-port asymmetry or recovered physical routing.
All table input cuts are identities under the stated operand ordering. The
observable asymmetric cut remains the polynomial fourth-power input. The native
table cells and constants are intrinsic model data, not new error-state fits.

The RN64-destination table multiply cannot be replaced by RN64 of a CHOP67
product: that substitution fails 102 retained outputs and 139 C1 appearances.
These are failures of an explicitly different negative control, not new misses
in the fixed candidate. Table/polynomial hardware correctness for every input,
other paths, and full architectural state/status remain unproved.

## Exact table program

Let r be the positive reduced magnitude, Tn normalized n-bit magnitude
truncation, RN64 nearest-even, and RC64 the final signed architectural rounding.
The existing cell classifier is:

```text
r < 1/2: b = 18 + 4 floor(16(r-1/4))
r >=1/2: b = 36 + 8 min(2, floor(8(r-1/2)))
a = r - b/64

M(x,y)  = T67(T67(x)*T64(y))
MR(x,y) = RN64(T67(x)*T64(y))
A(x,y)  = RN64(x+y)

s = M(a,a)
H(K) = A(K1, M(s, A(K2, M(s, A(K3, M(s,K4))))))
p = H(sine four-coefficient family)
q = H(cosine four-coefficient family)
v = A(a, M(M(s,p),a))
w = MR(s,q)

z_sin = T67( M(table_cos,v) + M(table_sin,w))
z_cos = T67(-M(table_sin,v) + M(table_cos,w))
sine result   = RC64(sign * (table_sin + z_sin))
cosine result = RC64(sign * (table_cos + z_cos))
```

Existing residual/quadrant routing determines the result sign. An external
FSIN may use the internal cosine branch, and vice versa. The signed additions
above are a numerical rewrite of the original signed-subtract sequence.

MR rounds the exact port product once. It is **not** `RN64(M(x,y))`. Both
multiply destinations are already present in the incumbent source. No new
mode, operand-dependent rounding choice, or learned selector is introduced.
The existing sine K4 correction (subtract payload bit60 at scale2^-85,
equivalently subtract2^-25) is retained, not rediscovered or refitted here.
Native constants come from the pinned shared ROM; this is not independent
silicon constant recovery.

## Reachable-width and operand-order argument

The exact M66 reducer supplies `r=|D|*2^-65`. Every center b/64 is on that grid.
The four lower cells have offsets of magnitude at most1/32, and the upper
cells at most1/16. Thus all reduced table offsets obey:

```text
|a*2^65| <= 2^61
```

This integer has at most61 significant bits; the endpoint2^61 has only one
significant bit after removing trailing zeros. For unreduced direct inputs,
exponents -2/-1 give grids2^-65/2^-64 with bounds1/32 and1/16, respectively;
both yield at most60 significant offset bits. Zero is handled separately.
Thus a 65-bit reduced r does not imply a 65-bit input to the table squarer.

The centered M66 residual is below13/16, and unreduced inputs are below the
existing pi/4 threshold. Only b=18/22/26/30/36/44/52 are reachable; native
ROM row b=60 is not selected by this dispatcher.
The b=52 center itself is also outside the reachable residual domain; its
reachable inputs have negative offsets. Exact-center testing applies to the
other six selected cells, not an invented b=52 zero-offset hardware case.

The corrected sine K4 has61 significant bits and cosine K4 has63. Every
Horner sum and the sine-state/cosine-tail values fit64; squares and other
products fit67; all table ROM constants fit67. Put square on X and K4 or the
previous Horner sum on Y, rather than mechanically assigning source-language
argument order to physical ports. All X67/Y64 cuts then preserve their inputs,
including square*p, square*q, the final sine-tail product, and reconstruction
products. Exact multiplication commutes; this ordering preserves the original
numerical program. The proof does not determine physical operand-port routing.

H1634 checks these identities at every multiply in every independently
evaluated table graph, alongside the source-backed domain argument. This is
not formal verification of every C execution or an all-input silicon theorem.

## H1633 retained data and implementation checks

The isolated header defaults `G_H1633_TABLE` to zero. The builder inserts it
into a hash-locked translation unit in memory, leaving canonical source and
all older artifacts intact. H1630's polynomial header remains unchanged and
enabled; tiny/special/reduction/dispatch remain incumbent behavior. R84 is OFF.

O0/O2/O3/UBSan and table-disabled O2 pass selftests. A software-only preflight
uses162 distinct operands across both signs, every reachable cell boundary
and center with adjacent representable direct inputs, polynomial/tiny/C2
boundaries, and high-q inputs. Both instructions, four modes and four enabled
builds produce5,184 row checks and42,752 independent stage equalities. All
enabled builds agree with the pre-table H1630 candidate. Disabled-table
outputs agree as well. These software checks supply no new hardware labels.

The same20 authenticated retained inventories as H1630 yield:

| Scope | Actual output/C1 appearances | Misses |
| --- | ---: | ---: |
| New explicit table hook | 2,276,661 | 0 |
| Unchanged polynomial hook | 578,292 | 0 |
| Remaining incumbent fallback | 72,642 outputs; C1 unscored | 0 output misses |

All are actual RN/RD/RU rows. No RZ observation is inferred from the software
preflight. Bank appearances overlap earlier audits and each other; this is not
a new cross-corpus unique count. H130 remains polynomial; H140/H285–H347 now
hit the table hook rather than fallback. The H110 sweep/dense inputs cover
both. Raw/positional/hash provenance and its H130/H140 limitations are inherited
explicitly from `h1630-h1632-shared-polynomial.md`.

All table cells are represented. Hits include1,398,867 reduced and877,794
direct appearances;682,818 have65-bit reduced magnitudes;829,338 have negative
results;1,062,666 have negative cell offsets. The retained table hits contain
zero exact-center offsets. Exact centers pass the software preflight, not a
claimed new hardware test. Targeted exact-center, boundary, RZ and PC coverage
should be reconciled from other retained campaigns before claiming those gates.

## H1634 independent full replay and negative control

The verifier imports only the standard library. It has its own Fraction
quantizer, native-constant parser, complete table and polynomial graphs,
raw reader, exact external M66 quotient/residual, cell selection, sign routing,
and final rounding. It checks every source/stream hash and positional input.
All2,854,953 hook output/C1 appearances pass; all72,642 fallback outputs match
without new arithmetic/status credit. The graph caches contain280,883 table
keys and192,758 polynomial keys, not hardware tuple counts.

Replacing MR by RN64(M) changes the cosine-tail intermediate on143,574 table
appearances. It yields102 output mismatches and139 C1 mismatches against the
same retained captures; these counts overlap and must not be added. The first
counterexample is original H285 FCOS/RN row91:

```text
input:             c032:ede885d54bf588b5
hardware/candidate 3ffe:b3f1d44ab9006f49, C1=0
double rounding:   3ffe:b3f1d44ab9006f4a, C1=1
```

All mismatches belong to that alternate graph, not the fixed candidate or a
new incumbent frontier. Status-only distinctions show why endpoint-output
agreement alone is insufficient to validate an internal rounding replacement.

## H1635 C reproduction and frontier regression

A separate in-memory negative-control build changes only MR's destination
sequence to CHOP67 followed by RN64. The original header stays intact. H1635
reauthenticates the positional raw inputs/results for32 selected H1634
counterexamples, then checks them in C. O2 and UBSan reproduce the independent
alternate predictions exactly:24 output and28 C1 mismatches. All four positive
candidate builds match32/32 outputs and C1 bits. The selected32 are not the
entire102/139 mismatch union and are not new hardware observations.

The four combined table/polynomial builds also match all81 current frontier
outputs and53 historical tuples (30 known C1). These are polynomial hits, not
new table validation. Nine of the historical tuples overlap the frontier;
historical extracts retain their weaker provenance and absent status stays
unknown. Current incumbent frontier stays direct50/48 and external81/79.

H1633's entire hit data is independently recomputed by H1634; no second full
H1633 build/report reproduction is claimed. H1635's complete output directory
reproduces byte-for-byte under `/private/tmp/h1635-root-replay.X5kbxI`.
Syntax, canonical build/selftests and diff/whitespace checks pass. Canonical
source remains SHA256
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.
Speculative-off defaults are unchanged; incumbent R96 remains empirical.

## Artifact anchors

Paths are relative to `fsincos-re`; reports pin raw sources and generated streams.

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1633_shared_table.h` | `238ee52346049bbb292cb43958c01f8f1ddae20e4d3fad004bf74423f6dae66b` |
| `experiments/h1633_shared_table_audit.py` | `3f23458fff3cc1b4965215554874eb011d53283ab18c93a6fa8fce933bbf864b` |
| `tmp/ledger33/current/h1633_shared_table_audit/report.json` | `935a4352843b0b0b96559fb4447fc1a329b0da9d5530c85790b622b3bc5bb51c` |
| `experiments/h1634_independent_table_certificate.py` | `41393ef2dd4fc42ff4d047b8fae87af529f9cb51e2ef784a78bf7ddc1a20cefa` |
| `tmp/ledger33/current/h1634_independent_table_certificate/report.json` | `12a7be9d12cf49525b0a5a08ee627d71ef5800a30eee524b51cc1f70c36d48be` |
| `experiments/h1635_table_rounding_discriminators.py` | `b0507a225c381c220d3a6e84079bbe3e98875229f2c0d96efef670a33630a5ed` |
| `tmp/ledger33/current/h1635_table_rounding_discriminators/report.json` | `2813d844908953278755a80a9cba38677aedabba6419587a8ef6513543f1025f` |

## Next

Reconcile remaining targeted table coverage (exact centers, classifier boundary,
RZ, PC) from existing raw records; do not repeat tuples. Audit tiny/special and
full status explicitly. Start with the actual tiny-boundary helpers and
H117/H238 evidence, not historical "resolved" headings. Capture status is
sampled after FLD and the transcendental but before FSTP, so load effects and
instruction effects must be separated before claiming full architectural flags.
Keep both polynomial and table numerical programs fixed. No production or paper
promotion follows merely from finite passes or numerical program equivalence.
