# Errata for the published Pentium FPU constant ROM table

Source: Ken Shirriff, "Pi in the Pentium: reverse-engineering the constants
in its floating-point unit", righto.com, January 2025 — appendix table of
304 constants.  Saved copy: `../data/pentium-rom/righto-pentium-fpu-rom.html`.
Verification script: `../experiments/h26_errata_audit.py` (parses the
article HTML directly and checks every trig entry against exact-rational
cosines/sines; independently cross-checked against libm and Taylor series
at two precisions).

## The two errata

Two trigonometric table entries deviate from the true function values by
exactly one power of two in the significand, while the other fourteen trig
entries all sit within ±0.95 units of the last (68th) significand bit:

| row | label      | printed sig (hex)   | dev. from true | corrected sig       |
|-----|------------|---------------------|----------------|---------------------|
| 186 | cos(44/64) | `62ec41e9772401864` | +2^43 sig-units (+2^-24 in value) | `62ec4169772401864` |
| 189 | cos(18/64) | `7af8853ddbbe9ffd0` | +2^12 sig-units (+2^-55 in value) | `7af8853ddbbe9efd0` |

## Evidence

1. **Row 186 is checkable with a calculator.** The article's own decimal
   column prints `0.7728350058`, but cos(44/64) = cos(0.6875) =
   `0.7728349461…` — the printed value is wrong from the 7th decimal
   place.  (The decimal column is evidently derived from the hex, so hex
   and decimal are consistent with each other; both carry the deviation.)
2. **Row 189's deviation (+2^-55) is below the 10-digit display**, so its
   decimal column looks fine; the hex, however, is 2^12 significand units
   above the true value — ~4000× the deviation of every other trig entry.
3. **Modern Intel silicon matches the corrected values.**  We reconstructed
   the Skylake x87 FSINCOS bit-exactly (~99.4% of outputs in the table
   region, residual all 1-ulp): with the printed constants the
   reconstruction fails grossly in exactly the two affected table cells;
   with the corrected constants those cells behave like all others.
   Skylake's trig microcode constants demonstrably descend from the
   Pentium's (all other table entries and both polynomial families match
   through the reconstruction), so its behavior reflects the intended
   master values.
## Likely cause

A single-bit error in the ROM read-out or processing pipeline (the decimal
column, being derived from the hex, propagates it for row 186 and cannot
reveal it for row 189).  The alternative — that the Pentium die genuinely
holds these bits — would make P5's FCOS visibly inaccurate (error ~2^-24 ≈
6e-8) for arguments in [0.625, 0.75), which contradicts the accuracy
studies of the era; it is however directly testable by running an FCOS
capture on period hardware (a capture kit exists in `../capture-kit/`).
