#!/usr/bin/env python3
"""Debug cell 44: compare model S4/C4/result vs exact sin/cos at high prec."""
from fractions import Fraction
SCR="/private/tmp/claude-501/-Users-steve-llm-coduo-binary-analysis/7d0d0788-22c7-4b55-8fbf-66cb5d3d5805/scratchpad"
PREC=200
def series_sin(t):
    tot=Fraction(0); term=t; k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        tot+=term; term=-term*t*t/((2*k)*(2*k+1)); k+=1
    return tot
def series_cos(t):
    tot=Fraction(0); term=Fraction(1); k=1
    while abs(term)>Fraction(1,2**(PREC+16)):
        tot+=term; term=-term*t*t/((2*k-1)*(2*k)); k+=1
    return tot
ROM={}
for line in open("/Users/steve/llm/coduo-binary-analysis/fsincos-re/data/pentium-rom/rom-constants.tsv"):
    p=line.rstrip("\n").split("\t")
    if p[0]=="row": continue
    ROM[int(p[0])]=(int(p[1],16),int(p[2]),int(p[4],16))
def romfrac(row):
    ef,s,sig=ROM[row]
    return ((-1)**s)*Fraction(sig)*Fraction(2)**((ef-0xFFFD)-68)
# exact poly evaluation (NO rounding) with ROM 4-term coefficients:
def S4_exact(a):
    p=romfrac(172)
    for row in (171,170,169):
        p=p*a*a+romfrac(row)
    return a+p*a*a*a
def C4_exact(a):
    q=romfrac(176)
    for row in (175,174,173):
        q=q*a*a+romfrac(row)
    return 1+q*a*a
# check poly accuracy across |a| range
print("4-term poly approx error vs |a| (in units of 2^-68):")
for anum in (1,4,8,12,16,20,24,28,31):
    a=Fraction(anum,512)   # up to ~0.06
    es=(S4_exact(a)-series_sin(a))*Fraction(2)**68
    ec=(C4_exact(a)-series_cos(a))*Fraction(2)**68
    print(f"  a={float(a):+.5f}: sinerr={float(es):+12.3f}  coserr={float(ec):+12.3f}")
print()
# same for 6-term polys rows 157-162/163-168 at cell-44-scale a AND the direct r
def S6_exact(a):
    p=romfrac(162)
    for row in (161,160,159,158,157):
        p=p*a*a+romfrac(row)
    return a+p*a*a*a
def C6_exact(a):
    q=romfrac(168)
    for row in (167,166,165,164,163):
        q=q*a*a+romfrac(row)
    return 1+q*a*a
print("6-term poly error at a=1/16, and at r=0.24:")
for a in (Fraction(1,16), Fraction(24,100)):
    es=(S6_exact(a)-series_sin(a))*Fraction(2)**68
    ec=(C6_exact(a)-series_cos(a))*Fraction(2)**68
    print(f"  a={float(a):.4f}: sinerr={float(es):+12.3f} coserr={float(ec):+12.3f}")
# check table entries vs true sin/cos(k/64), in 2^-68 units of the entry
print("\ntable entries vs true values (units of last ROM bit 2^-68-scale):")
GRID=[18,22,26,30,36,44,52,60]
SINROW={18:181,22:182,26:183,30:184,36:177,44:178,52:179,60:180}
COSROW={18:189,22:190,26:191,30:192,36:185,44:186,52:187,60:188}
for b in GRID:
    ts=romfrac(SINROW[b]); tc=romfrac(COSROW[b])
    strue=series_sin(Fraction(b,64)); ctrue=series_cos(Fraction(b,64))
    # entry ulp = 2^(exp-68): compute diff / 2^-68 normalized by entry exponent
    ds=(ts-strue)*Fraction(2)**68; dc=(tc-ctrue)*Fraction(2)**68
    print(f"  b={b}/64: sinT-true={float(ds):+10.3f}·2^-68  cosT-true={float(dc):+10.3f}·2^-68")
