"""Pin and score D0023's local-only, pre-observation index alternatives.

No capture is performed here. Every observation is read from its authenticated
immutable artifact; no alternate prediction is recomputed after opening it.
"""
import argparse
import collections
import gzip
import hashlib
import itertools
import json
from pathlib import Path

from compressed_guard import digest
from d0010_causal_intervals import BASE
from prepare import save
from protocol import validate_output


def authenticated(job):
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    hypotheses = json.loads((job / 'INDEX-HYPOTHESES.json').read_text())
    assert digest(job / 'MANIFEST.json') == hypotheses['manifest_sha256']
    assert digest(job / 'index-alternatives.jsonl.gz') == hypotheses['alternatives_sha256']
    for name, sha in manifest['files'].items():
        assert digest(job / name) == sha
    for name, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / name) == sha
    assert hypotheses['rows'] == manifest['rows']
    return manifest, hypotheses


def pin(job):
    for name in ('DISPATCHED.json', 'STARTED.json', 'COMPLETE.json', 'hardware.txt.gz'):
        assert not (job / name).exists(), 'Cannot claim a pre-dispatch pin after dispatch'
    manifest, hypotheses = authenticated(job)
    count = 0
    signatures = collections.Counter()
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'predictions.txt.gz', 'rt') as primary, \
         gzip.open(job / 'index-alternatives.jsonl.gz', 'rt') as alternatives:
        for i, p, a in itertools.zip_longest(inputs, primary, alternatives):
            assert None not in (i, p, a)
            record = json.loads(a)
            assert record['input'] == i.strip()
            assert set(record['expected']) == set(hypotheses['hypotheses'])
            assert p.split()[0] == i.split()[0]
            expected = [int(v, 16) for v in p.split()[1:]]
            assert record['expected']['lower'] == expected
            signature = '|'.join(r for r in hypotheses['hypotheses'][1:]
                                 if record['expected'][r] != expected)
            signatures[signature or 'all-agree'] += 1
            count += 1
    assert count == manifest['rows']
    assert dict(signatures) == hypotheses['signature_counts']
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(
        status='FROZEN_ALTERNATIVES_PINNED_BEFORE_DISPATCH', rows=count,
        manifest_sha256=digest(job / 'MANIFEST.json'),
        index_hypotheses_sha256=digest(job / 'INDEX-HYPOTHESES.json'),
        alternatives_sha256=digest(job / 'index-alternatives.jsonl.gz'),
        scorer_sha256=digest(Path(__file__)),
        limitation='Lower, odd and reciprocal-chop67 are endpoint aliases on this bank.',
        hardware_executed=False, hardware_labels_opened=False))
    print('Pinned authenticated alternatives:', count, 'rows', flush=True)


def score(job):
    manifest, hypotheses = authenticated(job)
    structural = json.loads((job / 'STRUCTURAL-HYPOTHESIS.json').read_text())
    dispatch = json.loads((job / 'DISPATCHED.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    assert dispatch['structural_hypothesis_sha256'] == digest(job / 'STRUCTURAL-HYPOTHESIS.json')
    assert structural['index_hypotheses_sha256'] == digest(job / 'INDEX-HYPOTHESES.json')
    assert structural['alternatives_sha256'] == digest(job / 'index-alternatives.jsonl.gz')
    assert structural['scorer_sha256'] == digest(Path(__file__))
    assert complete['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert complete['hardware_gzip_sha256'] == digest(job / 'hardware.txt.gz')
    counters = {r: collections.Counter() for r in hypotheses['hypotheses']}
    groups = collections.defaultdict(lambda: {r: collections.Counter() for r in counters})
    rawhash = hashlib.sha256()
    count = 0
    with gzip.open(job / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(job / 'hardware.txt.gz', 'rt') as hardware, \
         gzip.open(job / 'categories.tsv.gz', 'rt') as categories, \
         gzip.open(job / 'index-alternatives.jsonl.gz', 'rt') as alternatives, \
         gzip.open(job / 'index-alternative-misses.jsonl.gz', 'xt') as misses:
        for i, h, c, a in itertools.zip_longest(inputs, hardware, categories, alternatives):
            assert None not in (i, h, c, a)
            rawhash.update(h.encode('ascii'))
            record = json.loads(a)
            assert record['input'] == i.strip()
            ident, category = c.rstrip().split('\t')
            assert ident == i.split()[0]
            observed = validate_output(h, i)
            actual = [observed['se'], observed['sig'], observed['C1'],
                      observed['sw'] & 63, observed['before'] & 63]
            failed = {}
            for rule, expected in record['expected'].items():
                differences = dict(output_misses=expected[:2] != actual[:2],
                                   C1_misses=expected[2] != actual[2],
                                   exception_misses=expected[3] != actual[3],
                                   before_misses=expected[4] != actual[4],
                                   any_misses=expected != actual)
                for counter in (counters[rule], groups[category][rule]):
                    counter['rows'] += 1
                    counter.update(differences)
                if expected != actual:
                    failed[rule] = expected
            if failed:
                misses.write(json.dumps(dict(input=i.strip(), category=category,
                                             observed=actual, failed=failed,
                                             dispatched_index=record['dispatched_index'])) + '\n')
            count += 1
    assert count == manifest['rows'] == complete['rows']
    assert rawhash.hexdigest() == complete['hardware_sha256']
    save(job / 'INDEX-SCORE.json', dict(
        status='FROZEN_PROSPECTIVE_ALTERNATIVES_SCORED', rows=count,
        counts=counters, groups=groups,
        survivors=[r for r, counter in counters.items() if not counter['any_misses']],
        structural_hypothesis_sha256=digest(job / 'STRUCTURAL-HYPOTHESIS.json'),
        hardware_sha256=complete['hardware_sha256'],
        predictions_frozen_before_capture=True, numerical_model_promoted=False,
        hardware_executed=False))
    print(json.dumps(counters, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=('pin', 'score'))
    args = parser.parse_args()
    globals()[args.step](BASE / 'd0023')
