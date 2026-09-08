# H1636–H1637: retained RZ/PC transfer and a tiny-path closed form

2026-09-04. Analysis-only. No hardware observation, private-ledger access,
manifest, emulator/default change, or paper/PDF edit. Full closure is unproved.

## Progress and remaining boundaries

The unchanged combined polynomial/table program passes the available FSIN RZ
and RN precision-control banks. A separate tiny-output/C1 formula now explains
every retained tiny row checked, including reduced tiny residuals. It needs
only a leading value, a 64-bit predecessor, sign/mode logic, and the existing
external tiny bypass—not an arbitrary far-sticky magnitude.

This does not fill missing FCOS/RZ or FCOS/PC evidence, exact table centers,
special encodings, denormal behavior, or full architectural-state semantics.
The historical i7 special/boundary archive was not recovered this turn: one
read-only SSH attempt to the correct user-designated i7,142.132.217.24, timed
out on port22. No old capture runner was executed. The Xeon remains45.32.204.118;
standing research authority on both is unchanged. Local evidence permits work
to continue; the timeout is not a global goal blocker.

## H1636: what the retained control-mode records actually cover

R88's previously opened VM RZ bank has three surviving FSIN streams: H347,
sweep, and dense. All raw files and CPU metadata match their SHA256SUMS.
The historical runner and mirrored-input mapping identify the positional inputs,
which match the H1633-pinned input files. The old restoration/re-capture history
is historical provenance, not authorization to repeat these tuples now.

H172 supplies FSIN/RN sweep and H171 table discriminators at PC24/PC53/PC64.
For each family, all three stored full result/status streams are byte-identical
to each other and to the prior PC64 stream. H172 lacks a complete historical
checksum manifest; its source/raw pins and legacy byte-equality are recorded
without pretending otherwise. Its old script's universal "proves ignores PC"
wording is not adopted. The numerical candidate itself has no newly implemented
PC control field or full-status API.

| Actual captured setting | Total appearances | Table output/C1 | Polynomial output/C1 | Fallback outputs only |
| --- | ---: | ---: | ---: | ---: |
| FSIN RZ, PC64 | 487,082 | 378,849 | 96,126 | 12,107 |
| FSIN RN, PC24 | 50,321 | 22,088 | 16,126 | 12,107 |
| FSIN RN, PC53 | 50,321 | 22,088 | 16,126 | 12,107 |
| FSIN RN, PC64 | 50,321 | 22,088 | 16,126 | 12,107 |
| Total | 638,045 | 445,113 | 144,504 | 48,428 |

Every output and every hook C1 comparison passes. Every one of the589,617
hook rows is recomputed with H1634's separate Fraction graph, exact external
M66 reducer, sign routing and raw parser. PC metadata is retained rather than
silently treating the three settings as one tuple. The banks overlap previous
audits; these are retained appearances, not fresh or independent discoveries.
Another676 selected scope/sign/mode rows agree across O0/O2/O3/UBSan builds.
The current81-row frontier is unchanged, not expanded by this transfer.

No exact table-center row occurs here either. The local canonical capture-input
search finds direct-center operands in FPTAN/F2XM1 input banks, not matching
FSIN/FCOS observations; sibling-instruction labels are not transferred by name.
The six reachable table centers and targeted lane-boundary evidence remain
specific gaps. The b=52 center is unreachable, as H1634 already establishes.

## H1637: explicit tiny arithmetic and C1

For a non-bypassed tiny residual magnitude `0 < r < 2^-32`, let L be the
positive leading value: L=r for the sine branch and L=1 for the cosine branch.
Let `pred64(L)` be its immediately preceding positive 64-bit representable
value, accounting for a binade boundary. The quadrant gives the output sign.

```text
toward_magnitude_zero = RZ or (RD and positive result) or (RU and negative result)

if toward_magnitude_zero:
    magnitude = pred64(L); C1 = 0
else:
    magnitude = L;         C1 = 1   # RN or directed away from magnitude zero
```

This describes ordinary final magnitude rounding of a value infinitesimally
below L. In this domain `0 < r-sin(r) < r^3/6` lies below half a predecessor
spacing, including at powers of two. Also `0 < 1-cos(r) < r^2/2 < 2^-65`,
below the midpoint between1 and its predecessor. A nonzero reduced tiny input
is `D*2^-65` with at most33 significant bits, so its leading r is exactly
representable at64 bits. No extra rounding of a hidden wider r is required.

The incumbent far-sticky term also lies strictly below that midpoint. Its
particular scale (the arbitrary320-bit separation) is unnecessary for this
numerical result: sign/mode and predecessor suffice. This is a source-backed
mathematical equivalence, not full C formal verification or proof of the
chip's internal epsilon-generation mechanism.

Keep the **external bypass** distinct. Unreduced input top exponent below-68
returns x for FSIN or1 for FCOS in every mode, with C1=0. The threshold is the
existing silicon-observed rule, not newly fitted here or deduced from Taylor
bounds. This bypass is not correctly directed mathematical sin/cos rounding.
It still sets precision on the normal nonzero operands actually observed.
Do not apply it to reduced tiny residuals: those remain in the sticky rule.

