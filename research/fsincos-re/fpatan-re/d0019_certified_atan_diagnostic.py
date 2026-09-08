"""Certified math/P5-polynomial diagnostics on the saved direct frontier.

This does not propose correctly rounded atan as the FPATAN implementation.
Alternating rational Taylor sums enclose atan without a host math library.
Comparing atan of the exact ratio and of its C67 quotient distinguishes
quotient loss from subsequent polynomial/evaluation error on this bank only.
All hardware observations are reused; no capture or numerical default changes.
"""
import collections
import hashlib
import json
from d0010_causal_intervals import BASE, Interval, observation_interval
from graph_v5 import prevalue
from model import F, ROM, encode, exponent, pow2, value
from prepare import save


def atan_bounds(z, terms=24):
    assert 0 <= z < F(1, 2) and terms >= 1
    # For 0 < z < 1, successive alternating partial sums bracket atan(z).
    # Closed endpoints are conservative; no transcendental equality assumed.
    total = F(0)
    power = z
    for k in range(terms):
        total += (-1 if k & 1 else 1) * power / (2 * k + 1)
        power *= z * z
    other = total + (-1 if terms & 1 else 1) * power / (2 * terms + 1)
    return min(total, other), max(total, other)


def relation(bounds, target):
    lo, hi = bounds
    enclosing = Interval(lo, hi, True, True)
    if not enclosing.intersect(target).valid():
        return 'DISJOINT'
    if target.contains(lo) and target.contains(hi):
        return 'CONTAINED'
    return 'UNKNOWN'


def rounded_observation(bounds, negative, rc):
    lo, hi = bounds
    if negative:
        lo, hi = -hi, -lo
    a, b = encode(lo, rc), encode(hi, rc)
    if a != b:
        return None
    q = value(*a)
    c1a, c1b = int(abs(q) > abs(lo)), int(abs(q) > abs(hi))
    if c1a != c1b:
        return None
    return [*a, c1a]


def points():
    seen = set()
    selected = []
    for pair in json.loads((BASE / 'd0009-kernel-frontier.json').read_text())['pairs']:
        trace = {}
        prevalue(*pair['raw'], trace=trace)
        if trace['kind'] != 'direct' or trace['swap'] or pair['raw'][2] & 32768:
            continue
        band = observation_interval(pair['rows'])
        key = trace['z'], band
        if key in seen:
            continue
        seen.add(key)
        selected.append((pair, trace, band))
    return selected


def main():
    counts = collections.defaultdict(collections.Counter)
    results = []
    for pair, trace, band in points():
        z, ratio = trace['z'], trace['ratio']
        assert 0 < z <= ratio < F(3, 64)
        poly = z + sum(ROM[k] * z ** (2 * (k - 118) + 3) for k in range(118, 124))
        bounds = dict(atan_c67=atan_bounds(z), atan_ratio=atan_bounds(ratio),
                      exact_p5_polynomial=(poly, poly))
        output = {}
        for name, enclosure in bounds.items():
            state = relation(enclosure, band)
            counts[name][state] += 1
            observations = []
            for row in pair['rows']:
                got = rounded_observation(enclosure, bool(pair['raw'][0] & 32768), row['rc'])
                expected = [row['se'], row['sig'], row['C1']]
                if got is None:
                    counts[name]['unknown_rows'] += 1
                else:
                    counts[name]['certified_rows'] += 1
                    counts[name]['output_misses'] += got[:2] != expected[:2]
                    counts[name]['C1_misses'] += got[2] != expected[2]
                    counts[name]['union_misses'] += got != expected
                observations.append(dict(input=row['input'], predicted=got, observed=expected))
            output[name] = dict(bounds=[str(v) for v in enclosure], relation=state, observations=observations)
        # These offsets enclose all permitted hardware prevalues, rather
        # than fitting a chosen point inside an observed rounding interval.
        alo, ahi = bounds['atan_c67']
        ulp = pow2(exponent(z) - 63)
        tail_ulp = pow2(exponent(z - poly) - 66)
        offsets = {}
        for name, scale in (('output_ulp', ulp), ('tail_ulp', tail_ulp)):
            offsets[name] = [str((band.lo - ahi) / scale), str((band.hi - alo) / scale)]
        results.append(dict(raw=pair['raw'], z=str(z), exact_ratio=str(ratio),
                            hardware_interval=band.json(), variants=output,
                            hardware_minus_atan_c67=offsets,
                            p5_minus_atan_c67_output_ulp=[str((poly - ahi) / ulp), str((poly - alo) / ulp)]))
    path = BASE / 'd0009-kernel-frontier.json'
    report = dict(status='CERTIFIED_MATHEMATICAL_DIAGNOSTIC_NOT_A_SILICON_MODEL',
                  frontier_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  groups=len(results), taylor_terms=24, counts={k: dict(v) for k, v in counts.items()},
                  results=results, hardware_executed=False, numerical_model_promoted=False)
    save(BASE / 'd0019-certified-atan-diagnostic.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'groups', 'counts')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
