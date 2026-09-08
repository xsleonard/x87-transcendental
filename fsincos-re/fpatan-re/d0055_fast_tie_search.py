"""Run and independently verify the analysis-only integer-dyadic miner.

All native-C target records remain immutable, including masked occurrences.
Only distinct changed-H squares are propagated/lifted. Neither raw target
occurrence counts nor overlapping software runs are called unique inputs.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import time

from compressed_guard import digest
import d0031_internal_rounding_coverage as audit
from d0045_tie_observability import target_and_correction
from d0049_algebraic_tie_preimages import domains, graph, fraction, target_event, expose
from prepare import save

HERE = Path(__file__).resolve().parent


def write_domains(path, choices):
    with path.open('x') as stream:
        stream.write(f'{len(choices)}\n')
        for d in choices:
            stream.write(f'{d["u_low"]:x} {d["u_high"]:x} {d["v_low"]:x} {d["v_high"]:x} '
                f'{d["v_step"]} {d["drop"]} {d["coefficient"]:x} {d["coefficient_step"]} '
                f'{d["unit"]} {d["first"]:x} {d["modulus"]:x} {d["count"]:x}\n')


def verify(directory, node, exponent, verify_all):
    counts, checks, propagation = Counter(), Counter(), Counter()
    carries, witnesses = set(), []
    rng = random.Random('d0055-distinct-carry-external-lifts')
    with (directory / 'targets.tsv').open() as source, (directory / 'propagation.tsv').open('x') as stream:
        for number, line in enumerate(source):
            fields = line.split()
            assert fields[0] == 'T' and int(fields[1]) == node and int(fields[3]) == exponent
            index, um = int(fields[2]), int(fields[4], 16)
            parity, changed, outer_changed = map(int, fields[5:8])
            counts['tie_occurrences'] += 1
            counts[f'parity{parity}'] += 1
            counts['first_outer_changed'] += outer_changed
            counts['H_changed'] += changed
            if verify_all or outer_changed or number % 4096 == 0:
                target, h, outer = graph(node, (um, exponent - 63))
                other_target, other, other_outer = graph(node, (um, exponent - 63), True)
                assert target == other_target and target_event(target) == parity
                assert (h != other, outer != other_outer) == (bool(changed), bool(outer_changed))
                checks['independent_dyadic_replays'] += 1
                if outer_changed:
                    t, fh = target_and_correction(node, um * audit.two(exponent - 63))
                    _, fo = target_and_correction(node, um * audit.two(exponent - 63), True)
                    assert (fraction(target), fraction(h), fraction(other)) == (t, fh, fo)
                    checks['full_fraction_replays'] += 1
            if changed:
                if um in carries:
                    checks['duplicate_changed_H_occurrences'] += 1
                    continue
                carries.add(um)
                expose(node, exponent, um, index, parity, stream, propagation, witnesses, rng)
    return dict(counts=counts, checks=checks, propagation=propagation,
                distinct_changed_H_squares=[f'{um:016x}' for um in sorted(carries)], witnesses=witnesses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--node', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--exponent', type=int, required=True)
    parser.add_argument('--searches', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--verify-all', action='store_true')
    args = parser.parse_args()
    assert args.exponent <= (-13 if args.node == 2 else -9) and 0 < args.searches < 1 << 64
    args.out.mkdir(exist_ok=False)
    names = ('d0055_fast_tie_search.py', 'd0055_fast_tie_miner.c', 'd0049_algebraic_tie_preimages.py',
        'd0045_tie_observability.py', 'd0037_polynomial_node_census.py',
        'd0031_internal_rounding_coverage.py', 'fpatan_candidate.c', 'PSEUDOCODE.md')
    pins = {name: digest(HERE / name) for name in names}
    choices = domains(args.node, args.exponent)
    domain_file = args.out / 'domains.txt'
    write_domains(domain_file, choices)
    command = [str(args.binary.resolve()), 'search', str(args.node), str(args.exponent),
               str(args.searches), str(domain_file.resolve())]
    started = time.monotonic()
    binary_sha = digest(args.binary)
    save(args.out / 'STARTED.json', dict(status='INTEGER_DYADIC_SOFTWARE_SEARCH', command=command,
        node=args.node, exponent=args.exponent, searches=args.searches, domains=choices,
        source_sha256=pins, binary_sha256=binary_sha, domain_sha256=digest(domain_file),
        verify_all=args.verify_all, hardware_executed=False))
    with (args.out / 'targets.tsv').open('x') as target, (args.out / 'miner.log').open('x') as log:
        process = subprocess.Popen(command, stdout=target, stderr=subprocess.PIPE, text=True)
        final = None
        for line in process.stderr:
            log.write(line)
            log.flush()
            print(line.rstrip(), flush=True)
            if line.startswith('{'):
                final = json.loads(line)
        code = process.wait()
        assert code == 0, (code, command)
    native_seconds = time.monotonic() - started
    assert final and final['target_searches'] == args.searches
    print('Independent arithmetic replay and distinct-carry propagation', flush=True)
    checked = verify(args.out, args.node, args.exponent, args.verify_all)
    assert all(final[key] == value for key, value in checked['counts'].items())
    assert digest(args.binary) == binary_sha
    assert all(digest(HERE / name) == sha for name, sha in pins.items())
    report = dict(status='VERIFIED_INTEGER_DYADIC_TIE_SEARCH', **checked,
        node=args.node, exponent=args.exponent, searches=args.searches,
        native_counts=final, native_seconds=native_seconds,
        elapsed_seconds=time.monotonic() - started, source_sha256=pins,
        binary_sha256=binary_sha, domain_sha256=digest(domain_file),
        target_sha256=digest(args.out / 'targets.tsv'), log_sha256=digest(args.out / 'miner.log'),
        propagation_sha256=digest(args.out / 'propagation.tsv'), verify_all=args.verify_all,
        hardware_executed=False, hardware_labels_opened=False, numerical_model_changed=False,
        limits='Sampled target lattice. Target counts are occurrences, not unique U inputs. Every changed outer/H state and all exposed candidates are independently replayed; other targets are all replayed only when verify_all is true. Bounded lift failure remains UNKNOWN.')
    save(args.out / 'REPORT.json', report)
    print('PASS', json.dumps(dict(native_counts=final, checks=checked['checks'],
        propagation=checked['propagation'], native_seconds=native_seconds)), flush=True)


if __name__ == '__main__':
    main()
