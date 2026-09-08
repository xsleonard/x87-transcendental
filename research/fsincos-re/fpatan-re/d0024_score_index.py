"""D0024 pre-dispatch pin and reuse of the immutable D0023 scoring logic."""
import argparse
import collections
import gzip
import itertools
import json
from pathlib import Path

from compressed_guard import digest
from d0010_causal_intervals import BASE
from d0023_score_index import authenticated, score
from prepare import save


def pin(job):
    for name in ('DISPATCHED.json', 'STARTED.json', 'COMPLETE.json', 'hardware.txt.gz'):
        assert not (job / name).exists()
    manifest, hypotheses = authenticated(job)
    count = 0
    signatures = collections.Counter()
    different = set()
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
            differs = [r for r in hypotheses['hypotheses'][1:] if record['expected'][r] != expected]
            different.update(differs)
            signatures['|'.join(differs) or 'all-agree'] += 1
            count += 1
    assert count == manifest['rows']
    assert dict(signatures) == hypotheses['signature_counts']
    save(job / 'STRUCTURAL-HYPOTHESIS.json', dict(
        status='FROZEN_ALTERNATIVES_PINNED_BEFORE_DISPATCH', rows=count,
        manifest_sha256=digest(job / 'MANIFEST.json'),
        index_hypotheses_sha256=digest(job / 'INDEX-HYPOTHESES.json'),
        alternatives_sha256=digest(job / 'index-alternatives.jsonl.gz'),
        scorer_sha256=digest(Path(__file__).with_name('d0023_score_index.py')),
        pin_script_sha256=digest(Path(__file__)),
        endpoint_aliases_to_lower=[r for r in hypotheses['hypotheses'][1:] if r not in different],
        hardware_executed=False, hardware_labels_opened=False))
    print('Pinned authenticated alternatives:', count, 'rows', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=('pin', 'score'))
    args = parser.parse_args()
    globals()[args.step](BASE / 'd0024')
