"""Algebraically invert inner-addition halfways without a bisection search.

Target T67(v*C) exactly, invert its multiplication interval, then invert
v=T67(u*u) using integer square roots. All accepted targets are replayed
through a separately written dyadic graph. Observable candidates receive
full Fraction replay and an exact external lift before being retained.
"""
import argparse
from collections import Counter
import json
from math import isqrt
from pathlib import Path
import random
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0037_polynomial_node_census import restored
from d0045_tie_observability import target_and_correction, replay_z, lift_at
from prepare import save

HERE = Path(__file__).resolve().parent
COEFFICIENTS = ((121, 123), (120, 122), (115, 117))


def dyad(value):
    return value.numerator, -(value.denominator.bit_length() - 1)


def fraction(value):
    return value[0] * audit.two(value[1])


ROM = {index: dyad(value) for index, value in audit.ROM.items()}


def add(a, b):
    step = min(a[1], b[1])
    return (a[0] << (a[1] - step)) + (b[0] << (b[1] - step)), step


def mul(a, b):
    return a[0] * b[0], a[1] + b[1]


def rounding(value, bits=67, nearest=False, flip=False):
    n, scale = value
    if not n:
        return 0, 0
    negative, magnitude = n < 0, abs(n)
    shift = magnitude.bit_length() - bits
    if shift <= 0:
        assert not flip
        return n << (-shift), scale + shift
    whole, remainder = magnitude >> shift, magnitude & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    increment = nearest and (remainder > half or (remainder == half and whole & 1))
    if flip:
        assert nearest and remainder == half
        increment = not (whole & 1)
    return (-1 if negative else 1) * (whole + int(increment)), scale + shift


def target_event(value):
    n, _ = value
    shift = abs(n).bit_length() - 64
    assert shift > 0 and abs(n) & ((1 << shift) - 1) == 1 << (shift - 1)
    return (abs(n) >> shift) & 1


def graph(node, u, flip=False):
    """Independent integer dyad implementation of the correction subgraph."""
    product = lambda a, b: rounding(mul(a, b))
    rn = lambda a, hit=False: rounding(a, 64, True, flip and hit)
    v = product(u, u)
    if node == 2:
        even = rounding(add(ROM[114], product(v, ROM[116])))
        target = add(ROM[115], product(v, ROM[117]))
        odd = rn(target, True)
        first_outer = odd
    else:
        odd_pre = add(ROM[121], product(v, ROM[123]))
        even_pre = add(ROM[120], product(v, ROM[122]))
        target = odd_pre if node == 0 else even_pre
        odd_inner, even_inner = rn(odd_pre, node == 0), rn(even_pre, node == 1)
        odd = rounding(add(ROM[119], product(v, odd_inner)))
        even = rounding(add(ROM[118], product(v, even_inner)))
        first_outer = odd if node == 0 else even
    return target, rn(add(product(u, odd), even)), first_outer


def ceil_sqrt(value):
    root = isqrt(value)
    return root + (root * root < value)


def domains(node, exponent):
    base_index, coefficient_index = COEFFICIENTS[node]
    bn, bs = ROM[base_index]
    kn, ks = ROM[coefficient_index]
    bn, kn = abs(bn), abs(kn)
    round_step = bn.bit_length() - 1 + bs - 63
    unit = min(bs, round_step - 1)
    modulus = 1 << (round_step - unit)
    residue = ((1 << (round_step - 1 - unit)) - (bn << (bs - unit))) % modulus
    u_low = 1 << 63
    u_high = 9 << 60 if exponent == -9 else (1 << 64) - 1
    result = []
    for ve in (2 * exponent, 2 * exponent + 1):
        square_drop = ve - 2 * exponent + 60
        low = max(1 << 66, (u_low * u_low) >> square_drop)
        high = min((1 << 67) - 1, (u_high * u_high) >> square_drop)
        if low > high:
            continue
        vs = ve - 66
        alignment = unit - vs - ks
        assert alignment > 0
        # Include the bounding grid points, then enforce exact interval and
        # u-domain conditions on every candidate; no endpoint is assumed.
        first = (low * kn) >> alignment
        last = ((high * kn) >> alignment) + 1
        first += (residue - first) % modulus
        count = (last - first) // modulus + 1
        if count > 0:
            result.append(dict(v_low=low, v_high=high, v_step=vs, drop=square_drop,
                coefficient=kn, coefficient_step=ks, unit=unit, first=first,
                modulus=modulus, count=count, u_low=u_low, u_high=u_high))
    return result


