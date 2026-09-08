"""Locate and measure masking in authenticated algebraic-search witnesses.

Only completed software artifacts are read. Distances to a cut describe
these particular inputs, not a probability model or a reachability proof.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction, replay_z
from d0049_algebraic_tie_preimages import graph, fraction
from prepare import save


def stages(node, u, opposite):
    rom, chop, nearest = audit.ROM, audit.T, audit.N64
    fourth = chop(u * u, 67)

    def rn(value, target=False):
        if not target or not opposite:
            return nearest(value)
        event = audit.event(value, 64)
        assert event['relation'] == 'tie'
        step = audit.exponent(abs(value)) - 63
        magnitude = abs(value) / audit.two(step)
        whole = magnitude.numerator // magnitude.denominator
        return (-1 if value < 0 else 1) * (whole + int(not (whole & 1))) * audit.two(step)

    if node == 2:
        even = chop(rom[114] + chop(fourth * rom[116], 67), 67)
        target = rom[115] + chop(fourth * rom[117], 67)
        odd = rn(target, True)
        inner, outer = odd, odd
    else:
        a = rom[121] + chop(fourth * rom[123], 67)
        b = rom[120] + chop(fourth * rom[122], 67)
        oi, ei = rn(a, node == 0), rn(b, node == 1)
        target, inner = (a, oi) if node == 0 else (b, ei)
        odd = chop(rom[119] + chop(fourth * oi, 67), 67)
        even = chop(rom[118] + chop(fourth * ei, 67), 67)
        outer = odd if node == 0 else even
    weighted = chop(u * odd, 67)
    return dict(target=target, inner=inner, outer=outer, weighted=weighted,
                pre_H=weighted + even, H=nearest(weighted + even))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    results, pins = {}, {}
    for directory in args.directories:
        report_path = directory / 'REPORT.json'
        report = json.loads(report_path.read_text())
        rows = directory / 'targets.tsv'
        assert digest(rows) == report['target_sha256']
        pins[str(report_path)] = digest(report_path)
        pins[str(rows)] = digest(rows)
        counts, closest, selected = Counter(), [], []
        with rows.open() as stream:
            for line in stream:
                p = line.split()
                kind, node, e, um = p[0], int(p[1]), int(p[3]), int(p[4], 16)
                if kind == 'T':
                    counts['ties'] += 1
                    if not int(p[6] if node == 2 else p[7]):
                        continue
                    u = um * audit.two(e - 63)
                    a, b = stages(node, u, False), stages(node, u, True)
                    target, h = target_and_correction(node, u)
                    _, other_h = target_and_correction(node, u, True)
                    assert (a['target'], a['H'], b['H']) == (target, h, other_h)
                    assert (h != other_h) == bool(int(p[6]))
                    for stage in ('inner', 'outer', 'weighted', 'pre_H', 'H'):
                        counts['selected:' + stage + ':changed'] += a[stage] != b[stage]
                    selected.append(dict(node=node, square_exponent=e, square_sig=p[4],
                        parity=int(p[5]), changes={name: str(b[name] - a[name])
                        for name in ('inner', 'outer', 'weighted', 'pre_H', 'H')}))
                elif kind == 'Z':
                    z, value, other, parity = replay_z(node, int(p[6], 16), int(p[7]))
                    assert parity == int(p[5]) and value != other
                    step = audit.exponent(value) - 66
                    unit = audit.two(step)
                    scaled = value / unit
                    whole = scaled.numerator // scaled.denominator
                    distance = ((whole + 1) * unit - value if other > value
                                else value - whole * unit)
                    delta = abs(other - value)
                    changed = audit.T(value, 67) != audit.T(other, 67)
                    assert changed == bool(int(p[8]))
                    counts['residual_preimages'] += 1
                    counts['cut_changed'] += changed
                    closest.append(dict(node=node, square_exponent=e, square_sig=p[4],
                        parity=parity, z_sig=p[6], z_step=int(p[7]), cut_changed=changed,
                        delta_in_cut_ulps=str(delta / unit),
                        distance_in_cut_ulps=str(distance / unit),
                        distance_over_delta=str(distance / delta)))
        assert counts['ties'] == report['counts']['ties']
        closest.sort(key=lambda row: audit.Q(row['distance_over_delta']))
        results[directory.name] = dict(counts=counts, selected_states=selected,
            closest_cut_cases=closest[:12],
            selected_scope='All first-outer changes for long nodes; all changed-H states for short odd.')
    source = Path(__file__).resolve()
    for name in ('d0052_propagation_barriers.py', 'd0045_tie_observability.py',
                 'd0049_algebraic_tie_preimages.py', 'd0031_internal_rounding_coverage.py'):
        pins[str(source.with_name(name))] = digest(source.with_name(name))
    save(args.out, dict(status='EXACT_MASKING_STAGE_AUDIT', results=results,
        artifact_sha256=pins, hardware_executed=False, hardware_labels_opened=False,
        numerical_model_changed=False, goal_complete=False,
        limits='Exact propagation and boundary distances for saved witnesses only. No new rule identified; no claim of global masking, unreachability or statistical independence.'))
    print(json.dumps({name: dict(counts=r['counts'], closest=r['closest_cut_cases'][:1])
                      for name, r in results.items()}, indent=2), flush=True)


if __name__ == '__main__':
    main()
