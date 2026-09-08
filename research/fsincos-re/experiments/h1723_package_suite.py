#!/usr/bin/env python3
"""Package the public corpus and five separately attributed CPU datasets."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);a=p.parse_args();root=a.root.resolve();base=root/'corpus-suite';archive=a.archive.resolve()
    assert not archive.exists() and not (base/'MANIFEST.json').exists()
    payload=[base/name for name in ('README.md','suite.py','run_capture.py','merge_observations.py','test_suite.py','capture_numeric.c','Makefile')]
    refs=('h1715-skylake','h1712-h1714-skylake','review-20260905-skylake','h1722-i7','h1722-skylake')
    for directory in [base/'corpus-v1',*[base/'references'/r for r in refs]]:
        manifest=suite.verify_dataset(directory);payload.append(directory/'MANIFEST.json');payload.extend(directory/name for name in manifest['files'])
    for directory in (base/'jobs-core',base/'jobs-smoke'):
        export=json.loads((directory/'EXPORT.json').read_text());payload.append(directory/'EXPORT.json')
        assert export['corpus_id']==suite.verify_dataset(base/'corpus-v1')['corpus_id']
        for job in export['jobs']:
            target=directory/job['directory'];assert suite.digest(target/'JOB.json')==job['job_sha256']
            info=json.loads((target/'JOB.json').read_text());assert suite.digest(target/'inputs.txt')==info['inputs_sha256']
            payload.extend((target/'JOB.json',target/'inputs.txt'))
    payload=sorted(set(payload));assert all(p.is_file() and p.is_relative_to(base) for p in payload)
    assert not any(p.suffix in ('.sqlite','.pdf','.pyc') or any(w in ('supplemental','standalone','__pycache__') for w in p.relative_to(base).parts) for p in payload)
    manifest=dict(schema='x87-suite-v1',kind='distribution',corpus_id=suite.verify_dataset(base/'corpus-v1')['corpus_id'],
        files={str(path.relative_to(base)):suite.digest(path) for path in payload},private_material_included=False,raw_hardware_rerun_required=False,
        package_policy='Explicit public payload allowlist; no model/private sources, PDFs, databases or reservation ledgers.',builder_sha256=suite.digest(Path(__file__)))
    suite.save(base/'MANIFEST.json',manifest);payload.append(base/'MANIFEST.json')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(payload):
            info=zipfile.ZipInfo('x87-trig-suite/'+str(path.relative_to(base)),date_time=(1980,1,1,0,0,0));info.external_attr=0o100644<<16
            info.compress_type=zipfile.ZIP_STORED if path.suffix=='.gz' else zipfile.ZIP_DEFLATED;z.writestr(info,path.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={'x87-trig-suite/'+str(path.relative_to(base)) for path in payload}
        for path in payload:assert hashlib.sha256(z.read('x87-trig-suite/'+str(path.relative_to(base)))).hexdigest()==suite.digest(path)
    with archive.with_suffix('.zip.sha256').open('x') as f:f.write(suite.digest(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(status='PASS_DISTRIBUTION_ARCHIVE',files=len(payload),bytes=archive.stat().st_size,sha256=suite.digest(archive))),flush=True)


if __name__=='__main__':main()
