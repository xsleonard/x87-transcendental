# H1592 — independent exact-integer arithmetic specification

**Independent arithmetic implementation agrees with the exposed ordinary
stages; ordinary terminal reconstruction is still not a silicon solution.**
No selector was proposed or promoted. No hardware ran, no label was inferred,
and no emulator source/default or paper/PDF was edited by this investigation.

## What is independent, and what remains an assumption

`experiments/h1592_independent_integer_spec.py` implements signed dyadics
`n * 2^e` with Python arbitrary-precision integers. Addition aligns integer
scales, multiplication multiplies signed numerators, and materialization
selects the normalized significand by an independently written integer
quotient/remainder quantizer. It supports nearest-even, toward zero, signed
up/down, magnitude-away, and round-to-odd/jam. The quantizer returns the
numerical rounding direction as a separate, explicitly derived field.
There is no bounded C accumulator, C include/wrapper, reused arithmetic
helper, reused trace parser, multiplier topology, terminal selector, operand
ledger, or empirical decision tree in this specification.

The mathematical polynomial regrouping is

```text
1 + x² [C1 + x⁴ (C3 + x⁴ C5)]
  + x⁴ [C2 + x⁴ (C4 + x⁴ C6)].
```

The six literal signed ROM constants are explicit inputs, checked against
`src/p5_rom_constants.h`. They are shared with the existing reconstruction,
not independently recovered from silicon. Likewise, the **proposed** finite
operation schedule is an assumption to test, not an observation of internal
hardware:

```text
S = CHOP67(x*x)
F = CHOP67(S*S)
N = RN64(C1 + CHOP67(F * RN64(C3 + CHOP67(F*C5))))
P = RN64(C2 + CHOP67(F * RN64(C4 + CHOP67(F*C6))))
L = CHOP67(S*N)
R = CHOP67(F*P)
C = CHOP67(L+R)
Y = RC64(1+C)
```

The implementation scope is finite-normal direct cosine operands with
`1/8 <= |x| < 1/4`. It does not implement argument reduction, table-region
polynomials, FSIN, exceptional encodings, or a purported complete x87 unit.
The unlimited dyadic exponent is appropriate to this bounded audit; full
architectural underflow/overflow handling is not claimed.

## Tests that do not use the C arithmetic

The quantizer passes 30,660 cases against an independently enumerated set of
exact rational neighboring representables. These cover both signs, all six
tested rounding rules, exact values, half ties, and asymmetric binade gaps.
Four thousand further wide signed cases verify exact addition/multiplication
against `Fraction`, together with 72,000 normalized-width, numerical-history,
and idempotence checks. Production arithmetic uses integers; rational
arithmetic is used for tests and for human-readable exact difference units.

These tests verify implementation properties. They do not establish which
internal precision or rounding operation silicon uses.

## C-stage comparison and the observed-label boundary

The named bank is exactly:

- eleven observed historical H1378 mode rows over ten operands;
- eleven H1580 observed rows over eleven fresh operands;
- fifteen H1587 observed rows over fifteen fresh operands.

Thus **37 actual hardware labels cover 36 distinct operands**. H1592 also
generates 2,048 deterministic random operands as **software-only controls**.
All 2,084 operands are compared in all four software rounding modes, giving
**8,336 software mode rows per C build**, not 8,336 hardware observations.
Unobserved modes remain unlabeled, including all random controls.

Two fresh external C comparator builds are used: current source with R84
disabled, and that same source with every named optional Horner history
correction disabled. Both retain their existing terminal behavior; the
second is not an implementation of ordinary terminal `CHOP67(L+R)`.

For **each** build, all 8,336 software rows agree at every compared upstream
boundary: magnitude, square, fourth, negative factor, positive factor,
chopped left product, and chopped right product. All six exposed numerical
rounding-history fields also agree. The six unexposed intermediate Horner
results are generated and retained by the independent specification, but
are not falsely counted as directly traced C stage comparisons.

An additional independent reconstruction rounds the actual exposed C final
addition inputs under the requested architectural mode. It matches the C
endpoint on 8,336/8,336 rows per build. This is conditional implementation
agreement given C internal inputs, not an observation of silicon internals.

