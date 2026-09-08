"""Authenticate both native campaigns and append their shared input pack.

Disagreements are preserved and reported, never asserted away. Cross-CPU
equality is empirical for the captured contexts, not a generation claim.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import shutil

from compressed_guard import digest, packed, save
from protocol import parse_line, validate_output

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = HERE.parent / 'tmp/fpatan-re'


def authenticate(job, signature, microcode):
    manifest = json.loads((job / 'MANIFEST.json').read_text())
    complete = json.loads((job / 'COMPLETE.json').read_text())
    started = json.loads((job / 'STARTED.json').read_text())
    ledger = json.loads((job / 'LEDGER-AUDIT.json').read_text())
    assert complete['state'] == 'OBSERVED'
    assert complete['manifest_sha256'] == digest(job / 'MANIFEST.json')
    assert started['manifest_sha256'] == complete['manifest_sha256']
    assert started['identity'].split()[1] == signature and started['microcode'] == [microcode]
    assert digest(job / 'hardware.txt.gz') == complete['hardware_gzip_sha256']
    assert ledger['integrity'] == 'ok'
    assert [signature + ':' + microcode, job.name, 'OBSERVED', complete['rows']] in ledger['compressed_batches']
    for name, sha in manifest['files'].items():
        assert digest(job / name) == sha
    for name, sha in manifest['source_pins'].items():
        assert digest(job / 'sources' / name) == sha == digest(HERE / name)
    frozen = json.loads((job / 'INPUTS-FROZEN.json').read_text())
    assert frozen['status'] == 'INPUTS_FROZEN_BEFORE_CANDIDATE_IMPORT'
    assert frozen['model_loaded'] is False
    assert digest(job / 'INPUTS-FROZEN.json') == manifest['input_freeze_sha256']
    for name, sha in frozen['files'].items():
        assert digest(job / name) == sha
    for name in ('C-PREFLIGHT.json', 'C-SANITIZED-PREFLIGHT.json'):
        check = json.loads((job / name).read_text())
        assert check['rows'] == complete['rows'] and check['C_frozen_Python_differences'] == 0
        binary = Path('/private/tmp/fpatan-d0066-' + ('sanitized' if 'SANITIZED' in name else 'clang')) / 'fpatan'
        assert check['binary_sha256'] == digest(binary)
    assert complete['rows'] == manifest['rows'] == frozen['rows']
    return manifest, complete


def append_corpus(job, manifest):
    corpus = HERE / 'corpus-v1'
    old_path = corpus / 'CATALOG-D0063.json'
    old_hash = digest(old_path)
    old = json.loads(old_path.read_text())
    target = corpus / 'extensions/d0066'
    target.mkdir(exist_ok=False)
    with (target / 'inputs.txt.gz').open('xb') as dest, (job / 'inputs.txt.gz').open('rb') as source:
        shutil.copyfileobj(source, dest)
    packs = dict(old['packs'])
    packs['d0066'] = dict(path='extensions/d0066/inputs.txt.gz',
        sha256=digest(target / 'inputs.txt.gz'), source_manifest_sha256=digest(job / 'MANIFEST.json'))
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
        if name == 'd0066':
            assert counts['rows'] == manifest['rows']
            pack['counts'] = counts
        else:
            assert counts == pack['counts']
        total.update(counts)
        print('Verified corpus pack', name, counts['rows'], flush=True)
    save(target / 'MANIFEST.json', dict(status='APPEND_ONLY_CPU_INDEPENDENT_INPUT_EXTENSION',
        name='d0066', pack=packs['d0066'],
        families=manifest['counts'], model_predictions_included=False,
        hardware_labels_included=False, private_data_included=False,
        warning='Observed once on both recorded contexts (Skylake D0066, i7 D0067). Reuse saved labels. Audit a new context before capture.'))
    assert digest(old_path) == old_hash and digest(corpus / 'MANIFEST.json') == old['base_manifest_sha256']
    save(corpus / 'CATALOG-D0066.json', dict(format='fpatan-corpus-v1-additive-catalog',
        previous_catalog=dict(path=old_path.name, sha256=old_hash),
        base_manifest_sha256=old['base_manifest_sha256'],
        extension_manifest_sha256=digest(target / 'MANIFEST.json'), packs=packs, counts=total,
        exact_tuple_duplicates=0, previous_provisional_pool=old['previous_provisional_pool'],
        extension_pools=old['extension_pools'], hardware_labels_included=False,
        private_data_included=False, builder_sha256=digest(Path(__file__))))
    return total


def main():
    sky, i7 = BASE / 'd0066', BASE / 'd0067'
    sky_m, sky_c = authenticate(sky, '00050654', '0x1')
    i7_m, i7_c = authenticate(i7, '000506e3', '0xf0')
    assert sky_m['files'] == i7_m['files']
    construction = json.loads((BASE / 'd0069-independent-input-audit.json').read_text())
    assert construction['status'] == 'PASS_INDEPENDENT_INPUT_CONSTRUCTION'
    cross, counts = Counter(), {'skylake': Counter(), 'i7': Counter()}
    groups = defaultdict(Counter)
    rawhash = {'skylake': hashlib.sha256(), 'i7': hashlib.sha256()}
    with gzip.open(sky / 'inputs.txt.gz', 'rt') as inputs, \
         gzip.open(sky / 'predictions.txt.gz', 'rt') as predictions, \
         gzip.open(sky / 'categories.tsv.gz', 'rt') as categories, \
         gzip.open(sky / 'hardware.txt.gz', 'rt') as first, \
         gzip.open(i7 / 'hardware.txt.gz', 'rt') as second:
        for line, predicted, category, s, i in itertools.zip_longest(inputs, predictions, categories, first, second):
            assert None not in (line, predicted, category, s, i)
            parse_line(line)
            cid, family = category.rstrip().split('\t')
            ident, *expected = predicted.split()
            assert cid == ident == line.split()[0]
            expected = tuple(int(v, 16) for v in expected)
            a, b = validate_output(s, line), validate_output(i, line)
            for host, result, raw in (('skylake', a, s), ('i7', b, i)):
                rawhash[host].update(raw.encode('ascii'))
                observed = result['se'], result['sig'], result['C1'], result['sw'] & 63, result['before'] & 63
                misses = dict(candidate_misses=observed[:2] != expected[:2],
                    candidate_C1_misses=observed[2] != expected[2],
                    exception_misses=observed[3] != expected[3],
                    before_exception_misses=observed[4] != expected[4])
                counts[host].update(rows=1, union_misses=observed != expected, **misses)
                groups[host + ':' + family.split(':')[0]].update(rows=1, union_misses=observed != expected, **misses)
            cross['rows'] += 1
            cross['result_differences'] += (a['se'], a['sig']) != (b['se'], b['sig'])
            cross['C1_differences'] += a['C1'] != b['C1']
            cross['exception_differences'] += (a['sw'] & 63) != (b['sw'] & 63)
            cross['preload_exception_differences'] += (a['before'] & 63) != (b['before'] & 63)
            cross['raw_status_differences'] += a['sw'] != b['sw']
            cross['raw_preload_status_differences'] += a['before'] != b['before']
    for host, job, complete in (('skylake', sky, sky_c), ('i7', i7, i7_c)):
        assert rawhash[host].hexdigest() == complete['hardware_sha256']
        assert counts[host]['rows'] == complete['rows']
        score = json.loads((job / 'SCORE.json').read_text())
        for key in ('rows', 'candidate_misses', 'candidate_C1_misses', 'exception_misses', 'before_exception_misses'):
            assert score['counts'][key] == counts[host][key]
        assert score['hardware_sha256'] == complete['hardware_sha256']
    paper = json.loads((BASE / 'd0030-paper-verification.json').read_text())
    assert digest(ROOT / 'output/pdf/skylake-fpatan.pdf') == paper['pdf_sha256']
    assert digest(HERE / 'fpatan_candidate.c') == paper['numerical_source_sha256']
    publication = json.loads((HERE / 'paper/generated/SOURCE-MANIFEST.json').read_text())
    for name, sha in publication['files'].items():
        assert digest(ROOT / name) == sha
    # The prior publication receipt remains the authority for its unchanged
    # snapshot. This campaign does not update any publication artifact.
    total = append_corpus(sky, sky_m)
    evidence = ('MANIFEST.json', 'INPUTS-FROZEN.json', 'C-PREFLIGHT.json',
        'C-SANITIZED-PREFLIGHT.json', 'HISTORY.json', 'STAGED.json', 'DISPATCHED.json',
        'STARTED.json', 'COMPLETE.json', 'SCORE.json', 'LEDGER-AUDIT.json')
    save(BASE / 'd0070-independent-verification.json', dict(
        status='PASS_INDEPENDENT_TWO_CPU_CHALLENGE' if not any(c['union_misses'] for c in counts.values()) else 'MISSES_FOUND_INDEPENDENT_TWO_CPU_CHALLENGE',
        counts=counts, family_counts=groups, cross_cpu=cross, corpus_counts=total,
        construction_receipt_sha256=digest(BASE / 'd0069-independent-input-audit.json'),
        evidence_sha256={job.name: {name: digest(job / name) for name in evidence} for job in (sky, i7)},
        verifier_sha256=digest(Path(__file__)), candidate_unchanged=True, paper_changed=False,
        publication_manifest_sha256=digest(HERE / 'paper/generated/SOURCE-MANIFEST.json'),
        limits='Finite independent challenge on two recorded CPU contexts. No exhaustive full-format correctness or equivalence proof.'))
    print(json.dumps(dict(counts=counts, cross_cpu=cross, corpus=total), indent=2), flush=True)


if __name__ == '__main__':
    main()
