#!/usr/bin/env python3
"""Independent, first-principles audit of every claim in the Shirriff note.
No reliance on earlier TSVs or scripts: parse the article HTML directly."""
import re, html as H
from fractions import Fraction

htm = open('data/pentium-rom/righto-pentium-fpu-rom.html', encoding='utf-8', errors='replace').read()
text = re.sub(r'<[^>]+>', ' ', htm); text = H.unescape(text); text = re.sub(r'\s+', ' ', text)

# 1) extract rows 177-192 (all 16 trig entries) fresh from the article text
pat = re.compile(r'\b(1[78][0-9]|19[0-2]) (0fff[de]) ([01]) ([01]) ([0-9a-f]{17}) ([0-9.]+) (sin|cos)\((\d+)/64\)')
rows = {}
for m in pat.finditer(text):
    rows[int(m.group(1))] = dict(exp=int(m.group(2),16), sign=int(m.group(3)),
        sig=int(m.group(5),16), sightxt=m.group(5), dec=m.group(6),
        fn=m.group(7), num=int(m.group(8)))
assert len(rows) == 16, f"expected 16 trig rows, got {len(rows)}"

# 2) independent high-precision sin/cos via Taylor with exact rationals
PREC = 260
def series(t, is_cos):
    tot = Fraction(1) if is_cos else Fraction(t)
    term = tot; k = 1
    while abs(term) > Fraction(1, 2**(PREC+16)):
        term = -term * t * t / ((2*k-1)*(2*k)) if is_cos else -term * t * t / ((2*k)*(2*k+1))
        tot += term; k += 1
    return tot

# 3) decode formula (calibrated): value = sig * 2^(expfield - 0xFFFD - 68)
#    Cross-validated below against the article's own decimal column.
print("row  fn        printed-dec   hex-decodes-to  match?  hex-vs-true (2^-68 units)")
issues = []
for r in sorted(rows):
    d = rows[r]
    val = Fraction(d['sig']) * Fraction(2)**(d['exp'] - 0xFFFD - 68)
    if d['sign']: val = -val
    true = series(Fraction(d['num'], 64), d['fn'] == 'cos')
    # format decoded value to 10 decimals like the article
    dec10 = f"{float(val):.10f}"
    match = dec10 == d['dec']
    dev = float((val - true) * Fraction(2)**68)
    print(f"{r}  {d['fn']}({d['num']}/64)  {d['dec']}  {dec10}  "
          f"{'OK ' if match else 'MISMATCH'}  {dev:+.3f}")
    if abs(dev) > 2 or not match:
        issues.append((r, d, dev, match))

print("\n=== anomalies ===")
for r, d, dev, match in issues:
    print(f"row {r} {d['fn']}({d['num']}/64): hex deviates from true value by "
          f"{dev:+.1f} * 2^-68;  hex-vs-own-decimal consistent: {match}")
    # find the single power of two that reconciles hex with true
    delta = Fraction(d['sig']) * Fraction(2)**(d['exp']-0xFFFD-68) - series(Fraction(d['num'],64), d['fn']=='cos')
    k = round(float(delta).hex().count('') and 0) # placeholder
    import math
    lk = math.log2(abs(float(delta)))
    print(f"   deviation = 2^{lk:.6f} -> exactly a power of two? ", end="")
    kk = round(lk)
    exact = (delta == Fraction(2)**kk) or (delta == -Fraction(2)**kk)
    print(f"{'YES, 2^%d' % kk if exact else 'no'}")
    if exact:
        # corrected sig
        sig_fix = d['sig'] - (1 << (kk - (d['exp']-0xFFFD-68))) * (1 if delta > 0 else -1)
        cval = Fraction(sig_fix)*Fraction(2)**(d['exp']-0xFFFD-68)
        cdev = float((cval - series(Fraction(d['num'],64), d['fn']=='cos'))*Fraction(2)**68)
        print(f"   corrected sig = {sig_fix:017x}  (bit {kk-(d['exp']-0xFFFD-68)}); "
          f"corrected-vs-true = {cdev:+.3f} * 2^-68")