## Tiny and precision-flag evidence

H1637 authenticates the H117 generator's exact360-input order without running
the capture script, then uses its actual RN/RD/RU streams. It also uses both
instructions' H110 sweep streams and the available FSIN RZ/PC sweep extensions.
The H172 PC64 RN duplicate of H110 is not counted twice here. Source streams
and all generated outputs are pinned before and after scoring.

| Tiny path | Actual output/C1 tuples | Misses |
| --- | ---: | ---: |
| Direct FSIN bypass | 7,830 | 0 |
| Direct FCOS bypass | 3,867 | 0 |
| Direct sticky sine | 9,942 | 0 |
| Direct sticky cosine | 4,539 | 0 |
| Reduced sticky sine | 40,965 | 0 |
| Reduced sticky cosine | 42,762 | 0 |
| Total tiny | 109,905 | 0 |

These and18 out-of-range C2 responses make109,923 unique instruction/mode/PC/
operand tuples within this audit. The C2 responses validate the response marker
and recorded C2 bit, not a stored unchanged ST0 payload absent from the output
format. They receive no modeled C1 credit. The audit sees341,499 additional
table/polynomial rows as existing numerical-hook output regression, not a new
independent polynomial/table proof. In total it reads451,422 appearances.
Another2,373 selected tiny scope/exponent/sign/mode rows agree across all four
C builds; the new tiny formula remains a separate analysis implementation.

Every one of451,404 observed normal finite nonzero in-range appearances has
exception bits `SW & 0x3f == 0x20` (precision only), across the audited tiny,
polynomial and table paths. This is a separately tested instruction-flag
hypothesis; it is not computed from final-prevalue exactness. All bypass status
words are3820; non-bypass tiny status is3820 or3a20 according to C1. The18
out-of-range words are3c00. Full captured SW includes TOP and potentially
undefined condition codes; these observations do not implement arbitrary
initial-state, stack, unmasked-exception or reserved-control behavior.

No zero, denormal, pseudo-denormal, infinity, NaN or invalid-encoding row is
present in this selected data. H1637's source-classification branches for those
cases are not credited as hardware-validated merely because they exist in code.
The former historical "special classes resolved" heading is not a substitute
for the missing raw evidence. Capture SW is sampled after FLD+instruction and
before FSTP, so special-value/load effects require deliberate separation.

## A reduced-zero branch can be excluded analytically

For this specific M66 program, nonzero external operands cannot reduce to an
exact zero. M66 is odd and has66 bits. Suppose
`sig * 2^(e+2) = N*M66`, where sig has at most64 bits. N=0 immediately
contradicts nonzero input. Otherwise remove powers of two on both sides. Since
M66 is odd, the remaining odd part of sig would equal `odd(N)*M66`, which has
at least66 bits. That contradicts sig's64-bit bound.

Thus the canonical exact-reduced-zero branch is unreachable from nonzero valid
external64-bit significands under this reducer. External zero is a separate
entry case and still needs its own architecture/status coverage. This proof is
about the specified integer reducer, not a claim of recovered physical quotient
circuitry or universal silicon equivalence. Do not launch an impossible exact-
zero-preimage search or manufacture a missing hardware alias for this branch.

## Verification and anchors

H1636 executes the C candidate and a separate rational forward model on every
hook row; H1637 executes C alongside the closed-form predecessor rule on every
tiny row. H1637's complete output directory reproduces byte-for-byte under
`/private/tmp/h1637-root-replay.aimghc`. No second full H1636 C/report
reproduction is claimed. Syntax, canonical build/selftests and
diff/whitespace checks pass. Canonical source remains SHA256
`0339a7d6161c29164232fadd46053a538b7163d5d4449889e3600e9245026f2b`.
All speculative defaults stay off; R84 stays off in comparisons; R96 remains
empirical/incomplete in the incumbent. Frontier stays direct50/48, external81/79.

Paths below are relative to `fsincos-re`:

| Artifact | SHA256 |
| --- | --- |
| `experiments/h1636_retained_rz_pc_transfer.py` | `9d44c92b5c6267752da7bab906e160ae82bb1eda338f93c86c8e7732adb45707` |
| `tmp/ledger33/current/h1636_retained_rz_pc_transfer/report.json` | `f38c41fd45e304685be1705b3dd094eed35eb3bc73fcd31c569407e523ccddd5` |
| `experiments/h1637_tiny_closed_form_audit.py` | `ea6e22d450dda2d5046d1ed309d971b2d50a8434cc5b934b7413995c81ebf0f2` |
| `tmp/ledger33/current/h1637_tiny_closed_form_audit/report.json` | `a18fb1a7a9dad745e7fea87430bfa1820273a52d43e99a175a8de5becb0d7158` |

## Next

Implement the predecessor-based tiny rule in an isolated, default-off combined
C program, retaining its distinct bypass and emitting C1 explicitly. Reconcile
or freshly discriminate the still-missing table-center, FCOS RZ/PC and special-
value/status cases with full local public/private freshness and immutable
predictions. Standing host authority already exists; do not ask for it again.
Do not run old scripts that repeat captures or access unrelated remote services.
No production or paper promotion follows from these finite checks.
