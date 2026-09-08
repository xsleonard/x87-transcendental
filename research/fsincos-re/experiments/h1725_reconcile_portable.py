#!/usr/bin/env python3
"""Final local portable-data checksum/count/native-text audit. No hardware."""
import argparse
import gzip
import hashlib
import json
import time

from h1725_full_campaign import BASE, HOSTS, suite, save


def observation_rows(path):
    with gzip.open(path, 'rb') as f:
        assert f.readline() == ('\t'.join(suite.FIELDS) + '\n').encode()
        return sum(block.count(b'\n') for block in iter(lambda: f.read(1 << 20), b''))


def native_text(path):
    h = hashlib.sha256(); rows = 0
    with gzip.open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block); rows += block.count(b'\n')
    return h.hexdigest(), rows


def audit(host):
    started = time.time(); out = BASE / host
    closure = out / 'native-completion-20260907'
    native = json.loads((closure / 'REPORT.json').read_text())
    assert native['status'] == 'NATIVE_SELECTED_RUN_RECONCILED_PASS'
    cfg = json.loads((closure / 'CUTOVER.json').read_text())
    assert {p.name for p in (out / 'autonomous-portable').glob('job-*') if p.is_dir()} == {
        f'job-{n:06d}' for n in range(cfg['start_job'], native['total_shards'])}
    shards = []; rows = 0; new_rows = 0
    for number in range(native['total_shards']):
        name = f'job-{number:06d}'
        if number < cfg['start_job']:
            job = out / 'jobs' / name; portable = job / 'observations'
            score = json.loads((job / 'score.json').read_text())
            complete = json.loads((job / 'COMPLETE.json').read_text())
            expected = score['counts']['rows']
            assert suite.digest(job / 'outputs.txt.gz') == complete['outputs_sha256'] == score['raw_sha256']
        else:
            job = out / 'autonomous-portable' / name; portable = job / 'observations'
            receipt = json.loads((out / 'autonomous-observed' / (name + '.DONE.json')).read_text())
            provenance = json.loads((portable / 'provenance.json').read_text())
            expected = receipt['rows']; new_rows += expected
            assert provenance['archive_sha256'] == receipt['archive_sha256']
            assert suite.digest(out / 'autonomous-observed' / (name + '.json.gz')) == receipt['archive_sha256']
            assert provenance['hardware_executions'] == 0 and provenance['observations_reused']
            digest, actual_rows = native_text(job / 'native-output.txt.gz')
            assert digest == receipt['native_text_sha256'] == provenance['native_text_sha256']
            assert actual_rows == expected
        manifest = suite.verify_dataset(portable)
        assert manifest['kind'] == 'hardware_observations' and manifest['rows'] == expected
        assert observation_rows(portable / 'observations.tsv.gz') == expected
        assert json.loads((portable / 'cpu.json').read_text())['context_id'] == cfg['cpu_context_id']
        rows += expected
        shards.append(dict(directory=str(portable.relative_to(out)), rows=expected,
                           manifest_sha256=suite.digest(portable / 'MANIFEST.json')))
        if (number + 1) % 250 == 0:
            print(json.dumps(dict(host=host, checked_shards=number + 1, rows=rows, seconds=time.time()-started)), flush=True)
    assert rows == native['totals']['rows'] == cfg['selected_cases']
    assert new_rows == native['autonomous_rows']
    index = dict(schema='h1725-portable-shard-index-v1', kind='hardware_observation_shard_collection', host=host,
                 cpu_context_id=cfg['cpu_context_id'], rows=rows, shards=shards,
                 paths_relative_to='directory containing this index',
                 note='Only listed observation datasets are the portable collection; unrelated campaign working files are not export material.')
    save(out / 'PORTABLE-INDEX.json', index)
    report = dict(status='SELECTED_NATIVE_AND_PORTABLE_RECONCILED_PASS', host=host, rows=rows,
                  shards=len(shards), autonomous_rows=new_rows, autonomous_shards=native['autonomous_shards'],
                  native_completion_report_sha256=suite.digest(closure / 'REPORT.json'),
                  portable_index_sha256=suite.digest(out / 'PORTABLE-INDEX.json'),
                  native_misses=0, full_matrix_complete=False, selection_counts=native['selection_counts'],
                  hardware_executions=0, seconds=time.time()-started, completed_unix=time.time(),
                  checks='Every dataset file hash, decompressed TSV row count, CPU identity, legacy raw-gzip hash, autonomous archive hash and decoded native-text hash/count.')
    save(out / 'PORTABLE-COMPLETE.json', report); print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--host', choices=HOSTS, required=True)
    audit(p.parse_args().host)
