#!/usr/bin/env python3
"""Pristine-package, new-observation inclusion, preservation and pin checks."""
import argparse
import json
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path
from h1719_run_saved_suite import PINS,digest,save
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'corpus-suite'))
import suite


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.output_dir.resolve()
    out.mkdir(parents=True,exist_ok=False);archive=root/'deliverables/x87-trig-suite-v1.zip'
    assert (archive.with_suffix('.zip.sha256')).read_text().split()[0]==digest(archive)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():assert name.startswith('x87-trig-suite/') and '..' not in Path(name).parts and not Path(name).is_absolute()
        z.extractall(out/'pristine')
    pristine=out/'pristine/x87-trig-suite';distribution=suite.verify_dataset(pristine)
    corpus=suite.verify_dataset(pristine/'corpus-v1')
    assert corpus['corpus_id']=='x87-trig-v1-2126cf9ff5272e9d'
    proc=subprocess.run([sys.executable,'-W','error::ResourceWarning','test_suite.py','-v'],cwd=pristine,capture_output=True,text=True,check=True)
    with (out/'unit-tests.log').open('x') as f:f.write(proc.stdout+proc.stderr)
    frozen=json.loads((root/'transfer-tests/h1722/manifest.json').read_text());expected={r['case_id'] for r in frozen}
    observed={}
    for host in ('i7','skylake'):
        cases={r['case_id'] for r in suite.observations(pristine/'references'/('h1722-'+host))}
        assert cases==expected;observed[host]=len(cases)
    with sqlite3.connect('file:'+str(root/'corpus-suite/corpus-v1/catalog.sqlite')+'?mode=ro',uri=True) as db:
        for op in {r['operand'] for r in frozen}:assert db.execute('SELECT profiles FROM operands WHERE op=?',(op,)).fetchone()[0]&1
    remaining=set(expected);jobrows=0
    export=json.loads((pristine/'jobs-core/EXPORT.json').read_text())
    for job in export['jobs']:
        d=pristine/'jobs-core'/job['directory'];spec=json.loads((d/'JOB.json').read_text());assert suite.digest(d/'inputs.txt')==spec['inputs_sha256']
        count=0
        with (d/'inputs.txt').open() as f:
            for line in f:
                words=line.split();assert len(words)==9 and suite.capture_line(words[0])==line.rstrip('\n')
                remaining.discard(words[0]);count+=1
        assert count==spec['rows']==job['rows'];jobrows+=count
    assert not remaining and jobrows==2562948
    old=root/'corpus-suite/releases/h1718-v1-policy2/corpus-v1';previous=suite.verify_dataset(old)
    preserved=json.loads((root/'corpus-suite/corpus-v1/preservation.json').read_text())
    assert preserved['previous_manifest_sha256']==digest(old/'MANIFEST.json') and not preserved['missing_operands_or_memberships']
    for name,sha in PINS.items():assert digest(root/name)==sha,name
    paper={'paper/skylake-x87.tex':'9d11c734967fcb1c830d571fc99387a0de0bd1765519dc771daf4b7dfa4829ff',
        'paper/skylake-x87.pdf':'e08a56571c3a40c011fddf3487ceeb44a1483e194d1495dee43ea3b9bdf636e0'}
    for name,sha in paper.items():assert digest(root/name)==sha,name
    subprocess.run([str(root/'src/fsincos_skylake'),'--selftest'],check=True)
    subprocess.run([sys.executable,str(root/'src/test_general_paired.py'),str(root/'src/fsincos_skylake')],check=True)
    subprocess.run(['git','diff','--check'],cwd=root,check=True)
    result=dict(status='PASS_PRISTINE_DELIVERY',archive_sha256=digest(archive),archive_bytes=archive.stat().st_size,
        files=len(distribution['files'])+1,corpus_id=corpus['corpus_id'],core_export_rows=jobrows,
        all_new_observations_in_core=True,pristine_observation_rows=observed,toolkit_unit_tests=8,
        previous_operands_preserved=previous['profiles']['full']['operands'],private_files_in_package=False,
        candidate_changed=False,paper_changed=False,hardware_execution='none',sha256=dict(candidate=PINS,paper=paper))
    save(out/'report.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
