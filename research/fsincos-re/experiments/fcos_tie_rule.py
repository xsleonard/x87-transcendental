#!/usr/bin/env python3
"""REFERENCE PREDICATE: the FCOS tie-gate rule (Phase C2 assembly,
2026-08-10).

fire (hardware terminal subtract loses its +1 carry; result R-1
instead of R) is predicted per exact-tie row from:
  dist, low3          -- stratum frame (h471)
  XT                  -- fourth power's below-chop tail, as a fraction
  XD                  -- right product's discarded field, as a fraction
  mf                  -- reduced operand m / 2^64 (64-bit normalized)
(all computable from m alone via the bit-exact replica: h500 build()).

Structure: piecewise-linear boundaries  fire <=> mf < c + s*XT,
tiled by XD zones with steps at 1/3 and 2/3 (h493's digit-selection
constants); the three mid-ladder dist=9 lines share one pivot
(XT=0, m0=0.707687) with 1/s arithmetic in low3, step 2.9257 (h508);
dist=7 boundaries are curved in XD and represented by per-twelfth
tangents.  Rows within band_w of a boundary, and the DECLARED regions
(schedule/arrangement-state dominant, h488/h491), are UNPREDICTED.

Hardware-blind validation (h518, shifted comb-4, 1,812,249 fresh
labeled rows, i7-6700 microcode 0xf0, locked before capture):
  predicted 1,403,005 rows -> 3,684 wrong (0.263%), of which
    dist=9 families:       0 wrong / ~281k   (EXACT outside band)
    dist=7 families:       0 wrong / ~57k    (EXACT outside band)
    dist=8 @ le2=-73:      0 wrong / ~125k   (EXACT outside band)
    (8,7) @ -72:           1 wrong / 61k
    (8,3) @ -72:         275 wrong (0.13%, within locked tolerance)
    (8,5) @ -72:         542 wrong (0.32%, over the 0.2% bar)
    (8,4)/(8,6) @ -72: ~1.4k wrong each (0.7%, over the bar)
  band 2.9% of rows, declared 19.7%, uncovered 0; replica exactness
  1 OTHER / 1.81M.  Paired-FSINCOS lane: NO m-law exists (h518b:
  ~44-47% fire, no line beats never-fire in any stratum).

Windows covered: m-fraction [0.656, 0.938) of the canonical binade
(le2 -73/-72).  The neighboring m-binade (~54% of original-corpus
ties) is NOT covered -- needs its own comb campaign.
"""

TW73_81 = {0: (0.33717, 0.63957), 1: (0.31898, 0.65565),
           2: (0.31898, 0.65565), 3: (0.39510, 0.58911),
           4: (0.36809, 0.61250), 5: (0.36055, 0.61987),
           6: (0.36055, 0.61987), 7: (0.34966, 0.62838)}
TW73_83 = {4: (0.12465, 0.85699), 5: (0.15678, 0.83706),
           6: (0.14644, 0.84353), 7: (0.16063, 0.83509),
           8: (0.15385, 0.83886), 9: (0.16972, 0.82932),
           10: (0.16704, 0.83082), 11: (0.15932, 0.83565)}
TW73_85 = {8: (0.09648, 0.89892), 9: (0.09978, 0.89790),
           10: (0.08949, 0.90163), 11: (0.09871, 0.89831)}
TW73_D8L1 = {0: (0.364029, 0.343320), 1: (0.362411, 0.344806),
             2: (0.353500, 0.352698), 3: (0.357498, 0.349299),
             4: (0.354904, 0.352109), 5: (0.361984, 0.345132),
             6: (0.364609, 0.342681), 7: (0.362320, 0.344699)}

PIVOT = 0.707687          # d9 mid-ladder common intercept (h508)


def _line(s, c, w, XT, mf):
    r = mf - s * XT - c
    if abs(r) < w:
        return "band", None
    return "line", (1 if r < 0 else 0)


TW1_93 = {0: (0.135574, 0.578116), 1: (0.137436, 0.577261),
          2: (0.132523, 0.579170), 3: (0.136948, 0.577521),
          4: (0.130203, 0.580224), 5: (0.121109, 0.583519),
          6: (0.131638, 0.579461), 7: (0.130081, 0.580214),
          8: (0.130295, 0.580311), 9: (0.121933, 0.582541),
          10: (0.127365, 0.581567), 11: (0.128860, 0.581055)}


