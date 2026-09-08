#!/usr/bin/env python3
"""Package only explicitly allowed public suite payloads, never private/index files."""
import argparse
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--archive',required=True,type=Path);a=p.parse_args();root=a.root.resolve();base=root/'corpus-suite';archive=a.archive.resolve()
    assert not archive.exists() and not (base/'MANIFEST.json').exists()
    payload=[base/name for name in ('README.md','suite.py','run_capture.py','merge_observations.py','test_suite.py','capture_numeric.c','Makefile')]
    for directory in (base/'corpus-v1',base/'references/h1715-skylake',base/'references/h1712-h1714-skylake'):
        manifest=suite.verify_dataset(directory);payload.append(directory/'MANIFEST.json')
        payload.extend(directory/name for name in manifest['files'])
    for directory in (base/'jobs-core',base/'jobs-smoke'):
        export=json.loads((directory/'EXPORT.json').read_text());payload.append(directory/'EXPORT.json')
        for job in export['jobs']:
            target=directory/job['directory'];assert suite.digest(target/'JOB.json')==job['job_sha256']
            info=json.loads((target/'JOB.json').read_text());assert suite.digest(target/'inputs.txt')==info['inputs_sha256']
            payload.extend((target/'JOB.json',target/'inputs.txt'))
    payload=sorted(set(payload));assert all(p.is_file() and p.is_relative_to(base) for p in payload)
    assert not any(p.suffix in ('.sqlite','.pdf','.pyc') or any(w in ('supplemental','standalone','__pycache__') for w in p.relative_to(base).parts) for p in payload)
    manifest=dict(schema='x87-suite-v1',kind='distribution',corpus_id=suite.verify_dataset(base/'corpus-v1')['corpus_id'],
        files={str(path.relative_to(base)):suite.digest(path) for path in payload},
        private_material_included=False,raw_hardware_rerun_required=False,
        package_policy='Explicit payload allowlist. No private files, scratch/index databases, local reservation ledgers, PDFs or unverified legacy prebuilts.',
        builder_sha256=suite.digest(Path(__file__)))
    suite.save(base/'MANIFEST.json',manifest);payload.append(base/'MANIFEST.json')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(payload):
            member='x87-trig-suite/'+str(path.relative_to(base))
            info=zipfile.ZipInfo(member,date_time=(1980,1,1,0,0,0));info.external_attr=0o100644<<16
            info.compress_type=zipfile.ZIP_STORED if path.suffix=='.gz' else zipfile.ZIP_DEFLATED
            z.writestr(info,path.read_bytes())
    # Verify archived bytes, not just the source directory used to write them.
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={'x87-trig-suite/'+str(path.relative_to(base)) for path in payload}
        for path in payload:
            import hashlib
            assert hashlib.sha256(z.read('x87-trig-suite/'+str(path.relative_to(base)))).hexdigest()==suite.digest(path)
    with archive.with_suffix(archive.suffix+'.sha256').open('x') as f:f.write(suite.digest(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(status='PASS_DISTRIBUTION_ARCHIVE',archive=str(archive),bytes=archive.stat().st_size,
        files=len(payload),sha256=suite.digest(archive),manifest_sha256=suite.digest(base/'MANIFEST.json')),sort_keys=True))


if __name__=='__main__':main()
