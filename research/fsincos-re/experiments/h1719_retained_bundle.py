#!/usr/bin/env python3
"""Package/replay authenticated public retained tests with bounded disk use.

Build is local and reads only explicit prior verifier inventories and public
normalized references. Replay extracts one job at a time and never executes
hardware instructions. No private supplemental material is accessed.
"""
import argparse
import csv
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def build(root, destination):
    import h1709_paired_retained_census as paired
    import h1707_packaged_candidate_regression as standalone
    pb, pe = paired.inventory(root); sb, se = standalone.inventory(root)
    jobs = []; files = {}; names = {}; evidence = {**pe, **se}
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def add_file(path):
            relative = str(path.relative_to(root))
            if relative not in names:
                name = f'files/{len(names):04d}.txt'; names[relative] = name
                assert digest(path) == evidence[relative]
                z.write(path, name); files[name] = dict(sha256=digest(path), origin=relative)
            return names[relative]

        def add_text(name, text, origin):
            data = text.encode(); z.writestr(name, data)
            files[name] = dict(sha256=hashlib.sha256(data).hexdigest(), origin=origin)
            return name

        for bank in pb:
            inputs = add_file(root / bank['inputs']) if bank['inputs'] else add_text(
                'derived/comb7-inputs.txt', '\n'.join(paired.operands(root, bank)) + '\n',
                'documented sorted unique ties_comb7 reconstruction; h1709 inventory')
            for mode, capture in bank['captures'].items():
                jobs.append(dict(tag='paired_' + bank['tag'], instruction='fsincos', mode=mode,
                                 inputs=inputs, labels=add_file(root / capture), label_origin=bank['provenance']))
        for bank in sb:
            jobs.append(dict(tag='standalone_' + bank['tag'], instruction=bank['instruction'], mode=bank['mode'],
                             inputs=add_file(root / bank['inputs']), labels=add_file(root / bank['capture']),
                             label_origin='authenticated historical standalone inventory'))
        # Keep PC-specific rows and original status words, even though the
        # numerical model is PC-independent. They are appearances, not new
        # observations or additional independent arithmetic tests.
        for dataset in ('h1712-h1714-skylake', 'h1715-skylake', 'review-20260905-skylake'):
            directory = root / 'corpus-suite/references' / dataset
            manifest = json.loads((directory / 'MANIFEST.json').read_text())
            for name, sha in manifest['files'].items(): assert digest(directory / name) == sha
            groups = defaultdict(list)
            with gzip.open(directory / 'observations.tsv.gz', 'rt') as f:
                for row in csv.DictReader(f, delimiter='\t'):
                    schema, insn, mode, pc, encoding = row['case_id'].split('-')
                    assert schema == 'n1' and len(encoding) == 20
                    groups[insn, mode].append((encoding[:4] + ' ' + encoding[4:], row))
            assert sum(map(len, groups.values())) == manifest['rows']
            for (insn, mode), rows in groups.items():
                inp = []; labels = []
                for operand, row in rows:
                    inp.append(operand)
                    value = 'C2' if row['C2'] == '1' else 'OK ' + ' '.join(
                        row[lane].replace(':', ' ') for lane in ('sin', 'cos') if row[lane] != '-')
                    assert int(row['C1']) == ((int(row['SW'], 16) >> 9) & 1)
                    labels.append(value + ' SW ' + row['SW'])
                stem = f'derived/{dataset}_{insn}_{mode}'
                jobs.append(dict(tag=dataset, instruction=insn, mode=mode,
                                 inputs=add_text(stem + '_inputs.txt', '\n'.join(inp) + '\n', dataset),
                                 labels=add_text(stem + '_labels.txt', '\n'.join(labels) + '\n', dataset),
                                 label_origin=json.loads((directory / 'cpu.json').read_text())))
        prior = root / 'tmp/ledger33/current/h1638_tiny_c_transfer/report.json'
        assert digest(prior) == 'db6c8cbc1e0e2c9acdb54da5e1e381407a6b8c5f6f62cc7b1c52c4d90f8510e0'
        report = json.loads(prior.read_text())
        for group in ('frontier', 'legacy'):
            groups = defaultdict(list)
            for row in report['frontier_checks'][group]['candidate_O2']:
                groups[row['instruction'], row['mode']].append(row)
            for (insn, mode), rows in groups.items():
                inp = []; labels = []
                for row in rows:
                    inp.append(row['operand'])
                    value = 'C2' if row['output'] is None else 'OK ' + row['output'].replace(':', ' ')
                    if row['metadata'] is not None:
                        value += f' SW {row["metadata"]["C1"] << 9:04x}'
                    labels.append(value)
                stem = f'derived/{group}_{insn}_{mode}'
                jobs.append(dict(tag='fixture_' + group, instruction=insn, mode=mode,
                                 inputs=add_text(stem + '_inputs.txt', '\n'.join(inp) + '\n', str(prior.relative_to(root))),
                                 labels=add_text(stem + '_labels.txt', '\n'.join(labels) + '\n', str(prior.relative_to(root))),
                                 label_origin='Previously authenticated fixture expectations; SW encodes C1 only, not full status'))
        manifest = dict(schema='h1719-public-retained-replay', jobs=jobs, files=files,
                        scope='Overlapping saved evidence. Original label provenance is preserved; execution host is not capture host.',
                        hardware_executions=0, private_access=False)
        z.writestr('MANIFEST.json', json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('BUNDLE', destination, destination.stat().st_size, digest(destination), 'jobs', len(jobs), flush=True)


def replay(root, bundle, output):
    output.mkdir(parents=True, exist_ok=False); began = time.time(); records = []
    driver = root / 'experiments/h1719_saved_verifier'; binary_hash = digest(driver)
    assert digest(root / 'src/general/paired.h') == '4eeb671562969e39b334923cbf41a40cb86f2a5ecb3dbad23de320be315b9a5d'
    with zipfile.ZipFile(bundle) as z:
        manifest = json.loads(z.read('MANIFEST.json'))
        assert manifest['schema'] == 'h1719-public-retained-replay'
        for i, job in enumerate(manifest['jobs']):
            # Only this generated, bounded scratch directory is cleaned up.
            # Original captures, source and report files are never removed.
            with tempfile.TemporaryDirectory(prefix='h1719_job_', dir=output) as td:
                paths = []
                for kind in ('inputs', 'labels'):
                    path = Path(td) / (kind + '.txt'); name = job[kind]
                    with z.open(name) as src, path.open('xb') as dst: shutil.copyfileobj(src, dst)
                    assert digest(path) == manifest['files'][name]['sha256']; paths.append(str(path))
                with (output / f'{i:03d}.log').open('x') as err:
                    p = subprocess.run(['nice', '-n', '10', str(driver), job['instruction'], job['mode'], *paths],
                                       text=True, stdout=subprocess.PIPE, stderr=err)
                counts = json.loads(p.stdout) if p.returncode in (0, 1) else None
                row = dict(job=job, counts=counts, status='PASS' if p.returncode == 0 else 'FAIL', returncode=p.returncode)
                with (output / f'{i:03d}.json').open('x') as f: json.dump(row, f, indent=2, sort_keys=True)
                records.append(row); print(i, job['tag'], job['mode'], row['status'], counts, flush=True)
    assert digest(driver) == binary_hash
    totals = sum((Counter(r['counts']) for r in records if r['counts']), Counter())
    result = dict(status='PASS' if all(r['status'] == 'PASS' for r in records) else 'FAIL',
                  counts=dict(totals), jobs=len(records), records=records, seconds=time.time() - began,
                  hardware_executions=0, bundle_sha256=digest(bundle), driver_sha256=binary_hash,
                  script_sha256=digest(Path(__file__)), boundary=manifest['scope'])
    with (output / 'report.json').open('x') as f: json.dump(result, f, indent=2, sort_keys=True)
    print('FINAL', result['status'], dict(totals), flush=True)
    if result['status'] != 'PASS': raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('build', 'replay')); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--bundle', type=Path, required=True); p.add_argument('--output-dir', type=Path)
    a = p.parse_args()
    if a.action == 'build': build(a.root.resolve(), a.bundle.resolve())
    else: replay(a.root.resolve(), a.bundle.resolve(), a.output_dir.resolve())


if __name__ == '__main__': main()
