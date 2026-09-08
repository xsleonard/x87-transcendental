"""Fresh-build verification of the delivered C implementation and archive.

Reuses immutable native observations; never runs an x87 hardware capture.
Builds in a new temporary directory and preserves all reports/build outputs.
The numerical implementation, original release and old receipts are read-only.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

from compressed_guard import digest
from d0008_schedule_replay import BASE
from prepare import save

HERE=Path(__file__).resolve().parent


def command(argv, cwd, label):
    result=subprocess.run(argv,cwd=cwd,text=True,capture_output=True)
    report=dict(command=argv,cwd=str(cwd),returncode=result.returncode,
                stdout=result.stdout,stderr=result.stderr)
    save(BASE/f'd0028-{label}.json',report)
    assert result.returncode==0,(label,result.returncode,result.stderr)
    return report


def replay(binary, label):
    destination=BASE/f'd0028-{label}-full-replay.json'
    argv=['python3',str(HERE/'verify_delivery.py'),'--binary',str(binary),'--out',str(destination)]
    with (BASE/f'd0028-{label}-replay.log').open('x') as log:
        run=subprocess.run(argv,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
    assert run.returncode==0,(label,'Inspect preserved replay log')
    report=json.loads(destination.read_text())
    assert all(v==0 for k,v in report['counts'].items() if k!='rows')
    print('PASS',label,report['counts'],flush=True)
    return dict(report_sha256=digest(destination),binary_sha256=digest(binary),
                counts=report['counts'],jobs=report['jobs'])


def main():
    destination=BASE/'d0028-reverification.json'
    assert not destination.exists()
    previous=json.loads((BASE/'d0027-delivery-checks.json').read_text())
    assert previous['status']=='PASS' and previous['model_promoted']
    for name,sha in previous['source_sha256'].items():
        assert digest(HERE/name)==sha,('Delivered source changed',name)
    archive=Path(previous['bundle'])
    assert digest(archive)==previous['bundle_sha256']
    uncomment=lambda s:re.sub(r'/\*.*?\*/','',s,flags=re.S)
    assert uncomment((HERE/'fpatan_candidate.c').read_text()).split()==uncomment((HERE/'fpatan_candidate_v7.c').read_text()).split()
    work=Path(tempfile.mkdtemp(prefix='fpatan-d0028-'))
    with tarfile.open(archive,'r:gz') as tar:
        tar.extractall(work,filter='data')
    fresh=work/'fpatan-d0027-v1'
    manifest=json.loads((fresh/'evidence-manifest.json').read_text())
    for name,sha in manifest['files'].items():assert digest(fresh/name)==sha
    for name in ('fpatan_candidate.c','fpatan_library.c','fpatan_library.h','example_batch.c','test_library.c','Makefile'):
        assert (fresh/name).read_bytes()==(HERE/name).read_bytes()
    save(BASE/'d0028-started.json',dict(status='LOCAL_REVERIFICATION_STARTED',
         build_root=str(work),archive_sha256=digest(archive),hardware_executed=False,
         source_sha256=previous['source_sha256']))
    print('Authenticated unchanged source, release and archived build files',flush=True)
    sanitized=fresh/'sanitized'
    gcc=fresh/'gcc15'
    flags='-O1 -g -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all'
    checks={}
    checks['sanitized_build']=command(['make','all','check','CC=clang',f'BUILD_DIR={sanitized}',f'CFLAGS={flags}'],fresh,'sanitized-build')
    checks['gcc_build']=command(['make','all','check','CC=gcc-15',f'BUILD_DIR={gcc}'],fresh,'gcc-build')
    print('PASS fresh sanitized Clang and GCC builds, CLI and library regressions',flush=True)
    # Read-only compiler analysis supplements dynamic sanitizer coverage.
    checks['static_analysis']=command(['clang','--analyze','-std=c11','-Wall','-Wextra','-Werror',
        '-I/opt/homebrew/include','-Xanalyzer','-analyzer-output=text','fpatan_candidate.c','fpatan_library.c'],fresh,'static-analysis')
    assert not checks['static_analysis']['stderr'],'Review static analyzer output before acceptance'
    print('PASS static analysis; starting complete saved-hardware replays',flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(replay,sanitized/'fpatan','sanitized')
        b=pool.submit(replay,gcc/'fpatan_batch','gcc-library')
        results={'sanitized':a.result(),'gcc_library':b.result()}
    expected_jobs=sorted(p.parent.name for p in BASE.glob('d[0-9][0-9][0-9][0-9]/MANIFEST.json'))
    for report in results.values():
        assert sorted(report['jobs'])==expected_jobs
        assert report['counts']['rows']==previous['observations']
    baseline=json.loads((BASE/'d0027-main-full-replay.json').read_text())
    for report in results.values():
        for name,result in report['jobs'].items():
            assert result['hardware_sha256']==baseline['jobs'][name]['hardware_sha256']
            assert result['output_sha256']==baseline['jobs'][name]['output_sha256']
    checks['units']=command(['/private/tmp/h1495-z3-venv/bin/python','-m','unittest','discover','-s','.',
                             '-p','test_d00*.py'],HERE,'unit-tests')
    checks['certificate']=command(['python3','d0025_midpoint_alias_certificate.py','--verify'],HERE,'certificate')
    checks['diff']=command(['git','diff','--check'],HERE,'diff-check')
    # The legacy artifact and all delivered bytes must remain unchanged after
    # building/testing: fresh build success alone would not establish identity.
    for name,sha in previous['source_sha256'].items():assert digest(HERE/name)==sha
    assert digest(archive)==previous['bundle_sha256']
    save(destination,dict(status='PASS',hardware_executed=False,numerical_code_changed=False,
        observations=previous['observations'],prospective_observations=previous['prospective_observations'],
        full_replays=results,checks={k:dict(command=v['command'],returncode=v['returncode']) for k,v in checks.items()},
        build_root=str(work),archive_sha256=digest(archive),
        source_sha256=previous['source_sha256'],previous_delivery_audit_sha256=digest(BASE/'d0027-delivery-checks.json'),
        script_sha256=digest(Path(__file__)),
        scope='Verified C implementation of the documented Skylake masked numerical contract; no exhaustive all-input or cross-CPU proof claimed.'))
    print('PASS current-state C reverification:',len(expected_jobs),'jobs,',previous['observations'],
          'observations per fresh build; no native capture repeated',flush=True)
    print('Report:',destination,flush=True)


if __name__=='__main__':main()