The history-disabled build has identical numerical results on this finite
bank. That establishes only software parity here; it neither invalidates
the previously measured history corrections elsewhere nor proves those
corrections globally correct.

## Exact discrepancy and no replacement claim

The only compared numerical-stage disagreement is the **terminal correction**:
the independent ordinary `CHOP67(L+R)` differs from the C model's explicit
carrier/selector replacement on 92 software mode rows per build. Twenty of
those are named-bank software rows and 72 are random software rows. The named
differences all have `C_current - C_ordinary = -1` unit of the correction's
local 67-bit grid. C and the independent specification agree upstream, so
this discrepancy is explicitly in the composed terminal behavior, not a
hidden disagreement in generic integer multiplication or rounding.

On the **37 observed labels**, the current C model is fourteen exact and
23 misses. Ordinary reconstruction is seventeen exact and twenty misses:

| Change relative to current C | Observed rows |
| --- | ---: |
| Both exact | 13 |
| Both miss | 19 |
| Ordinary repairs current miss | 4 |
| Ordinary regresses current exact | 1 |

The four repairs are the three historical far-corner RU rows and H1587
RN `3ffc:de3ffffc7a17c3dd`. The regression is H1587
RD `3ffc:e7400001dd7c7276`, which requires the current strict endpoint.
The other twenty observed misses remain. This is not a reason to install
ordinary terminal reconstruction, nor a general-input accuracy estimate.

The useful conclusion is narrower: there is now an independently tested
integer reference for the proposed ordinary arithmetic and explicit stage
differences. It separates implementation cross-checking from choosing the
correct micro-operation semantics. Agreement through the terminal products
does **not** prove a missing physical terminal-carry selector: a conditional
upstream silicon behavior absent from both hypothesized schedules remains
possible. Forced endpoint repair remains an effective intervention rather
than a physical-cause proof.

## Reproduction and provenance

```sh
python3 experiments/h1592_independent_integer_spec.py --selftest
python3 experiments/h1592_independent_integer_spec.py \
  --root . --output-dir /private/tmp/NEW_h1592_output --random-cases 2048
```

The output directory must not already exist. The script compiles comparator
executables and records source, constants, evidence, binary, and raw-trace
hashes. Before using labels it checks all three input evidence hashes against
H1590, cross-checks the eleven historical labels against the original H1378
no-ledger miss TSV, and checks H1580/H1587 OPENED sidecar, score and raw-capture
hashes. OPENED_ONCE and zero-repeat status are required. The current source
must match H1590's post-repair source hash. ASLR-dependent return addresses are
explicitly omitted from otherwise
retained C traces. Both full C traces and the complete named-stage records
are saved. Python syntax checks pass; replay into an independent temporary
directory reproduces the authoritative JSON **byte for byte**.

Authoritative artifacts, relative to `fsincos-re`:

- `experiments/h1592_independent_integer_spec.py`, SHA-256
  `0cc55ff4c0de1f957b30a5f48f5d63939ae22f2de99936f9bb41fe8543f80c82`.
- `tmp/ledger33/current/h1592_independent_integer_spec_v3/report.json`, SHA-256
  `9b986fe4baf377104feda7084129314e47d2be92bfa774cbea19592490674ed8`.
- Eight full normalized trace files and two comparator executables in that
  same directory; individual hashes are in the report.
- Compared canonical `src/fsincos_skylake.c`, SHA-256
  `de04d6543e06302c43d86198a0a8dd625110af8d6c1755c10de566e3c44562d1`.

The earlier `h1592_independent_integer_spec/report.json` and the v2 directory
are preserved as superseded preliminary audits. The first version's C
value-record history defaults were not observations; explicit
`history_comparison` records were added in v2 and carried forward to v3.
Version 3 adds the required input-evidence cross-checks. Historical H1590
pre-repair source and all
SAT/UNSAT/UNKNOWN artifacts remain unchanged. No newly observed failure or
frontier-count change is claimed by H1592.
