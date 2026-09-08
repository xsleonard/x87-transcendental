"""Final local delivery audit and source-only package; no hardware execution."""
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

from compressed_guard import digest
from d0008_schedule_replay import BASE, opened
from prepare import save

HERE=Path(__file__).resolve().parent


def checked(command, cwd=HERE):
    result=subprocess.run(command,cwd=cwd,text=True,capture_output=True,check=True)
    return dict(command=command,stdout=result.stdout,stderr=result.stderr)


def classify(se,sig):
    e=se&32767
    if not e:return 'zero' if not sig else 'pseudo-denormal' if sig>>63 else 'denormal'
    if not sig>>63:return 'unsupported'
    if e!=32767:return 'normal'
    return 'infinity' if sig==1<<63 else 'qnan' if sig&(1<<62) else 'snan'


def main():
    destination=BASE/'d0027-delivery-checks.json'
    assert not destination.exists()
    source=(HERE/'fpatan_candidate.c').read_text()
    frozen=(HERE/'fpatan_candidate_v7.c').read_text()
    uncomment=lambda s:re.sub(r'/\*.*?\*/','',s,flags=re.S)
    assert uncomment(source).split()==uncomment(frozen).split()
    assert not re.search(r'\b(?:getenv|__asm__|asm|atan|atan2|atanl|atan2l)\s*\(',uncomment(source))
    reports={}
    jobs=sorted(p.parent.name for p in BASE.glob('d[0-9][0-9][0-9][0-9]/MANIFEST.json'))
    assert len(jobs)==14
    for label in ('main','gcc15','library'):
        path=BASE/f'd0027-{label}-full-replay.json'
        report=json.loads(path.read_text())
        assert sorted(report['jobs'])==jobs
        assert report['counts']['rows']==2783208
        assert all(v==0 for k,v in report['counts'].items() if k!='rows')
        for name,sha in report['sources'].items():assert digest(HERE/name)==sha
        reports[label]=dict(sha256=digest(path),binary_sha256=report['binary_sha256'])
    inventory=collections.Counter()
    class_pairs=collections.Counter()
    corpus=[]
    for name in jobs:
        root=BASE/name;m=json.loads((root/'MANIFEST.json').read_text())
        receipt=json.loads((root/'COMPLETE.json').read_text())
        path=root/('inputs.txt.gz' if m.get('format')=='fpatan-gzip-v2' else 'inputs.txt')
        assert digest(path)==m['files'][path.name]
        count=0
        with opened(path) as f:
            for line in f:
                _,rc,pc,*words=line.split()
                ys,ym,xs,xm=(int(s,16) for s in words)
                ky,kx=classify(ys,ym),classify(xs,xm)
                inventory['rc-'+rc]+=1;inventory['pc-'+pc]+=1
                inventory['y-'+ky]+=1;inventory['x-'+kx]+=1
                class_pairs[ky+'/'+kx]+=1;count+=1
        assert count==m['rows']==receipt['rows']
        corpus.append(dict(job=name,rows=count,input_file=path.name,input_sha256=digest(path),
            hardware_sha256=receipt['hardware_sha256'],manifest_sha256=digest(root/'MANIFEST.json')))
    assert sum(item['rows'] for item in corpus)==2783208
    assert all(inventory['rc-'+r]>0 for r in ('rn','rd','ru','rz'))
    assert all(inventory['pc-'+p]>0 for p in ('24','53','64'))
    assert all(inventory[p+'-'+k]>0 for p in ('y','x') for k in
               ('zero','normal','denormal','pseudo-denormal','infinity','qnan','snan','unsupported'))
    prospective=0
    for name in ('d0023','d0024','d0026'):
        root=BASE/name;m=json.loads((root/'MANIFEST.json').read_text())
        score=json.loads((root/'SCORE.json').read_text())
        assert m['source_pins']['fpatan_candidate_v7.c']==digest(HERE/'fpatan_candidate_v7.c')
        assert all(score['counts'][k]==0 for k in
            ('candidate_misses','candidate_C1_misses','exception_misses','before_exception_misses'))
        prospective+=score['counts']['rows']
    assert prospective==624312
    checks=[]
    checks.append(checked(['make','all','check']))
    checks.append(checked(['/private/tmp/fpatan-d0027-main-sanitized','--selftest']))
    checks.append(checked(['/private/tmp/fpatan-d0027-library-test']))
    checks.append(checked(['/private/tmp/h1495-z3-venv/bin/python','-m','unittest','discover','-s','.', '-p','test_d00*.py']))
    for script in ('architecture.py','protocol.py','test_compressed_guard.py',
                   'test_compressed_pipeline.py','test_score_stream.py'):
        checks.append(checked(['python3',script]))
    checks.append(checked(['python3','d0025_midpoint_alias_certificate.py','--verify']))
    checks.append(checked(['python3','-m','compileall','-q','.']))
    checks.append(checked(['git','diff','--check']))
    expected='example 3ffe c90fdaa22168c235 1 20 00\n'
    example='example rn 64 3fff 8000000000000000 3fff 8000000000000000\n'
    for executable in ('fpatan','fpatan_batch'):
        r=subprocess.run([str(HERE/'build'/executable)],input=example,text=True,capture_output=True,check=True)
        assert r.stdout==expected and not r.stderr
    # Package an explicit allowlist; no private material, raw captures or
    # historical analysis switches are included. This is a local artifact.
    mapping={name:name for name in ('fpatan_candidate.c','fpatan_library.c','fpatan_library.h',
        'example_batch.c','test_library.c','Makefile','ALGORITHM.md','ACCEPTANCE.md')}
    mapping['README.md']='DELIVERY.md'
    blobs={name:(HERE/origin).read_bytes() for name,origin in mapping.items()}
    bundle_manifest=dict(status='VALIDATED_SKYLAKE_NUMERICAL_SOURCE_RELEASE',
        reference_signature='00050654',reported_microcode='0x1',observations=2783208,
        prospective_observations=624312,replays=reports,corpus=corpus,
        files={name:hashlib.sha256(data).hexdigest() for name,data in blobs.items()},
        limitation='Empirical bit-exact reconstruction; not exhaustive all-raw80 or cross-CPU proof.')
    blobs['evidence-manifest.json']=(json.dumps(bundle_manifest,indent=2,sort_keys=True)+'\n').encode()
    archive=BASE/'fpatan-d0027-v1-source.tar.gz'
    with archive.open('xb') as dest, gzip.GzipFile(filename='',mode='wb',fileobj=dest,mtime=0) as gz, \
         tarfile.open(fileobj=gz,mode='w|') as tar:
        for name,data in sorted(blobs.items()):
            entry=tarfile.TarInfo('fpatan-d0027-v1/'+name)
            entry.size=len(data);entry.mode=0o644;entry.mtime=0
            tar.addfile(entry,io.BytesIO(data))
    extracted=Path(tempfile.mkdtemp(prefix='fpatan-d0027-release-'))
    with tarfile.open(archive,'r:gz') as tar:
        tar.extractall(extracted,filter='data')
    fresh=extracted/'fpatan-d0027-v1'
    for name,data in blobs.items():assert (fresh/name).read_bytes()==data
    checks.append(checked(['make','all','check'],fresh))
    r=subprocess.run([str(fresh/'build/fpatan')],input=example,text=True,capture_output=True,check=True)
    assert r.stdout==expected and not r.stderr
    ledger=json.loads((BASE/'d0026/LEDGER-AUDIT.json').read_text())
    assert ledger['integrity']=='ok'
    assert all(row[2]=='OBSERVED' for row in ledger['counts']+ledger['compressed_batches'])
    save(destination,dict(status='PASS',main_token_identical_to_frozen_v7=True,
        replays=reports,observations=2783208,prospective_observations=prospective,
        inventory=inventory,class_pairs=class_pairs,corpus=corpus,checks=checks,
        bundle=str(archive),bundle_sha256=digest(archive),fresh_extraction=str(fresh),
        source_sha256={name:digest(HERE/name) for name in mapping.values()},
        hardware_executed=False,model_promoted=True,
        limits='Specified Skylake masked numerical contract; no universal all-input/cross-CPU claim.'))
    print('PASS delivery audit:',len(jobs),'jobs, 2783208 observations,',prospective,'prospective;',
          len(checks),'check commands; fresh source package built and tested',flush=True)
    print('Source package:',archive,flush=True)


if __name__=='__main__':main()
