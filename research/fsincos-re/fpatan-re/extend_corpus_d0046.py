"""Append confirmed-capture tie discriminators to the immutable input corpus."""
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
    previous_path = corpus / 'CATALOG-D0042.json'
    previous = json.loads(previous_path.read_text())
    old_hash = digest(previous_path)
    job = BASE / 'd0046'
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    assert complete['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
    output = corpus / 'extensions/d0046'
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'inputs.txt.gz').open('xb') as target, (job / 'inputs.txt.gz').open('rb') as source:
        shutil.copyfileobj(source, target)
    packs = dict(previous['packs'])
    packs['d0046'] = dict(path='extensions/d0046/inputs.txt.gz',
        sha256=digest(output / 'inputs.txt.gz'), source_manifest_sha256=digest(job / 'MANIFEST.json'))
    seen, total = set(), Counter()
    for name, pack in packs.items():
        path = corpus / pack['path']
        assert digest(path) == pack['sha256']
        counts = Counter()
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                key = packed(parse_line(line))
                assert key not in seen
                seen.add(key)
                fields = line.split()
                counts['rows'] += 1
                counts['rc:' + fields[1]] += 1
                counts['pc:' + fields[2]] += 1
        if name == 'd0046':
            assert counts['rows'] == complete['rows']
            pack['counts'] = counts
        else:
            assert counts == pack['counts']
        total.update(counts)
        print('Verified corpus pack', name, counts['rows'], flush=True)
    assert total['rows'] == previous['counts']['rows'] + complete['rows']
    mining_path = BASE / 'd0045-node3-upper/REPORT.json'
    mining = json.loads(mining_path.read_text())
    pool_path = output / 'visible-correction-tie-input-pool.tsv.gz'
    rows = 0
    with gzip.open(pool_path, 'xt') as target:
        for witness in mining['witnesses']:
            if witness['status'] != 'EXACT_EXTERNAL_ENDPOINT_SEPARATOR':
                continue
            fields = [str(witness[name]) for name in ('node', 'search', 'cell', 'sign')]
            target.write(' '.join(fields + witness['raw']) + '\n')
            rows += 1
    assert rows == mining['counts']['external_endpoint_separators'] == 76
    pool = dict(path=str(pool_path.relative_to(corpus)), sha256=digest(pool_path), rows=rows,
        columns=['node', 'search', 'cell', 'residual_sign', 'y_se', 'y_sig', 'x_se', 'x_sig'],
        status='CONSTRUCTION_INPUT_POOL_NOT_A_CAPTURE_PROTOCOL_PACK')
    save(output / 'MANIFEST.json', dict(status='APPEND_ONLY_CPU_INDEPENDENT_INPUT_EXTENSION',
        name='d0046', pack=packs['d0046'], pool=pool,
        warning='Already observed on the recorded Skylake context; reuse its labels. Audit the destination history before any other-context capture.',
        model_predictions_included=False, hardware_labels_included=False, private_data_included=False))
    assert digest(previous_path) == old_hash
    assert digest(corpus / 'MANIFEST.json') == previous['base_manifest_sha256']
    save(corpus / 'CATALOG-D0046.json', dict(format='fpatan-corpus-v1-additive-catalog',
        previous_catalog=dict(path=previous_path.name, sha256=old_hash),
        base_manifest_sha256=previous['base_manifest_sha256'],
        extension_manifest_sha256=digest(output / 'MANIFEST.json'), packs=packs, counts=total,
        exact_tuple_duplicates=0, previous_provisional_pool=previous['previous_provisional_pool'],
        extension_pools={**previous['extension_pools'], pool_path.name: pool},
        hardware_labels_included=False, private_data_included=False,
        builder_sha256=digest(Path(__file__))))
    print('PASS corpus', total['rows'], 'unique tuples across', len(packs), 'packs', flush=True)


if __name__ == '__main__':
    main()
