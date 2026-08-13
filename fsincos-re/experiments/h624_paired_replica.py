#!/usr/bin/env python3
"""h624: THE PAIRED-LANE FRAME SHIFT.

The paired FSINCOS cosine producer (legacy round18 path, exact
on general corpora) is a DIFFERENT dataflow from standalone:
  asq = chop67(r*r)
  q   = RN64-fused Horner: q_{k+1} = RN64(q_k*asq + C)
        over C6_6..C6_2, then q = RN64(chop67(q*asq) + C6_1)
  T   = chop67(q*asq);  result = round(1 - T) per mode.
Every historical "paired lane is flat/hidden" result used the
STANDALONE frame.  This script:
  1. replicates the paired producer exactly (verified against
     the C model's paired batch output on a sample);
  2. relabels the comb-7 paired cos-lane captures in the
     PAIRED frame: z' = d such that hw == refs'(T + d);
  3. census: exactness, deviation distribution, and whether
     deviations concentrate at the T-chop boundary (disc' near
     0 / all-ones) — the paired analog of the theta zone.
Usage: h624_paired_replica.py [verify|census]
"""
import subprocess
import sys
from collections import defaultdict
from multiprocessing import Pool
from h437_gate_extraction import ROUNDING_MODES, final_cosine_result
from h577_three_term import E2M
from h453_chain_variants import (C6_1, C6_2, C6_3, C6_4, C6_5,
                                 C6_6, mul_round)

CBIN = "/tmp/stageA/fsincos_skylake_r57"


def rn64(sign, I, scale):
    """RNE-64 of the exact value (-1)^sign * I * 2^scale,
    I > 0 integer.  Returns (sign, e2, sig64)."""
    sh = I.bit_length() - 64
    if sh <= 0:
        return (sign, scale + sh, I << -sh) if sh else \
            (sign, scale, I)
    top = I >> sh
    guard = (I >> (sh - 1)) & 1
    below = I & ((1 << (sh - 1)) - 1) if sh > 1 else 0
    if guard and (below or (top & 1)):
        top += 1
        if top >> 64:
            top >>= 1
            sh += 1
    return (sign, scale + sh, top)


def fma_c_rn64(a, c_add, b):
    """RN64(a*b + c_add); operands (sign, e2, sig)."""
    sa, ea, ma = a
    sb, eb, mb = b
    sc, ec, mc = c_add
    ep = ea + eb
    scale = min(ep, ec)
    I = (-1) ** (sa ^ sb) * (ma * mb << (ep - scale)) \
        + (-1) ** sc * (mc << (ec - scale))
    if I == 0:
        return (0, scale, 0)
    return rn64(1 if I < 0 else 0, abs(I), scale)


def paired_cos_T(m):
    """The paired producer's terminal: returns (T, ceT, rshp,
    discp) — the 67-bit tail significand, its lsb exponent, the
    final chop's shift and discarded field."""
    mag = (0, E2M, m)
    asq = mul_round(mag, mag, 67, "chop")
    q = C6_6
    for c_add in (C6_5, C6_4, C6_3, C6_2):
        q = fma_c_rn64(q, c_add, asq)
    qq = mul_round(q, asq, 67, "chop")
    q = fma_c_rn64((0, 0, 0) if qq[2] == 0 else qq, C6_1,
                   (0, 0, 1))
    # NOTE: fma with b = exact 1 implements RN64(qq + C6_1)
    full = q[2] * asq[2]
    rshp = full.bit_length() - 67
    discp = full & ((1 << rshp) - 1)
    T = full >> rshp
    ceT = q[1] + asq[1] + rshp
    sT = q[0] ^ asq[0]
    return T, ceT, rshp, discp, sT


def refsp(T, ceT, md):
    return final_cosine_result(-T, ceT, md)


