# Draft message to Ken Shirriff

**How to reach him:** Bluesky **@righto.com** (stated in the article itself:
"follow me on Bluesky (@righto.com)"; he notes he has left Twitter).
Alternatives: a comment on the article
(righto.com/2025/01/pentium-floating-point-ROM.html) or the contact email
on righto.com's About page.

Every factual claim below is machine-verified by
`fsincos-re/experiments/h26_errata_audit.py` (independent parse of the
article HTML + exact-rational trig, cross-checked against libm and Taylor
series at two working precisions) and by the silicon-capture reconstruction
described in `fsincos-re/notes/skylake-comparison.md`.  The row-186 claim
can be checked by hand with any calculator.

Suggested subject: *Two single-bit errata in the Pentium FPU ROM appendix
(cos 44/64 and cos 18/64)*

---

Hi Ken,

Your January 2025 Pentium FPU constant-ROM article became the key to a
reverse-engineering project of mine, and in the process I believe I found
two single-bit errors in the appendix's trig table that you may want to
correct.

**The simple one to check (row 186, cos(44/64)):** the appendix prints
significand `62ec41e9772401864` with decimal `0.7728350058`.  But
cos(44/64) = cos(0.6875) = `0.77283494615…` — the printed value is wrong
from the 7th decimal digit.  The deviation is exactly +2^43 in significand
units (one bit).  With bit 43 cleared, `62ec4169772401864`, the entry
lands within a fraction of a final-bit unit of the true cosine — like the
other fourteen trig entries.

**The subtle one (row 189, cos(18/64)):** printed `7af8853ddbbe9ffd0`
decodes to a value +2^12 significand units above the true cos(18/64) —
about 4000× the deviation of every other trig entry, though too small to
show in the 10-digit decimal column.  Corrected: `7af8853ddbbe9efd0`.

**Independent confirmation from silicon:** I've been reconstructing what
modern Intel CPUs compute for x87 FSINCOS, from bit-level captures on
Skylake under multiple rounding modes.  The reduction is the documented
66-bit-pi scheme — and the core turned out to be your Pentium algorithm:
the {18,22,26,30,36,44,52,60}/64 table, both the 4-term and the 6-term
polynomials (4-term for the 4/64-wide cells, 6-term for the 8/64-wide
cells and for |x| < 1/4 — which incidentally explains why the ROM stores
both variants), combined with the sin(a+b) identity in what behaves like a
single wide fused accumulation.  Built from your appendix constants, this
model reproduces Skylake's FSINCOS bit-for-bit on ~99% of a large input
sweep (all remaining differences are a single ulp) — but only with the two
corrections above; with the printed values it fails grossly in exactly
those two table cells.  So 2015 silicon still recognizably executes the
1993 constants you read off the die — and also serves as a witness for
what those two entries were meant to be.

Since the decimal column appears to be derived from the hex, a single-bit
slip in the read-out/processing pipeline would explain each; the
alternative — that the die really holds these bits — would have made the
original Pentium's FCOS noticeably inaccurate (~6e-8) for arguments in
[0.625, 0.75), which seems hard to reconcile with the accuracy studies of
the era.  If you still have the die photos handy, those two bits might be
worth a second look; I'd be curious either way.

Happy to share the reconstruction (portable C, capture data, experiment
log) if it's of interest.  And thanks for the ROM decode — none of this
would have been possible without it.

---

**Reviewer checklist for the sender (all verified):**
- [x] cos(0.6875) = 0.7728349461524715 (libm, and exact Taylor at two
      precisions agree to 40+ digits)
- [x] article hex row 186 decodes to 0.7728350057571… = printed decimal ✓,
      ≠ true cosine (deviation exactly 2^-24 + the entry's normal sub-ulp
      offset of +0.25·2^-68)
- [x] article hex row 189 decodes to true + 2^-55 (+8191.24·2^-68; normal
      entries: |dev| ≤ 0.95·2^-68)
- [x] corrected hexes decode to the true values within +0.25/−0.76·2^-68
- [x] silicon reconstruction: printed values → gross failure localized to
      cells 44 and 18; corrected values → those cells behave like all
      others (table region 33% → 0.6% mismatch in the step where the
      corrections landed, later 0.5%)
- [x] claims about "which polynomial where" and the fused combine are from
      falsification-tested experiments (notes/skylake-comparison.md)