def classify(dist, low3, XT, XD, mf):
    """-> (kind, prediction).  kind 'line'/'never'/'always' carry a
    0/1 prediction; 'band'/'declared' are unpredicted; 'uncovered' is
    outside the validated windows."""
    tw = min(11, int(XD * 12))
    if dist == 10 and 0.500 <= mf < 0.656:       # W1 (h520/h522)
        if low3 in (2, 3):
            return "never", 0
        if low3 in (4, 5, 6, 7):
            return "always", 1
    if dist == 9 and 0.500 <= mf < 0.656:        # W1 (h520/h522)
        if low3 == 1:
            return "never", 0
        if low3 == 2:
            if XD < 1/3:
                return "never", 0
            return "declared", None              # ~9% mixing on line
        if low3 == 3:
            s, c = TW1_93[tw]
            return _line(s, c, 0.005, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return _line(0.0980, 0.61265, 0.004, XT, mf)
            return "always", 1
        if low3 in (5, 6, 7):
            return "always", 1
    if dist == 9 and 0.656 <= mf < 0.938:
        if low3 == 1:
            return "never", 0
        if low3 == 2:
            if XD >= 1/3 and mf - 0.25 * XT < 0.475:
                return "declared", None
            return "never", 0
        if low3 == 3:
            return _line(0.125, 0.58325, 0.003, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return _line(0.0833, 0.6186, 0.006, XT, mf)
            return _line(0.084106, PIVOT, 0.003, XT, mf)
        if low3 == 5:
            return _line(0.067505, PIVOT, 0.003, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return _line(0.056366, PIVOT, 0.003, XT, mf)
            return _line(0.053818, 0.763793, 0.003, XT, mf)
        if low3 == 7:
            return _line(0.046380, 0.756040, 0.003, XT, mf)
    if dist == 8 and 0.656 <= mf < 0.781:            # le2=-73
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            s, c = TW73_D8L1[tw]
            return _line(s, c, 0.004, XT, mf)
        if low3 == 2:
            if XD < 1/3:
                return _line(0.1805, 0.5265, 0.004, XT, mf)
            return "always", 1
        return "always", 1
    if dist == 8 and 0.781 <= mf < 0.938:            # le2=-72
        if low3 == 1:
            return "declared", None
        if low3 == 2:
            if XD < 1/3:
                return "never", 0
            return "declared", None
        if low3 == 3:
            if XD < 2/3:
                return _line(0.10332, 0.71321, 0.003, XT, mf)
            return _line(0.1950, 0.8155, 0.006, XT, mf)
        if low3 == 4:
            if XD < 1/3:
                return _line(0.0755, 0.7148, 0.008, XT, mf)
            return _line(0.0714, 0.79190, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                k, p = _line(0.0619, 0.7750, 0.003, XT, mf)
                if k == "line" and p == 0:
                    r = mf - 0.0619 * XT - 0.7750
                    if 0.004 <= r <= 0.05:
                        return "declared", None      # echo stripe
                return k, p
            return _line(0.0510, 0.8285, 0.012, XT, mf)
        if low3 == 6:
            if XD < 1/3:
                return _line(0.05141, 0.76507, 0.003, XT, mf)
            return _line(0.0977, 0.8163, 0.005, XT, mf)
        if low3 == 7:
            if XD < 2/3:
                return _line(0.04320, 0.80194, 0.003, XT, mf)
            return _line(0.08009, 0.84601, 0.003, XT, mf)
    if dist == 7 and 0.938 <= mf < 1.0:          # W2 (h523)
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            return _line(0.4030, 0.5900, 0.005, XT, mf)
        if low3 == 3:
            if XD < 1/3:
                return "never", 0
            return _line(0.17175, 0.82850, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                return "never", 0
            return _line(0.10305, 0.89730, 0.004, XT, mf)
        if low3 == 7:
            return "never", 0
    if dist == 7 and 0.781 <= mf < 0.938:
        if low3 == 1:
            if XD >= 2/3:
                return "always", 1
            s, c = TW73_81[tw]
            return _line(s, c, 0.004, XT, mf)
        if low3 == 3:
            if XD < 1/3:
                return "never", 0
            s, c = TW73_83[tw]
            return _line(s, c, 0.004, XT, mf)
        if low3 == 5:
            if XD < 2/3:
                return "never", 0
            s, c = TW73_85[tw]
            return _line(s, c, 0.004, XT, mf)
        if low3 == 7:
            return "never", 0
    return "uncovered", None