def invert_target(domain, target):
    d = domain
    alignment = d['unit'] - d['v_step'] - d['coefficient_step']
    low = target << alignment
    product_step = target.bit_length() - 1 + d['unit'] - 66
    discard = product_step - d['v_step'] - d['coefficient_step']
    assert discard >= 0
    high_exclusive = low + (1 << discard)
    first_v = max(d['v_low'], (low + d['coefficient'] - 1) // d['coefficient'])
    last_v = min(d['v_high'], (high_exclusive - 1) // d['coefficient'])
    if first_v > last_v:
        return range(0)
    first_u = max(d['u_low'], ceil_sqrt(first_v << d['drop']))
    last_u = min(d['u_high'], isqrt(((last_v + 1) << d['drop']) - 1))
    return range(first_u, last_u + 1)


def expose(node, exponent, um, index, parity, stream, counts, witnesses, rng):
    u = um * audit.two(exponent - 63)
    target, h = target_and_correction(node, u)
    same_target, other_h = target_and_correction(node, u, True)
    assert target == same_target and h != other_h
    root = isqrt(um << (69 + (exponent & 1)))
    step = exponent // 2 - 66
    for m in range(root - 16, root + 17):
        z = m * audit.two(step)
        if m.bit_length() != 67 or (node < 2 and z > audit.Q(3, 64)):
            continue
        if audit.N64(z * audit.T(z, 64)) != u:
            continue
        _, value, changed, checked_parity = replay_z(node, m, step)
        assert checked_parity == parity
        counts['square_preimages_after_H_change'] += 1
        cut_changed = audit.T(value, 67) != audit.T(changed, 67)
        counts['pre_anchor_cut_changed'] += cut_changed
        stream.write(f'Z {node} {index} {exponent} {um:016x} {parity} {m:x} {step} {int(cut_changed)}\n')
        if node == 2 and not cut_changed:
            continue
        for sign in ((1, -1) if node == 2 else (1,)):
            for cell in (range(2, 33) if node == 2 else (0,)):
                if cell:
                    c = audit.Q(cell, 32)
                    ratio = (c + sign * z) / (1 - c * sign * z)
                    if not audit.Q(3, 64) < ratio <= 1:
                        continue
                    q = 32 * ratio - audit.Q(1, 2)
                    if -((-q.numerator) // q.denominator) != cell:
                        continue
                state = dict(path='table' if cell else 'direct', cell=cell)
                fixed, other = restored(state, sign * value), restored(state, sign * changed)
                a, b = audit.endpoint_vector(fixed), audit.endpoint_vector(other)
                mask = sum((v != w) << i for i, (v, w) in enumerate(zip(a, b)))
                counts['cell_proposals'] += 1
                stream.write(f'W {node} {index} {exponent} {um:016x} {parity} {m:x} {step} {sign} {cell} {mask:04x}\n')
                if not mask:
                    continue
                counts['internal_endpoint_separators'] += 1
                found = lift_at(sign * z, cell, rng, 8192)
                witness = dict(node=node, search=index, square_exponent=exponent,
                    square_sig=f'{um:016x}', parity=parity, z_sig=f'{m:x}', z_step=step,
                    sign=sign, cell=cell, endpoint_mask=f'{mask:04x}')
                if found is None:
                    witness.update(status='EXTERNAL_LIFT_UNKNOWN', bounded_attempts=8192)
                    counts['external_lift_unknown'] += 1
                else:
                    y, x, actual, attempts = found
                    assert actual['z'] == sign * z and actual['cell'] == cell
                    assert fixed[0] == audit.SPEC['finite_angle'](y, x)
                    witness.update(status='EXACT_EXTERNAL_ENDPOINT_SEPARATOR', attempts=attempts,
                        raw=[f'{y.se:04x}', f'{y.sig:016x}', f'{x.se:04x}', f'{x.sig:016x}'])
                    counts['external_endpoint_separators'] += 1
                witnesses.append(witness)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, type=int, choices=(0, 1, 2))
    parser.add_argument('--searches', required=True, type=int)
    parser.add_argument('--exponent', required=True, type=int)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assert 0 < args.searches and args.exponent <= (-13 if args.node == 2 else -9)
    args.out.mkdir(exist_ok=False)
    names = ('d0049_algebraic_tie_preimages.py', 'd0045_tie_observability.py',
        'd0037_polynomial_node_census.py', 'd0031_internal_rounding_coverage.py',
        'PSEUDOCODE.md', 'fpatan_candidate.c')
    pins = {name: digest(HERE / name) for name in names}
    search_domains = domains(args.node, args.exponent)
    save(args.out / 'STARTED.json', dict(status='SOFTWARE_ALGEBRAIC_TIE_SEARCH',
        node=args.node, searches=args.searches, square_exponent=args.exponent,
        domains=search_domains, source_sha256=pins, hardware_executed=False))
    rng = random.Random(f'd0049-node{args.node}-e{args.exponent}-n{args.searches}')
    lift_rng = random.Random('d0049-cell-specific-lifts')
    counts, seen, witnesses = Counter(), set(), []
    started = time.monotonic()
    with (args.out / 'targets.tsv').open('x') as stream:
        for index in range(args.searches):
            d = search_domains[index % len(search_domains)]
            term = d['first'] + d['modulus'] * rng.randrange(d['count'])
            counts['target_searches'] += 1
            for um in invert_target(d, term):
                if um in seen:
                    counts['duplicate_square_targets'] += 1
                    continue
                seen.add(um)
                u = um, args.exponent - 63
                target, h, outer = graph(args.node, u)
                other_target, other_h, other_outer = graph(args.node, u, True)
                assert target == other_target
                parity = target_event(target)
                # Check the constructed product interval directly as well as
                # checking the target half in the independently built graph.
                base = ROM[COEFFICIENTS[args.node][0]]
                expected_magnitude = add((abs(base[0]), base[1]), (term, d['unit']))
                assert abs(fraction(target)) == fraction(expected_magnitude)
                changed = h != other_h
                counts['ties'] += 1
                counts[f'parity{parity}'] += 1
                counts['first_outer_changed'] += outer != other_outer
                counts['H_changed'] += changed
                stream.write(f'T {args.node} {index} {args.exponent} {um:016x} {parity} {int(changed)} {int(outer != other_outer)}\n')
                if changed or counts['ties'] % 4096 == 1:
                    full_target, full_h = target_and_correction(args.node, fraction(u))
                    _, full_other = target_and_correction(args.node, fraction(u), True)
                    assert fraction(target) == full_target
                    assert fraction(h) == full_h and fraction(other_h) == full_other
                    counts['full_fraction_crosschecks'] += 1
                if changed:
                    expose(args.node, args.exponent, um, index, parity, stream, counts, witnesses, lift_rng)
            if index % 262144 == 0:
                stream.flush()
                print('PROGRESS', args.node, index, dict(counts),
                      'seconds', round(time.monotonic() - started, 2), flush=True)
    assert all(digest(HERE / name) == sha for name, sha in pins.items())
    report = dict(status='VERIFIED_ALGEBRAIC_TIE_PREIMAGE_SEARCH', node=args.node,
        square_exponent=args.exponent, counts=counts, witnesses=witnesses,
        elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        target_sha256=digest(args.out / 'targets.tsv'), hardware_executed=False,
        numerical_model_changed=False, hardware_labels_opened=False,
        limits='Deterministically sampled target lattice, not exhaustive. Every accepted tie is checked by exact dyadic arithmetic; all changed-H states and endpoint witnesses receive full Fraction replay. Failed bounded external lifts are UNKNOWN.')
    save(args.out / 'REPORT.json', report)
    print('PASS', json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
