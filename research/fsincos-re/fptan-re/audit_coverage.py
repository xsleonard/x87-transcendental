"""Distinguish generated mathematical coverage from history-cleared coverage."""
from collections import Counter, defaultdict

from protocol import parse
from support import BASE, digest, lines, read, save


def main():
    source, job = BASE / 't0001-inputs', BASE / 't0002'
    frozen = read(job / 'INPUTS-FROZEN.json')
    assert digest(job / 'inputs.txt.gz') == frozen['input_sha256']
    pool = {}
    for line in lines(source / 'operand-pool.tsv.gz'):
        operand, family = line.rstrip().split('\t')
        pool[tuple(int(v, 16) for v in operand.split())] = family
    admitted, controls, counts = set(), defaultdict(set), Counter()
    for line in lines(job / 'inputs.txt.gz'):
        parse(line)
        _, rc, pc, se, sig = line.split()
        operand = int(se, 16), int(sig, 16)
        assert operand in pool
        admitted.add(operand)
        assert (rc, pc) not in controls[operand]
        controls[operand].add((rc, pc))
        counts['rows'] += 1
    assert counts['rows'] == frozen['counts']['rows']
    for operand in admitted:
        assert all((rc, '64') in controls[operand] for rc in ('rn', 'rd', 'ru', 'rz'))
        counts['admitted:' + pool[operand]] += 1
    windows = []
    for window in read(source / 'WINDOWS.json'):
        expected = {(window['se'] | sign, int(window['sig'], 16) + delta)
                    for sign in (0, 32768) for delta in range(-128, 129)}
        missing = expected - admitted
        windows.append(dict(**window, generated=len(expected), admitted=len(expected - missing),
            held=len(missing), complete=not missing))
    bracket_counts = Counter()
    for bracket in read(source / 'BRACKETS.json'):
        lower, upper = [tuple(int(v, 16) for v in bracket[name]) for name in ('below', 'above')]
        for sign in (0, 32768):
            bracket_counts['signed_brackets'] += 1
            bracket_counts['both_endpoints_admitted'] += all((se | sign, sig) in admitted for se, sig in (lower, upper))
    witness_counts = Counter()
    for path in sorted((source / 'queries').glob('*.json')):
        query = read(path)
        for witness in query['exact_witnesses']:
            for sign in (0, 32768):
                operand = (query['exponent'] + 16383) | sign, int(witness['n'], 16)
                witness_counts['signed_witness_instances'] += 1
                witness_counts['admitted_signed_witness_instances'] += operand in admitted
    fields = {se & 32767 for se, _ in admitted}
    counts.update(generated_operands=len(pool), admitted_operands=len(admitted),
        held_operands=len(pool) - len(admitted), normal_exponent_fields=len(fields),
        complete_signed_windows=sum(w['complete'] for w in windows))
    save(BASE / 'INPUT-COVERAGE-AUDIT.json', dict(status='PASS_CAPTURE_COVERAGE_ACCOUNTING',
        counts=counts, windows=windows, brackets=bracket_counts, witnesses=witness_counts,
        input_freeze_sha256=digest(job / 'INPUTS-FROZEN.json'),
        limits='History-held inputs receive no fresh-capture credit. Certificate and witness counts may share external operands.'))
    print(dict(counts), dict(bracket_counts), dict(witness_counts), flush=True)


if __name__ == '__main__':
    main()
