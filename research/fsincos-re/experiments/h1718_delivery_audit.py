#!/usr/bin/env python3
"""Authenticate the delivered source, PDF and pristine cross-CPU archive."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    record={};binary=root/'src/fsincos_skylake'
    test=subprocess.run([str(binary),'--selftest'],text=True,capture_output=True,check=True);assert test.stdout=='SELFTEST: ok\n'
    for label,target,expected in (('promoted',binary,0),('rejected_policy1',root/'tmp/ledger33/current/h1717_pre_promotion/fsincos_skylake',1)):
        test=subprocess.run([sys.executable,str(root/'src/test_general_paired.py'),str(target)],text=True,capture_output=True)
        assert test.returncode==expected,(label,test.stdout,test.stderr)
        if expected:assert 'e79000000c3e46e7' in test.stderr and 'd857' in test.stderr
        record[label]=dict(exit_code=test.returncode,stdout=test.stdout,stderr=test.stderr)
    reports={}
    for name in ('h1717_paired_regression','h1717_standalone_regression','h1717_review_regression',
                 'h1717_promotion_checks','h1717_opened_replay','h1717_carrier_bounds','h1718_corpus_verification'):
        path=root/'tmp/ledger33/current'/name/'report.json';v=json.loads(path.read_text());assert v['status'].startswith('PASS')
        reports[name]=dict(sha256=suite.digest(path),status=v['status'])
    archive=root/'deliverables/x87-trig-suite-v1.zip';sha=suite.digest(archive)
    assert (archive.with_suffix('.zip.sha256')).read_text().split()[0]==sha
    temp=Path(tempfile.mkdtemp(prefix='x87_h1718_pristine_'));prefix='x87-trig-suite/'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():assert name.startswith(prefix) and '..' not in Path(name).parts
        manifest=json.loads(z.read(prefix+'MANIFEST.json'));assert manifest['kind']=='distribution'
        assert set(z.namelist())=={prefix+n for n in manifest['files']}|{prefix+'MANIFEST.json'}
        for name,digest in manifest['files'].items():assert hashlib.sha256(z.read(prefix+name)).hexdigest()==digest
        z.extractall(temp)
    pristine=temp/'x87-trig-suite';suite.verify_dataset(pristine);corpus=suite.verify_dataset(pristine/'corpus-v1')
    assert corpus['profiles']['full']['default_capture_tuples']==507401592 and corpus['profiles']['core']['default_capture_tuples']==2336004
    test=subprocess.run([sys.executable,'-W','error::ResourceWarning','test_suite.py','-v'],cwd=pristine,text=True,capture_output=True,check=True)
    assert 'Ran 8 tests' in test.stderr and 'OK' in test.stderr
    record['pristine_unit_tests']=test.stderr
    for profile in ('core','full'):
        plan=suite.plan(pristine/'corpus-v1',profile,list(suite.MODES),[64] if profile=='full' else list(suite.PCS),1000,168)
        assert plan['within_budget'];record[profile+'_plan']=plan
    tex=root/'paper/skylake-x87.tex';pdf=root/'paper/skylake-x87.pdf';log=(root/'paper/skylake-x87.log').read_text()
    assert not any(x in log for x in ('Overfull','Underfull','LaTeX Warning:','Undefined control sequence'))
    pdfinfo=subprocess.run(['pdfinfo',str(pdf)],text=True,capture_output=True,check=True).stdout
    assert 'Pages:           15' in pdfinfo
    checks=subprocess.run(['git','diff','--check'],cwd=root,text=True,capture_output=True,check=True);assert not checks.stdout
    result=dict(status='PASS_DELIVERY_AUDIT',hardware_executions=0,private_access=False,
        archive=dict(bytes=archive.stat().st_size,sha256=sha,files=len(manifest['files'])+1,pristine_directory=str(pristine)),
        evidence=reports,checks=record,pdf=dict(pages=15,tex_sha256=suite.digest(tex),pdf_sha256=suite.digest(pdf),
            visual_review='Main agent inspected all 15 pages; final pages 10-15 re-rendered/reviewed after the last text correction.'),
        sha256=dict(main_source=suite.digest(root/'src/fsincos_skylake.c'),paired=suite.digest(root/'src/general/paired.h'),
            binary=suite.digest(binary),corpus_manifest=suite.digest(pristine/'corpus-v1/MANIFEST.json'),
            distribution_manifest=suite.digest(pristine/'MANIFEST.json'),script=suite.digest(Path(__file__))))
    suite.save(out/'report.json',result);print(json.dumps({k:result[k] for k in ('status','archive','sha256')},sort_keys=True))


if __name__=='__main__':main()