def verify():
    ms = []
    n = 0
    for line in open("ties_comb7.txt"):
        n += 1
        if n % 9173:
            continue
        ms.append(int(line.split()[0], 16))
        if len(ms) >= 200:
            break
    inp = "".join(f"3ffc {m:016x}\n" for m in ms)
    PAIR = ("--round18-poly --round21-table-bias "
            "--round23-narrow-coefficient "
            "--round24-table-delta-rn67 --round29-p5-fmul-route "
            "--round30-fsin-cosine-square "
            "--round31-fsin-cosine-tail "
            "--round32-fsin-cosine-horner "
            "--round33-fsin-cosine-product "
            "--round34-table-lookup-firc "
            "--round35-table-p-terminal "
            "--round36-table-fadd-microcontrol "
            "--round37-p6-four-term --round41-fsin-cosine-split "
            "--round42-p6-sine-split --round43-p6-sine-bias "
            "--round44-p6-sine-bias --round45-p6-sine-fraction "
            "--round46-p6-narrow-sine-fraction "
            "--round47-p6-narrow-sine-fraction "
            "--round48-p6-narrow-sine-fraction "
            "--round49-p6-carrier-interval "
            "--round50-fsin-operation-classes "
            "--round51-fsin-fadd-signature "
            "--round40-fsincos-tiny "
            "--round53-fcos-operation-classes "
            "--round38-p6-cosine-split "
            "--round54-fsincos-table-lanes").split()
    ok = bad = 0
    for md in ROUNDING_MODES:
        args = [CBIN, "--batch"] + PAIR
        if md != "rn":
            args.append(f"--rc={md}")
        outs = subprocess.run(args, input=inp,
                              capture_output=True,
                              text=True).stdout.splitlines()
        for m, line in zip(ms, outs):
            t = line.split()
            if t[0] != "OK":
                continue
            chw = int(t[4], 16)
            T, ceT, rshp, discp, sT = paired_cos_T(m)
            ref = refsp(T, ceT, md)
            if ref == chw:
                ok += 1
            else:
                bad += 1
                if bad <= 5:
                    print(f"MISMATCH m={m:016x} md={md} "
                          f"model={chw:x} replica={ref:x} "
                          f"T={T:x} ceT={ceT}")
    print(f"verify: {ok} ok, {bad} mismatch")


def census_row(args):
    m, hw = args
    T, ceT, rshp, discp, sT = paired_cos_T(m)
    zs = [d for d in (-2, -1, 0, 1, 2)
          if [refsp(T + d, ceT, md)
              for md in ROUNDING_MODES] == hw]
    if not zs:
        return (m, None, rshp, 0)
    # boundary position of the paired chop
    top6 = int(discp >> max(rshp - 6, 0))
    return (m, tuple(zs), rshp, top6)


def census():
    seen = set()
    raw = []
    for line in open("ties_comb7.txt"):
        f = line.split()
        if f[0] in seen:
            continue
        seen.add(f[0])
        raw.append(f[0])
    inputs = sorted(raw)
    order = {w: i for i, w in enumerate(inputs)}
    st = {md: open(f"comb7_sc_{md}_status.txt").read()
          .splitlines() for md in ROUNDING_MODES}
    jobs = []
    n = 0
    for w in raw:
        n += 1
        if n % 8:
            continue
        i = order[w]
        hw = []
        okr = True
        for md in ROUNDING_MODES:
            t = st[md][i].split()
            if t[0] != "OK" or len(t) < 5:
                okr = False
                break
            hw.append(int(t[4], 16))
        if okr:
            jobs.append((int(w, 16), hw))
    print(f"census rows: {len(jobs)}", flush=True)
    with Pool(14) as pool:
        rs = pool.map(census_row, jobs, chunksize=200)
    zc = defaultdict(int)
    top6_by = defaultdict(lambda: defaultdict(int))
    for m, zs, rshp, top6 in rs:
        zc[zs] += 1
        if zs is not None:
            key = "exact0" if zs == (0,) else \
                ("has+1" if 1 in zs and 0 not in zs else
                 ("amb" if len(zs) > 1 else str(zs)))
            top6_by[key][top6 >> 3] += 1
    print("\nz-set census:", dict(sorted(zc.items(),
                                         key=str)))
    print("\ndisc'-top3 by class:")
    for k in sorted(top6_by, key=str):
        print(f"  {k}: {dict(sorted(top6_by[k].items()))}")


if __name__ == "__main__":
    if sys.argv[1] == "verify":
        verify()
    else:
        census()
