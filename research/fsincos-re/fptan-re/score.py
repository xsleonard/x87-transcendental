"""Authenticate FPTAN observations, preserve all disagreements, package inputs."""
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json

from protocol import parse, validate_output
from support import BASE, HERE, ROOT, copy, digest, lines, read, save


def compare_prediction(request, actual, prediction):
    """Compare every field the numerical adapter promises, independently."""
    parse(request)
    ident, *encoded = prediction.split()
    assert ident == request.split()[0]
    expected = tuple(int(value, 16) for value in encoded)
    assert len(expected) == 6 and expected[4] in (0, 1) and expected[5] in (0, 1)
    observed = validate_output(actual, request)
    values = tuple(observed[name] for name in ('se', 'sig', 'pushed_se', 'pushed_sig', 'C2', 'C1'))
    differences = dict(result_misses=values[:2] != expected[:2],
        pushed_value_misses=values[2:4] != expected[2:4], C2_misses=values[4] != expected[4],
        C1_misses=values[5] != expected[5], union_misses=values != expected)
    return expected, observed, values, differences


def authenticate(name):
    job = BASE / name
    manifest, start, complete = (read(job / n) for n in ('MANIFEST.json', 'STARTED.json', 'COMPLETE.json'))
    assert complete['state'] == 'OBSERVED' and complete['ledger_integrity'] == 'ok'
    assert complete['rows'] == complete['reserved_rows'] == manifest['rows']
    assert complete['manifest_sha256'] == start['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert start['identity'].split()[1] == manifest['signature']
    assert start['microcode'] == [manifest['microcode']]
    assert complete['hardware_gzip_sha256'] == digest(job / 'hardware.txt.gz')
    assert (job / 'hardware.stderr').read_text() == f'COMPLETE {complete["rows"]}\n'
    assert digest(job / 'CLEARANCE.json') == manifest['clearance_sha256']
    clearance = read(job / 'CLEARANCE.json')
    assert clearance['status'] == 'CLEARED_COMMON_TWO_HOST_INPUTS'
    assert clearance['rows'] == manifest['rows']
    assert clearance['input_sha256'] == manifest['files']['inputs.txt.gz']
    preflight = read(job / 'C-PREFLIGHT.json')
    assert preflight['rows'] == manifest['rows']
    assert preflight['optimized_sanitized_differences'] == 0
    assert preflight['source_pins_sha256'] == digest(job / 'SOURCE-PINS.json')
    assert preflight['candidate_source_sha256'] == manifest['candidate_source_sha256']
    assert not preflight['exception_latch_prediction']
    for file, sha in preflight['binaries'].items():
        assert digest(file) == sha
    for file, sha in manifest['files'].items():
        assert digest(job / file) == sha
    for file, sha in read(job / 'SOURCE-PINS.json').items():
        assert digest(ROOT / file) == sha
        assert digest(BASE / 't0002/local-only-source-snapshot' / file) == sha
    frozen = read(job / 'INPUTS-FROZEN.json')
    assert frozen['status'] == 'FROZEN_BEFORE_CANDIDATE_PREDICTIONS'
    assert not frozen['candidate_evaluated_on_these_inputs']
    assert frozen['input_sha256'] == manifest['files']['inputs.txt.gz']
    assert frozen['category_sha256'] == manifest['files']['categories.tsv.gz']
    return job, manifest, complete


def run():
    contexts = [authenticate(name) for name in ('t0002', 't0003')]
    assert contexts[0][1]['files'] == contexts[1][1]['files']
    all_counts, groups = {}, {}
    for job, manifest, complete in contexts:
        counts, families, hashes, pcs = Counter(), defaultdict(Counter), hashlib.sha256(), defaultdict(dict)
        previous = None
        def flush_pc():
            for group in pcs.values():
                if len(group) == 3:
                    counts['complete_three_PC_groups'] += 1
                    counts['PC_value_or_status_differences'] += len(set(group.values())) != 1
            pcs.clear()
        with gzip.open(job / 'misses.jsonl.gz', 'xt') as misses:
            for request, actual, prediction, category in itertools.zip_longest(lines(job / 'inputs.txt.gz'), lines(job / 'hardware.txt.gz'), lines(job / 'predictions.txt.gz'), lines(job / 'categories.tsv.gz')):
                assert None not in (request, actual, prediction, category)
                fields = request.split()
                cid, family = category.rstrip().split('\t')
                assert cid == fields[0]
                expected, observed, values, disagreements = compare_prediction(request, actual, prediction)
                for counter in (counts, families[family], families['RC:' + fields[1]], families['PC:' + fields[2]]):
                    counter.update(rows=1, **disagreements)
                counts['C2_returns'] += observed['C2']
                counts['exception_word:' + f'{observed["after"] & 63:02x}'] += 1
                if values != expected:
                    misses.write(json.dumps(dict(input=request.strip(), family=family,
                        expected=expected, observed=observed)) + '\n')
                key = tuple(fields[3:])
                if key != previous:
                    flush_pc()
                    previous = key
                pcs[fields[1]][fields[2]] = (*values, observed['before'], observed['after'], observed['end'])
                hashes.update(actual.encode('ascii'))
        flush_pc()
        assert counts['rows'] == complete['rows'] and hashes.hexdigest() == complete['hardware_sha256']
        result = dict(status='NO_MISSES' if not counts['union_misses'] else 'MISSES_FOUND',
            counts=counts, groups=families, hardware_sha256=complete['hardware_sha256'],
            exception_latch_model_verification=False, full_status_captured=True,
            model_source_sha256=manifest['candidate_source_sha256'])
        save(job / 'SCORE.json', result)
        all_counts[job.name], groups[job.name] = counts, families
        print(job.name, dict(counts), flush=True)

    cross = Counter()
    for request, left, right in itertools.zip_longest(lines(contexts[0][0] / 'inputs.txt.gz'), lines(contexts[0][0] / 'hardware.txt.gz'), lines(contexts[1][0] / 'hardware.txt.gz')):
        assert None not in (request, left, right)
        a, b = validate_output(left, request), validate_output(right, request)
        cross['rows'] += 1
        for name in ('se', 'sig', 'pushed_se', 'pushed_sig', 'C1', 'C2', 'before', 'after', 'end'):
            cross[name + '_differences'] += a[name] != b[name]
        cross['exception_flag_differences'] += (a['after'] & 63) != (b['after'] & 63)
        cross['raw_stream_row_differences'] += left != right
    for path, sha in read(BASE / 't0002/PUBLICATION-PINS.json').items():
        assert digest(ROOT.parent / path) == sha
    corpus = HERE / 'corpus-v1'
    corpus.mkdir(exist_ok=False)
    copy(BASE / 't0002/inputs.txt.gz', corpus / 'inputs.txt.gz')
    copy(BASE / 't0002/categories.tsv.gz', corpus / 'categories.tsv.gz')
    seen, inventory = set(), Counter()
    for line in lines(corpus / 'inputs.txt.gz'):
        key = parse(line)
        assert key not in seen
        seen.add(key)
        fields = line.split()
        inventory['rows'] += 1
        inventory['rc:' + fields[1]] += 1
        inventory['pc:' + fields[2]] += 1
    assert inventory['rows'] == contexts[0][1]['rows']
    save(corpus / 'MANIFEST.json', dict(format='fptan-corpus-v1-masked-clear-depth1', counts=inventory,
        files={name: digest(corpus / name) for name in ('inputs.txt.gz', 'categories.tsv.gz')}, exact_tuple_duplicates=0,
        source_manifests={job.name: digest(job / 'MANIFEST.json') for job, _, _ in contexts},
        capture_contexts=['00050654:0x1', '000506e3:0xf0'],
        labels_included=False, predictions_included=False, private_data_included=False,
        warning='Already observed once on both recorded contexts. Reuse saved labels there; audit and reserve before capture on a new context.'))
    status = ('INDEPENDENT_CHALLENGE_FOUND_MISSES' if any(c['union_misses'] for c in all_counts.values())
              else 'NUMERICAL_PASS_WITH_CPU_CONTEXT_DIFFERENCES' if cross['raw_stream_row_differences']
              else 'PASS_TWO_CPU_INDEPENDENT_CHALLENGE')
    save(BASE / 'FINAL-VERIFICATION.json', dict(status=status,
        model_counts=all_counts, family_counts=groups, cross_cpu=cross, corpus_counts=inventory,
        construction_audit_sha256=digest(BASE / 'INPUT-CONSTRUCTION-AUDIT.json'),
        admitted_coverage_audit_sha256=digest(BASE / 'INPUT-COVERAGE-AUDIT.json'),
        corpus_manifest_sha256=digest(corpus / 'MANIFEST.json'), source_sha256=digest(HERE / 'score.py'),
        code_changed=False, paper_changed=False, exception_latch_model_verification=False,
        limits='Finite validation of tangent/pushed value/C1/C2 and stack transitions; full flags compared between CPUs, not predicted by the numerical model. No all-input or cross-generation proof.'))
    print('FINAL', dict(cross), dict(inventory), flush=True)


if __name__ == '__main__':
    run()
