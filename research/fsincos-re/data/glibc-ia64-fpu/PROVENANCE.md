# Provenance

Files copied verbatim from the glibc git mirror:

- Repo: https://github.com/bminor/glibc (mirror of sourceware glibc.git)
- Tag: `glibc-2.38`, commit `36f2487f13e3540be9ee0fb51876b1da72176d3f`
- Path: `sysdeps/ia64/fpu/`
- Copied 2026-07-14.

Note: the ia64 port was **removed** from glibc in 2.39 (2024) — these files do
not exist on master. glibc-2.38 is the last release carrying them.

Authorship: Intel Corporation (BSD-style license in each file header,
"Copyright (c) 2000 - 2004, Intel Corporation ... Intel Corporation is the
author of this code"). The problem-report URL in the headers
(`http://www.intel.com/software/products/opensource/libraries/num.htm`) is the
dead "Intel assembly source" link from the original research — i.e. this IS
the lost source, preserved via Intel's contribution to glibc.

## Files

- `s_cosl.S` — `.file "sincosl.s"`; combined `sinl`/`cosl` in double-extended.
  Contains the complete algorithm description (Steps 0–10) and ALL constant
  tables (reduction pieces P_0..P_3/d_1/d_2, kernel coefficients
  PP_1_hi/PP_1_lo/PP_2..PP_8, QQ_1..QQ_8, S_1..S_5, C_1..C_5, thresholds).
  The header comments explicitly describe this as the FSIN/FCOS computation —
  the Itanium IA-32-compat implementation lineage verified in Harrison's
  FMCAD 2000 paper.
- `libm_sincosl.S` — combined two-output `sincosl` (the FSINCOS analog).
- `libm_reduce.S` — `__libm_pi_by_2_reduce`, the Payne–Hanek-style reduction
  used for |x| ≥ 2^63 (libm behavior; real x87 FSIN instead sets C2 and
  leaves the operand unchanged there).
