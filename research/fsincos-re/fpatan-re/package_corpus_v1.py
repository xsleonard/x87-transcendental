"""Package CPU-independent FPATAN inputs, with observations kept separate.

Copies only public input streams from fifteen authenticated completed jobs.
The full constructive D0032 pool is preserved as a provisional recipe pool,
NOT as freshness-cleared inputs or extra observations. No private ledger,
numerical implementation, predictions or hardware labels enter the package.
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
    destination = HERE / 'corpus-v1'
    destination.mkdir(exist_ok=False)
    inputs_dir = destination / 'inputs'
    inputs_dir.mkdir()
    baseline = json.loads((BASE / 'd0030-pseudocode-replay-v2.json').read_text())
    jobs = sorted([*baseline['jobs'], 'd0033'])
    assert len(jobs) == 15
    seen, packs, totals = set(), {}, Counter()
    for name in jobs:
        job = BASE / name
        manifest = json.loads((job / 'MANIFEST.json').read_text())
        complete = json.loads((job / 'COMPLETE.json').read_text())
        assert complete['state'] == 'OBSERVED'
        assert digest(job / 'MANIFEST.json') == complete['manifest_sha256']
        compressed = (job / 'inputs.txt.gz').exists()
        source = job / ('inputs.txt.gz' if compressed else 'inputs.txt')
        assert digest(source) == manifest['files'][source.name]
        target = inputs_dir / (name + '.txt.gz')
        if compressed:
            with target.open('xb') as stream, source.open('rb') as raw:
                shutil.copyfileobj(raw, stream)
        else:
            with target.open('xb') as stream, source.open('rb') as raw:
                with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as output:
                    shutil.copyfileobj(raw, output)
        counts = Counter()
        with gzip.open(target, 'rt') as stream:
            for line in stream:
                key = packed(parse_line(line))
                assert key not in seen, 'Repeated exact observation tuple across corpus packs'
                seen.add(key)
                fields = line.split()
                counts['rows'] += 1
                counts['rc:' + fields[1]] += 1
                counts['pc:' + fields[2]] += 1
        assert counts['rows'] == manifest['rows'] == complete['rows']
        totals.update(counts)
        packs[name] = dict(path=str(target.relative_to(destination)), sha256=digest(target),
                           counts=counts, source_manifest_sha256=digest(job / 'MANIFEST.json'))
        print('Packaged', name, counts['rows'], 'unique total', len(seen), flush=True)
    pool = BASE / 'd0032-square-tie-mining/candidate-pool.tsv.gz'
    mining = json.loads((pool.parent / 'REPORT.json').read_text())
    assert digest(pool) == mining['pool_sha256']
    pool_target = destination / 'provisional-exact-square-tie-pool.tsv.gz'
    with pool.open('rb') as source, pool_target.open('xb') as target:
        shutil.copyfileobj(source, target)
    assert totals['rows'] == len(seen) == 2818328
    save(destination / 'MANIFEST.json', dict(format='fpatan-corpus-v1',
        status='CPU_INDEPENDENT_INPUTS_WITH_SEPARATE_PROVISIONAL_POOL',
        instruction='FPATAN', operand_order='y=ST(1), x=ST(0)',
        capture_contract='masked-clear-depth2; FNINIT, FLDCW, FLD80 y, FLD80 x, one FPATAN',
        counts=totals, exact_tuple_duplicates=0, packs=packs,
        source_observation_reference='guest-reported Skylake Xeon CPUID 00050654, microcode 0x1; labels remain outside this input package',
        provisional_pool=dict(path=pool_target.name, sha256=digest(pool_target),
            base_pairs=mining['counts']['verified_base_pairs'],
            status='SOFTWARE_CERTIFIED_NOT_FRESHNESS_CLEARED',
            intended_full_sign_swap_RC64_upper_bound=32 * mining['counts']['verified_base_pairs'],
            admission='Apply private/public and per-host history checks; do not repeat an existing observation. This is not an additional native capture pack.'),
        package_builder_sha256=digest(Path(__file__)),
        new_hardware_executed=False, private_data_included=False,
        predictions_included=False, hardware_labels_included=False,
        warning='Existing Skylake pack tuples have already been observed and must not be captured again there. Check history independently on every future CPU.'))
    print('PASS portable FPATAN input corpus:', totals['rows'], 'unique observations;',
          mining['counts']['verified_base_pairs'], 'provisional constructive base pairs; no capture', flush=True)


if __name__ == '__main__':
    main()
