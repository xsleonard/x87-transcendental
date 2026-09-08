"""Append a new CPU-independent input pack without rewriting corpus v1.

The base manifest and its fifteen packs remain byte-identical. This creates
an exclusive extension directory and a new additive catalog. No hardware
labels, output predictions or private ledger data enter the corpus package.
"""
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
    manifest_path = corpus / 'MANIFEST.json'
    initial_hash = digest(manifest_path)
    original = json.loads(manifest_path.read_text())
    job = BASE / 'd0036'
    completed = json.loads((job / 'COMPLETE.json').read_text())
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    assert completed['state'] == 'OBSERVED'
    assert digest(job / 'MANIFEST.json') == completed['manifest_sha256']
    assert digest(job / 'inputs.txt.gz') == manifest['files']['inputs.txt.gz']
    destination = corpus / 'extensions/d0036'
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / 'inputs.txt.gz'
    with target.open('xb') as output, (job / 'inputs.txt.gz').open('rb') as source:
        shutil.copyfileobj(source, output)
    packs = dict(original['packs'])
    packs['d0036'] = dict(path=str(target.relative_to(corpus)), sha256=digest(target),
                         source_manifest_sha256=digest(job / 'MANIFEST.json'))
    seen, total = set(), Counter()
    for name, pack in packs.items():
        path = corpus / pack['path']
        assert digest(path) == pack['sha256']
        counts = Counter()
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                key = packed(parse_line(line))
                assert key not in seen, 'Duplicate observation tuple in the combined corpus'
                seen.add(key)
                fields = line.split()
                counts['rows'] += 1
                counts['rc:' + fields[1]] += 1
                counts['pc:' + fields[2]] += 1
        if name == 'd0036':
            assert counts['rows'] == completed['rows']
            pack['counts'] = counts
        else:
            assert counts == pack['counts']
        total.update(counts)
        print('Verified combined pack', name, counts['rows'], flush=True)
    assert total['rows'] == original['counts']['rows'] + completed['rows']
    pools = {}
    for name, source_path, columns in (
        ('quadrant-boundary-input-pool.tsv.gz', BASE / 'd0034-quadrant-boundaries/seeds.tsv', 9),
        ('nonzero-cut-history-input-pool.tsv.gz', BASE / 'd0035-cut-history-groups/candidate-pool.tsv', 8)):
        path = destination / name
        # Strip model endpoints and retained-state traces; keep only public
        # construction parameters and exact raw operands for future use.
        with source_path.open() as source, gzip.open(path, 'xt') as output:
            for line in source:
                output.write(' '.join(line.split()[:columns]) + '\n')
        pools[name] = dict(path=str(path.relative_to(corpus)), sha256=digest(path),
                          status='CONSTRUCTION_POOL_NOT_A_CAPTURE_PROTOCOL_PACK')
    save(destination / 'MANIFEST.json', dict(status='APPEND_ONLY_CPU_INDEPENDENT_INPUT_EXTENSION',
        format='fpatan-corpus-v1-extension', name='d0036', pack=packs['d0036'], pools=pools,
        captured_reference='guest-reported Skylake CPUID 00050654 / microcode 0x1',
        warning='Reuse saved observations on that context. Check per-host history and reserve fresh tuples before any future CPU capture.',
        model_predictions_included=False, hardware_labels_included=False,
        private_data_included=False, new_hardware_executed=False))
    assert digest(manifest_path) == initial_hash
    save(corpus / 'CATALOG-D0036.json', dict(format='fpatan-corpus-v1-additive-catalog',
        base_manifest_sha256=initial_hash,
        extension_manifest_sha256=digest(destination / 'MANIFEST.json'),
        packs=packs, counts=total, exact_tuple_duplicates=0,
        previous_provisional_pool=original['provisional_pool'], extension_pools=pools,
        hardware_labels_included=False, private_data_included=False,
        builder_sha256=digest(Path(__file__))))
    print('PASS append-only corpus:', len(packs), 'packs;', total['rows'], 'unique tuples; base unchanged.', flush=True)


if __name__ == '__main__':
    main()
