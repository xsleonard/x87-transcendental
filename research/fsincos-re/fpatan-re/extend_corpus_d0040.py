"""Append D0040 to the immutable input corpus and preserve the full seed pool."""
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil

from compressed_guard import digest, packed
from prepare import save
from protocol import parse_line

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'tmp/fpatan-re'


def main():
    corpus = HERE / 'corpus-v1'
    prior_path = corpus / 'CATALOG-D0036.json'
    prior_sha = digest(prior_path)
    prior = json.loads(prior_path.read_text())
    job = BASE / 'd0040'
    complete = json.loads((job / 'COMPLETE.json').read_text())
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert complete['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
    assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
    destination = corpus / 'extensions/d0040'
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / 'inputs.txt.gz'
    with target.open('xb') as output, (job / 'inputs.txt.gz').open('rb') as source:
        shutil.copyfileobj(source, output)
    packs = dict(prior['packs'])
    packs['d0040'] = dict(path=str(target.relative_to(corpus)), sha256=digest(target),
        source_manifest_sha256=digest(job / 'MANIFEST.json'))
    seen, total = set(), Counter()
    for name, pack in packs.items():
        path = corpus / pack['path']
        assert digest(path) == pack['sha256']
        counts = Counter()
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                key = packed(parse_line(line))
                assert key not in seen, 'Duplicate tuple across corpus packs'
                seen.add(key)
                fields = line.split()
                counts['rows'] += 1
                counts['rc:' + fields[1]] += 1
                counts['pc:' + fields[2]] += 1
        if name == 'd0040':
            assert counts['rows'] == complete['rows']
            pack['counts'] = counts
        else:
            assert counts == pack['counts']
        total.update(counts)
        print('Verified combined pack', name, counts['rows'], flush=True)
    assert total['rows'] == prior['counts']['rows'] + complete['rows']
    source_pool = BASE / 'd0039-correction-ties/candidate-pool.tsv'
    mining = json.loads((source_pool.parent / 'REPORT.json').read_text())
    assert digest(source_pool) == mining['pool_sha256']
    pool_path = destination / 'correction-halfway-input-pool.tsv.gz'
    rows = 0
    with source_pool.open() as source, gzip.open(pool_path, 'xt') as output:
        for line in source:
            fields = line.split()
            # Keep search identity and raw operands only; no internal state,
            # model endpoints, discriminator mask, or captured labels.
            output.write(' '.join([fields[0], *fields[5:9]]) + '\n')
            rows += 1
    assert rows == mining['verified_counts']['rows']
    pool = dict(path=str(pool_path.relative_to(corpus)), sha256=digest(pool_path), rows=rows,
        columns=['search_id', 'y_se', 'y_sig', 'x_se', 'x_sig'],
        status='CONSTRUCTION_INPUT_POOL_NOT_A_CAPTURE_PROTOCOL_PACK')
    save(destination / 'MANIFEST.json', dict(status='APPEND_ONLY_CPU_INDEPENDENT_INPUT_EXTENSION',
        format='fpatan-corpus-v1-extension', name='d0040', pack=packs['d0040'], pool=pool,
        captured_reference='guest-reported Skylake CPUID 00050654 / microcode 0x1',
        warning='Reuse saved observations on that context. Check per-host history and reserve fresh tuples before another CPU capture.',
        model_predictions_included=False, hardware_labels_included=False, private_data_included=False,
        new_hardware_executed=False))
    assert digest(prior_path) == prior_sha
    assert digest(corpus / 'MANIFEST.json') == prior['base_manifest_sha256']
    save(corpus / 'CATALOG-D0040.json', dict(format='fpatan-corpus-v1-additive-catalog',
        previous_catalog=dict(path=prior_path.name, sha256=prior_sha),
        base_manifest_sha256=prior['base_manifest_sha256'],
        extension_manifest_sha256=digest(destination / 'MANIFEST.json'),
        packs=packs, counts=total, exact_tuple_duplicates=0,
        previous_provisional_pool=prior['previous_provisional_pool'],
        extension_pools={**prior['extension_pools'], 'correction-halfway-input-pool.tsv.gz': pool},
        hardware_labels_included=False, private_data_included=False, builder_sha256=digest(Path(__file__))))
    print('PASS append-only corpus:', len(packs), 'packs;', total['rows'], 'unique tuples', flush=True)


if __name__ == '__main__':
    main()
